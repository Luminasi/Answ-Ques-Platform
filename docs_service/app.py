"""FastAPI 应用与路由：只做 HTTP 装配，文档读取的全部细节在 reader.py。

启动方式：
    python -m uvicorn docs_service.app:app --port 8000
    python -m docs_service
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docs_service import reader

DEFAULT_PORT = 8000


class DocOut(BaseModel):
    """单篇文档响应。"""

    source: str
    exists: bool
    content: str
    title: str


class DocListOut(BaseModel):
    """文档列表响应。

    字段名对齐《前后端交互说明.md》的契约：total 在前、files 在后。
    """

    total: int
    files: list[str]


class HealthOut(BaseModel):
    """健康检查响应。"""

    status: str


app = FastAPI(
    title="docs_service —— 文档阅读服务",
    description="按文件名读取语料全文，供前端阅读 RAG 引用文章。与 rag_baseline 完全隔离。",
)

# 前端在浏览器里跨端口调用时需要，开发阶段全开放
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    """健康检查。按规格固定返回 ok，不查磁盘。"""
    return HealthOut(status="ok")


@app.get("/api/docs", response_model=DocListOut)
def list_docs() -> DocListOut:
    """返回语料文件列表。"""
    files = reader.list_doc_files()
    return DocListOut(total=len(files), files=files)


@app.get("/api/docs/{source}", response_model=DocOut)
def get_doc(source: str) -> DocOut:
    """按文件名返回文档全文。

    先判格式（400）再判存在（404）：非法名不可能存在，且格式校验在任何
    文件系统操作之前完成，攻击者给的路径不会被 stat。
    """
    if not reader.is_valid_source(source):
        raise HTTPException(status_code=400, detail=f"非法文档名: {source}")

    doc = reader.read_doc(source)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档不存在: {source}")

    # exists 在成功响应里恒为 true，按接口约定保留该字段
    return DocOut(
        source=doc.source,
        exists=True,
        content=doc.content,
        title=doc.title,
    )
