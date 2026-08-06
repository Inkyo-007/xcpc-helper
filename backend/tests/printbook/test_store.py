"""store 层测试：册配置的读写回环、名称校验、损坏容错与资源管理。"""

from pathlib import Path

import pytest

from core.exceptions import BadRequestError, ConflictError, NotFoundError
from modules.printbook import store
from modules.printbook.models import (
    BookConfig,
    HeadingBlockNode,
    ImageBlockNode,
    MarkdownBlockNode,
    PageBreakBlockNode,
    TemplateBlockNode,
)


def _sample_config() -> BookConfig:
    config = BookConfig()
    config.cover.title = "测试册"
    config.cover.author = "Ink"
    config.blocks = [
        HeadingBlockNode(id="h1", title="数学", heading_level=1),
        TemplateBlockNode(
            id="t1", template="ds/dsu", version="weighted", heading_level=2
        ),
        MarkdownBlockNode(id="m1", title=None, content="自由文字"),
        ImageBlockNode(id="i1", src="assets/pic.png", caption=None),
        PageBreakBlockNode(id="p1"),
    ]
    return config


def test_create_book_creates_dir_and_config(books_dir: Path) -> None:
    name, config = store.create_book(books_dir, "  区域赛版  ", None)
    assert name == "区域赛版"
    assert config.cover.title == "区域赛版"  # 未填标题时回填册名
    assert (books_dir / "区域赛版" / "book.yaml").is_file()
    assert (books_dir / "区域赛版" / "assets").is_dir()


def test_create_book_duplicate_conflict(books_dir: Path) -> None:
    store.create_book(books_dir, "A", None)
    with pytest.raises(ConflictError):
        store.create_book(books_dir, "A", None)


def test_create_book_invalid_name(books_dir: Path) -> None:
    with pytest.raises(BadRequestError):
        store.create_book(books_dir, "a/b", None)


def test_save_and_load_round_trip(books_dir: Path) -> None:
    name, _ = store.create_book(books_dir, "A", None)
    store.save_book(books_dir, name, _sample_config())
    config = store.load_book(books_dir, name)
    assert config.cover.title == "测试册"
    assert config.cover.author == "Ink"
    assert len(config.blocks) == 5
    block = config.blocks[0]
    assert isinstance(block, HeadingBlockNode)
    assert block.heading_level == 1
    template_block = config.blocks[1]
    assert isinstance(template_block, TemplateBlockNode)
    assert template_block.version == "weighted"
    # None 字段不写入 yaml（缺省即默认）；options.include_body 是固定项，
    # 故块级 include_body 不出现时应只剩 options 里这一处
    text = (books_dir / name / "book.yaml").read_text(encoding="utf-8")
    assert text.count("include_body") == 1
    assert "caption" not in text
    assert "resolved" not in text


def test_load_book_missing(books_dir: Path) -> None:
    with pytest.raises(NotFoundError):
        store.load_book(books_dir, "不存在")


def test_corrupt_yaml_listed_with_error(books_dir: Path) -> None:
    name, _ = store.create_book(books_dir, "A", None)
    (books_dir / name / "book.yaml").write_text(
        "blocks: [{type: nope]", encoding="utf-8"
    )
    infos = store.list_books(books_dir)
    assert len(infos) == 1
    assert infos[0].config is None
    assert infos[0].error is not None
    with pytest.raises(BadRequestError):
        store.load_book(books_dir, name)


def test_list_books_skips_non_book_dirs(books_dir: Path) -> None:
    store.create_book(books_dir, "A", None)
    (books_dir / "随手放的目录").mkdir()
    (books_dir / ".hidden").mkdir()
    assert [info.name for info in store.list_books(books_dir)] == ["A"]


def test_rename_book(books_dir: Path) -> None:
    store.create_book(books_dir, "A", None)
    assert store.rename_book(books_dir, "A", "B") == "B"
    assert (books_dir / "B" / "book.yaml").is_file()
    assert not (books_dir / "A").exists()
    with pytest.raises(NotFoundError):
        store.rename_book(books_dir, "A", "C")
    store.create_book(books_dir, "D", None)
    with pytest.raises(ConflictError):
        store.rename_book(books_dir, "B", "D")


def test_delete_book(books_dir: Path) -> None:
    store.create_book(books_dir, "A", None)
    store.delete_book(books_dir, "A")
    assert not (books_dir / "A").exists()
    with pytest.raises(NotFoundError):
        store.delete_book(books_dir, "A")


def test_save_asset_and_collision_suffix(books_dir: Path) -> None:
    name, _ = store.create_book(books_dir, "A", None)
    first = store.save_asset(books_dir, name, "pic.png", b"\x89PNG")
    second = store.save_asset(books_dir, name, "pic.png", b"\x89PNG")
    assert first == "assets/pic.png"
    assert second == "assets/pic-2.png"


def test_save_asset_rejects_bad_ext_and_oversize(books_dir: Path) -> None:
    name, _ = store.create_book(books_dir, "A", None)
    with pytest.raises(BadRequestError):
        store.save_asset(books_dir, name, "note.txt", b"hello")
    with pytest.raises(BadRequestError):
        store.save_asset(books_dir, name, "big.png", b"0" * (store.ASSET_MAX_BYTES + 1))


def test_asset_file_guards_traversal(books_dir: Path) -> None:
    name, _ = store.create_book(books_dir, "A", None)
    src = store.save_asset(books_dir, name, "pic.png", b"\x89PNG")
    path = store.asset_file(books_dir, name, src.removeprefix("assets/"))
    assert path.name == "pic.png"
    with pytest.raises(BadRequestError):
        store.asset_file(books_dir, name, "../book.yaml")
    with pytest.raises(NotFoundError):
        store.asset_file(books_dir, name, "missing.png")
