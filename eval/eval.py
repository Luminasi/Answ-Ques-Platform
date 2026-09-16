"""
全链路尺子：从载入到生成，每一段的出口都设一根表笔。

为什么要有它 —— **端到端分数是烟雾报警器，不是诊断书。**
哪天总分从 80% 掉到 74%，一个数字只告诉你「着火了」，不告诉你火在哪：
是清洗洗坏了？精排换模型换废了？还是 LLM 抽风了？所以每一段都要独立出分。

    载入 →[①]→ 过滤 → 切块 →[②]→ 嵌入 → 检索 →[③]→ 改写 →[⑤′]→ 精排 →[④]→ 生成 →[⑤]
              ↑                ↑                ↑              ↑             ↑              ↑
           数据体检          块质量           检索分         改写后池子     精排分         答案分

三类指标，成本差三个数量级，从便宜往贵做：
  ① 体检型  免费，秒级    不需要标准答案，当哨兵用：噪声占比突变 = 语料变了
  ② 检索型  十几秒        要 cases.py 里的 src
  ③ 生成型  几分钟        要 must。第一期先用关键词检查，第二期换 LLM 裁判

⚠️ 自检（这条不能省）：③ 检索行**永远**等于 Eval/last_run.txt —— ③ 量的是 retrieve()，
   那是「地板」，RUN_REWRITE 开关不影响它。
   **但 ④ 精排行只在 RUN_REWRITE = False 时才等于 Rerank/last_run.txt。**
   改写打开后，④ 是在**多路合并的池子**上精排的，分母都变了，和 Rerank/ 那份对不上是**预期内**的，
   不是脚本坏了。要复现旧数就先关掉 RUN_REWRITE。

跑法（在项目根目录）：
    python Eval/pipeline.py

它不建库：库和语料指纹对不上就直接退出（先去跑 python baseline.py）。
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")   # Windows 控制台默认 GBK，中文输出会乱码

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                         # 为了 import baseline
sys.path.insert(0, os.path.join(ROOT, "Eval"))   # 为了 import cases / eval
os.chdir(ROOT)                                   # baseline 的路径都是相对项目根写的

# 先 import baseline：HF_HUB_OFFLINE 等环境变量是它在模块顶部设的，
# 必须在任何 huggingface 相关的东西被 import 之前生效。
import rag_baseline
import ruler       # 尺子：借它的 open_db / norm / first_rank，判定逻辑只留一份
from case import GROUPS, REFUSALS

POOL = 20                # 海选池大小，和 baseline.K / Eval.EVAL_K / Rerank.POOL 对齐
# frontmatter 是**文档级**概念（正则用 \A 锚文档开头），只能在「① 载入」按篇量。
# 拿到「② 切块」按块量会误报：块如果正好以 --- 开头（水平分隔线）、后面又有一条 --- 线，
# 就会被算成命中 —— 正则没错，是量的对象错了。
DOC_LEVEL = {"frontmatter"}
RUN_RERANK = True        # ④ 精排要 60 秒。只关心 ①②③ 时（比如调清洗）把它关掉
RUN_REWRITE = True       # ⑤′ 查询改写：复合问题拆成多路，各检一次再合并
CHECK_ANSWER = False     # ⑤ 生成要多调 15 次 LLM，几分钟
# True = 屏上只留「⑤ 生成」和「⑥ 拒答」两段。
# ①②③④ 照跑不误（生成要用精排后的上下文），只是**不打屏** ——
# 屏上只剩答案和裁判结果，肉眼验裁判用。
# 关掉它才是完整的全链路报告（改了清洗/精排之后要看的那个）。
ANSWER_ONLY = False
REPORT = os.path.join(ROOT, "Eval", "pipeline_last_run.txt")
ANSWERS = os.path.join(ROOT, "Eval", "answers_last_run.txt")   # 答案全文；屏上只打摘要


def stage_load():
    """① 载入：数文件，顺手把非文档文件揪出来。"""
    docs = rag_baseline.load_docs()
    names = [os.path.basename(d.metadata["source"]) for d in docs]
    junk = sorted({n for n in names if rag_baseline.is_corpus_noise_file(n)})
    return docs, names, junk


def pattern_hits(chunks, pairs):
    """每类模式命中多少块。体检型指标：不要标准答案，免费。pairs = [(标签, 正则), ...]"""
    n = len(chunks)
    return [(label, sum(1 for c in chunks if rx.search(c.page_content)), n)
            for label, rx in pairs]


def run_all(db, llm):
    """15 题走一遍。③ 和 ④ 共用**检索**，但**不是同一份结果** —— 这一点是故意的。

    加了改写之后，「③ 地板」和「④⑤ 实际用的池子」必须分开：
      · ③ 永远是 retrieve()，单路、纯向量。它是**参照系**，动了它，
        不但 Eval/eval.py 对不上，以后所有优化的收益也没有基准可算了。
      · ④⑤ 用的是池子：开了改写是多路合并的，关掉就是 hits 本身（逐位一致，不重复检索）。
    """
    rows = []
    for group, cases in GROUPS.items():
        for case in cases:
            q = case["q"]
            hits = rag_baseline.retrieve(db, q, k=POOL)              # ③ 地板：焊死，不参与优化
            if RUN_REWRITE:
                subs = rag_baseline.rewrite(llm, q)
                pool = rag_baseline.retrieve_multi(db, subs, k=POOL)
            else:
                subs, pool = [q], hits                           # 关掉时不重复检索，结果逐位一致
            row = {"group": group, "case": case, "hits": hits, "subs": subs, "pool": pool,
                   "before": ruler.first_rank(hits, case["src"]),
                   "extra": len(pool) - len(hits)}               # 多路一共多捞回来几块
            if RUN_RERANK:
                # 精排仍然按**用户原话**判 —— 改写只管海选，不该影响「什么才算答在问题上」
                rr = rag_baseline.rerank(q, pool, top_n=POOL)
                row["rr"] = rr
                row["after"] = ruler.first_rank(rr, case["src"])
            rows.append(row)
    return rows


def hit_lines(rows, key):
    """Hit@K 和 MRR。key 是 'before' 或 'after'。"""
    total = len(rows)
    out = []
    for k in (1, 3, 5, 10, POOL):
        hit = sum(1 for r in rows if r[key] and r[key] <= k)
        out.append(f"  Hit@{k:<3d} {hit:2d}/{total}   {hit / total:6.1%}")
    mrr = sum(1 / r[key] if r[key] else 0 for r in rows) / total
    out.append(f"  MRR    {mrr:>8.3f}   （排名倒数的平均，天花板 1.000）")
    return out, mrr


def rank_strip(rows, key):
    """15 题的名次压成一行。哪题崩了一眼看得见，不用翻别的脚本。"""
    cells = [f"{r[key]:2d}" if r[key] else "—" for r in rows]
    return "  " + " ".join(cells)


def oneline(text, width=110):
    """答案压成一行摘要：换行拍平，超长截断并标明还剩多少字。
    全文另存 ANSWERS —— 摘要用来看，全文用来核裁判。"""
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[:width] + f" …（+{len(flat) - width} 字）"


# ---------- 答案裁判 ----------
# 为什么不用关键词判：
#   must 那一列是死的 —— 答案对了但换个说法就判 ❌。
#   更要命的是它**两个方向都会错**：关键词出现了、但答案答非所问，它照样判 ✅。
#
# 但换成 LLM 裁判会引入一个新麻烦：**裁判本身也是会错的东西。**
# 所以 ⑤ 那一段把答案原文一起打出来（全文另存一份）—— 裁判判得对不对，得有人看着。
# **尺子自己也要被量**，这是老规矩。
JUDGE_PROMPT = """你是答案裁判。只判断一件事：这段回答有没有真正回答用户的问题。

用户问题：
{q}

回答应该涉及的概念（**只是线索，不是判据** —— 逐字没出现但意思到了，一样算过）：
{must}

待判定的回答：
{answer}

判定标准：

1. 只要回答**表达了**该概念就算过，不要求逐字出现 —— 同义词、换种说法、
   给代码示例、给步骤，都算。
2. 回答必须**答在问题上**。答非所问、含糊其辞、把资料原文抄一遍却没回答问题，算不过。

3. ⚠️ 这条最容易判错，看仔细：
   **「免责声明」和「整篇答不出来」是两件完全不同的事，别混。**

   - 回答**先声明资料不全**，但**后面给出了实质内容**（步骤、代码、要点、机制）
     → **算过**。
     很多好答案就是这个形状：「资料里没有给出完整的端到端示例，但关键机制是 X」。
     前半句是免责，后半句才是答案 —— **别看到前半句就判不过。**
   - 回答**通篇**只有「资料里没有相关信息」「无法回答」，一点实质内容都没有
     → **算不过**。

   判据很简单：**把那些免责的话删掉，剩下的还有没有东西。有，就算过。**

只回两行，格式严格照下面，不要有任何多余的字：
第一行：PASS 或 FAIL（只写这一个词，别的什么都不要）
第二行：一句话理由"""

REFUSAL_PROMPT = """判断下面这段回答，是在**如实说「我不知道」**，还是在**试图回答问题**。

用户问题：
{q}

待判定的回答：
{answer}

判定标准：
- 回答表示「资料里没有相关内容」「无法回答」「不知道」→ 回 REFUSE
- 回答给出了任何实质性的答案、步骤、代码、或者推荐 → 回 ANSWER
- 含糊其辞、答非所问、扯到别的话题 → 回 ANSWER（嘴上说不知道、底下还是编了，不算拒答）

只回一个词：REFUSE 或 ANSWER"""


def judge_answer(llm, question, answer, must):
    """判「答对了没有」。返回 (True / False / **None**, 理由)。

    ⚠️ must 在这里只是**线索**，不是判据。判据是「有没有答在问题上」。

    **第三个返回值 None = 裁判故障**（没按格式回），不是「答错了」。
    这两件事必须分开 —— 混在一起，裁判抽风就会被记成答案错，
    分数被悄悄压低，而屏幕上看起来一切正常。**和写死 误拒 0/15 是同一类错。**

    解析分两步，因为实测踩过两种坑：
      1. 理由是自由文本，里面会有冒号（`response_model:`、URL、全角「：」）——
         所以**不能**用 raw.split(":", 1)，那会从第一个冒号把理由拦腰截断。
      2. 模型有时不写前缀，直接开始唠叨（实测出现过只回「_model，并正确说明其作用」）。
         所以先看第一行，第一行没有就退一步在开头找一次独立出现的 PASS/FAIL。
         **再找不到就是故障，不许猜。**
    """
    raw = llm.invoke(JUDGE_PROMPT.format(q=question, must="、".join(must),
                                         answer=answer)).content.strip()
    lines = raw.splitlines() or [""]
    m = re.match(r"^(PASS|FAIL)\b", lines[0].strip(), re.I)       # ① 第一行
    if not m:
        m = re.search(r"\b(PASS|FAIL)\b", raw[:200], re.I)         # ② 开头兜底
    if not m:
        return None, f"裁判没按格式回，原话：{oneline(raw, 80)}"
    why = lines[1].strip() if len(lines) > 1 else oneline(raw, 80)
    return m.group(1).upper() == "PASS", why


def judge_refusal(llm, question, answer):
    """判「闭嘴了没有」。返回 (True / False / **None**, 裁判原话)。None = 裁判故障。

    和 judge_answer 同一套规矩：**看不懂就报故障，不许猜。**
    原来写的是 raw.upper().startswith("REFUSE") —— 模型要是回一句「这句话是在
    拒绝回答」它就判成 ANSWER，一声不响。猜错的方向还正好是「以为没拒答」。
    """
    raw = llm.invoke(REFUSAL_PROMPT.format(q=question, answer=answer)).content.strip()
    m = re.search(r"\b(REFUSE|ANSWER)\b", raw[:80], re.I)
    if not m:
        return None, f"裁判没按格式回，原话：{oneline(raw, 80)}"
    return m.group(1).upper() == "REFUSE", raw


def main():
    import time

    db = ruler.open_db()          # 库不对（没建 / 语料改过没重建）会在这里直接退出
    # LLM 得早建：run_all 里就要拿它去改写了，不能等到 ⑤ 那一段才建。
    # make_llm() 只是造个客户端对象、不联网，所以用不上时多建一个也无所谓。
    llm = ruler.make_llm() if (CHECK_ANSWER or RUN_REWRITE) else None
    t0 = time.time()
    lines = []

    def emit(text=""):
        print(text)               # 一边打屏一边攒报告，和 Eval/eval.py 一个套路
        lines.append(text)

    total = sum(len(cases) for cases in GROUPS.values())
    metas = db.get(include=["metadatas"])["metadatas"]
    n_blocks = len(metas)

    if not ANSWER_ONLY:
        emit("=" * 70)
        emit(f"RAG 全链路 · 题集 {total} 题")
        emit(f"库  ：{rag_baseline.DB_DIR}（{n_blocks} 块）")
        emit(f"切法：{rag_baseline.corpus_signature()}")
        emit("=" * 70)

        # ---------- ① 载入 ----------
        docs, names, junk = stage_load()
        emit("\n【① 载入】")
        emit(f"  文件         {len(docs)} 篇")
        if junk:
            emit(f"  非文档文件    {len(junk)} 篇  ← 混进库了：{'、'.join(junk)}")
        else:
            emit("  非文档文件    0 篇")

        fm = {l: r for l, r, _ in rag_baseline.CLEAN_RULES}["frontmatter"]
        emit(f"  frontmatter   {sum(1 for d in docs if fm.search(d.page_content))} 篇")

    # 尺子自检（**不受 ANSWER_ONLY 影响**，永远跑）：题集里写的 src，库里到底有没有？
    # 写错的 src，或**被清洗丢掉的文档**，会让那题永远判 ❌ ——
    # 而你会以为是检索退步了。尺子坏了比没尺子更糟，所以每一次跑都查。
    # 它平时一句话不说，**开口就是有事** —— 所以 ANSWER_ONLY 也拦不住它。
    # src 那侧**也要过 norm()** —— 和 first_rank 用同一套折法，两边必须一致。
    # 只折库那一侧的话这里会**误报**：src 写成反斜杠或大写时，
    # first_rank 明明能命中（它两边都折了），这儿却会喊「库里没有」。
    # 自检喊错了比不喊更坏 —— 你会去改一个根本没写错的 src。
    in_db = {ruler.norm(m["source"]) for m in metas}
    phantom = sorted({s for cases in GROUPS.values() for c in cases for s in c["src"]
                      if ruler.norm(s) not in in_db})
    if phantom:
        emit(f"\n  ⚠️ 尺子自检失败：题集里 {len(phantom)} 个 src 库里没有")
        for s in phantom:
            emit(f"       {s}")
        emit("     这些题会永远判 ❌。要么 src 写错了，要么那些文档被清洗丢掉了。")

    if not ANSWER_ONLY:
        # ---------- ② 切块 ----------
        chunks = rag_baseline.split(docs)
        lens = sorted(len(c.page_content) for c in chunks)
        emit("\n【② 切块】")
        emit(f"  块           {len(chunks)}")
        emit(f"  块长         最短 {lens[0]} / 中位 {lens[len(lens) // 2]} / "
             f"最长 {lens[-1]} / 平均 {sum(lens) / len(lens):.0f}")

        emit("  噪声（该洗的）")
        for label, hit, n in pattern_hits(chunks, [(l, r) for l, r, _ in rag_baseline.CLEAN_RULES
                                                   if l not in DOC_LEVEL]):
            mark = "  ← 这一批没洗" if label in rag_baseline.CLEAN_SKIP else ""
            emit(f"    {label:<18}{hit:4d} 块  {hit / n:6.1%}{mark}")
        emit("  信号（不该动的 —— 洗了就没答案了）")
        for label, hit, n in pattern_hits(chunks, list(rag_baseline.SIGNAL_PATTERNS.items())):
            emit(f"    {label:<18}{hit:4d} 块  {hit / n:6.1%}")

    # ---------- ③ 检索（跑，但不一定打屏：生成要用它） ----------
    rows = run_all(db, llm)
    if not ANSWER_ONLY:
        emit("\n【③ 检索】纯向量，就是「地板」")
        body, mrr_before = hit_lines(rows, "before")
        for line in body:
            emit(line)
        emit(f"  名次        {rank_strip(rows, 'before')}")

    # ---------- ④ 精排 ----------
    if RUN_RERANK and not ANSWER_ONLY:
        emit("\n【④ 精排】检索 + 交叉编码器重排")
        body, mrr_after = hit_lines(rows, "after")
        for line in body:
            emit(line)
        emit(f"  名次        {rank_strip(rows, 'after')}")
        emit(f"  精排净收益   MRR {mrr_after - mrr_before:+.3f}")
    elif not RUN_RERANK:
        emit("\n【④ 精排】（跳过：RUN_RERANK = False）")

    # ---------- ⑤ 生成 ----------
    full = []                      # 答案全文，另存一份
    if not CHECK_ANSWER:
        emit("\n【⑤ 生成】（跳过：CHECK_ANSWER = False。开了要多调 15 次 LLM，几分钟）")
    elif not RUN_RERANK:
        emit("\n【⑤ 生成】（跳过：生成要用精排后的上下文，先开 RUN_RERANK）")
    else:
        emit("\n【⑤ 生成】每题的答案都打出来 —— 裁判判得对不对，你自己看")
        emit(f"         全文另存 {os.path.relpath(ANSWERS, ROOT)}")
        # 改写是个**安静**的优化：它动了检索，屏幕上却一个字都不会说。
        # 不打这一行，你没法知道它到底开没开、动了几道题 —— 而「不知道它开没开」
        # 会让两次跑出来的分差别没法解释。
        if RUN_REWRITE:
            split = [i for i, r in enumerate(rows, 1) if len(r["subs"]) > 1]
            emit(f"  改写：{len(split)} 题拆开了（第 {split} 题），其余 {len(rows) - len(split)} 题原样")
        else:
            emit("  改写：关（RUN_REWRITE = False）")
        emit("")
        ok = 0
        for i, r in enumerate(rows, 1):
            case = r["case"]
            # 喂给模型的是精排后的前 TOP_N 条 —— 和 baseline.main() 完全一致
            answer = rag_baseline.generate(llm, case["q"], r["rr"][:rag_baseline.TOP_N])
            passed, why = judge_answer(llm, case["q"], answer, case["must"])
            # 端到端 = 该找的文档进了上下文，**且**裁判认为答在问题上。
            # 前半个条件现在恒真（Hit@5 = 100%），但留着 —— 哪天检索退步了，
            # 它能把「资料根本没给到」和「给了但没答好」分开报。
            in_ctx = r["after"] is not None and r["after"] <= rag_baseline.TOP_N
            r["passed"] = passed
            r["e2e"] = bool(in_ctx and passed)   # passed=None（故障）时这里为 False，宁可保守
            r["answer"] = answer          # ⑥ 要用它算误拒
            ok += r["e2e"]

            # 三个符号，三件事：✅ 答对 / ❌ 答错 / ⚠️ **裁判坏了**（不是答案的错）
            mark = "⚠️" if passed is None else ("✅" if r["e2e"] else "❌")
            verdict = "故障 " if passed is None else ("PASS" if passed else "FAIL")
            emit(f"  {i:2d} {mark} {r['group']}")
            emit(f"     问 {case['q']}")
            if len(r["subs"]) > 1:
                # 只在这题真被拆开时才多一行。哪题动了、动成几条，就写在它自己身上。
                emit(f"     拆 {len(r['subs'])} 路（池子 {len(r['pool'])} 块，多捞 {r['extra']}）")
            emit(f"     答 {oneline(answer)}")
            emit(f"     裁 {verdict} {why}")
            full.append(f"【{i:2d}】{mark} {r['group']}\n"
                        f"问题：{case['q']}\n"
                        f"关键词：{'、'.join(case['must'])}\n"
                        f"答案：{answer}\n"
                        f"裁判：{verdict} {why}\n")

        emit(f"\n  答案正确率   {ok}/{len(rows)}   {ok / len(rows):.1%}")
        broken = [r["case"]["q"] for r in rows if r["passed"] is None]
        if broken:
            emit(f"  ⚠️ 裁判故障   {len(broken)} 题  ← **尺子坏了，不是答案坏了。**")
            emit(f"     这些题按 ❌ 计进了上面的分母，所以那个数被压低了，别当真。")
            for q in broken:
                emit(f"       {q}")

        # ---------- ⑥ 拒答 ----------
        # 库里根本没有答案的问题：该闭嘴的时候，有没有闭嘴。
        # 这一段给两个**互不相同**的数，别混着看：
        #   有没有拒答 → 现有提示词（「若资料中没有相关信息，请如实告知」）管不管用
        #   最近距离   → **阈值守卫这条路走不走得通**（库内库外的分布有没有缝）
        emit("\n【⑥ 拒答】库里没有的问题：该不该张嘴\n")
        ref_rows = []
        for q in REFUSALS:
            # ⚠️ 这里的池子必须和 ⑤ 用的是**同一个阶段**，而且下面 in_d 也得跟着一起换。
            # 只换一侧的话，「缝」就成了**拿苹果比橘子**：库外取多路的最小值、
            # 库内取单路的最小值，多路那个天然更小 —— 缝会显得莫名其妙地窄，
            # 而你会以为是拒答退步了。**量出来的缝必须是同一个阶段上的缝。**
            if RUN_REWRITE:
                subs = rag_baseline.rewrite(llm, q)
                pool = rag_baseline.retrieve_multi(db, subs, k=POOL)
            else:
                subs, pool = [q], rag_baseline.retrieve(db, q, k=POOL)
            final = (rag_baseline.rerank(q, pool, top_n=rag_baseline.TOP_N) if RUN_RERANK
                     else pool[:rag_baseline.TOP_N])
            answer = rag_baseline.generate(llm, q, final)
            refused, _ = judge_refusal(llm, q, answer)
            ref_rows.append((pool[0][1], q, refused, answer))

        for dist, q, refused, answer in ref_rows:
            emit(f"  {'⚠️' if refused is None else ('✅' if refused else '❌')}"
                 f" 距离 {dist:5.2f}  {q}")
            emit(f"             答 {oneline(answer, 80)}")
        n_ref = len(ref_rows)
        ok_ref = sum(1 for _, _, refused, _ in ref_rows if refused)
        emit(f"\n  拒答正确率   {ok_ref}/{n_ref}   {ok_ref / n_ref:.1%}")

        # 误拒：库内题的答案里，有没有被模型回成「资料里没有」。
        # 这个数**必须真跑出来**，不能写死 —— 写死的数看起来最漂亮，也最会骗人。
        # 代价是不对称的：用户问了个你库里明明有答案的问题、你说不知道，比答得差更伤。
        mis, mis_broken = [], 0
        for r in rows:
            refused, _ = judge_refusal(llm, r["case"]["q"], r["answer"])
            if refused is None:
                mis_broken += 1          # 裁判故障：**不知道**是不是误拒，不许猜成「不是」
            elif refused:
                mis.append(r["case"]["q"])
        emit(f"  误拒         {len(mis)}/{len(rows)}   （库内题被答成「资料里没有」的数量）")
        for q in mis:
            emit(f"       {q}")
        if mis_broken:
            emit(f"      （另有 {mis_broken} 题裁判故障没算进来 —— 它们**可能**是误拒，只是不知道）")

        # 分布有没有缝 —— 这才是「阈值守卫能不能做」的真答案。
        # **只报数，不设阈值**：拍一个数出来就没法复盘了。
        # 得先看见缝在哪，阈值才有依据；没缝就说明这条路根本不通，得换机制。
        # 两边都取 pool（④⑤⑥ 真正用的那个池子），**不能一边 hits 一边 pool** ——
        # 理由见 ⑥ 开头。开了改写时 pool 是多路合并的，所以这个缝是「改写之后」的缝。
        in_d = sorted(r["pool"][0][1] for r in rows)
        ref_d = sorted(d for d, _, _, _ in ref_rows)
        med = lambda xs: xs[len(xs) // 2]
        whence = "改写后多路池" if RUN_REWRITE else "单路（地板）"
        emit(f"\n  最近一条的距离（越小越像「库里有」）· 取自：{whence}")
        emit(f"    库内 {len(in_d):2d} 题   最小 {in_d[0]:.2f} / 中位 {med(in_d):.2f} / 最大 {in_d[-1]:.2f}")
        emit(f"    库外 {len(ref_d):2d} 题   最小 {ref_d[0]:.2f} / 中位 {med(ref_d):.2f} / 最大 {ref_d[-1]:.2f}")
        if ref_d[0] > in_d[-1]:
            emit(f"    → **有缝**：库外最小 {ref_d[0]:.2f} > 库内最大 {in_d[-1]:.2f}")
            emit(f"      阈值可以取在 {in_d[-1]:.2f} ~ {ref_d[0]:.2f} 之间，有依据、能复盘")
        else:
            emit(f"    → **没有缝**：库外最小的 {ref_d[0]:.2f} 落在库内区间里"
                 f"（库内最大 {in_d[-1]:.2f}）")
            emit("      单靠距离卡不住 —— 那个库外问题在语义空间里离库很近。")
            emit("      硬卡只会误伤库内题（C 组口语题距离天然就大），得换机制。")

    # ---------- 端到端 ----------
    emit("\n" + "-" * 70)
    if CHECK_ANSWER and RUN_RERANK:
        ok = sum(1 for r in rows if r.get("e2e"))
        emit(f"  端到端正确率 {ok}/{len(rows)}   {ok / len(rows):.1%}   ← 用户唯一能感觉到的数")
        emit(f"  拒答正确率   {ok_ref}/{n_ref}   {ok_ref / n_ref:.1%}   ← 库外题单独算，**不进上面那个分母**")
    else:
        emit("  端到端正确率  ?   （要 CHECK_ANSWER = True 才量得到）")
    emit("  但它是最后一行，不是唯一一行 —— 上面每一行都是诊断书。")

    emit(f"\n耗时 {time.time() - t0:.1f} 秒")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n报告已存 {REPORT}（下次跑会覆盖）")
    if full:
        with open(ANSWERS, "w", encoding="utf-8") as f:
            f.write("\n".join(full))
        print(f"答案全文已存 {ANSWERS}")


if __name__ == "__main__":
    main()
