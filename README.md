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

## rag_service —— HTTP 问答服务（SSE 流式 + 多轮会话记忆）

把 baseline 流水线包成 HTTP 接口，补上 baseline 没有的两件事：**逐 token 流式输出**
和**多轮会话记忆**。`rag_baseline/` 与 `docs_service/` 零改动 —— 整个包里只有
`rag_service/pipeline.py` 一处 `import rag_baseline`，且只用它的公开函数。

```
python -m rag_service          # 默认 127.0.0.1:8001（HOST / PORT 可覆盖）
```

**端口 8001 是刻意的**：文档服务占着 8000，两个服务都要提供 `/api/health`，同端口会撞。
接口契约（含 SSE 事件表、前端 fetch 消费方式）见 [前后端交互说明.md](前后端交互说明.md)。

| 接口 | 说明 |
|---|---|
| `POST /api/answer` | 问答主接口，响应是 **SSE 流**（`meta` → `message`* → `sources` → `done`）。带 `conversation_id` 即多轮，不带则退化成单轮（行为与 baseline 完全一致，且全程不碰会话库） |
| `POST /api/conversations` | 新建会话，返回 `id` |
| `GET /api/conversations` | 会话列表（按最近更新倒序），供前端侧边栏 |
| `GET /api/conversations/{id}/messages` | 查历史消息与引用来源 |
| `GET /api/health` | `ok` / 未就绪时 503 `starting` |

启动时会载入语料与向量库（指纹相符则秒级复用）、同步 `chunks` 影子表、**预热重排模型**
（约 400MB 常驻内存，换掉第一个用户的模型加载等待；内存紧张设 `RAG_SKIP_RERANK_WARMUP=1` 关掉）。

### 会话数据

存 `knowledge/chat_history.db`（SQLite，标准库 `sqlite3`，零新依赖）。**删掉这个文件即重置
全部会话**，与向量库一样属于「运行时生成、删掉可再生」，已在 `.gitignore` 里。

四张表：`conversations` / `messages` / `citations`，外加一张从 Chroma 同步来的 `chunks`
影子表 —— 设计文档里 `citations.chunk_id` 的外键要指向它，而本项目的语料块只存在向量库
（`Document.metadata` 只有 `source` 一个字段，检索结果拿不到 vector_id），所以启动时按
`vector_id` 幂等同步一份。

历史窗口是**最近 8 条消息、总字符 ≤3000**（最旧先裁），只影响送进模型的上下文，不删库里的行。

### 多轮是怎么做的

历史非空才做**指代消解改写**（把「那它呢？」补成「Python 呢？」），改写后的问题用于检索与
生成，落库的仍是用户原话。首轮/单轮模式跳过改写，此时提示词与 baseline **逐字节相同**。

改写失败方向与 baseline 的 `rewrite` 一致：**失败 = 没改写，不是没检索**。超时、报错、输出
不像话（空的 / 比原问题长 60 字以上 / 超过 3 行 / 抄了模板词）一律退回原问题 —— 最坏只是这
一轮指代没补上，绝不会变成「什么都没检索到」。

### 一个坑

**重建向量库前先停掉本服务**：Windows 上服务进程持有 `chroma_db_baseline` 的文件句柄，
不停服务就重建会撞文件锁。另外 `rag_baseline` 的路径全是相对路径，`config.py` 里那句
`os.chdir(PROJECT_ROOT)` 是必须的，不是保险 —— 少了它，从别的目录启服务会读到空语料并
安静地建一个空库。
