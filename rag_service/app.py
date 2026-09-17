"""FastAPI 应用与路由：只做 HTTP 装配。

问答细节在 pipeline.py，存储细节在 store.py —— 本模块不含检索、生成、SQL 的任何逻辑。

启动方式：
    python -m rag_service
    python -m uvicorn rag_service.app:app --port 8001
"""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from rag_service import pipeline, store
from rag_service.config import (DEFAULT_CONVERSATION_NAME, EVENT_DONE, EVENT_ERROR,
                                EVENT_MESSAGE, EVENT_META, EVENT_SOURCES,
                                QUESTION_MAX_CHARS, SKIP_RERANK_WARMUP)
from rag_service.prompts import build_history_text
from rag_service.schemas import (AnswerIn, ConversationIn, ConversationListOut,
                                 ConversationOut, DocumentChunksOut, HealthOut,
                                 HistoryOut, MessageOut)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    # 将来若挡在 Nginx 之类的反代后面，没有这一行 SSE 会被整段缓冲，
    # 「流式」退化成「憋很久然后一次性吐出来」。
    "X-Accel-Buffering": "no",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时把重家伙全部就位：语料 → 向量库 → 会话库 → 两个 LLM 客户端 → 精排模型。

    不做「首次请求再懒加载」：那样第一个用户要连着等模型加载，并发首问还会同时触发
    好几次。启动慢几秒，换请求路径上没有惊喜。
    """
    engine = await asyncio.to_thread(pipeline.build_engine)
    app.state.engine = engine

    store.init_db()
    n_chunks = await asyncio.to_thread(pipeline.sync_corpus_chunks, engine.vector_db)

    if not SKIP_RERANK_WARMUP:
        await asyncio.to_thread(pipeline.warm_up_reranker)

    # 检索 + 精排的串行闸门（理由见 pipeline.run_pipeline）
    app.state.retrieve_lock = asyncio.Lock()
    app.state.ready = True
    # 不在这里报端口：HOST/PORT 环境变量是在 __main__ 里读的，这里并不知道实际监听地址
    print(f"rag_service 已就绪（{n_chunks} 个语料块已入会话库影子表）")
    yield


app = FastAPI(
    title="rag_service —— 问答服务",
    description="把 rag_baseline 流水线封装成 HTTP 接口：SSE 流式回答 + 多轮会话记忆（SQLite）。"
                "rag_baseline 与 docs_service 零改动。",
    lifespan=lifespan,
)

# 前端在浏览器里跨端口直连时需要，开发阶段全开放（语料与问答均为公开数据、无鉴权）。
# 注意 POST 必须列进来：带 Content-Type: application/json 的请求会触发 OPTIONS 预检。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _require_ready():
    if not getattr(app.state, "ready", False):
        raise HTTPException(status_code=503, detail="服务正在启动，请稍后重试")


async def _sse_stream(events):
    """把 pipeline 产出的 (事件名, data) 序列化成 SSE 帧。

    每帧一个事件；data 必须是**单行** JSON（SSE 规范里 data 不能含裸换行），
    所以 json.dumps 不加缩进，并且不转义中文 —— 前端直接读中文，省一层 unescape。
    """
    async for name, data in events:
        yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _collect_answer(events):
    """非流式模式：把事件流完整消费掉，拼成一次返回的纯答案。

    返回 (answer, sources, meta)；出错时 meta 里带 error 字段。
    """
    parts = []
    sources = []
    meta = {"conversation_id": None, "user_message_id": None, "assistant_message_id": None}
    error = None
    async for name, data in events:
        if name == EVENT_META:
            meta["conversation_id"] = data.get("conversation_id")
            meta["user_message_id"] = data.get("user_message_id")
        elif name == EVENT_MESSAGE:
            parts.append(data.get("delta", ""))
        elif name == EVENT_SOURCES:
            sources = data.get("sources", [])
        elif name == EVENT_DONE:
            meta["conversation_id"] = data.get("conversation_id")
            meta["user_message_id"] = data.get("user_message_id")
            meta["assistant_message_id"] = data.get("assistant_message_id")
        elif name == EVENT_ERROR:
            error = data.get("detail")
    return "".join(parts).strip(), sources, meta, error


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    """健康检查。未就绪时返回 503（文档服务那边是固定 200，差异已写进契约）。"""
    _require_ready()
    return HealthOut(status="ok")


@app.post(
    "/api/answer",
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE 事件流"}},
)
async def answer(req: AnswerIn) -> StreamingResponse:
    """问答。返回 SSE 流，事件顺序 meta → message* → sources → done。

    校验在**返回流之前**做完：那几类错误必须以普通 JSON + HTTP 状态码返回，
    一旦开始流式输出，状态码就再也改不了了（只能靠 error 事件）。
    """
    _require_ready()

    question = req.question.strip()
    # 400 先于 404 判 —— 沿用 docs_service 的「先判格式、再判存在」顺序
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")
    if len(question) > QUESTION_MAX_CHARS:
        raise HTTPException(
            status_code=400, detail=f"question 超过 {QUESTION_MAX_CHARS} 字上限"
        )

    history_text = ""
    if req.conversation_id is not None:
        if not store.conversation_exists(req.conversation_id):
            raise HTTPException(status_code=404, detail=f"会话不存在: {req.conversation_id}")
        history_text = build_history_text(store.get_history(req.conversation_id))

    events = pipeline.run_pipeline(
        llm=app.state.engine.llm,
        llm_rewrite=app.state.engine.llm_rewrite,
        vector_db=app.state.engine.vector_db,
        question=question,
        conversation_id=req.conversation_id,
        history_text=history_text,
        retrieve_lock=app.state.retrieve_lock,
    )

    # stream=false：非流式模式，直接返回纯答案 JSON（拼好整段答案 + 来源），
    # 事件序列与 SSE 完全相同，只是不逐帧输出。
    if not req.stream:
        answer, sources, meta, error = await _collect_answer(events)
        if error:
            raise HTTPException(status_code=500, detail=error)
        return JSONResponse(
            {
                "answer": answer,
                "sources": sources,
                "conversation_id": meta["conversation_id"],
                "user_message_id": meta["user_message_id"],
                "assistant_message_id": meta["assistant_message_id"],
            }
        )

    # media_type 传 "text/event-stream"，Starlette 会自动补上 "; charset=utf-8"
    return StreamingResponse(_sse_stream(events), media_type="text/event-stream",
                             headers=SSE_HEADERS)


@app.post("/api/conversations", response_model=ConversationOut)
def create_conversation(req: ConversationIn | None = None) -> ConversationOut:
    """新建会话。整个 body 可省略 —— 省略时用默认名「新会话」。

    新会话天然不继承历史（新 id，messages 里没有它的行），不需要额外代码。
    """
    _require_ready()
    name = ((req.name if req else None) or "").strip() or DEFAULT_CONVERSATION_NAME
    return ConversationOut(**store.create_conversation(name))


@app.get("/api/conversations", response_model=ConversationListOut)
def list_conversations() -> ConversationListOut:
    """会话列表（按最近更新倒序）。空列表是正常结果，不是 404。"""
    _require_ready()
    rows = store.list_conversations()
    return ConversationListOut(
        total=len(rows),
        conversations=[ConversationOut(**r) for r in rows],
    )


@app.get("/api/conversations/{conversation_id}/messages", response_model=HistoryOut)
def get_conversation_messages(conversation_id: int) -> HistoryOut:
    """取一个会话的全部消息与引用来源（时间正序）。

    路径参数声明成 int：非正整数由 FastAPI 直接拦成 422，不用手判。
    """
    _require_ready()
    if conversation_id < 1 or not store.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail=f"会话不存在: {conversation_id}")
    messages = store.get_messages_with_citations(conversation_id)
    return HistoryOut(
        conversation_id=conversation_id,
        messages=[MessageOut(**m) for m in messages],
    )


@app.get("/api/docs/{source}/chunks", response_model=DocumentChunksOut)
def get_document_chunks(source: str) -> DocumentChunksOut:
    """返回一个语料文档的块表，供来源卡片跳转到命中区域。"""
    _require_ready()
    try:
        result = pipeline.document_chunks(source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {source}")
    return DocumentChunksOut(**result)

