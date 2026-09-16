"""提示词集中管理：生成提示词（复制 rag_baseline 模板 + 插历史段）、改写提示词（指代消解）。

纯函数模块，**不 import rag_baseline** —— 生成提示词是复制过来的，不是 import 的：
rag_baseline.generator.generate() 内部用 llm.invoke 一次性返回，没法流式；
本服务要走 llm.astream，只能自己拼同一份提示词。
"""

from rag_service.config import SNIPPET_CHARS

# rag_baseline/generator.py 模板的开头句与结尾 4 条要求，逐字复制。
# 那 4 条每一条都是踩出来的：资料只覆盖一部分时，模型有一半概率用「资料中没有给出完整的 X…」
# **开头**，而裁判对「先认怂」这个形状是稳定地判不过的（温度压不住，temp 0.0 照样先认怂）。
# 想改这里的措辞前先回去读 generator.py 的注释 —— 别顺手「优化」掉。
_GENERATE_HEAD = "请根据以下资料回答问题。\n\n"

_GENERATE_RULES = (
    "回答要求：\n"
    "1. 先直接回答，把资料里能支持这个问题的内容（步骤、代码、要点）完整写出来。\n"
    "2. 资料往往只覆盖问题的一部分，这很正常 —— **照样先答已有的那部分**，\n"
    "   确有余下没覆盖到的，放到**最后**再补一句说明。\n"
    "3. **不要用「资料中没有…」「资料里没有给出…」这类句子开头。**\n"
    "   只有资料**完全**答不了这个问题时，才直接说明不知道。\n"
    "4. 以上内容都必须出自资料，不要自己补充资料里没有的东西。"
)


def build_generate_prompt(question, hits, history_text=""):
    """拼生成提示词：rag_baseline 的模板原样照抄，只在中间插一段对话历史。

    插入位置对齐系统设计文档附录 B 的 build_prompt 顺序：
    开头句 → 对话历史 → 参考资料 → 问题 → 回答要求。
    历史为空（首轮 / 单轮模式）时整段省略，行为与 baseline 完全一致。
    """
    context = "\n\n".join(doc.page_content for doc, _ in hits)
    history_section = f"对话历史：\n{history_text}\n\n" if history_text else ""
    return (
        f"{_GENERATE_HEAD}"
        f"{history_section}"
        f"资料：\n{context}\n\n"
        f"问题：{question}\n\n"
        f"{_GENERATE_RULES}"
    )


# 指代消解改写：**不能**复用 rag_baseline.rewrite()。
# 那个是「多意图拆分」，注释里写死了「不要换说法」—— 因为换说法会把拒答守卫的
# 0.04 距离缝隙吃掉。而指代消解恰恰就是换说法（「它」→「Python」），目的完全不同。
REWRITE_PROMPT = (
    "把学生的追问改写成一个**不依赖对话历史也能看懂**的独立问题。\n"
    "\n"
    "规则：\n"
    "1. 把追问里的指代词（它、这个、那个、上面说的、之前提到的……）换成对话历史里对应的具体对象。\n"
    "2. 只补全指代，不要添加学生没问的内容，不要回答问题，不要换说法。\n"
    "3. 如果追问本身已经完整（不含指代、不依赖历史），就一字不改地原样返回它。\n"
    "4. 只输出改写后的问题本身。不要编号，不要解释，不要输出任何别的东西。\n"
    "\n"
    "对话历史：\n{history}\n"
    "\n"
    "学生追问：{question}\n"
    "改写后的问题：\n"
)


def build_history_text(history):
    """把消息列表拼成「用户：…／助手：…」的纯文本，改写与生成共用同一份。

    传进来的 history 应当已经过窗口裁剪（见 store.get_history）——
    这里不再裁一次，免得两处口径不一致。
    """
    if not history:
        return ""
    lines = []
    for msg in history:
        who = "用户" if msg["role"] == "user" else "助手"
        lines.append(f"{who}：{msg['content']}")
    return "\n".join(lines)


def make_snippet(text):
    """来源片段预览：前 34 字、换行替空格（照抄 rag_baseline/main.py 的预览做法）。

    块里自带换行，不换掉会把 JSON 里一个字段撑成好几行，前端卡片也跟着变形。
    """
    return text[:SNIPPET_CHARS].replace("\n", " ")
