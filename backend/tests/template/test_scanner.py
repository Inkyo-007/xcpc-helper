"""content/ 目录扫描器的单元测试。"""

from pathlib import Path

from modules.template.scanner import scan_content


def test_scan_all_forms(content_dir: Path) -> None:
    result = scan_content(content_dir)
    ids = {t.id for t in result.templates}
    # broken-no-code 无代码文件被跳过；broken-no-title 保留但产生诊断
    assert ids == {"math/sieve", "ds/dsu", "graph/tarjan", "字符串/哈希", "misc/broken-no-title"}


def test_single_version_template(content_dir: Path) -> None:
    result = scan_content(content_dir)
    sieve = next(t for t in result.templates if t.id == "math/sieve")
    assert len(sieve.versions) == 1
    version = sieve.versions[0]
    assert version.slug == ""  # 单版本无副标签
    assert version.lang == "cpp"
    assert version.meta.title == "线性筛（欧拉筛）"
    assert version.meta.priority == 5
    assert "最小质因子" in version.body


def test_multi_version_template(content_dir: Path) -> None:
    result = scan_content(content_dir)
    dsu = next(t for t in result.templates if t.id == "ds/dsu")
    assert [v.slug for v in dsu.versions] == ["path-compression", "with-weight"]
    assert all(v.lang == "cpp" for v in dsu.versions)


def test_single_subdir_collapsed_to_single_version(content_dir: Path) -> None:
    result = scan_content(content_dir)
    tarjan = next(t for t in result.templates if t.id == "graph/tarjan")
    assert len(tarjan.versions) == 1


def test_chinese_paths(content_dir: Path) -> None:
    result = scan_content(content_dir)
    hashed = next(t for t in result.templates if t.id == "字符串/哈希")
    assert hashed.category == "字符串"
    assert hashed.versions[0].meta.title == "字符串哈希（双模）"
    # page 填写但 source 缺失 → 产生告警
    assert any("source" in d.message for d in result.diagnostics)


def test_diagnostics_collected(content_dir: Path) -> None:
    result = scan_content(content_dir)
    messages = [d.message for d in result.diagnostics]
    assert any("title" in m for m in messages)  # broken-no-title 缺 title
    assert any("未找到任何可用版本" in m for m in messages)  # broken-no-code
    assert any("updated" in m for m in messages)  # tarjan 的坏日期


def test_missing_content_dir(tmp_path: Path) -> None:
    result = scan_content(tmp_path / "not-exist")
    assert result.templates == []
    assert any(d.level == "error" for d in result.diagnostics)
