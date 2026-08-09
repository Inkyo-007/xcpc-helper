"""books/ 目录的读写：册配置与图片资源的文件系统落盘。

设计原则与模板写操作一致：
- 册名经 common.validation.validate_name 校验，杜绝路径穿越与非法目录名；
- book.yaml 与资源写入均走 临时文件 + os.replace 原子替换；
- 删除为物理删除（前端确认弹窗已明确提示不可找回）；
- 损坏的 book.yaml 不阻断列表：list_books 逐册容错并携带 error。
"""

import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from common.validation import FORBIDDEN_CHARS, RESERVED_NAMES, validate_name
from core.exceptions import BadRequestError, ConflictError, NotFoundError
from modules.printbook.models import BookConfig, StoredBookInfo

BOOK_FILE = "book.yaml"
ASSETS_DIR = "assets"

# 允许的图片扩展名与单文件大小上限（5MB）
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
ASSET_MAX_BYTES = 5 * 1024 * 1024


def _book_dir(books_dir: Path, name: str) -> Path:
    return books_dir / validate_name(name, "打印册")


def _read_config(book_file: Path) -> BookConfig:
    raw = yaml.safe_load(book_file.read_text(encoding="utf-8"))
    return BookConfig.model_validate(raw or {})


def _corrupt_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        return f"配置校验失败: {loc} {first.get('msg', '')}".strip()
    return f"配置解析失败: {exc}"


def _atomic_write(path: Path, text: str) -> None:
    """原子写入文本文件：先写同目录临时文件，再 os.replace 覆盖目标。"""
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ===== 册扫描与读取 =====


def list_books(books_dir: Path) -> list[StoredBookInfo]:
    """扫描 books/ 下所有册目录（含 book.yaml 的子目录）；损坏配置逐册容错。"""
    if not books_dir.is_dir():
        return []
    infos: list[StoredBookInfo] = []
    for path in sorted(
        (p for p in books_dir.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name.lower(),
    ):
        book_file = path / BOOK_FILE
        if not book_file.is_file():
            continue
        config: BookConfig | None = None
        error: str | None = None
        try:
            config = _read_config(book_file)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            error = _corrupt_message(exc)
        infos.append(
            StoredBookInfo(
                name=path.name,
                config=config,
                error=error,
                updated=datetime.fromtimestamp(book_file.stat().st_mtime, tz=UTC).astimezone(),
            )
        )
    return infos


def load_book(books_dir: Path, name: str) -> BookConfig:
    """读取单册配置；不存在 404，损坏 400（错误信息可供前端展示）。"""
    book_file = _book_dir(books_dir, name) / BOOK_FILE
    if not book_file.is_file():
        raise NotFoundError(f"打印册不存在: {name}")
    try:
        return _read_config(book_file)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise BadRequestError(f"打印册「{name}」{_corrupt_message(exc)}") from exc


# ===== 册写操作 =====


def save_book(books_dir: Path, name: str, config: BookConfig) -> None:
    """原子写入 book.yaml。None 字段不写入，保持文件干净。"""
    book_dir = _book_dir(books_dir, name)
    if not book_dir.is_dir():
        raise NotFoundError(f"打印册不存在: {name}")
    text = yaml.safe_dump(
        config.model_dump(exclude_none=True), allow_unicode=True, sort_keys=False
    )
    _atomic_write(book_dir / BOOK_FILE, text)


def create_book(books_dir: Path, name: str, title: str | None) -> tuple[str, BookConfig]:
    """新建册目录（含空 assets/），返回规范化后的 (册名, 初始配置)。"""
    name = validate_name(name, "打印册")
    book_dir = books_dir / name
    if book_dir.exists():
        raise ConflictError(f"打印册已存在: {name}")
    (book_dir / ASSETS_DIR).mkdir(parents=True)
    config = BookConfig()
    config.cover.title = (title or "").strip() or name
    save_book(books_dir, name, config)
    return name, config


def rename_book(books_dir: Path, name: str, new_name: str) -> str:
    """册目录改名，返回新册名；与原名相同为无操作。"""
    src = _book_dir(books_dir, name)
    if not src.is_dir():
        raise NotFoundError(f"打印册不存在: {name}")
    new_name = validate_name(new_name, "打印册")
    if new_name == name:
        return name
    dst = books_dir / new_name
    if dst.exists():
        raise ConflictError(f"打印册已存在: {new_name}")
    os.rename(src, dst)
    return new_name


def delete_book(books_dir: Path, name: str) -> None:
    """物理删除整个册目录（含 assets）。"""
    book_dir = _book_dir(books_dir, name)
    if not book_dir.is_dir():
        raise NotFoundError(f"打印册不存在: {name}")
    shutil.rmtree(book_dir)


def place_book_tree(books_dir: Path, name: str, source_dir: Path) -> str:
    """把外部册目录整体就位到 books/（供册导入使用），返回规范化册名。

    原子性：先整体复制到 books/ 下的 .tmp-<uuid> 暂存目录，再一次 rename 到位；
    目标已存在抛 409（覆盖/改名策略由调用方先决策）。
    source_dir 必须含 book.yaml；缺 assets/ 时就位后补空目录。
    """
    name = validate_name(name, "打印册")
    if not (source_dir / BOOK_FILE).is_file():
        raise BadRequestError(f"册目录缺少 {BOOK_FILE}: {source_dir.name}")
    books_dir.mkdir(parents=True, exist_ok=True)
    target = books_dir / name
    if target.exists():
        raise ConflictError(f"打印册已存在: {name}")
    staging = Path(tempfile.mkdtemp(prefix=".tmp-", dir=books_dir))
    try:
        staged_book = staging / name
        shutil.copytree(source_dir, staged_book)
        (staged_book / ASSETS_DIR).mkdir(exist_ok=True)
        os.rename(staged_book, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return name


# ===== 图片资源 =====


def _sanitize_asset_stem(stem: str) -> str:
    cleaned = stem.strip().strip(".")
    cleaned = "".join("_" if c in FORBIDDEN_CHARS else c for c in cleaned)
    cleaned = cleaned.replace("..", "_")
    if not cleaned or cleaned.upper() in RESERVED_NAMES:
        cleaned = "image"
    return cleaned[:80]


def save_asset(books_dir: Path, name: str, filename: str, content: bytes) -> str:
    """保存上传图片到 assets/，返回相对册目录的 src。重名自动追加序号。"""
    book_dir = _book_dir(books_dir, name)
    if not book_dir.is_dir():
        raise NotFoundError(f"打印册不存在: {name}")
    if len(content) > ASSET_MAX_BYTES:
        raise BadRequestError("图片大小超过 5MB 限制")
    ext = Path(filename).suffix.lower()
    if ext not in ASSET_EXTENSIONS:
        allowed = ", ".join(sorted(ASSET_EXTENSIONS))
        raise BadRequestError(f"不支持的图片格式: {ext or '(无扩展名)'}（支持: {allowed}）")
    stem = _sanitize_asset_stem(Path(filename).stem)
    assets = book_dir / ASSETS_DIR
    assets.mkdir(exist_ok=True)
    target = f"{stem}{ext}"
    counter = 2
    while (assets / target).exists():
        target = f"{stem}-{counter}{ext}"
        counter += 1
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=assets)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp, assets / target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return f"{ASSETS_DIR}/{target}"


def asset_file(books_dir: Path, name: str, rel: str) -> Path:
    """解析 assets/ 内的资源相对路径，防路径穿越。"""
    book_dir = _book_dir(books_dir, name)
    if not book_dir.is_dir():
        raise NotFoundError(f"打印册不存在: {name}")
    assets = (book_dir / ASSETS_DIR).resolve()
    target = (assets / rel).resolve()
    if not target.is_relative_to(assets):
        raise BadRequestError("非法的资源路径")
    if not target.is_file():
        raise NotFoundError(f"资源不存在: {rel}")
    return target
