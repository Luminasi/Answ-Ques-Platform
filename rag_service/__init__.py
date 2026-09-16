"""rag_service：独立的问答服务。

把 rag_baseline 流水线封装成 HTTP 接口：SSE 流式回答 + 多轮会话记忆（SQLite）。
与 rag_baseline 保持隔离：不修改其任何文件，只调用它的公开函数
（见 pipeline.py，那是本包唯一 import rag_baseline 的地方）。
"""

from rag_service.app import app

__all__ = ["app"]
