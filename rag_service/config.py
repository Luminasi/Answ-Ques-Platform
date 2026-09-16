"""服务级常量：端口、路径锚点、长度上限、SSE 事件名。

纯常量模块：不 import rag_baseline，也不 import FastAPI —— 被各层共用。
"""

import os
from pathlib import Path

# 项目根：以本文件位置为锚（rag_service/config.py → 上一级的上一级），与启动时的 cwd 无关。
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 这一行是必须的，不是保险 ──
# rag_baseline 的语料/库路径全是**相对路径**（config.SRC_DIR = "data/qacp_docs"、
# DB_DIR = "knowledge/chroma_db_baseline"），只有 cwd 在项目根时才能解析对。
# run_baseline.py 和 eval/ruler.py 都靠 os.chdir(ROOT) 保证这件事，本服务同样把 cwd
# 钉死：否则从别的目录 python -m rag_service 会读到空语料，然后安静地建一个空库。
os.chdir(PROJECT_ROOT)

DEFAULT_PORT = 8001

# 会话记忆库：放 knowledge/ 下与向量库同区 —— 都是「运行时生成、删掉可再生」的数据
DB_PATH = PROJECT_ROOT / "knowledge" / "chat_history.db"

DEFAULT_CONVERSATION_NAME = "新会话"

# ── 契约上限（对齐《前后端交互说明.md》）──
QUESTION_MAX_CHARS = 500
NAME_MAX_CHARS = 100

# ── 历史窗口：防 token 爆炸 ──
# 8 条 = 4 轮问答，满足系统设计文档「连续对话不少于三轮仍能正确理解指代」。
HISTORY_MAX_MESSAGES = 8
HISTORY_MAX_CHARS = 3000

# ── 指代消解改写 ──
# 超时 / 输出不像话一律退回原问题：改写失败的后果必须是「没改写」，不能是「没检索」。
REWRITE_TIMEOUT = 15.0

# 长度守卫用**相对**尺子，不用固定字数：改写只补指代，长度应当和原问题同量级。
# 固定阈值两头都不对 —— 短追问（「那它呢？」4 字）改完天然涨好几倍，
# 而用户真写了 200 字的长问题，改写结果也该有 200 字。
REWRITE_EXTRA_CHARS = 60     # 允许比原问题多出的字数
REWRITE_MIN_CHARS = 60       # 下限保护：4 字的追问也得容得下正常改写
REWRITE_MAX_LINES = 3        # 超过 3 行 = 它在输出多个候选或加解释，不是在改写

SNIPPET_CHARS = 34           # 来源卡片预览字数（对齐契约）

# ── SSE 事件名 ──
EVENT_META = "meta"
EVENT_MESSAGE = "message"
EVENT_SOURCES = "sources"
EVENT_DONE = "done"
EVENT_ERROR = "error"

# 重排器预热：默认预热（常驻约 400MB 内存，换掉首问的几秒模型加载）。
# 内存紧张时设 RAG_SKIP_RERANK_WARMUP=1 关闭，代价是第一个问题慢几秒。
SKIP_RERANK_WARMUP = os.environ.get("RAG_SKIP_RERANK_WARMUP") == "1"
