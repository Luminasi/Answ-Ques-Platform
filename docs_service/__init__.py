"""docs_service：独立的文档阅读服务。

按文件名读取 data/qacp_docs/ 下的语料全文并通过 HTTP 暴露。
与 rag_baseline 完全隔离：不修改其任何文件，也不 import 其任何模块。
"""

from docs_service.app import app

__all__ = ["app"]
