"""
rag_baseline —— 从原项目 RagDemo/baseline.py 隔离出来的 RAG 功能流水线。

每个功能模块一个文件：
  config      全局配置（语料/库路径、切分/检索/精排参数、环境变量）
  embeddings  嵌入模型适配器（jina v3，query/passage 分流）
  cleaner     清洗（CLEAN_RULES / clean_md / is_corpus_noise_file）
  loader      ① 载入（load_docs）
  splitter    ② 过滤 + ③ 切块（filter_chunks / split）
  vectorstore ④ 入盘（corpus_signature / build / get_db，含语料指纹）
  retriever   ⑤ 检索 + ⑤′ 查询改写（retrieve / retrieve_multi / rewrite）
  reranker    ⑥ 精排（get_reranker / rerank）
  generator   ⑦ 生成（generate）
  main        流水线组装与入口（python -m rag_baseline.main）
"""
from .cleaner import (CLEAN_RULES, CLEAN_SKIP, SIGNAL_PATTERNS,
                      clean_md, is_corpus_noise_file)
from .config import (CHUNK_OVERLAP, CHUNK_SIZE, DB_DIR, EMBED_MODEL, K,
                     RERANK_MODEL, REWRITE_MAX, SRC_DIR, TOP_N)
from .embeddings import MyEmbeddings
from .generator import generate
from .loader import load_docs
from .reranker import get_reranker, rerank
from .retriever import retrieve, retrieve_multi, rewrite, rewrite_prompt
from .splitter import filter_chunks, split
from .vectorstore import build, corpus_signature, get_db, read_signature

__all__ = [
    "CLEAN_RULES", "CLEAN_SKIP", "SIGNAL_PATTERNS",
    "clean_md", "is_corpus_noise_file",
    "CHUNK_OVERLAP", "CHUNK_SIZE", "DB_DIR", "EMBED_MODEL", "K",
    "RERANK_MODEL", "REWRITE_MAX", "SRC_DIR", "TOP_N",
    "MyEmbeddings", "generate", "load_docs",
    "get_reranker", "rerank", "retrieve", "retrieve_multi", "rewrite", "rewrite_prompt",
    "filter_chunks", "split", "build", "corpus_signature", "get_db", "read_signature",
]
