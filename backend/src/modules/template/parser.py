"""README.md 解析：front matter（YAML）+ Markdown 正文。

鲁棒性原则：任何解析问题都只产生 Diagnostic，绝不抛异常中断扫描。
"""

import datetime
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from modules.template.models import Diagnostic, ReadmeMeta

_FRONT_MATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z",
    re.DOTALL,
)


def _coerce_meta(data: dict[str, Any], path: str, diags: list[Diagnostic]) -> ReadmeMeta:
    """将 YAML dict 规范化为 ReadmeMeta，容忍常见的书写误差。"""
    normalized = dict(data)

    # tags 允许写成单个字符串
    tags = normalized.get("tags")
    if isinstance(tags, str):
        normalized["tags"] = [tags]
    elif tags is None:
        normalized["tags"] = []

    # priority 允许字符串数字
    priority = normalized.get("priority")
    if isinstance(priority, str) and priority.strip().isdigit():
        normalized["priority"] = int(priority.strip())

    # updated 允许日期以外的字符串，尝试按 ISO 格式解析
    updated = normalized.get("updated")
    if isinstance(updated, str):
        try:
            normalized["updated"] = datetime.date.fromisoformat(updated.strip())
        except ValueError:
            diags.append(
                Diagnostic(level="warning", path=path, message=f"updated 日期无法解析: {updated!r}")
            )
            normalized["updated"] = None
    elif isinstance(updated, datetime.datetime):
        normalized["updated"] = updated.date()

    try:
        meta = ReadmeMeta.model_validate(normalized)
    except ValidationError as exc:
        diags.append(
            Diagnostic(level="warning", path=path, message=f"front matter 字段异常，已按默认值兜底: {exc.errors()[0]['msg']}")
        )
        meta = ReadmeMeta(title=data.get("title") if isinstance(data.get("title"), str) else None)

    if not meta.title:
        diags.append(Diagnostic(level="error", path=path, message="front matter 缺少必填项 title"))
    if meta.page and not meta.source:
        diags.append(
            Diagnostic(level="warning", path=path, message="填写了 page 但未填写 source，链接将不会显示")
        )
    return meta


def parse_readme_text(text: str, path: str, diags: list[Diagnostic]) -> tuple[ReadmeMeta, str]:
    """解析 README 文本，返回 (元数据, 正文)。正文去除首尾空白。"""
    text = text.removeprefix(chr(0xFEFF))
    match = _FRONT_MATTER_RE.match(text)
    if match is None:
        diags.append(
            Diagnostic(level="warning", path=path, message="未找到 front matter，已按默认元数据处理")
        )
        return _coerce_meta({}, path, diags), text.strip()

    raw_front, body = match.group(1), match.group(2)
    try:
        data = yaml.safe_load(raw_front)
    except yaml.YAMLError as exc:
        diags.append(Diagnostic(level="error", path=path, message=f"front matter YAML 解析失败: {exc}"))
        return _coerce_meta({}, path, diags), body.strip()

    if data is None:
        data = {}
    if not isinstance(data, dict):
        diags.append(Diagnostic(level="error", path=path, message="front matter 不是键值对结构"))
        return _coerce_meta({}, path, diags), body.strip()

    return _coerce_meta(data, path, diags), body.strip()


def parse_readme_file(file: Path, rel_path: str, diags: list[Diagnostic]) -> tuple[ReadmeMeta, str]:
    """读取并解析 README 文件，兼容 UTF-8 BOM 与 GBK 误存。"""
    try:
        text = file.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        diags.append(
            Diagnostic(level="warning", path=rel_path, message="文件不是 UTF-8 编码，已尝试按 GBK 读取")
        )
        text = file.read_text(encoding="gbk", errors="replace")
    except OSError as exc:
        diags.append(Diagnostic(level="error", path=rel_path, message=f"README 读取失败: {exc}"))
        return ReadmeMeta(), ""
    return parse_readme_text(text, rel_path, diags)
