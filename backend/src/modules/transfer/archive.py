"""zip 归档的安全读写：导入/导出共用的底层工具。

安全要点：
- 中文文件名兜底：无 UTF-8 标志的条目名按 cp437 取回原始字节后
  依次尝试 UTF-8 / GBK 重解码（Windows 资源管理器压制的 zip 常见 GBK 形态）；
- zip slip 防护：条目路径规范化后必须留在归档根内，拒绝绝对路径、".." 与盘符；
- 限量：条目数、总解压大小、单文件大小超限整体拒绝（400）。
"""

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from core.exceptions import BadRequestError

MANIFEST_NAME = "manifest.json"
ARCHIVE_APP = "xcpc-helper"
ARCHIVE_FORMAT = 1


def decode_entry_name(info: zipfile.ZipInfo) -> str:
    """解码 zip 条目名：UTF-8 标志缺失时对原始字节做 UTF-8/GBK 重解码兜底。"""
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437", errors="replace")
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return info.filename


def _safe_relpath(name: str) -> PurePosixPath:
    """校验并返回安全的归档内相对路径，非法（zip slip）时抛 400。"""
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise BadRequestError(f"压缩包包含非法路径: {name!r}")
    if path.parts and ":" in path.parts[0]:
        raise BadRequestError(f"压缩包包含非法路径: {name!r}")
    return path


def extract_archive(
    data: bytes,
    dest: Path,
    *,
    max_entries: int,
    max_total_mb: int,
    max_file_mb: int,
) -> None:
    """把 zip 字节流安全解压到 dest（dest 必须已存在）。任一校验失败整体拒绝。"""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BadRequestError("文件不是有效的 zip 压缩包") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > max_entries:
            raise BadRequestError(f"压缩包条目过多（{len(infos)} > {max_entries}）")
        total = 0
        max_file = max_file_mb * 1024 * 1024
        max_total = max_total_mb * 1024 * 1024
        for info in infos:
            name = decode_entry_name(info)
            rel = _safe_relpath(name)
            if info.is_dir():
                # 显式目录条目（如空主标签）需要落盘，否则往返会丢
                try:
                    dest.joinpath(*rel.parts).mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    raise BadRequestError(
                        f"压缩包内目录名在当前系统不可用: {name}（{exc}）"
                    ) from exc
                continue
            if info.file_size > max_file:
                raise BadRequestError(f"压缩包内单文件超过 {max_file_mb}MB: {name}")
            total += info.file_size
            if total > max_total:
                raise BadRequestError(f"压缩包解压后总大小超过 {max_total_mb}MB")
            target = dest.joinpath(*rel.parts)
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(info))
            except OSError as exc:
                # 其他平台制作的 zip 可能含 Windows 非法文件名（如 "<"），
                # 直接整体拒绝并给出明确原因，不留半成品
                raise BadRequestError(
                    f"压缩包内文件名在当前系统不可用: {name}（{exc}）"
                ) from exc


def build_manifest(kind: str, counts: dict[str, int]) -> bytes:
    """生成归档标识 manifest.json 的字节内容。"""
    payload = {
        "app": ARCHIVE_APP,
        "kind": kind,
        "format": ARCHIVE_FORMAT,
        "exported_at": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
        "counts": counts,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def read_manifest(root: Path) -> dict | None:
    """读取归档根的 manifest.json；缺失/损坏/非本软件归档返回 None。"""
    file = root / MANIFEST_NAME
    if not file.is_file():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("app") != ARCHIVE_APP:
        return None
    return data


def strip_wrapper_dir(root: Path) -> Path:
    """剥离单层包裹目录：把整个文件夹打成 zip 会让归档多一层外壳，这里静默下钻。

    根目录仅含一个条目且为目录（忽略点开头条目）时考虑下钻，条件为其中任一：
    - 该目录含 manifest.json / content/ / books/（本软件导出的归档被整体打包）；
    - 该目录子项中目录数多于文件数（外来模板库按「文件夹/分类/代码」整体打包；
      单分类外来库的子项以代码文件为主，不会误下钻）。
    """
    entries = [p for p in root.iterdir() if not p.name.startswith(".")]
    if len(entries) != 1 or not entries[0].is_dir():
        return root
    wrapper = entries[0]
    own_markers = (wrapper / MANIFEST_NAME).is_file() or any(
        (wrapper / d).is_dir() for d in ("content", "books")
    )
    if own_markers:
        return wrapper
    children = [p for p in wrapper.iterdir() if not p.name.startswith(".")]
    dirs = sum(1 for p in children if p.is_dir())
    if dirs > len(children) - dirs:
        return wrapper
    return root


def write_archive(files: list[tuple[str, bytes]], dir_entries: list[str] | None = None) -> bytes:
    """把内存中的文件集合打成 zip 字节流。arcname 一律 posix 风格（utf-8 标志自动置位）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in dir_entries or []:
            zf.writestr(d.rstrip("/") + "/", b"")
        for arcname, content in files:
            zf.writestr(arcname, content)
    return buf.getvalue()
