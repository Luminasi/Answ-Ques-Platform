"""
嵌入模型适配器（jina v3，本地跑）。

为什么要适配器：LangChain 只认 embed_documents / embed_query 两个方法，
fastembed 的接口名不一样，中间必须有人翻译。
jina v3 是多任务模型：查询必须走 query_embed（retrieval.query 任务），
文档必须走 passage_embed（retrieval.passage 任务）——直接 embed() 会把
查询也当文档嵌入，检索质量打折扣。
bge 系列没有任务之分，query/passage_embed 等价于 embed，两种模型都安全。
注意 embed_query 要返回**一维**向量（[0]），返回 [[...]] 会让 Chroma 报错。
"""
from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings

from .config import EMBED_MODEL


class MyEmbeddings(Embeddings):
    def __init__(self):
        self.model = TextEmbedding(model_name=EMBED_MODEL)

    def embed_documents(self, texts):
        # batch_size 必须在调用时传（构造参数不生效），否则默认 256 一批会打爆内存
        return list(self.model.passage_embed(texts, batch_size=32))

    def embed_query(self, text):
        return list(self.model.query_embed([text]))[0]
