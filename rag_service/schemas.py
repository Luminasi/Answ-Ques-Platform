"""HTTP 层的请求 / 响应模型（pydantic）。字段名对齐《前后端交互说明.md》。"""

from pydantic import BaseModel, Field

from rag_service.config import NAME_MAX_CHARS


class AnswerIn(BaseModel):
    """问答请求。

    question **故意不设 max_length**：契约要求超长返回 400，而 pydantic 的长度约束
    会由 FastAPI 转成 422。所以长度在路由里手判（先 400，与 docs_service 同一套做法）。
    """

    question: str = Field(description="用户问题，上限 500 字，超长返回 400")
    conversation_id: int | None = Field(
        default=None, ge=1, description="会话 id；省略即单轮模式（不带上下文、不落库）"
    )
    stream: bool = Field(
        default=True, description="true=SSE 流式（默认）；false=一次返回纯答案 JSON"
    )


class ConversationIn(BaseModel):
    """新建会话请求，整个 body 可省略。"""

    name: str | None = Field(default=None, max_length=NAME_MAX_CHARS, description="会话名，省略则填「新会话」")


class ConversationOut(BaseModel):
    id: int
    name: str
    created_at: str
    updated_at: str


class SourceOut(BaseModel):
    """来源卡片。与 SSE `sources` 事件里的对象字段完全一致，前端可复用同一个组件。"""

    rank: int
    source: str
    score: float
    snippet: str
    chunk_index: int | None = Field(
        default=None,
        description="命中块在该文档中的 1-based 序号；用于跳转到文档块",
    )


class ChunkOut(BaseModel):
    index: int
    content: str
    start_char: int
    end_char: int


class DocumentChunksOut(BaseModel):
    source: str
    exists: bool
    total: int
    chunks: list[ChunkOut]


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    citations: list[SourceOut] = Field(default_factory=list, description="只有 assistant 消息会有")


class HistoryOut(BaseModel):
    conversation_id: int
    messages: list[MessageOut]


class ConversationListOut(BaseModel):
    """会话列表。total 恒等于 conversations 的长度（对齐 docs 列表接口的 {total, files} 风格）。"""

    total: int
    conversations: list[ConversationOut]


class HealthOut(BaseModel):
    status: str
