"""templates_io 模块：导出规范化与导入识别的单元测试。"""

import io
import json
import zipfile
from pathlib import Path

import pytest

from core.exceptions import BadRequestError
from modules.template.scanner import scan_content
from modules.transfer import templates_io
from modules.transfer.archive import extract_archive
from tests.transfer.conftest import make_zip

LIMITS = {"max_entries": 500, "max_total_mb": 50, "max_file_mb": 5}


def _extract(data: bytes, tmp_path: Path) -> Path:
    """解压到独立子目录（避免与 content_dir fixture 共用 tmp_path 互相污染）。"""
    dest = tmp_path / "pkg"
    dest.mkdir()
    extract_archive(data, dest, **LIMITS)
    return dest


def _zip_names(data: bytes) -> set[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return set(zf.namelist())


# ===== 导出 =====


def test_export_normalizes_to_three_levels(content_dir: Path) -> None:
    """三种目录形态统一导出为三层标准结构，顶层单版本升格、GBK 转 UTF-8。"""
    scan = scan_content(content_dir)
    names = _zip_names(templates_io.build_templates_archive(scan.templates))

    # 顶层单版本升格：content/math/sieve/sieve/...
    assert "content/math/sieve/sieve/euler_sieve.cpp" in names
    assert "content/math/sieve/sieve/README.md" in names
    # 多版本原样保持
    assert "content/ds/dsu/basic/dsu.cpp" in names
    assert "content/ds/dsu/weighted/dsu_w.cpp" in names
    # 单子目录形态保持
    assert "content/graph/tarjan/v1/tarjan.cpp" in names
    # 中文路径
    assert "content/字符串/哈希/哈希/str_hash.cpp" in names
    # 空主标签写显式目录条目
    assert "content/misc/empty-tpl/" in names
    # manifest
    assert "manifest.json" in names


def test_export_manifest_and_utf8(content_dir: Path) -> None:
    scan = scan_content(content_dir)
    data = templates_io.build_templates_archive(scan.templates)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["app"] == "xcpc-helper"
        assert manifest["kind"] == "templates"
        assert manifest["counts"]["templates"] == 6
        # GBK 代码导出为 UTF-8
        code = zf.read("content/misc/gbk-code/gbk-code/gbk.cpp").decode("utf-8")
        assert "中文注释" in code
        # README 元数据保留
        readme = zf.read("content/math/sieve/sieve/README.md").decode("utf-8")
        assert "priority: 5" in readme
        assert "线性筛说明" in readme


# ===== 导入识别：外来平铺结构 =====


def test_foreign_flat_mapping(tmp_path: Path) -> None:
    data = make_zip(
        {
            "图论/dijkstra.cpp": "// dij",
            "图论/spfa.cpp": "// spfa",
            "数据结构/线段树.cpp": "// seg",
        }
    )
    kind, plans, warnings = templates_io.analyze_templates_archive(_extract(data, tmp_path))
    assert kind == "foreign"
    assert warnings == []
    assert {p.id for p in plans} == {"图论/dijkstra", "图论/spfa", "数据结构/线段树"}
    for plan in plans:
        assert len(plan.versions) == 1
        assert plan.versions[0].dir_name == plan.name


def test_foreign_warnings_for_unrecognized(tmp_path: Path) -> None:
    """子目录、根部文件、白名单外扩展名（含 .txt）一律进警告并跳过。"""
    data = make_zip(
        {
            "图论/dijkstra.cpp": "// dij",
            "图论/最短路/floyd.cpp": "// floyd",
            "说明.txt": "readme",
            "图论/note.txt": "note",
            "root.cpp": "// root",
        }
    )
    kind, plans, warnings = templates_io.analyze_templates_archive(_extract(data, tmp_path))
    assert kind == "foreign"
    assert [p.id for p in plans] == ["图论/dijkstra"]
    warned_paths = {w.path for w in warnings}
    assert "图论/最短路" in warned_paths  # 子目录
    assert "图论/note.txt" in warned_paths  # .txt 不识别
    assert "root.cpp" in warned_paths  # 根部散落文件
    assert "说明.txt" in warned_paths


def test_foreign_sanitize_and_split_same_stem(tmp_path: Path) -> None:
    """非法字符清洗；同主名多扩展名拆成两份模板（后者自动改名）。"""
    data = make_zip(
        {
            "dp/dsu.cpp": "// cpp",
            "dp/dsu.py": "# py",
            "dp/a..b.cpp": "// dots",
        }
    )
    _kind, plans, warnings = templates_io.analyze_templates_archive(_extract(data, tmp_path))
    ids = {p.id for p in plans}
    assert "dp/dsu" in ids
    assert "dp/dsu-2" in ids  # 同主名拆分改名
    assert "dp/a_b" in ids  # ".." 清洗
    messages = "\n".join(w.message for w in warnings)
    assert "拆分" in messages
    assert "清洗" in messages


def test_foreign_reserved_names_fallback(tmp_path: Path) -> None:
    # "~.cpp" 在 Windows 可落盘；CON 等保留名连解压都无法进行，走 sanitize 单元测试
    data = make_zip({"cat/~.cpp": "// y"})
    _kind, plans, warnings = templates_io.analyze_templates_archive(_extract(data, tmp_path))
    assert {p.id for p in plans} == {"cat/未命名"}
    assert any("清洗" in w.message for w in warnings)


def test_wrapped_foreign_archive(tmp_path: Path) -> None:
    """用户把整个文件夹打成 zip：剥离 ownlib 包裹层后按外来平铺结构识别。"""
    data = make_zip(
        {
            "ownlib/图论/dijkstra.cpp": "// dij",
            "ownlib/图论/最短路/floyd.cpp": "// floyd",
            "ownlib/图论/note.txt": "note",
            "ownlib/dp/dsu.cpp": "// cpp",
            "ownlib/dp/dsu.py": "# py",
            "ownlib/root_loose.cpp": "// root",
        }
    )
    kind, plans, warnings = templates_io.analyze_templates_archive(_extract(data, tmp_path))
    assert kind == "foreign"
    assert {p.id for p in plans} == {"图论/dijkstra", "dp/dsu", "dp/dsu-2"}
    warned_paths = {w.path for w in warnings}
    assert "图论/最短路" in warned_paths  # 分类下的子目录
    assert "图论/note.txt" in warned_paths  # 白名单外扩展名
    assert "root_loose.cpp" in warned_paths  # 根部散落文件


def test_sanitize_name() -> None:
    """名称清洗对齐 common.validation 规则：保留名/空名兜底、非法字符替换、长度截断。"""
    assert templates_io.sanitize_name("CON") == ("未命名", True)
    assert templates_io.sanitize_name("~") == ("未命名", True)
    assert templates_io.sanitize_name("  abc  ") == ("abc", True)
    assert templates_io.sanitize_name(".abc.") == ("abc", True)
    assert templates_io.sanitize_name("a..b") == ("a_b", True)
    assert templates_io.sanitize_name("a<b>c") == ("a_b_c", True)
    assert templates_io.sanitize_name("正常名称") == ("正常名称", False)
    name, changed = templates_io.sanitize_name("x" * 120)
    assert len(name) == 100
    assert changed


# ===== 导入识别：标准归档 =====


def test_standard_archive_round_trip_plan(content_dir: Path, tmp_path: Path) -> None:
    """本软件导出的归档可直接识别回全部模板（含空主标签）。"""
    scan = scan_content(content_dir)
    data = templates_io.build_templates_archive(scan.templates)
    kind, plans, warnings = templates_io.analyze_templates_archive(_extract(data, tmp_path))
    assert kind == "standard"
    assert warnings == []
    ids = {p.id for p in plans}
    assert ids == {t.id for t in scan.templates}
    by_id = {p.id: p for p in plans}
    assert len(by_id["ds/dsu"].versions) == 2
    assert by_id["misc/empty-tpl"].versions == []
    assert len(by_id["math/sieve"].versions) == 1
    assert by_id["math/sieve"].versions[0].readme_path is not None


def test_analyze_rejects_books_archive(tmp_path: Path) -> None:
    manifest = json.dumps({"app": "xcpc-helper", "kind": "books"})
    data = make_zip({"manifest.json": manifest, "books/册A/book.yaml": "cover: {}"})
    with pytest.raises(BadRequestError, match="打印册归档"):
        templates_io.analyze_templates_archive(_extract(data, tmp_path))


def test_analyze_rejects_templates_archive_without_content(tmp_path: Path) -> None:
    manifest = json.dumps({"app": "xcpc-helper", "kind": "templates"})
    data = make_zip({"manifest.json": manifest})
    with pytest.raises(BadRequestError, match="content"):
        templates_io.analyze_templates_archive(_extract(data, tmp_path))
