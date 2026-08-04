"""README.md 解析：front matter（YAML）+ Markdown 正文。

鲁棒性原则：任何解析问题都只产生 Diagnostic，绝不抛异常中断扫描。

【初学者导读】
每个模板目录下的 README.md 分成两部分：

    ---            <- 开头三个横线
    tags: [搜索]   <- front matter：YAML 格式的元数据（给程序读的）
    updated: 2026-08-01
    ---            <- 结尾三个横线
    二分查找的做法…… <- 正文：Markdown 格式的说明（给人看的）

本文件负责把这两部分拆开，并把元数据变成 models.py 里的 ReadmeMeta 对象。
"""

import datetime
import re  # 标准库：正则表达式，用于把 front matter 和正文拆开
from pathlib import Path
from typing import Any  # Any 表示"任意类型"

import yaml  # 第三方库 PyYAML：把 YAML 文本解析成 Python 字典
from pydantic import ValidationError  # Pydantic 校验失败时抛出的异常类型

from modules.template.models import Diagnostic, ReadmeMeta

# 用正则表达式描述 front matter 的格式。
# 这个正则分三段匹配整个文本：
#   \A---[ \t]*\r?\n  开头是 "---"（可能跟空格），然后换行
#   (.*?)            第一段捕获：YAML 元数据（非贪婪，到第一个结束线为止）
#   \r?\n---[ \t]*\r?\n?  中间的结束 "---"
#   (.*)\Z           第二段捕获：剩余全部内容（正文）
# re.DOTALL 让 . 也能匹配换行符（否则 . 匹配不到多行内容）
_FRONT_MATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z",
    re.DOTALL,
)


def _coerce_meta(data: dict[str, Any], path: str, diags: list[Diagnostic]) -> ReadmeMeta:
    """将 YAML dict 规范化为 ReadmeMeta，容忍常见的书写误差。

    设计思路：README 是"人写的"，难免写得不规范。
    本函数先尽力修正（比如 tags 写成了单个字符串），
    实在修不好的地方记一条诊断并用默认值兜底，绝不抛异常。
    """
    # dict(data) 复制一份，避免直接修改调用方传进来的字典
    normalized = dict(data)

    # tags 允许写成单个字符串（比如 tags: 搜索），统一转成列表
    tags = normalized.get("tags")  # dict.get(key)：没有这个键时返回 None，不报错
    if isinstance(tags, str):  # isinstance：判断对象是不是某个类型
        normalized["tags"] = [tags]  # 包一层列表
    elif tags is None:
        normalized["tags"] = []

    # priority 允许字符串数字（比如 priority: "5"），统一转成整数
    priority = normalized.get("priority")
    if isinstance(priority, str) and priority.strip().isdigit():
        normalized["priority"] = int(priority.strip())  # strip() 去掉首尾空白

    # updated 允许日期以外的字符串，尝试按 ISO 格式（2026-08-01）解析
    updated = normalized.get("updated")
    if isinstance(updated, str):
        try:
            normalized["updated"] = datetime.date.fromisoformat(updated.strip())
        except ValueError:
            # 日期写错了：记一条 warning，当成"没填日期"处理
            diags.append(
                Diagnostic(level="warning", path=path, message=f"updated 日期无法解析: {updated!r}")
            )
            normalized["updated"] = None
    elif isinstance(updated, datetime.datetime):
        # YAML 有时会把日期解析成 datetime，转成 date 即可
        normalized["updated"] = updated.date()

    try:
        # model_validate 让 Pydantic 按 ReadmeMeta 的字段定义校验并构造对象
        meta = ReadmeMeta.model_validate(normalized)
    except ValidationError as exc:
        # 校验仍失败（比如 priority 是 "abc"）：
        # 记一条 warning 并用全默认值的 ReadmeMeta 兜底
        diags.append(
            Diagnostic(level="warning", path=path, message=f"front matter 字段异常，已按默认值兜底: {exc.errors()[0]['msg']}")
        )
        meta = ReadmeMeta()

    # 业务规则提示：只填了 page 没填 source 时，前端不会显示链接
    if meta.page and not meta.source:
        diags.append(
            Diagnostic(level="warning", path=path, message="填写了 page 但未填写 source，链接将不会显示")
        )
    return meta


def parse_readme_text(text: str, path: str, diags: list[Diagnostic]) -> tuple[ReadmeMeta, str]:
    """解析 README 文本，返回 (元数据, 正文)。正文去除首尾空白。

    返回值 tuple[ReadmeMeta, str] 表示一个二元组：
    第一个是 ReadmeMeta 对象，第二个是正文字符串。
    """
    # removeprefix：去掉开头的 BOM 字符（\ufeff，有些编辑器保存时会加）
    text = text.removeprefix(chr(0xFEFF))
    match = _FRONT_MATTER_RE.match(text)  # match 为 None 表示没有 front matter
    if match is None:
        diags.append(
            Diagnostic(level="warning", path=path, message="未找到 front matter，已按默认元数据处理")
        )
        return _coerce_meta({}, path, diags), text.strip()

    # match.group(1) 是正则第一段捕获（YAML），group(2) 是第二段（正文）
    raw_front, body = match.group(1), match.group(2)
    try:
        # yaml.safe_load 把 YAML 文本解析成 Python 字典
        data = yaml.safe_load(raw_front)
    except yaml.YAMLError as exc:
        diags.append(Diagnostic(level="error", path=path, message=f"front matter YAML 解析失败: {exc}"))
        return _coerce_meta({}, path, diags), body.strip()

    if data is None:
        data = {}  # front matter 是空的（---\n---），按空字典处理
    if not isinstance(data, dict):
        diags.append(Diagnostic(level="error", path=path, message="front matter 不是键值对结构"))
        return _coerce_meta({}, path, diags), body.strip()

    return _coerce_meta(data, path, diags), body.strip()


def parse_readme_file(file: Path, rel_path: str, diags: list[Diagnostic]) -> tuple[ReadmeMeta, str]:
    """读取并解析 README 文件，兼容 UTF-8 BOM 与 GBK 误存。"""
    try:
        # utf-8-sig 编码：读取时自动去掉开头的 BOM
        text = file.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        # 文件可能是在 Windows 上用 GBK 编码保存的，换个编码再试
        diags.append(
            Diagnostic(level="warning", path=rel_path, message="文件不是 UTF-8 编码，已尝试按 GBK 读取")
        )
        # errors="replace"：实在解码不了的字符用  占位，不抛异常
        text = file.read_text(encoding="gbk", errors="replace")
    except OSError as exc:
        # 文件本身读不了（权限问题等），记 error 并返回默认元数据 + 空正文
        diags.append(Diagnostic(level="error", path=rel_path, message=f"README 读取失败: {exc}"))
        return ReadmeMeta(), ""
    return parse_readme_text(text, rel_path, diags)
