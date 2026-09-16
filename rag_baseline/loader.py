"""
① 载入：读文件 → 清洗 → 变成 Document。丢掉什么都会打出来（军规 ④：清洗必须吵闹）。
"""
import glob
import os

from langchain_core.documents import Document

from .cleaner import clean_md, is_corpus_noise_file
from .config import PATTERN, SRC_DIR


def load_docs():
    docs, skipped = [], []
    for path in sorted(glob.glob(os.path.join(SRC_DIR, PATTERN), recursive=True)):
        name = os.path.basename(path)
        if is_corpus_noise_file(name):
            skipped.append(f"{name}（非文档文件）")
            continue
        with open(path, encoding="utf-8") as f:
            text = clean_md(f.read().strip())
        if len(text) < 80:                      # 洗完好只剩几十个字：空页 / 纯索引页
            skipped.append(f"{name}（洗完不足 80 字）")
            continue
        # source 用相对路径（tutorial/cors.md）：文档里 index.md 有好多份，取 basename 会重名。
        docs.append(Document(page_content=text,
                             metadata={"source": os.path.relpath(path, SRC_DIR)}))
    if skipped:
        print(f"清洗丢掉 {len(skipped)} 篇：{'、'.join(skipped)}")
    return docs
