"""打印册的导出与导入识别。

导出：books/<册名>/ 目录（book.yaml + assets/）原样打包 + manifest。
册内 template 块只存引用不存内容，单独导出/导入不附带模板库；
缺失引用由打印册既有的 missing_template 失效引用机制报告（只报告、不改写），
后续导入模板库后自动复原。

导入：仅接受本软件导出的标准归档（manifest kind=books）；
缺 book.yaml 或配置损坏的册列入警告并跳过，不阻断其余册。
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from core.exceptions import BadRequestError
from modules.printbook.models import BookConfig
from modules.printbook.store import BOOK_FILE
from modules.transfer.archive import build_manifest, read_manifest, write_archive
from modules.transfer.schemas import BookAnalyzeItem, TransferWarning

# ===== 导出 =====


def build_books_archive(books_dir: Path, names: list[str]) -> bytes:
    """把指定册目录整体打包为 zip 字节流（调用方保证册名均存在）。"""
    files: list[tuple[str, bytes]] = []
    for name in names:
        book_dir = books_dir / name
        for path in sorted(book_dir.rglob("*")):
            if path.is_file() and not path.name.startswith(".tmp-"):
                rel = path.relative_to(book_dir).as_posix()
                files.append((f"books/{name}/{rel}", path.read_bytes()))
    files.append(("manifest.json", build_manifest("books", {"books": len(names)})))
    return write_archive(files)


# ===== 导入识别 =====


@dataclass
class ImportBookPlan:
    """一册待导入的打印册：暂存区内的来源目录 + 展示名。"""

    name: str
    title: str
    source_dir: Path


def analyze_books_archive(root: Path) -> tuple[list[ImportBookPlan], list[TransferWarning]]:
    """识别暂存区根目录下的 books/ 子树。非册归档（含模板库归档）抛 400。"""
    manifest = read_manifest(root)
    if manifest is None:
        raise BadRequestError("不是本软件导出的打印册归档（缺少 manifest.json）")
    kind = manifest.get("kind")
    if kind == "templates":
        raise BadRequestError("这是模板库归档，请到模板库页面导入")
    if kind != "books":
        raise BadRequestError("无法识别的归档类型")
    books_root = root / "books"
    if not books_root.is_dir():
        raise BadRequestError("打印册归档缺少 books/ 目录")
    plans: list[ImportBookPlan] = []
    warnings: list[TransferWarning] = []
    for entry in sorted(books_root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        rel = f"books/{entry.name}"
        book_file = entry / BOOK_FILE
        if not book_file.is_file():
            warnings.append(TransferWarning(path=rel, message="缺少 book.yaml，已跳过"))
            continue
        try:
            raw = yaml.safe_load(book_file.read_text(encoding="utf-8"))
            config = BookConfig.model_validate(raw or {})
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            warnings.append(TransferWarning(path=rel, message=f"book.yaml 损坏（{exc}），已跳过"))
            continue
        plans.append(
            ImportBookPlan(
                name=entry.name,
                title=config.cover.title or entry.name,
                source_dir=entry,
            )
        )
    return plans, warnings


def to_book_items(plans: list[ImportBookPlan]) -> list[BookAnalyzeItem]:
    """导入计划 → analyze 响应的只读预览项。"""
    return [BookAnalyzeItem(name=p.name, title=p.title) for p in plans]
