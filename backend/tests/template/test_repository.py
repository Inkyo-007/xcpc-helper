"""FTS5 检索索引与元数据缓存的单元测试。"""

import json
from pathlib import Path

import pytest

from modules.template import repository
from modules.template.scanner import scan_content


@pytest.fixture
def db_path(tmp_path: Path, content_dir: Path) -> Path:
    path = tmp_path / "data" / "index.db"
    rebuild = scan_content(content_dir)
    repository.rebuild_index(path, rebuild)
    return path


def test_rebuild_and_list(db_path: Path) -> None:
    rows = repository.list_templates(db_path)
    ids = {row["id"] for row in rows}
    assert "math/sieve" in ids
    assert "ds/dsu" in ids
    sieve = next(row for row in rows if row["id"] == "math/sieve")
    assert sieve["slug"] == "sieve"
    assert sieve["priority"] == 5
    assert sieve["updated"] == "2026-07-29"


def test_template_row_aggregates_versions(db_path: Path) -> None:
    """多版本模板的列表字段：优先级取最大、更新日期取最晚、标签取并集。"""
    row = repository.get_template(db_path, "ds/dsu")
    assert row is not None
    assert row["priority"] == 4  # max(4, 3)
    assert row["updated"] == "2026-07-10"  # max(2026-07-01, 2026-07-10)
    assert json.loads(row["tags"]) == ["连通性"]


def test_versions_ordered(db_path: Path) -> None:
    versions = repository.get_versions(db_path, "ds/dsu")
    assert [v["slug"] for v in versions] == ["path-compression", "with-weight"]
    assert versions[0]["id"] == "ds/dsu/path-compression"


def test_versions_carry_meta(db_path: Path) -> None:
    """版本行携带各自的元信息，供详情页切换版本时展示。"""
    versions = repository.get_versions(db_path, "ds/dsu")
    assert versions[0]["priority"] == 4
    assert versions[0]["updated"] == "2026-07-01"
    assert versions[1]["priority"] == 3
    assert versions[1]["updated"] == "2026-07-10"
    assert json.loads(versions[1]["tags"]) == ["连通性"]


def test_category_filter_and_counts(db_path: Path) -> None:
    rows = repository.list_templates(db_path, category="ds")
    assert {row["id"] for row in rows} == {"ds/dsu"}
    counts = {row["category"]: row["count"] for row in repository.category_counts(db_path)}
    assert counts["ds"] == 1
    assert counts["字符串"] == 1


def test_search_chinese_long_term_via_fts(db_path: Path) -> None:
    ids = repository.search_ids(db_path, "线性筛")
    assert "math/sieve" in ids


def test_search_chinese_short_term_via_like(db_path: Path) -> None:
    # 双字标签走 LIKE 退化路径
    ids = repository.search_ids(db_path, "素数")
    assert "math/sieve" in ids


def test_search_multi_terms_intersect(db_path: Path) -> None:
    ids = repository.search_ids(db_path, "线性筛 素数")
    assert ids == {"math/sieve"}


def test_search_code_content(db_path: Path) -> None:
    ids = repository.search_ids(db_path, "bits/stdc")
    assert "math/sieve" in ids


def test_get_template(db_path: Path) -> None:
    row = repository.get_template(db_path, "math/sieve")
    assert row is not None
    assert row["variant_count"] == 1
    assert repository.get_template(db_path, "not/exist") is None
