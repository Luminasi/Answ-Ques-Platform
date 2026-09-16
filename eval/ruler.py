"""
RAG 的尺子：一套固定题集 + 自动打分，把「感觉答得还行」变成「Hit@5 = 87%」。

为什么要有它：改完切分、换完模型，你怎么知道是变好了还是变坏了？
两道题看着都像答对了 —— 靠感觉会骗人。有了尺子才有分数：
分数涨了才叫优化，没涨就是白改（甚至改坏了）。

跑法（在项目根目录）：
    python Eval/eval.py

它测两件事：
  ① 检索（默认测）
     · Hit@K：该被找到的那篇文档，进没进前 K 名。K 取 1 / 3 / 5 / 10 / 20
     · MRR  ：它排名的倒数，全题取平均。排第 1 得 1.0，第 5 得 0.2，没进前 20 得 0
     为什么要 MRR：Hit@5 只看「进没进」，看不出「从第 110 名爬到第 1 名」这种大进步。
  ② 答案（可选，把下面 CHECK_ANSWER 改成 True）
     看答案里有没有出现该出现的关键词。代价是多调 15 次 LLM，要等几分钟。

题集在 cases.py —— 加题、改题、改期望来源都在那个文件里。

这个脚本**只管量、不管建**：库没建好会直接报错退出，绝不会偷偷跑 8 分钟建库。
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")   # Windows 控制台默认 GBK，中文输出会乱码

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                   # 让 import baseline 在 Eval/ 里也找得到
os.chdir(ROOT)                             # baseline 的路径（data/、knowledge/）都是相对项目根写的
import rag_baseline as baseline                           # 先 import 它：HF_HUB_OFFLINE 等环境变量是它在模块顶部设的
from langchain_chroma import Chroma

from case import GROUPS

EVAL_K = 20             # 每题取前多少条来判排名。和 baseline 喂给模型的条数一致
CHECK_ANSWER = False    # True = 顺便调 LLM 生成答案、检查关键词（慢，几分钟）
REPORT = os.path.join(ROOT, "Eval", "last_run.txt")   # 报告存这儿，下次跑覆盖


def open_db():
    """开门，不建库。
    
    库是 assess 的前提：没有库就量不了。这里故意不调用 baseline.build() ——
    建库要 8~10 分钟，评估脚本偷偷触发它是个陷阱。库没建好就明说，让人自己去跑 baseline.py。
    """
    if baseline.read_signature() != baseline.corpus_signature():
        print("库和当前语料对不上（要么还没建，要么语料/切分参数改过没重建）。")
        print(f"  库目录  ：{baseline.DB_DIR}")
        print(f"  应有指纹：{baseline.corpus_signature()}")
        print("先跑一次 python baseline.py 把库建好，再回来评估。")
        sys.exit(1)
    return Chroma(persist_directory=baseline.DB_DIR, embedding_function=baseline.MyEmbeddings())


def make_llm():
    """和 baseline.main() 同一套配置。故意抄一份，不去动 baseline.py。"""
    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI
    load_dotenv()
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0.3,
        default_headers={"x-opencode-session": "eval-session"},
    )


def norm(path):
    """把一个 source 折成**唯一可比的形式**：正斜杠 + 全小写。

    折这两样，各对应一个真踩过的坑：

    · **反斜杠** —— Windows 上 os.path.relpath 给的是 tutorial\\cors.md，
      题集里写的是 tutorial/cors.md，直接比字符串会全不相等 ——
      尺子坏了，分数会是假的 0 分（第一版就栽在这儿）。

    · **大小写** —— 字符串比较区分大小写，Windows 文件系统不区分。
      哪天混进一个 README.md 这种带大写的路径，那道题会**安静地**永远判 ❌。
      实测库里 120 个 source 现在全是小写，所以还没暴露 ——
      **正因为没暴露，才要在暴露之前先堵上。** 等它暴露，你只会看到分数掉了，
      找不到原因，因为没有任何一行代码做过错事。

    ⚠️ **两边都要过这一道。只折一侧等于没折。**
    写成 `norm(库那侧) in src那侧`：src 写反斜杠就永远对不上，
    而且**不报错** —— 只是那道题永远判 ❌。第一版就是这么写的，坑一直留到现在。
    """
    return path.replace("\\", "/").lower()


def first_rank(hits, expected):
    """期望的文档排第几？没进前 EVAL_K 名就返回 None。

    返回 `None` 而不是 `[]` —— 这函数给的是**一个数**（第几名），不是集合。
    没找到就是「没有值」，`None` 是 Python 里那句话的标准写法。
    下游全是 `if r["rank"] and ...` 和 `is None` 这两种用法，恰好都跟 None 对上；
    换成 `[]` 得动两个文件，而且是**把两道守卫改弱**，不是改对。

    expected 是**列表**（可以写多篇，命中任意一篇都算）。**两侧都过 norm()** ——
    正/反斜杠、大/小写怎么写都能对上。折一侧是白折，理由见 norm()。
    """
    # 写成字符串不会报错，但 `in` 会**静默退化成子串匹配**：少写几个字母也算命中。
    # 这是假阳性，方向最坏 —— 分数虚高，而分数好看的尺子人更愿意信。所以吵闹地拦掉。
    if isinstance(expected, str):
        raise TypeError(
            f"src 得写成列表，不能写成字符串：{expected!r}\n"
            f"    这里用的是 `in`，对字符串它会退化成**子串匹配**：\n"
            f'      "tutorial/cor.md" in "tutorial/cors.md"  →  True\n'
            f"    少写几个字母也算命中，分数虚高，而且不报错。\n"
            f"    只写一篇就写成：[{expected!r}]")
    want = {norm(s) for s in expected}
    for rank, (doc, _) in enumerate(hits, 1):
        if norm(doc.metadata["source"]) in want:
            return rank
    return None


def main():
    import time

    db = open_db()
    total = sum(len(cases) for cases in GROUPS.values())
    n_blocks = len(db.get(include=["metadatas"])["ids"])

    lines = []

    def emit(text=""):
        print(text)            # 一边打屏（跑的时候就能看见进度），一边攒进报告
        lines.append(text)

    emit("=" * 66)
    emit(f"RAG 尺子 · 题集 {total} 题" + ("（含答案关键词检查）" if CHECK_ANSWER else "（只测检索）"))
    emit(f"库  ：{baseline.DB_DIR}（{n_blocks} 块）")
    emit(f"切法：{baseline.corpus_signature()}")
    emit("=" * 66)

    llm = make_llm() if CHECK_ANSWER else None
    results = []
    t0 = time.time()

    n = 0
    for group, cases in GROUPS.items():
        emit(f"\n【{group}】")
        for case in cases:
            n += 1
            hits = baseline.retrieve(db, case["q"], k=EVAL_K)
            rank = first_rank(hits, case["src"])
            results.append({"group": group, "rank": rank})

            if rank:
                emit(f" {n:2d} ✅ 第 {rank:2d} 名   {case['q']}")
            else:
                emit(f" {n:2d} ❌ 没进前 {EVAL_K}   {case['q']}")
                top3 = " ｜ ".join(
                    f"[{score:.3f}] {doc.metadata['source']}" for doc, score in hits[:3]
                )
                emit(f"       实际前 3：{top3}")

            if CHECK_ANSWER:
                answer = baseline.generate(llm, case["q"], hits)
                missing = [w for w in case["must"] if w.lower() not in answer.lower()]
                emit("       答案关键词：" + ("全中 ✅" if not missing
                                             else "缺 " + "、".join(missing) + " ❌"))

    # ---------- 汇总 ----------
    emit("\n" + "-" * 66)
    emit(f"命中率（全 {total} 题）")
    for k in (1, 3, 5, 10, EVAL_K):
        hit = sum(1 for r in results if r["rank"] and r["rank"] <= k)
        emit(f"  Hit@{k:<3d} {hit:2d}/{total}   {hit / total:6.1%}")
    mrr = sum(1 / r["rank"] if r["rank"] else 0 for r in results) / total
    emit(f"  MRR    {mrr:.3f}   （排名倒数的平均，天花板 1.000）")

    emit("\n分组对比（哪组最差，就是下一个优化该治的病）")
    for group in GROUPS:
        rs = [r for r in results if r["group"] == group]
        hit5 = sum(1 for r in rs if r["rank"] and r["rank"] <= 5)
        g_mrr = sum(1 / r["rank"] if r["rank"] else 0 for r in rs) / len(rs)
        emit(f"  {group}：Hit@5 {hit5}/{len(rs)}   MRR {g_mrr:.3f}")

    emit(f"\n耗时 {time.time() - t0:.1f} 秒")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n报告已存 {REPORT}（下次跑会覆盖）")


if __name__ == "__main__":
    main()
