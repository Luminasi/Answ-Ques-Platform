"""
④ 入盘：库是语料的函数 —— 换了语料、改了切分参数，旧库就是错的（查出来驴唇不对马嘴）。
但每次运行都重建（1052 块 × jina v3，本机 CPU 约 8~10 分钟）太磨人 ——
折中：把「语料指纹」写进库目录，开库前对一眼，对得上复用、对不上重建。
指纹认不出的改动（换嵌入模型、改 filter_chunks 逻辑）要手动重建：REBUILD = True。
"""
import os
import shutil

from langchain_chroma import Chroma

from .cleaner import CLEAN_RULES, CLEAN_SKIP
from .config import (CHUNK_OVERLAP, CHUNK_SIZE, DB_DIR, EMBED_MODEL,
                     PATTERN, REBUILD, SIG_PATH, SRC_DIR)
from .embeddings import MyEmbeddings


def corpus_signature() -> str:
    """库里这份内容由什么决定。任何一项变了，旧库就是错的，必须重建。

    清洗规则和嵌入模型也在这里面 —— 它们同样是「库里是什么」的决定因素。
    改了 CLEAN_SKIP（比如第三批打开 markdown 链接）→ 指纹变 → 自动重建。
    **不用再靠人记得去改 REBUILD：靠人记得的事早晚会忘，而忘了不报错。**
    """
    active = ",".join(label for label, _, _ in CLEAN_RULES if label not in CLEAN_SKIP)
    return (f"{SRC_DIR}|{PATTERN}|chunk={CHUNK_SIZE}/{CHUNK_OVERLAP}"
            f"|emb={EMBED_MODEL}|clean={active}")


def read_signature() -> str:
    if not os.path.exists(SIG_PATH):
        return ""
    with open(SIG_PATH, encoding="utf-8") as f:
        return f.read().strip()


def build(chunks):
    """重建整库，并写下语料指纹。

    整库重建永远不会像增量写入那样攒出重复副本；代价是全部块重新嵌入，
    所以用指纹把「复用」和「重建」分开（见上）。
    生产里「砌墙」是离线一次性动作，服务启动只「开门」（Chroma(persist_directory=...) 一行）。
    """
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)
    db = Chroma.from_documents(chunks, embedding=MyEmbeddings(), persist_directory=DB_DIR)
    with open(SIG_PATH, "w", encoding="utf-8") as f:
        f.write(corpus_signature())
    return db


def get_db(chunks):
    """先对语料指纹，再开门 —— 顺序不能反：

    build() 要 rmtree 整个库目录，若库已被打开（sqlite 被本进程占用），
    Windows 会报 WinError 32「另一个程序正在使用此文件」。
    build 返回的 db 本身就是开着的，直接拿来用，不用再开一次。
    """
    if REBUILD or read_signature() != corpus_signature():
        db = build(chunks)
        print(f"已建库并写入 {DB_DIR}\n")
    else:
        db = Chroma(persist_directory=DB_DIR, embedding_function=MyEmbeddings())
        print(f"复用现成的库 {DB_DIR}（强制重建：REBUILD=True 或删掉库目录）\n")
    return db
