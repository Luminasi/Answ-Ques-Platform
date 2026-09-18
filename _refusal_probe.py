"""拒答实测（临时脚本，测完即删）。

需求分析报告把「无依据拒答」写成系统的**底线**（§2.2.3、§5），§3.3 也把它列进
基础功能第 4 条。但 eval/pipeline_last_run.txt 是 CHECK_ANSWER=False 跑的，
只出了 Hit@k / MRR —— **这条底线从来没被量过**。

这里只跑那 5 道拒答题，复用 eval/eval.py 的 judge_refusal 保证判定口径一致
（它看不懂就返回 None 报裁判故障，不猜）。生成提示词用 rag_service 的
build_generate_prompt —— 已逐字节验过与 rag_baseline.generator 的空历史模板相同。
"""

import importlib.util
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import rag_baseline
from langchain_openai import ChatOpenAI

from rag_service.prompts import build_generate_prompt

# eval/eval.py 不能被 `import eval` 拿到（会 shadow 内置函数），按路径加载
spec = importlib.util.spec_from_file_location("evalmod", os.path.join(ROOT, "eval", "eval.py"))
evalmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evalmod)
judge_refusal = evalmod.judge_refusal
REFUSALS = evalmod.REFUSALS

POOL, TOP_N = 20, 5


def main():
    t0 = time.time()
    print("载入语料与向量库……")
    db = rag_baseline.get_db(rag_baseline.split(rag_baseline.load_docs()))

    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        temperature=0.3,                                   # 与 baseline / rag_service 生成端一致
        default_headers={"x-opencode-session": "refusal-probe"},
    )

    print(f"库就绪，{time.time() - t0:.0f}s。开始跑 {len(REFUSALS)} 道库外问题\n")
    print("=" * 72)

    ok = faults = 0
    for i, q in enumerate(REFUSALS, 1):
        t = time.time()
        hits = rag_baseline.retrieve(db, q, k=POOL)
        hits = rag_baseline.rerank(q, hits, top_n=TOP_N)
        top = float(hits[0][1]) if hits else 0.0
        answer = llm.invoke(build_generate_prompt(q, hits, "")).content.strip()
        refused, why = judge_refusal(llm, q, answer)

        mark = "❓裁判故障" if refused is None else ("✅ 拒答" if refused else "❌ 答了")
        if refused is None:
            faults += 1
        elif refused:
            ok += 1
        print(f"\n{i}. {q}")
        print(f"   最高相关度 {top:.2f}｜{mark}｜{time.time() - t:.0f}s")
        print(f"   答案：{answer[:150].replace(chr(10), ' ')}…")
        if refused is False:
            print(f"   裁判：{str(why)[:100]}")

    n = len(REFUSALS)
    print("\n" + "=" * 72)
    print(f"  拒答正确率   {ok}/{n}   {ok / n:.1%}" + (f"   （另有 {faults} 题裁判故障，未计入）" if faults else ""))
    print(f"  耗时 {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
