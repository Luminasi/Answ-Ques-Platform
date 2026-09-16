"""
② 过滤 + ③ 切块。
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE


def filter_chunks(chunks):
    """丢掉空白块。

    块里还混着 mkdocs 语法（`/// tip`、`{ #anchor }`）和非文档文件的内容
    （_llm-test.md 排在全库第一块）—— 但那属于清洗，不是地板该干的事，原样留着。
    """
    return [c for c in chunks if c.page_content.strip()]


def split(docs):
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", "。", "！", "？", "；", " "],   # 先按段落，切不动再按句，最后才按字符
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,                              # 重叠防关键信息正好卡在边界上
    )
    return filter_chunks(splitter.split_documents(docs))
