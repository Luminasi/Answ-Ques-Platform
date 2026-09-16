"""
⑥ 精排：向量检索是「海选」——语义上沾边的都捞回来，但分不清「沾边」和「就是它」。
交叉编码器把（问题, 文档）拼成**一条**送进模型，读得出「讲的是同一件事」和
「只是都在讲 FastAPI」的区别，所以能把对的顶上来。
代价：约 4 秒/题（20 条候选，本机 CPU）—— 这是拿延迟换的分数。
原项目实测（Rerank/README.md）：MRR 0.758 → 0.852，Hit@5 86.7% → 100%。
"""
from .config import RERANK_MODEL, TOP_N

_reranker = None


def get_reranker():
    """第一次用到才加载模型。

    为什么绕这一下：别处 import 本包时不一定用到精排。
    写成模块级 import 的话，用不到精排的调用方也得白白背上 torch + 400MB 权重。
    """
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANK_MODEL, max_length=512)
    return _reranker


def rerank(question, hits, top_n=TOP_N):
    """给候选重新打分，取前 top_n 条。

    返回结构和 retrieve() 一样（[(文档, 分数), ...]），所以 generate() 不用改就能接。
    但分数的**方向是反的**：这边越大越像，retrieve() 那边越小越像 —— 量纲也不同
    （一个是「这一对配不配」的相关分，一个是向量距离）。所以要全量重打，不能混着排。
    """
    model = get_reranker()
    scores = model.predict([(question, doc.page_content) for doc, _ in hits])
    order = sorted(zip(hits, scores), key=lambda x: x[1], reverse=True)
    return [(doc, float(score)) for (doc, _), score in order[:top_n]]
