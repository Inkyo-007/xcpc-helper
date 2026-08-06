"""跨功能共用的名称校验（分类/模板/副标签/打印册等目录名）。

规则与 Windows 文件系统兼容：禁止非法字符与保留设备名、
点开头、尾部空格或点、".."，长度限制防 MAX_PATH 问题。
"""

from core.exceptions import BadRequestError

# Windows 保留设备名（不分大小写，目录名与文件名主名都禁止使用）
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# 目录名/文件名中禁止出现的字符（Windows 非法字符 + 路径分隔符）
FORBIDDEN_CHARS = set('/\\:*?"<>|')

# 名称长度上限（防止超长路径在 Windows 上踩 MAX_PATH 坑）
MAX_NAME_LEN = 100


def validate_name(name: str, kind: str) -> str:
    """校验目录名（分类/模板/副标签/打印册），返回去空白后的名字，非法时抛 400。

    kind 是"分类"/"模板"/"副标签"这类中文称呼，用于拼装错误信息。
    """
    cleaned = name.strip()
    if not cleaned:
        raise BadRequestError(f"{kind}名称不能为空")
    if len(cleaned) > MAX_NAME_LEN:
        raise BadRequestError(f"{kind}名称过长（最多 {MAX_NAME_LEN} 个字符）")
    bad = sorted(set(cleaned) & FORBIDDEN_CHARS)
    if bad:
        raise BadRequestError(f"{kind}名称包含非法字符: {' '.join(bad)}")
    if cleaned.startswith("."):
        raise BadRequestError(f"{kind}名称不能以点开头（会被扫描器忽略）")
    if cleaned != cleaned.rstrip(" ."):
        raise BadRequestError(f"{kind}名称不能以空格或点结尾")
    if cleaned in (".", "..") or ".." in cleaned:
        raise BadRequestError(f"{kind}名称不能包含 '..'")
    if cleaned == "~":
        raise BadRequestError(f"{kind}名称不能使用保留字 '~'")
    if cleaned.upper() in RESERVED_NAMES:
        raise BadRequestError(f"{kind}名称不能使用 Windows 保留名: {cleaned}")
    return cleaned
