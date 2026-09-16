"""
把 QACP 中文 Python 问答集（NTAIX/Chinese-Python-QA-Dataset）转成检索语料。

数据集是**两个文件、靠 id 关联**：
  QACP_Q.json  534 条问题，UTF-8，带知识点/问题类型/答案类型
  QACP_A.csv   534 条答案，**GB18030** —— 不是 UTF-8，按 UTF-8 读会在第 20 字节崩掉

产物：data/qacp_docs/q001.md … q534.md，一篇问答一个文件。

**为什么一篇一个文件**：loader 把 source 设成相对路径，一篇一文件检索结果才能指回
「具体是哪道题」。按知识点合并成 10 个大文件文件是少了，但一条命中说不清是哪道题
贡献的，引用也就没了依据。（代价：534 个小文件，切块后约 1.4k 块。）

用法（项目根目录，两种方式都行）：
    python tools/build_qacp_corpus.py              # 用已有的 data/_qacp_raw/
    python tools/build_qacp_corpus.py --download   # 原文件缺了，先下再转
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")   # Windows 控制台默认 GBK，中文输出会乱码

# 路径按脚本位置反推，不按当前工作目录 —— 这样在哪个目录敲命令都一样
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "_qacp_raw")
OUT_DIR = os.path.join(ROOT, "data", "qacp_docs")

BASE_URL = "https://raw.githubusercontent.com/NTAIX/Chinese-Python-QA-Dataset/master"
FILES = ["QACP_Q.json", "QACP_A.csv", "readme.md"]

UA = "rag-baseline-corpus-builder"
SEP = " ｜ "   # 元数据行里的分隔符；用全角竖线，避免和答案正文里的半角 | 混淆


def _fetch(url, tries=4):
    """下载一个文件，失败就退避重试。

    raw.githubusercontent.com 在国内**随机断连**（实测：同一个 UA 连续三次，
    前两次 200、第三次 RemoteDisconnected），不是 UA 问题也不是频率问题 ——
    所以重试是必需品，不是保险。"""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"    {type(e).__name__}，{2 ** i}s 后重试（{i + 1}/{tries - 1}）")
            time.sleep(2 ** i)


def download():
    """原文件缺了或要重下时走这里。"""
    os.makedirs(RAW_DIR, exist_ok=True)
    for name in FILES:
        data = _fetch(f"{BASE_URL}/{name}")
        dst = os.path.join(RAW_DIR, name)
        # 先写 .tmp 再原子替换。**不能**直接 open(dst, "wb")：下到一半断线会把
        # 已经下好的那份截断成半截，而文件看着还在，很难发现。
        tmp = dst + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dst)
        print(f"  下载 {name} → {os.path.relpath(dst, ROOT)}（{len(data)} 字节）")


def load_qa():
    """读两个文件并按 id 合并。合不上的**必须报错**，不能默默丢 ——
    丢了一条，检索时表现为「这个问题答不上来」，而不是「数据缺了」，很难查。"""
    q_path = os.path.join(RAW_DIR, "QACP_Q.json")
    a_path = os.path.join(RAW_DIR, "QACP_A.csv")
    for p in (q_path, a_path):
        if not os.path.exists(p):
            sys.exit(f"缺原文件：{os.path.relpath(p, ROOT)}\n先跑 python tools/build_qacp_corpus.py --download")

    questions = json.load(open(q_path, encoding="utf-8"))
    # GB18030：数据集作者用的是这个。newline="" 交给 csv 模块自己处理引号内的换行
    answers = {r["id"].strip(): r["Answer"]
               for r in csv.DictReader(open(a_path, encoding="gb18030", newline=""))}

    qa, no_answer, seen = [], [], set()
    for q in questions:
        qid = str(q["id"]).strip()
        if qid in seen:
            sys.exit(f"id 重复：{qid}")
        seen.add(qid)
        if qid not in answers:
            no_answer.append(qid)
            continue
        qa.append({
            "id": qid,
            # 原始数据里有带前后空格的（如 " Exception Handling"），统一 strip
            "kp":    str(q["Knowledge Point"]).strip(),
            "qtype": str(q["Question Type"]).strip(),
            "atype": str(q["Answer Type"]).strip(),
            "q":     str(q["Question"]).strip(),
            "a":     answers[qid].strip(),
        })

    extra = set(answers) - seen
    if no_answer or extra:
        sys.exit(f"Q/A 对不上 —— 有问题没答案：{no_answer[:10]}；有答案没问题：{sorted(extra)[:10]}")
    return qa


def render(item) -> str:
    """一道题渲染成一篇文章。

    问题做成 H1：既是切块器的天然首块，也是引用时给模型看的标题。
    元数据单独成段（\n\n 隔开）—— 它是检索时的**上下文**，不该和答案正文黏在一起，
    否则切块时会被算进正文字数。
    """
    meta = SEP.join([f"**知识点**：{item['kp']}",
                     f"**问题类型**：{item['qtype']}",
                     f"**答案类型**：{item['atype']}"])
    return f"# {item['q']}\n\n{meta}\n\n{item['a']}\n"


def main():
    ap = argparse.ArgumentParser(description="QACP 问答集 → RAG 检索语料")
    ap.add_argument("--download", action="store_true", help="先重新下载原文件再转换")
    args = ap.parse_args()

    if args.download:
        print("下载原文件：")
        download()

    qa = load_qa()
    # 全量重写：删掉旧的，避免上一版改了命名规则后新旧文件混在一起（库是按目录建的）
    if os.path.isdir(OUT_DIR):
        old = [f for f in os.listdir(OUT_DIR) if f.endswith(".md")]
        for f in old:
            os.remove(os.path.join(OUT_DIR, f))
        print(f"清掉旧的 {len(old)} 篇")
    os.makedirs(OUT_DIR, exist_ok=True)

    for item in qa:
        with open(os.path.join(OUT_DIR, f"q{int(item['id']):03d}.md"), "w", encoding="utf-8") as f:
            f.write(render(item))

    chars = sum(len(render(i)) for i in qa)
    kps = {i["kp"] for i in qa}
    print(f"\n写好 {len(qa)} 篇 → {os.path.relpath(OUT_DIR, ROOT)}")
    print(f"共 {chars} 字，覆盖 {len(kps)} 个知识点，平均每篇 {chars // len(qa)} 字")
    print("接下来：把 rag_baseline/config.py 的 SRC_DIR 指到 data/qacp_docs 再跑 run_baseline.py")


if __name__ == "__main__":
    main()
