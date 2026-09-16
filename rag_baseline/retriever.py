"""
⑤ 检索 + ⑤′ 查询改写（多路检索）。

检索返回的分数是 L2 平方距离（BGE 向量已归一化 → d² = 2 - 2·cos），**越小越像**。
这里不做任何过滤 —— 阈值守卫是优化，不是地板。
"""
import re

from .config import K, REWRITE_MAX


def retrieve(db, question, k=K):
    """问题转向量 → 和库里所有块算距离 → 取最近的 k 条。"""
    return db.similarity_search_with_score(question, k=k)


# ---------- ⑤′ 查询改写（多路检索）----------
# 第二步优化。只治一种病：**一句话里两个意图**。
#
# CORS 那一问「CORS 是什么？怎么在 FastAPI 里配置？」—— 一个查询只能嵌成**一个**向量，
# 落在「是什么」和「怎么配」中间，两头都不像。实测含「跨域资源共享」定义的那块排到
# 全库第 175 / 804，精排的池子（前 20）里根本没有它 —— 模型看不见，答案是半截的。
# 拆开单独问「CORS 是什么？」，同一块排第 1。
#
# ⚠️ 这里**只拆、不换说法**，是量出来的取舍，不是省事：
# 多路检索合并时取的是各路里的**最小值** —— 路越多，这个值只会越小，题看着越像「库里有」。
# 而拒答守卫的全部依据就是这个值：库外最近 1.00（Django 1.16），库里最远 0.96，**缝只有 0.04**。
# 换说法（同义改写、HyDE 之类）会白白往下压它，把缝吃掉。所以不干那件事。
#
# 另一个安全性质：返回的列表**第一个永远是原问题**，所以多路检索只会**多捞**、不会少捞。
# 原来能捞到的，改写完还在 —— 改写最坏也只是「没起作用」，不会「变差」。


def rewrite_prompt(question):
    """改写用的提示词。**写成函数、不写成常量** —— 尾巴上要把问题拼进去。

    例子故意用**库外**的话题（吃 / 玩），不拿库里的题当例子：
    那样等于在教模型背题，量出来的分数是例子的功劳，不是改写的功劳。
    也不能拿拒答题当例子 —— 那是在告诉它哪几道该拒。
    """
    return (
        "把下面这个用户问题拆成几个各自只问一件事的小问题。\n"
        "\n"
        "规则：\n"
        "1. 只做拆分。**不要换说法、不要同义改写、不要补充原文没有的信息。**\n"
        "2. 如果原问题本来就只问一件事，就**一字不改地原样返回它**。\n"
        "3. 拆出来的每一句都要能独立看懂（该带的主语要带上）。\n"
        "4. 一行一句。不要编号，不要解释，不要输出任何别的东西。\n"
        "\n"
        "例子：\n"
        "  问题：北京有什么好吃的？怎么坐地铁去？\n"          # 两个意图 → 拆
        "  输出：\n"
        "  北京有什么好吃的？\n"
        "  怎么坐地铁去？\n"
        "\n"
        "  问题：周末去哪比较好玩？\n"                        # 只有一个意图 → 原样返回
        "  输出：\n"
        "  周末去哪比较好玩？\n"
        "\n"
        f"问题：{question}\n"
        "输出：\n"
    )


def rewrite(llm, question):
    """把复合问题拆成几个单意图的子问题。返回的列表**第一个永远是原问题**。

    拆不动 / 拆歪了 → 返回 [question] 一条，**退回地板**。
    这是故意的失败方向：改写失败的后果是「没改写」，不是「没检索」。
    （对比一下裁判那边：解析失败如果当成「判不过」，分数会被静默压低 —— 方向反了。）
    """
    raw = llm.invoke(rewrite_prompt(question)).content.strip()
    subs = []
    for line in raw.splitlines():
        # 只剥**行首的编号/项目符号**。不能用 strip("0123456789.") —— 那会把
        # 正文开头的字也啃掉（比如「1.1 是什么」剥成「是什么」），而且不报错。
        line = re.sub(r"^\s*(?:[-*·•]|\d+[.、)])\s*", "", line).strip()
        if line:
            subs.append(line)

    # 三种「拆歪了」的样子，一律退回原样。宁可少捞，不可乱捞：
    #   · 一行都没有        —— 模型在胡说 / 只回了空白
    #   · 超过 REWRITE_MAX  —— 它在发散，不是在拆
    #   · 有一行特别长      —— 它在**回答问题**，不是在拆问题
    if not subs or len(subs) > REWRITE_MAX or any(len(s) > 100 for s in subs):
        return [question]

    out = [question]                       # 原问题永远在，保证「只多捞、不少捞」
    for s in subs:
        if s != question and s not in out: # 单意图时模型原样返回 → 这里去重，免得白检一遍
            out.append(s)
    return out


def retrieve_multi(db, questions, k=K):
    """每路各捞 k 条，按块去重合并。同一个块留**它最像的那一路**的距离。

    返回结构和 retrieve() 一样（[(文档, 距离), ...]，越小越像），所以 rerank() 不用改就能接。
    这也是为什么不去用 RRF 那类「按名次融合」的算法：那会把距离扔掉，
    而拒答守卫要的正是距离这个数。
    """
    best, order = {}, []                   # 用 dict 去重，同时记住首次出现的顺序（结果才稳定）
    for q in questions:
        for doc, score in retrieve(db, q, k=k):
            key = (doc.metadata["source"], doc.page_content)   # 同源同文 = 同一块
            if key not in best:
                best[key] = (doc, score)
                order.append(key)
            elif score < best[key][1]:
                best[key] = (doc, score)
    hits = [best[key] for key in order]
    hits.sort(key=lambda x: x[1])
    return hits
