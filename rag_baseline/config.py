"""
全局配置：环境变量、语料/库路径、切分/检索/精排参数。

从原项目 baseline.py 的常量区抽出来的独立模块。改这里任何一项，
只要它进了语料指纹（corpus_signature），旧库会自动判定失效并重建 ——
不用靠人记得去改 REBUILD（见 vectorstore.corpus_signature）。
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")   # Windows 控制台默认 GBK，中文输出会乱码

import os

# 模型从 hf-mirror 拉，别直连；禁 Xet（大文件会被重定向到国内解析不了的域名）；
# 模型已缓存就离线加载（不设的话启动会联网核对版本，本机 LFS 通道限速会挂死）。
# 要换新模型，先删掉 HF_HUB_OFFLINE 这行把模型下完再开。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("FASTEMBED_CACHE_PATH", r"C:\Users\lenovo\.cache\fastembed")

# 语料 = QACP 中文 Python 问答集（534 篇，10 个知识点），一篇问答一个文件。
# 原始数据在 data/_qacp_raw/，用 tools/build_qacp_corpus.py 重新生成（含 --download）。
# 换回 FastAPI 文档：把这里改回 "data/fastapi_docs" —— 指纹跟着变，旧库自动重建。
SRC_DIR = "data/qacp_docs"
PATTERN = "**/*.md"

# 库目录必须独立，**不能**用 chroma_db_v2：build() 每次都会 rmtree 重建，
# 指到 v2 会把 ingest.py 建的真库整个抹掉；而且两边切分方式不同、块也不一样。
DB_DIR = "knowledge/chroma_db_baseline"
SIG_PATH = os.path.join(DB_DIR, "_corpus.txt")   # 语料指纹小纸条

EMBED_MODEL = "jinaai/jina-embeddings-v3"        # 提成常量是为了进语料指纹：换模型也必须触发重建
CHUNK_SIZE, CHUNK_OVERLAP = 500, 50              # 中文文档建议 200-500 字，重叠取 10%
K = 20                                           # 检索捞回多少条候选（喂给精排的海选池）
TOP_N = 5                                        # 精排后留几条喂给模型（原项目实测：精排后 Hit@5 = 100%，
                                                 # 5 是能覆盖全部题的最小条数）
REWRITE_MAX = 4                                  # 查询改写最多拆几路（再多是噪声，每路都要嵌一次）
RERANK_MODEL = "BAAI/bge-reranker-base"

REBUILD = False                                  # True = 无条件重建整库
