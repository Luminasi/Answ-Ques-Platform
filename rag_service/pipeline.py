"""问答流水线：指代消解改写 → 检索 → 精排 → 流式生成 → 结构化事件。

**本模块是整个 rag_service 里唯一 import rag_baseline 的地方**，而且只用它的公开函数
（retrieve / rerank），不碰它的内部实现，也不修改它的任何文件。

生成提示词是**复制**的，不是 import 的：rag_baseline.generator.generate() 内部用
llm.invoke 一次性返回，拿不到流；本服务要走 llm.astream，只能在包装层拼同一份模板
（见 prompts.py，那 4 条要求是逐字照抄的）。
"""

import asyncio
import os
from dataclasses import dataclass

import rag_baseline
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from rag_service import store
from rag_service.config import (EVENT_DONE, EVENT_ERROR, EVENT_MESSAGE, EVENT_META,
                                EVENT_SOURCES, REWRITE_EXTRA_CHARS, REWRITE_MAX_LINES,
                                REWRITE_MIN_CHARS, REWRITE_TIMEOUT)
from rag_service.prompts import REWRITE_PROMPT, build_generate_prompt, make_snippet

# 模型偶尔会把提示词的尾巴抄进答案里（「改写后的问题：…」），这种输出一律弃用
_LEAK_WORDS = ("改写后", "输出：", "回答：")

_REQUIRED_ENV = ("LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL")


@dataclass
class Engine:
    """启动时装配好、之后长期持有的重家伙。

    放这里而不是 app.py：「怎么开向量库、怎么建 LLM 客户端」是流水线知识，
    不是 HTTP 装配知识 —— app.py 只管路由与序列化。
    """

    llm: object          # 生成用（temperature 0.3，与 baseline 一致）
    llm_rewrite: object  # 指代消解用（temperature 0.0，改写要确定）
    vector_db: object    # Chroma 向量库


def _make_llm(session, temperature):
    """复制一份 rag_baseline/main.py 的 ChatOpenAI 配置。

    这是 eval/ruler.py 的 make_llm() 已经立过的先例：**复制配置，不去动 rag_baseline**。
    session 头取独立值，避免远端把不同用途的请求混进同一个会话上下文。
    """
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=temperature,
        default_headers={"x-opencode-session": session},
    )


def build_engine():
    """载入语料 → 切块 → 开门（指纹相符则秒级复用）→ 建两个 LLM 客户端。

    顺序照抄 rag_baseline/main.py 的 main()。**会阻塞**，调用方自己丢进线程池。
    """
    load_dotenv()
    missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "缺少环境变量：" + "、".join(missing)
            + "\n请在项目根目录的 .env 里配置 LLM_MODEL / LLM_API_KEY / LLM_BASE_URL。"
        )

    docs = rag_baseline.load_docs()
    if not docs:
        raise RuntimeError("没有读到任何语料，请检查 data/qacp_docs/ 是否存在。")
    chunks = rag_baseline.split(docs)
    vector_db = rag_baseline.get_db(chunks)

    return Engine(
        llm=_make_llm("rag-service-session", 0.3),
        llm_rewrite=_make_llm("rag-service-rewrite-session", 0.0),
        vector_db=vector_db,
    )


def sync_corpus_chunks(vector_db):
    """把向量库里的语料块同步进 SQLite 影子表，返回条数。

    没有这张影子表，设计文档 §4.2 里 citations.chunk_id 那个外键就无处可指
    （本项目的块只存在 Chroma，SQLite 侧本来没有 chunks 表）。同步是幂等的，
    每次启动全量跑一遍即可。
    """
    data = vector_db.get(include=["metadatas", "documents"])
    rows = [
        (vector_id, (meta or {}).get("source", ""), text or "")
        for vector_id, meta, text in zip(data["ids"], data["metadatas"], data["documents"])
    ]
    store.sync_chunks(rows)
    return len(rows)


def warm_up_reranker():
    """把精排模型先加载好（懒加载单例，第一次调用要读 400MB 权重）。

    启动时预热，代价是启动慢几秒 + 常驻内存；换掉的是**第一个用户**的额外等待。
    内存紧张可用 RAG_SKIP_RERANK_WARMUP=1 关掉。
    """
    rag_baseline.get_reranker()


async def resolve_question(llm, history_text, question):
    """把依赖前文的追问补全成独立问题；历史为空（首轮 / 单轮模式）直接原样返回。

    失败方向与 rag_baseline.rewrite 一致：**失败 = 没改写，不是没检索**。
    超时、报错、输出不像话，一律退回原问题 —— 最坏也只是这一轮指代没补上，
    绝不会变成「什么都没检索到」。
    """
    if not history_text:
        return question

    try:
        raw = await asyncio.wait_for(
            llm.ainvoke(REWRITE_PROMPT.format(history=history_text, question=question)),
            timeout=REWRITE_TIMEOUT,
        )
    except Exception:
        return question

    content = getattr(raw, "content", "")
    if not isinstance(content, str):
        return question
    out = content.strip()

    # 四种「改歪了」的样子，一律退回原问题：
    #   · 空的           —— 模型只回了空白
    #   · 比原问题长太多 —— 它在**回答问题**，不是在改写
    #   · 超过 3 行      —— 它在输出多个候选，或加了解释
    #   · 带模板残留词   —— 它把「改写后的问题：」这类提示词抄了回来
    limit = max(REWRITE_MIN_CHARS, len(question) + REWRITE_EXTRA_CHARS)
    if not out or len(out) > limit or len(out.splitlines()) > REWRITE_MAX_LINES:
        return question
    if any(w in out for w in _LEAK_WORDS):
        return question
    return out


def build_sources(hits):
    """把精排结果映射成契约里的 sources 数组：rank 升序、score 两位小数、snippet 前 34 字。

    字段名对齐《前后端交互说明.md》；snippet 的取法与 rag_baseline/main.py 打印预览
    的那几行是同一个意思。
    """
    return [
        {
            "rank": rank,
            "source": doc.metadata["source"],
            "score": round(float(score), 2),
            "snippet": make_snippet(doc.page_content),
        }
        for rank, (doc, score) in enumerate(hits, 1)
    ]


def _citation_rows(hits):
    """落库用的引用行 (chunk_id, score, snippet)。

    chunk_id 得靠「文件名 + 块原文」去 chunks 影子表里查 —— rag_baseline 的
    Document.metadata 只有 source 一个字段，检索结果里拿不到向量库的 vector_id。
    """
    rows = []
    for doc, score in hits:
        chunk_id = store.get_chunk_id(doc.metadata["source"], doc.page_content)
        rows.append((chunk_id, float(score), make_snippet(doc.page_content)))
    return rows


def _save_partial(conversation_id, saved, partial):
    """流中断时的兜底：把已经生成的那半截回答落库。

    不落的话，历史里会留下一条孤零零的用户提问。下一轮做指代消解时，模型看到的是
    一段没有下文的对话，比看到半截回答更容易跑偏。

    这里必须是**同步** sqlite 调用：本函数会在 CancelledError 路径上被调用，
    那条路径的协程已经取消，再 await 会立刻再抛一次 CancelledError。
    """
    if conversation_id is None or saved:
        return
    text = "".join(partial).strip()
    if not text:
        return
    try:
        store.save_answer(conversation_id, text, ())
    except Exception:
        # 兜底本身再失败就不往上抛了 —— 那会盖掉真正的错误原因。留一行日志即可。
        print(f"[warn] 半截回答落库失败（conversation_id={conversation_id}）")


async def run_pipeline(*, llm, llm_rewrite, vector_db, question, conversation_id,
                       history_text, retrieve_lock):
    """跑一轮问答，逐条产出 (事件名, data) 元组，由 app 层序列化成 SSE 帧。

    事件顺序：meta → message* → sources → done；出错则产出 error 并结束流。
    """
    user_message_id = None
    assistant_message_id = None

    # 先落 user 行，meta 事件才能带上它的 id。这个写是毫秒级的，不会拖慢首字节。
    # 单轮模式（conversation_id 为 None）全程不读写会话库。
    if conversation_id is not None:
        user_message_id = store.insert_message(conversation_id, "user", question)
        store.touch_conversation(conversation_id)

    yield EVENT_META, {"conversation_id": conversation_id, "user_message_id": user_message_id}

    partial = []     # 累积已生成的文本，中断时用来落一条半截回答
    saved = False    # assistant 行是否已落库 —— 决定异常路径要不要兜底
    try:
        resolved = await resolve_question(llm_rewrite, history_text, question)

        # 检索 + 精排串行化：重排器是懒加载单例、内部跑 torch，并发进来只会互相挤内存。
        # 课程项目并发量很小，串行几乎无感，换来的是「不会同时跑两份 400MB 模型」。
        async with retrieve_lock:
            hits = await asyncio.to_thread(rag_baseline.retrieve, vector_db, resolved)
            hits = await asyncio.to_thread(rag_baseline.rerank, resolved, hits)

        # 生成用**改写后**的问题：检索与生成口径一致，指代补全后的问法本身也更完整。
        # 落库的仍是原始问题（上面已写），历史展示不受影响。
        prompt = build_generate_prompt(resolved, hits, history_text)
        async for chunk in llm.astream(prompt):
            piece = chunk.content
            if isinstance(piece, str) and piece:
                partial.append(piece)
                yield EVENT_MESSAGE, {"delta": piece}

        if conversation_id is not None:
            try:
                assistant_message_id = store.save_answer(
                    conversation_id, "".join(partial), _citation_rows(hits)
                )
            except Exception as exc:
                # 答案已经流给前端了，此时只提示、不收回 —— 前端保留已渲染的内容。
                yield EVENT_ERROR, {"detail": f"答案已生成，但保存会话历史失败：{exc}"}
                return
            saved = True

        # 落库成功之后才发 sources/done，避免前端拿到「已完成」却查不到历史
        yield EVENT_SOURCES, {"sources": build_sources(hits)}
        yield EVENT_DONE, {
            "conversation_id": conversation_id,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        }
    except asyncio.CancelledError:
        # 客户端断开：Starlette 会取消这个生成器。落库走同步调用（理由见 _save_partial），
        # 写完把异常继续往上抛，让 Starlette 正常收尾。
        _save_partial(conversation_id, saved, partial)
        raise
    except Exception as exc:
        _save_partial(conversation_id, saved, partial)
        yield EVENT_ERROR, {"detail": f"回答失败：{exc}"}
