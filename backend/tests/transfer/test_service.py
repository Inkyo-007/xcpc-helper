"""transfer 服务与路由的端到端测试（临时目录 + TestClient）。"""

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from modules.template.scanner import scan_content
from tests.transfer.conftest import make_zip


def _upload(client: TestClient, data: bytes, url: str) -> dict:
    resp = client.post(url, files={"file": ("pack.zip", data, "application/zip")})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _apply(client: TestClient, staging_id: str, strategy: str = "skip") -> dict:
    resp = client.post(
        "/api/transfer/import/templates/apply",
        json={"staging_id": staging_id, "strategy": strategy},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _scan_ids(content_dir: Path) -> set[str]:
    return {t.id for t in scan_content(content_dir).templates}


# ===== 导出 =====


def test_export_templates_endpoint(client: TestClient) -> None:
    resp = client.get("/api/transfer/export/templates")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "attachment" in resp.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "content/math/sieve/sieve/euler_sieve.cpp" in names


# ===== 导入：外来平铺结构 =====


def test_foreign_import_full_flow(client: TestClient, content_dir: Path) -> None:
    data = make_zip(
        {
            "图论/dijkstra.cpp": "// dij",
            "图论/最短路/floyd.cpp": "// floyd",
            "图论/note.txt": "note",
        }
    )
    result = _upload(client, data, "/api/transfer/import/templates/analyze")
    assert result["kind"] == "foreign"
    assert result["template_count"] == 1
    assert result["category_count"] == 1
    assert result["conflicts"] == []
    assert len(result["warnings"]) == 2

    report = _apply(client, result["staging_id"])
    assert report["created"] == ["图论/dijkstra"]
    assert report["failed"] == []
    # 落盘为三层标准结构
    assert (content_dir / "图论" / "dijkstra" / "dijkstra" / "dijkstra.cpp").is_file()
    assert (content_dir / "图论" / "dijkstra" / "dijkstra" / "README.md").is_file()
    assert "图论/dijkstra" in _scan_ids(content_dir)
    # 暂存区已清理
    staging = content_dir.parent / "data" / ".staging"
    assert not list(staging.glob("transfer-*"))


def test_analyze_rejects_empty_archive(client: TestClient) -> None:
    data = make_zip({"说明.txt": "没有任何代码"})
    resp = client.post(
        "/api/transfer/import/templates/analyze",
        files={"file": ("pack.zip", data, "application/zip")},
    )
    assert resp.status_code == 400
    assert "没有可识别的模板" in resp.json()["error"]["message"]


def test_analyze_rejects_books_archive(client: TestClient) -> None:
    manifest = json.dumps({"app": "xcpc-helper", "kind": "books"})
    data = make_zip({"manifest.json": manifest, "books/册A/book.yaml": "cover: {}"})
    resp = client.post(
        "/api/transfer/import/templates/analyze",
        files={"file": ("pack.zip", data, "application/zip")},
    )
    assert resp.status_code == 400
    assert "打印册归档" in resp.json()["error"]["message"]


def test_apply_rejects_invalid_staging(client: TestClient) -> None:
    resp = client.post(
        "/api/transfer/import/templates/apply",
        json={"staging_id": "0" * 32, "strategy": "skip"},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/api/transfer/import/templates/apply",
        json={"staging_id": "../../etc", "strategy": "skip"},
    )
    assert resp.status_code == 400


# ===== 导入：冲突策略 =====


def _conflict_zip() -> bytes:
    return make_zip({"math/sieve.cpp": "// 新的 sieve"})


def test_conflict_skip(client: TestClient, content_dir: Path) -> None:
    result = _upload(client, _conflict_zip(), "/api/transfer/import/templates/analyze")
    assert result["conflicts"] == ["math/sieve"]
    report = _apply(client, result["staging_id"], "skip")
    assert report["skipped"] == ["math/sieve"]
    assert report["created"] == []
    # 原文件未被改动
    assert (content_dir / "math" / "sieve" / "euler_sieve.cpp").is_file()


def test_conflict_rename(client: TestClient, content_dir: Path) -> None:
    result = _upload(client, _conflict_zip(), "/api/transfer/import/templates/analyze")
    report = _apply(client, result["staging_id"], "rename")
    assert report["renamed"] == [{"source": "math/sieve", "target": "math/sieve-2"}]
    assert report["created"] == ["math/sieve-2"]
    assert (content_dir / "math" / "sieve-2" / "sieve-2" / "sieve.cpp").is_file()
    assert "math/sieve-2" in _scan_ids(content_dir)


def test_conflict_overwrite(client: TestClient, content_dir: Path) -> None:
    old_ids = _scan_ids(content_dir)
    result = _upload(client, _conflict_zip(), "/api/transfer/import/templates/analyze")
    report = _apply(client, result["staging_id"], "overwrite")
    # 全量替代：旧库整体清除（无论是否冲突），只保留归档内容
    assert report["overwritten"] == sorted(old_ids)
    assert report["created"] == ["math/sieve"]
    assert _scan_ids(content_dir) == {"math/sieve"}
    # 无关旧分类目录也被移除，不留空目录
    assert not (content_dir / "ds").exists()
    assert not (content_dir / "graph").exists()
    assert not (content_dir / "字符串").exists()
    assert not (content_dir / "misc").exists()
    # 冲突项旧内容被整体替换为归档内容（三层标准结构）
    assert not (content_dir / "math" / "sieve" / "euler_sieve.cpp").exists()
    assert (content_dir / "math" / "sieve" / "sieve" / "sieve.cpp").is_file()


# ===== 导出 → 导入 round-trip =====


def test_round_trip_export_then_import(
    client: TestClient, content_dir: Path, tmp_path: Path
) -> None:
    """导出的标准归档导入到空库后，模板集合与版本数一致。"""
    import shutil

    before = scan_content(content_dir).templates
    data = client.get("/api/transfer/export/templates").content

    # 清空原库后重新导入（物理删除，测试目录无妨）
    shutil.rmtree(content_dir)
    content_dir.mkdir()

    result = _upload(client, data, "/api/transfer/import/templates/analyze")
    assert result["kind"] == "standard"
    assert result["template_count"] == len(before)
    report = _apply(client, result["staging_id"])
    assert len(report["created"]) == len(before)
    assert report["failed"] == []

    after = {t.id: t for t in scan_content(content_dir).templates}
    assert set(after) == {t.id for t in before}
    for tpl in before:
        assert len(after[tpl.id].versions) == len(tpl.versions)
        for v in tpl.versions:
            codes = {av.code for av in after[tpl.id].versions}
            assert v.code in codes
    # 空主标签往返保留
    assert (content_dir / "misc" / "empty-tpl").is_dir()
