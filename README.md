# rag_baseline —— 从 RagDemo 隔离出的 RAG 功能流水线

从 `F:\RagDemo` 的 `baseline.py` 中隔离出来的**功能代码**，每个功能模块拆成一个文件。
原项目代码**一行未动**，这里是全新的独立文件。

**未包含**（按你的要求）：评估系统（`Eval/`）、`ingest.py`、`rag_core.py`、
`probe_threshold.py`（依赖 rag_core）、`Rerank/`（评测脚本）—— 那些属于评测/生产链路，
不是 baseline 功能本身。

## 模块 ↔ 流水线环节

| 文件 | 环节 | 主要内容 |
|---|---|---|
| `config.py` | 全局配置 | 语料/库路径、切分/检索/精排参数、环境变量、REBUILD |
| `embeddings.py` | 嵌入 | `MyEmbeddings`（jina v3，query/passage 分流） |
| `cleaner.py` | 清洗 | `CLEAN_RULES` / `CLEAN_SKIP` / `clean_md` / `is_corpus_noise_file` |
| `loader.py` | ① 载入 | `load_docs`（读文件→清洗→Document） |
| `splitter.py` | ② 过滤 ③ 切块 | `filter_chunks` / `split` |
| `vectorstore.py` | ④ 入盘 | `corpus_signature` / `read_signature` / `build` / `get_db` |
| `retriever.py` | ⑤ 检索 ⑤′ 改写 | `retrieve` / `retrieve_multi` / `rewrite` |
| `reranker.py` | ⑥ 精排 | `get_reranker` / `rerank` |
| `generator.py` | ⑦ 生成 | `generate` |
| `main.py` | 组装+入口 | `answer()` / `main()` |

## 跑法

在项目根目录（本 README 所在目录）执行，三种方式任选：

```
python run_baseline.py                        # 顶层入口，推荐（不带参数=用手写死的冒烟题）
python run_baseline.py "装饰器怎么用？"        # 直接提问，可传多个
python -m rag_baseline                        # 包入口
python -m rag_baseline.main                   # 模块入口
```

**不要**直接执行 `rag_baseline/main.py` —— 包内文件用相对导入，
直接跑会报 `ImportError: attempted relative import with no known parent package`。

## 语料：QACP 中文 Python 问答集

`data/qacp_docs/`（534 篇，10 个知识点），来自
[NTAIX/Chinese-Python-QA-Dataset](https://github.com/NTAIX/Chinese-Python-QA-Dataset)。
一篇问答一个文件，`SRC_DIR` 已指向这里。

原始文件留档在 `data/_qacp_raw/`，要重新生成（或重新下载）跑：

```
python tools/build_qacp_corpus.py              # 就地转换
python tools/build_qacp_corpus.py --download   # 原文件缺了，先下再转
```

三个坑记在这：

- `QACP_A.csv` 是 **GB18030** 编码，按 UTF-8 读会在第 20 字节崩掉。
- 答案中位数 885 字，超过 `CHUNK_SIZE=500`，所以多数问答会切成 2~3 块。
- **52 组问题逐字重复**（占 9.7%），但这不是脏数据 —— 是同一道题分别由
  「Beginner」和「Experience in Programming」两类学习者提出，**52 组的答案全都不一样**
  （如 q88 有 922 字、q89 只有 280 字）。代价是检索时会**两个版本一起进 TOP_N**，
  实测问「Python是什么？」的 TOP5 里 q001 和 q002 各占一条。要按用户水平路由或者去重，
  得在检索之后自己加一层。

换回 FastAPI 文档：把 `config.py` 的 `SRC_DIR` 改回 `data/fastapi_docs`
并把语料拷进来 —— 指纹跟着变，旧库自动重建。

## 运行前提（密钥未随代码拷贝）

1. **语料**：已随项目提供（见上）。`data/qacp_docs/` 不在的话，按上面两条命令重新生成。
2. **向量库**：`knowledge/chroma_db_baseline`。首次运行会按语料指纹自动建
   （1549 块 × jina v3，本机 CPU 约 12~15 分钟，只建一次）；指纹对得上就直接复用。
3. **模型**：jina v3 / bge-reranker-base 已缓存于本机，离线加载（`HF_HUB_OFFLINE=1`）。
4. **密钥**：复制 `.env.example` 为 `.env` 并填入 `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL`。

## 设计要点（继承自 baseline.py）

- **语料指纹**：库是语料的函数，指纹对不上就自动重建，不靠人记得改 REBUILD。
- **检索只捞不筛**：检索是「地板」，阈值守卫/清洗是优化，各自分层，不混在一起。
- **改写只拆不换说法**：多路检索取各路最小值，换说法会把拒答守卫的缝隙（约 0.04）吃掉。
- **精排全量重打**：rerank 分数方向/量纲和向量距离不同，不能混着排。
- **生成先答后免责**：先答已有的部分，不许拿「资料中没有…」开头。
