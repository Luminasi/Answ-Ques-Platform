"""文件校验与读取：纯标准库实现，不依赖 FastAPI，也不依赖 rag_baseline。

本模块是 docs_service 的领域层，只负责「给定文件名 → 返回全文」这件事本身，
不含任何 HTTP 语义（状态码、响应模型等归 app.py）。
"""

import re
from dataclasses import dataclass
from pathlib import Path

# 语料根目录：以本文件位置为锚，向上两级即项目根，与启动时的 cwd 无关。
# 注意：不能写成 Path("data/qacp_docs")，那样会跟着 cwd 漂移。
CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "qacp_docs"

# 严格白名单：只放行 q + 数字 + .md。字符集限定在 [a-z0-9.]，
# 数学上排除 / \ % .. 等一切路径穿越字符，与 URL 解码行为无关。
# 捕获组留给 list_doc_files 提取序号排序用。
SOURCE_RE = re.compile(r"^q(\d+)\.md$")


@dataclass
class Doc:
    """一篇语料文档。"""

    source: str   # 文件名（已通过白名单校验）
    content: str  # 全文原样，含 CRLF，不清洗、不切块
    title: str    # 首个 "# " 行的正文，没有则回退文件名


def is_valid_source(source: str) -> bool:
    """白名单校验。fullmatch 整串匹配，杜绝前缀/后缀绕过。"""
    return SOURCE_RE.fullmatch(source) is not None


def resolve_doc_path(source: str) -> Path:
    """白名单 → 拼路径 → 规范化后再验一次仍在语料目录内（纵深防御）。

    即使将来有人放宽了白名单正则，这里的断言仍能拦住越界。
    """
    if not is_valid_source(source):
        raise ValueError(f"非法文档名: {source}")
    path = (CORPUS_DIR / source).resolve()
    if not path.is_relative_to(CORPUS_DIR.resolve()):
        raise ValueError(f"路径越界: {source}")
    return path


def read_text(path: Path) -> str:
    """UTF-8 优先，失败则用 GB18030 兜底。

    用 read_bytes().decode() 而非 read_text()：文本模式会做 universal newlines
    转换，把语料的 CRLF 悄悄变成 LF，违背「content 原样返回」的要求。
    """
    data = path.read_bytes()
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"UTF-8 与 GB18030 均无法解码: {path.name}")


def extract_title(text: str, filename: str) -> str:
    """取首个 "# " 开头的行作为标题（去掉前缀）；没有则用文件名。"""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return filename


def read_doc(source: str) -> Doc | None:
    """读取单篇文档；文件不存在时返回 None（由 app 层转成 404）。"""
    path = resolve_doc_path(source)
    try:
        text = read_text(path)
    except FileNotFoundError:
        # 校验与读取之间文件被删的竞态，按「不存在」处理更友好
        return None
    return Doc(source=source, content=text, title=extract_title(text, source))


def list_doc_files() -> list[str]:
    """列出语料目录下的文档名，按文件名数字自然排序（q001 → q534）。

    非递归 iterdir + 复用同一个白名单正则，保证「列出来的名字一定能被读到」。
    目录缺失时让异常冒泡（部署错误应当吵闹，不静默返回空列表）。
    """
    names = [
        p.name
        for p in CORPUS_DIR.iterdir()
        if p.is_file() and SOURCE_RE.fullmatch(p.name)
    ]
    # 按数字排序而非字典序：将来出现 q1000.md 时字典序会把它排到 q999.md 前面
    return sorted(names, key=lambda n: int(SOURCE_RE.match(n).group(1)))
