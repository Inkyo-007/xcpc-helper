"""archive 模块：zip 安全读写的单元测试。"""

import io
import json
import zipfile
from pathlib import Path

import pytest

from core.exceptions import BadRequestError
from modules.transfer.archive import (
    build_manifest,
    decode_entry_name,
    extract_archive,
    read_manifest,
    write_archive,
)
from tests.transfer.conftest import make_zip

LIMITS = {"max_entries": 100, "max_total_mb": 10, "max_file_mb": 5}


def test_decode_entry_name_gbk_fallback() -> None:
    """无 UTF-8 标志的条目名：cp437 取回原始字节后按 GBK 重解码（Windows 压缩常见）。"""
    info = zipfile.ZipInfo("x")
    info.filename = "图论/dijkstra.cpp".encode("gbk").decode("cp437")
    info.flag_bits = 0
    assert decode_entry_name(info) == "图论/dijkstra.cpp"


def test_decode_entry_name_utf8_flag() -> None:
    info = zipfile.ZipInfo("图论/dijkstra.cpp")
    info.flag_bits |= 0x800
    assert decode_entry_name(info) == "图论/dijkstra.cpp"


def test_extract_rejects_zip_slip(tmp_path: Path) -> None:
    data = make_zip({"../evil.cpp": "x", "a/b.cpp": "y"})
    with pytest.raises(BadRequestError, match="非法路径"):
        extract_archive(data, tmp_path, **LIMITS)


def test_extract_rejects_drive_letter(tmp_path: Path) -> None:
    data = make_zip({"C:/evil.cpp": "x"})
    with pytest.raises(BadRequestError, match="非法路径"):
        extract_archive(data, tmp_path, **LIMITS)


def test_extract_rejects_bad_zip(tmp_path: Path) -> None:
    with pytest.raises(BadRequestError, match="zip"):
        extract_archive(b"not a zip at all", tmp_path, **LIMITS)


def test_extract_rejects_too_many_entries(tmp_path: Path) -> None:
    data = make_zip({f"cat/f{i}.cpp": "x" for i in range(5)})
    with pytest.raises(BadRequestError, match="条目过多"):
        extract_archive(data, tmp_path, max_entries=3, max_total_mb=10, max_file_mb=5)


def test_extract_rejects_oversized_file(tmp_path: Path) -> None:
    data = make_zip({"cat/big.cpp": "x" * 1024})
    with pytest.raises(BadRequestError, match="单文件超过"):
        extract_archive(data, tmp_path, max_entries=100, max_total_mb=10, max_file_mb=0)


def test_manifest_round_trip(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_bytes(build_manifest("templates", {"templates": 3}))
    manifest = read_manifest(tmp_path)
    assert manifest is not None
    assert manifest["app"] == "xcpc-helper"
    assert manifest["kind"] == "templates"
    assert manifest["counts"]["templates"] == 3


def test_read_manifest_missing_or_foreign(tmp_path: Path) -> None:
    assert read_manifest(tmp_path) is None
    (tmp_path / "manifest.json").write_text("not json", encoding="utf-8")
    assert read_manifest(tmp_path) is None
    (tmp_path / "manifest.json").write_text(json.dumps({"app": "other"}), encoding="utf-8")
    assert read_manifest(tmp_path) is None


def test_write_archive_with_dir_entries_and_unicode() -> None:
    data = write_archive(
        [("content/数学/筛法/筛法/code.cpp", "代码".encode())],
        ["content/misc/empty-tpl"],
    )
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert "content/misc/empty-tpl/" in names
        assert "content/数学/筛法/筛法/code.cpp" in names
        assert zf.read("content/数学/筛法/筛法/code.cpp").decode("utf-8") == "代码"
