"""会话记忆的存储层：SQLite 建表、落库、查询。纯标准库 sqlite3，不含任何 HTTP 语义。

表结构对齐《课程知识点答疑台系统设计文档》§4.2 的 conversations / messages / citations
三张表；另加一张 chunks 影子表 —— 设计文档里 citations.chunk_id 指向 chunks 表，但本项目的
语料块存在 Chroma 里、SQLite 侧没有这张表，所以启动时同步一份进来让外键真正成立（见 sync_chunks）。
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

from rag_service.config import DB_PATH, HISTORY_MAX_CHARS, HISTORY_MAX_MESSAGES

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT    NOT NULL DEFAULT '新会话',
  created_at TEXT    NOT NULL,
  updated_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT    NOT NULL CHECK (role IN ('user','assistant')),
  content         TEXT    NOT NULL,
  created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);

-- Chroma 里的语料块在 SQLite 侧的映射。没有它，citations.chunk_id 那个外键无处可指。
CREATE TABLE IF NOT EXISTS chunks (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  source    TEXT    NOT NULL,
  content   TEXT    NOT NULL,
  vector_id TEXT    NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_chunks_src_content ON chunks(source, content);

CREATE TABLE IF NOT EXISTS citations (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id      INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  chunk_id        INTEGER NOT NULL REFERENCES chunks(id),
  relevance_score REAL    NOT NULL,
  snippet         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_citations_message ON citations(message_id);
"""


def _now():
    """统一时间戳格式 'YYYY-MM-DD HH:MM:SS'。

    由 Python 侧显式写，不用 SQLite 的 CURRENT_TIMESTAMP —— 格式可控，
    也不会因为换了个 SQLite 版本就悄悄变样。
    """
    return datetime.now().isoformat(sep=" ", timespec="seconds")


@contextmanager
def conn():
    """一次操作一个连接。

    为什么不共享一个长连接：sqlite3 的连接默认 `check_same_thread=True`，跨线程用会直接抛错，
    而本服务的同步路由跑在 FastAPI 的线程池里、SSE 生成器跑在事件循环上 —— 共享连接等于两边打架。
    每操作新建连接的开销极小（打开一个本地文件），换来的线程安全是白捡的。

    PRAGMA 是**每连接**生效的，所以这两行必须写在建连接这里，不能只写在 init_db：
      · foreign_keys  —— SQLite 默认**关**，不开外键约束就是摆设
      · busy_timeout  —— 并发写时等锁而不是立刻抛 database is locked
    """
    c = sqlite3.connect(DB_PATH, timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=5000")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init_db():
    """建库建表。幂等：每次启动都跑一遍，已存在就跳过。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        # WAL 让读（历史查询）不阻塞写（落库），多个并发写只阻塞在写事务本身。
        # 这个设置是**持久化在库文件里**的，执行一次就够，重复执行无害。
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(_SCHEMA)


# ---------- 会话 ----------

def create_conversation(name=None):
    """新建一个空会话，返回它的完整信息。

    新会话天然不继承任何历史（新 id，messages 里没有它的行）——
    「新建后上下文清零」这个需求不需要额外代码，是表结构给的。
    """
    stamp = _now()
    with conn() as c:
        cur = c.execute(
            "INSERT INTO conversations(name, created_at, updated_at) VALUES(?,?,?)",
            (name, stamp, stamp),
        )
        new_id = cur.lastrowid
    return {"id": new_id, "name": name, "created_at": stamp, "updated_at": stamp}


def conversation_exists(conversation_id):
    with conn() as c:
        row = c.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone()
    return row is not None


def list_conversations():
    """全部会话，按最近更新倒序 —— 供前端侧边栏「最近聊过的在前」。

    updated_at 相同时按 id 倒序兜底（新建的在前），保证顺序稳定不跳动。
    MVP 不分页：会话数到不了需要分页的量级，列表接口保持简单。
    """
    with conn() as c:
        rows = c.execute(
            "SELECT id, name, created_at, updated_at FROM conversations"
            " ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def touch_conversation(conversation_id):
    """把会话的 updated_at 推到当前时刻，供前端按「最近更新」排序会话列表。"""
    with conn() as c:
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (_now(), conversation_id))


# ---------- 消息与引用 ----------

def insert_message(conversation_id, role, content):
    """写一条消息，返回 message_id。"""
    with conn() as c:
        cur = c.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES(?,?,?,?)",
            (conversation_id, role, content, _now()),
        )
        return cur.lastrowid


def save_answer(conversation_id, content, citations=()):
    """把助手回答和它的引用**写在一个事务里**，返回 assistant 的 message_id。

    一个事务是必须的，不能拆成两次写：中间崩了会留下「有回答、没来源」的半截记录，
    历史查询里那条回答就永远缺 citations，而且**不报错**。

    citations 是可迭代的 (chunk_id, score, snippet)；chunk_id 为 None 的行会被丢掉 ——
    影子表里找不到对应块时（比如向量库重建过），宁缺一条引用，不写脏外键。
    """
    stamp = _now()
    with conn() as c:
        cur = c.execute(
            "INSERT INTO messages(conversation_id, role, content, created_at) VALUES(?,?,?,?)",
            (conversation_id, "assistant", content, stamp),
        )
        message_id = cur.lastrowid

        rows = [
            (message_id, chunk_id, float(score), snippet)
            for chunk_id, score, snippet in citations
            if chunk_id is not None
        ]
        if rows:
            c.executemany(
                "INSERT INTO citations(message_id, chunk_id, relevance_score, snippet)"
                " VALUES(?,?,?,?)",
                rows,
            )
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (stamp, conversation_id))
    return message_id


def get_history(conversation_id, limit=HISTORY_MAX_MESSAGES, max_chars=HISTORY_MAX_CHARS):
    """取最近 limit 条消息（按时间正序），再从**最旧**的一条开始丢到总字符数 ≤ max_chars。

    丢最旧而不是最新：改写和生成要的是紧邻当前问题的上下文，
    很久以前的轮次对指代消解的贡献，远小于它占掉的 token。

    返回 [{"role": ..., "content": ...}, ...]，直接喂给 prompts.build_history_text。
    """
    with conn() as c:
        rows = c.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()

    msgs = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    total = sum(len(m["content"]) for m in msgs)
    while msgs and total > max_chars:
        total -= len(msgs.pop(0)["content"])
    return msgs


def get_messages_with_citations(conversation_id):
    """取一个会话的全部消息，每条带上它的引用来源。

    rank 不落库：它只是「展示时的第几名」，存下来就得跟着 score 一起维护；
    查询时按 relevance_score DESC 现算一次更省心，结果与契约要求的「rank 升序」等价。
    """
    with conn() as c:
        msgs = c.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id=? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        if not msgs:
            return []

        ids = [m["id"] for m in msgs]
        placeholders = ",".join("?" * len(ids))
        rows = c.execute(
            "SELECT ct.message_id, ct.relevance_score, ct.snippet, ch.source,"
            " (SELECT COUNT(*) FROM chunks c2 WHERE c2.source = ch.source AND c2.id <= ch.id) AS chunk_index"
            " FROM citations ct JOIN chunks ch ON ch.id = ct.chunk_id"
            f" WHERE ct.message_id IN ({placeholders})"
            " ORDER BY ct.relevance_score DESC",
            ids,
        ).fetchall()

    by_message = {}
    for r in rows:
        by_message.setdefault(r["message_id"], []).append(r)

    out = []
    for m in msgs:
        citations = by_message.get(m["id"], [])
        out.append({
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "created_at": m["created_at"],
            "citations": [
                {
                    "rank": rank,
                    "source": r["source"],
                    "score": round(float(r["relevance_score"]), 2),
                    "snippet": r["snippet"],
                    "chunk_index": r["chunk_index"],
                }
                for rank, r in enumerate(citations, 1)
            ],
        })
    return out


# ---------- 语料块影子表 ----------

def sync_chunks(rows):
    """把向量库里的块同步进影子表。幂等：vector_id 唯一，已存在的行忽略。

    为什么要有这张表：设计文档 §4.2 的 citations.chunk_id 是指向 chunks 的外键，
    而本项目的块只存在 Chroma（SQLite 侧没有表）。同步一份影子行，外键才成立，
    历史查询也才有「chunk_id → source 文件名」的 JOIN 路径。

    库重建后旧行保留无害 —— citations 是历史快照，指向的旧块仍能查到当时的文件名。

    rows 是可迭代的 (vector_id, source, content)。
    """
    with conn() as c:
        c.executemany(
            "INSERT OR IGNORE INTO chunks(vector_id, source, content) VALUES(?,?,?)",
            list(rows),
        )


def get_chunk_id(source, content):
    """按（文件名, 块原文）定位影子表里的 chunk_id；找不到返回 None。

    为什么不用向量库的 vector_id：rag_baseline 的 Document.metadata 只有 source 一个字段
    （loader.py 确认），检索结果里拿不到 vector_id，只能靠「文件名 + 块原文」定位。
    """
    with conn() as c:
        row = c.execute(
            "SELECT id FROM chunks WHERE source=? AND content=? LIMIT 1", (source, content)
        ).fetchone()
    return row["id"] if row else None


def list_chunks(source):
    """按建库/同步顺序返回某个文档的全部块。"""
    with conn() as c:
        rows = c.execute(
            "SELECT id, content FROM chunks WHERE source=? ORDER BY id",
            (source,),
        ).fetchall()
    return [{"id": r["id"], "content": r["content"]} for r in rows]


def get_chunk_index(source, content):
    """按（文件名, 块原文）返回 1-based 块序号；找不到返回 None。"""
    with conn() as c:
        row = c.execute(
            "SELECT (SELECT COUNT(*) FROM chunks c2"
            " WHERE c2.source = c.source AND c2.id <= c.id)"
            " FROM chunks c WHERE c.source=? AND c.content=? LIMIT 1",
            (source, content),
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else None

