"""打印册导出/导入的端到端测试（临时目录 + TestClient）。"""

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from tests.transfer.conftest import make_zip


def _upload_books(client: TestClient, data: bytes) -> dict:
    resp = client.post(
        "/api/transfer/import/books/analyze",
        files={"file": ("pack.zip", data, "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _apply_books(client: TestClient, staging_id: str, strategy: str = "skip") -> dict:
    resp = client.post(
        "/api/transfer/import/books/apply",
        json={"staging_id": staging_id, "strategy": strategy},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ===== 导出 =====


def test_export_all_books(client: TestClient, books_dir: Path) -> None:
    resp = client.get("/api/transfer/export/books")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "books/册A/book.yaml" in names
        assert "books/册A/assets/logo.png" in names
        assert "books/册B/book.yaml" in names
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["kind"] == "books"
        assert manifest["counts"]["books"] == 2


def test_export_single_book(client: TestClient, books_dir: Path) -> None:
    resp = client.get("/api/transfer/export/books/册A")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = set(zf.namelist())
        assert "books/册A/book.yaml" in names
        assert "books/册B/book.yaml" not in names


def test_export_missing_book_404(client: TestClient, books_dir: Path) -> None:
    resp = client.get("/api/transfer/export/books/不存在")
    assert resp.status_code == 404


# ===== 导入 =====


def test_import_round_trip_with_assets(client: TestClient, books_dir: Path) -> None:
    """导出 → 删除 → 导入恢复，assets 一并还原。"""
    data = client.get("/api/transfer/export/books/册A").content
    import shutil

    shutil.rmtree(books_dir / "册A")

    result = _upload_books(client, data)
    assert [b["name"] for b in result["books"]] == ["册A"]
    assert result["books"][0]["title"] == "示例打印册"
    assert result["conflicts"] == []
    report = _apply_books(client, result["staging_id"])
    assert report["created"] == ["册A"]
    assert (books_dir / "册A" / "book.yaml").is_file()
    assert (books_dir / "册A" / "assets" / "logo.png").is_file()


def test_import_rejects_templates_archive(client: TestClient) -> None:
    manifest = json.dumps({"app": "xcpc-helper", "kind": "templates"})
    data = make_zip({"manifest.json": manifest, "content/math/sieve/sieve/code.cpp": "x"})
    resp = client.post(
        "/api/transfer/import/books/analyze",
        files={"file": ("pack.zip", data, "application/zip")},
    )
    assert resp.status_code == 400
    assert "模板库归档" in resp.json()["error"]["message"]


def test_import_rejects_archive_without_manifest(client: TestClient) -> None:
    data = make_zip({"books/册C/book.yaml": "cover: {}"})
    resp = client.post(
        "/api/transfer/import/books/analyze",
        files={"file": ("pack.zip", data, "application/zip")},
    )
    assert resp.status_code == 400
    assert "manifest" in resp.json()["error"]["message"]


def test_import_skips_corrupt_book(client: TestClient) -> None:
    """损坏 book.yaml 与缺 book.yaml 的册进警告，其余正常导入。"""
    manifest = json.dumps({"app": "xcpc-helper", "kind": "books"})
    data = make_zip(
        {
            "manifest.json": manifest,
            "books/好册/book.yaml": "cover:\n  title: 好册\n",
            "books/坏册/book.yaml": "blocks: [unclosed",
            "books/空册/README.md": "没有 book.yaml",
        }
    )
    result = _upload_books(client, data)
    assert [b["name"] for b in result["books"]] == ["好册"]
    warned = {w["path"] for w in result["warnings"]}
    assert warned == {"books/坏册", "books/空册"}
    report = _apply_books(client, result["staging_id"])
    assert report["created"] == ["好册"]


def test_import_conflict_strategies(client: TestClient, books_dir: Path) -> None:
    manifest = json.dumps({"app": "xcpc-helper", "kind": "books"})
    data = make_zip(
        {"manifest.json": manifest, "books/册B/book.yaml": "cover:\n  title: 新的册B\n"}
    )

    # skip：保留现有
    result = _upload_books(client, data)
    assert result["conflicts"] == ["册B"]
    report = _apply_books(client, result["staging_id"], "skip")
    assert report["skipped"] == ["册B"]
    assert "校内赛版" in (books_dir / "册B" / "book.yaml").read_text(encoding="utf-8")

    # rename：自动改名，两边都保留
    result = _upload_books(client, data)
    report = _apply_books(client, result["staging_id"], "rename")
    assert report["renamed"] == [{"source": "册B", "target": "册B-2"}]
    assert (books_dir / "册B-2" / "book.yaml").is_file()

    # overwrite：整体替换
    result = _upload_books(client, data)
    report = _apply_books(client, result["staging_id"], "overwrite")
    assert report["overwritten"] == ["册B"]
    assert "新的册B" in (books_dir / "册B" / "book.yaml").read_text(encoding="utf-8")
