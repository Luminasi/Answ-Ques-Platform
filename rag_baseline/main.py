"""
流水线组装 + 入口：载入 → 过滤 → 切块 → 嵌入 → 入盘 → 检索 → 精排 → 生成。

和原项目 baseline.py 的 main() 等价，只是各环节被拆进了独立模块。
跑法（在本包所在目录的上层，即项目根目录）：
    python run_baseline.py          # 顶层入口，推荐
    python -m rag_baseline          # 包入口
    python -m rag_baseline.main     # 模块入口

⚠️ 首次运行 / 换语料 / 改切分参数时会重建向量库（jina v3，本机 CPU 约 12~15 分钟）；
库目录里记着语料指纹，对得上就复用现成的库（秒级启动）。提问本身只要几秒（只嵌 1 条查询）。
"""
import sys

# 包内文件只能作为包成员被调用（-m / import）。直接执行本文件（python rag_baseline/main.py）
# 时 __package__ 为空，下面的相对导入会报 ImportError —— 提前拦下来给一句人话。
if __package__ in (None, ""):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.write(
        "不能直接执行包内文件。请在项目根目录（F:\\answer-question-APP）运行：\n"
        "  python run_baseline.py      （或 python -m rag_baseline）\n"
    )
    sys.exit(1)

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .config import PATTERN, SRC_DIR
from .generator import generate
from .loader import load_docs
from .reranker import rerank
from .retriever import retrieve
from .splitter import split
from .vectorstore import get_db


def answer(db, llm, question):
    """问一个问题：海选 → 精排 → 生成。返回 (精排后的 hits, 回答文本)。"""
    hits = retrieve(db, question)      # 海选：捞回 K 条
    hits = rerank(question, hits)      # 精排：重打分，只留最像的 TOP_N 条
    return hits, generate(llm, question, hits)


def main():
    load_dotenv()
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0.3,
        default_headers={"x-opencode-session": "baseline-session"},
    )
    docs = load_docs()
    if not docs:
        sys.stderr.write(
            f"没有读到任何语料（{SRC_DIR} 下没有匹配 {PATTERN} 的文件）。\n"
            "语料可用 python tools/build_qacp_corpus.py --download 重新生成；\n"
            "或改 rag_baseline/config.py 里的 SRC_DIR 指向别的语料。\n"
        )
        sys.exit(1)
    chunks = split(docs)
    db = get_db(chunks)

    data = db.get(include=["metadatas"])
    sources = sorted({m["source"] for m in data["metadatas"]})
    print(f"库中共 {len(data['ids'])} 块，来自 {len(sources)} 个文件：")

    # 问题从命令行拿：python run_baseline.py "装饰器怎么用？"
    # 不给就用一道库里的原题做冒烟测试。原来是写死的 "FastAPI是什么" ——
    # 换成 QACP 语料后那题整个在库外，跑起来只会得到「资料中没有」，看着像坏了。
    questions = sys.argv[1:] or ["Python是什么？"]

    for question in questions:
        hits, text = answer(db, llm, question)
        for rank, (doc, score) in enumerate(hits, 1):
            preview = doc.page_content[:34].replace("\n", " ")   # 块里自带换行，不换掉会把一行撑成好几行
            print(f"  {rank}. {score:.3f}  [{doc.metadata['source']}] {preview}…")
        print(f"\n回答：{text}\n")


if __name__ == "__main__":
    main()
