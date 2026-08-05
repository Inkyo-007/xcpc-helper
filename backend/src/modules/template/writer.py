"""content/ 目录的写入操作：可视化增删改的文件系统落盘。

设计原则：
- 所有名称在落盘前经 validate_name 校验，杜绝路径穿越与非法目录名；
- 新建版本先写入 content/ 下的 .tmp-<uuid>/ 暂存目录，
  全部写成功后一次 os.rename 到位，避免半成品被 scanner 看到；
- 更新文件走 临时文件 + os.replace 原子替换；
- 删除为物理删除（产品决策：确认弹窗已明确告知不可找回）；
- README 由 render_readme 按表单数据全量生成（表单即真相），
  写出的内容保证能被 parser 原样读回（回环一致）。

【初学者导读】
这个文件是"写操作"模块：service.py 决定"要新建/修改/删除什么"，
本文件真正负责"在 content/ 目录里把文件创建/覆盖/删掉"。
它和 scanner.py 正好是一对：
- scanner.py 负责读（目录 -> 内存对象）
- writer.py 负责写（内存请求 -> 目录）
为了让 scanner 永远看不到"写了一半"的目录，
本文件大量使用 暂存目录 + 原子改名 的方式落盘。
"""

import os  # 标准库：操作系统接口（文件改名、删除等）
import shutil  # 标准库：目录级操作（删除整棵目录树）
import tempfile  # 标准库：创建临时文件/临时目录
from pathlib import Path
from typing import Any

import yaml  # 第三方库 PyYAML：把元数据转成 README 头部的 YAML 文本

from core.exceptions import BadRequestError, ConflictError, NotFoundError
from modules.template.models import DEFAULT_PRIORITY
from modules.template.scanner import CODE_EXTENSIONS
from modules.template.schemas import VersionMetaInput, VersionUpsert

# Windows 保留设备名（不分大小写，目录名与文件名主名都禁止使用）。
# 在 Windows 上创建名为 CON 的目录会引发系统级问题，所以提前拦截。
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),  # COM1 ~ COM9
    *(f"LPT{i}" for i in range(1, 10)),  # LPT1 ~ LPT9
}

# 目录名/文件名中禁止出现的字符（Windows 非法字符 + 路径分隔符）。
# 只要出现其中之一就拒绝，避免生成无法在 Windows 上使用的路径。
_FORBIDDEN_CHARS = set('/\\:*?"<>|')

# 名称长度上限（防止超长路径在 Windows 上踩 MAX_PATH 坑）
_MAX_NAME_LEN = 100


def validate_name(name: str, kind: str) -> str:
    """校验目录名（分类/模板/副标签），返回去空白后的名字，非法时抛 400。

    kind 是"分类"/"模板"/"副标签"这类中文称呼，用于拼装错误信息。
    """
    cleaned = name.strip()  # 去掉首尾空白后校验
    if not cleaned:
        raise BadRequestError(f"{kind}名称不能为空")
    if len(cleaned) > _MAX_NAME_LEN:
        raise BadRequestError(f"{kind}名称过长（最多 {_MAX_NAME_LEN} 个字符）")
    # 找出名称里所有非法字符（去重后排序，方便展示）
    bad = sorted(set(cleaned) & _FORBIDDEN_CHARS)
    if bad:
        raise BadRequestError(f"{kind}名称包含非法字符: {' '.join(bad)}")
    if cleaned.startswith("."):
        # 点开头会被 scanner 当作隐藏目录忽略，用户会以为创建失败
        raise BadRequestError(f"{kind}名称不能以点开头（会被扫描器忽略）")
    if cleaned != cleaned.rstrip(" ."):
        raise BadRequestError(f"{kind}名称不能以空格或点结尾")
    if cleaned in (".", "..") or ".." in cleaned:
        # ".." 是路径穿越的关键：name 里出现它可能让路径跳出 content/
        raise BadRequestError(f"{kind}名称不能包含 '..'")
    if cleaned == "~":
        # "~" 是顶层单版本的保留寻址符，见 schemas.py 的 ROOT_VERSION_TOKEN
        raise BadRequestError(f"{kind}名称不能使用保留字 '~'")
    if cleaned.upper() in _RESERVED_NAMES:
        raise BadRequestError(f"{kind}名称不能使用 Windows 保留名: {cleaned}")
    return cleaned


def validate_ext(ext: str) -> str:
    """校验代码扩展名（不含点），返回小写规范化结果，非法时抛 400。"""
    # 去掉空白、转小写、去掉可能的点：用户写 ".CPP" 也能通过
    cleaned = ext.strip().lower().lstrip(".")
    if f".{cleaned}" not in CODE_EXTENSIONS:
        allowed = ", ".join(sorted(e.lstrip(".") for e in CODE_EXTENSIONS))
        raise BadRequestError(f"不支持的代码扩展名: {ext!r}（支持: {allowed}）")
    return cleaned


def validate_code_filename(file: str, ext: str) -> str:
    """校验代码文件名：必须以 .<ext> 结尾，主名规则同目录名（允许内部含点）。"""
    cleaned = file.strip()
    suffix = f".{ext}"  # 例如 ".cpp"
    if not cleaned.lower().endswith(suffix):
        raise BadRequestError(f"代码文件名必须以 {suffix} 结尾: {file!r}")
    stem = cleaned[: -len(suffix)]  # 去掉扩展名后的主名
    if not stem or stem.startswith(".") or stem != stem.rstrip(" ."):
        raise BadRequestError(f"代码文件名不合法: {file!r}")
    bad = sorted(set(cleaned) & _FORBIDDEN_CHARS)
    if bad:
        raise BadRequestError(f"代码文件名包含非法字符: {' '.join(bad)}")
    if ".." in cleaned:
        raise BadRequestError("代码文件名不能包含 '..'")
    if stem.upper() in _RESERVED_NAMES:
        raise BadRequestError(f"代码文件名不能使用 Windows 保留名: {stem}")
    return cleaned


def validate_version_payload(payload: VersionUpsert) -> tuple[str, str]:
    """校验版本请求体的业务规则，返回规范化的 (扩展名, 代码文件名)。"""
    # 业务规则：填了 page 就必须填 source，否则前端链接无法显示
    if payload.meta.page and not payload.meta.source:
        raise BadRequestError("填写了 page 但未填写 source，链接将不会显示")
    ext = validate_ext(payload.ext)
    filename = (
        validate_code_filename(payload.file, ext) if payload.file else f"code.{ext}"
    )
    return ext, filename


def render_readme(meta: VersionMetaInput, body: str) -> str:
    """按表单数据生成 README.md 全文（front matter + 正文）。

    字段缺省时省略对应行（与解析端"不填即默认"的语义一致）；
    priority 等于默认值时省略，保持 README 干净。
    """
    data: dict[str, Any] = {}
    if meta.updated is not None:
        data["updated"] = meta.updated.isoformat()  # date -> "2026-08-01"
    # 去掉标签列表里的空白项，只保留非空标签
    tags = [t.strip() for t in meta.tags if t.strip()]
    if tags:
        data["tags"] = tags
    if meta.source and meta.source.strip():
        data["source"] = meta.source.strip()
    if meta.page and meta.page.strip():
        data["page"] = meta.page.strip()
    if meta.priority != DEFAULT_PRIORITY:
        data["priority"] = meta.priority

    # 空 front matter 也要保留一个空行（"---\n\n---"），否则解析端正则不匹配。
    # yaml.safe_dump 把字典转成 YAML 文本，allow_unicode=True 允许中文原样输出。
    front = (
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False) if data else "\n"
    )
    text = f"---\n{front}---\n"
    if body.strip():
        text += f"\n{body.strip()}\n"
    return text


# ===== 内部工具 =====


def _atomic_write(path: Path, text: str) -> None:
    """原子写入文本文件：先写同目录临时文件，再 os.replace 覆盖目标。

    为什么这样做？如果直接打开目标文件写入，写一半时被 scanner 读到，
    就是残缺内容。改成"先写临时文件、再整体替换"，读者要么看到旧文件，
    要么看到完整新文件，永远不会看到一半。
    """
    # mkstemp 在同目录创建以 .tmp- 开头的临时文件，返回 (文件描述符, 路径)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        # os.fdopen 把文件描述符包装成文件对象；newline="" 避免 Windows 转换换行
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        # os.replace 是"原子替换"：要么旧文件在，要么新文件在
        os.replace(tmp, path)
    except BaseException:
        # 任何一步失败：删掉临时文件，避免残留 .tmp- 垃圾
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _has_visible_entries(path: Path) -> bool:
    """目录是否含有非隐藏条目（点开头的文件/目录不算，如 .gitkeep）。"""
    return any(not p.name.startswith(".") for p in path.iterdir())


def _cleanup_empty_category(content_dir: Path, category: str) -> None:
    """删除模板后顺手清理空分类目录（删不掉说明里面还有东西，忽略）。"""
    category_dir = content_dir / category
    try:
        if category_dir.is_dir() and not _has_visible_entries(category_dir):
            shutil.rmtree(category_dir)  # 整目录递归删除
    except OSError:
        pass  # 清理失败不影响主流程，只是留一个空分类


def _find_readme(path: Path) -> Path | None:
    """在目录里找 README.md（大小写不敏感），找不到返回 None。"""
    for p in path.iterdir():
        if p.is_file() and p.name.lower() == "readme.md":
            return p
    return None


# ===== 模板（主标签）操作 =====


def create_template_dir(
    content_dir: Path, category: str, name: str
) -> tuple[str, str]:
    """新建空主标签目录，返回规范化后的 (分类, 模板名)。分类不存在时一并创建。"""
    category = validate_name(category, "分类")
    name = validate_name(name, "模板")
    target = content_dir / category / name  # 目标目录的完整路径
    if target.exists():
        raise ConflictError(f"模板已存在: {category}/{name}")
    category_existed = (content_dir / category).is_dir()  # 记录分类是否原本存在
    try:
        # parents=True 创建缺失的分类目录；exist_ok=False 表示目标已存在时报错
        target.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise ConflictError(f"模板已存在: {category}/{name}") from None
    except BaseException:
        # 失败时清理刚创建的空分类目录，不留半成品
        if not category_existed:
            _cleanup_empty_category(content_dir, category)
        raise
    return category, name


def rename_template_dir(
    content_dir: Path,
    category: str,
    name: str,
    *,
    new_category: str | None = None,
    new_name: str | None = None,
) -> tuple[str, str]:
    """主标签重命名/换分类，返回新的 (分类, 模板名)。两者都不变为无操作。"""
    src = content_dir / category / name  # 原路径
    if not src.is_dir():
        raise NotFoundError(f"模板不存在: {category}/{name}")
    # 只填了其中一个时，另一个保持原值
    dst_category = validate_name(new_category, "分类") if new_category else category
    dst_name = validate_name(new_name, "模板") if new_name else name
    if (dst_category, dst_name) == (category, name):
        return category, name  # 什么都没改：直接返回
    dst = content_dir / dst_category / dst_name
    if dst.exists():
        raise ConflictError(f"目标模板已存在: {dst_category}/{dst_name}")
    (content_dir / dst_category).mkdir(parents=True, exist_ok=True)  # 目标分类先建好
    os.rename(src, dst)  # 目录整体改名/移动
    _cleanup_empty_category(content_dir, category)  # 原分类空了就清掉
    return dst_category, dst_name


def delete_template_dir(content_dir: Path, category: str, name: str) -> None:
    """删除空主标签目录。目录内仍有可见内容时拒绝（409），防止误删整棵树。"""
    target = content_dir / category / name
    if not target.is_dir():
        raise NotFoundError(f"模板不存在: {category}/{name}")
    if _has_visible_entries(target):
        raise ConflictError("模板目录不为空，请先删除所有版本")
    target.rmdir()  # rmdir 只能删空目录，非空会报错（配合上面的检查双保险）
    _cleanup_empty_category(content_dir, category)


# ===== 版本操作 =====


def create_version_dir(
    content_dir: Path, category: str, name: str, payload: VersionUpsert
) -> str:
    """在模板目录下新建副标签版本目录，返回规范化后的副标签名。

    全程先在 content/ 的 .tmp-<uuid>/ 暂存目录里写好两个文件，
    再一次 rename 到位：scanner 要么看不到、要么看到完整版本。
    """
    template_dir = content_dir / category / name
    if not template_dir.is_dir():
        raise NotFoundError(f"模板不存在: {category}/{name}")
    if payload.name is None:
        raise BadRequestError("新建版本时必须填写版本名（副标签）")
    slug = validate_name(payload.name, "副标签")
    ext, filename = validate_version_payload(payload)
    target = template_dir / slug
    if target.exists():
        raise ConflictError(f"版本已存在: {category}/{name}/{slug}")

    # mkdtemp 在 content/ 下创建 .tmp- 开头的随机临时目录
    staging = Path(tempfile.mkdtemp(prefix=".tmp-", dir=content_dir))
    try:
        version_dir = staging / slug
        version_dir.mkdir()
        # 在暂存目录里先写好代码文件和 README，全部成功后才改名
        (version_dir / filename).write_text(
            payload.code, encoding="utf-8", newline=""
        )
        (version_dir / "README.md").write_text(
            render_readme(payload.meta, payload.body), encoding="utf-8", newline=""
        )
        os.rename(version_dir, target)  # 一次性移动到最终位置
    finally:
        # 无论成功失败都清理暂存目录（ignore_errors=True 表示清理失败也不抛）
        shutil.rmtree(staging, ignore_errors=True)
    return slug


def update_version_dir(
    content_dir: Path,
    category: str,
    name: str,
    current_slug: str,
    current_file: str,
    payload: VersionUpsert,
) -> str:
    """更新版本内容（代码/元数据/正文），支持副标签改名与代码文件名变更。

    current_slug 为空字符串表示"顶层单版本"（文件直接在模板目录下），
    顶层版本位置固定、不支持改名。返回更新后的副标签名。
    """
    template_dir = content_dir / category / name
    if not template_dir.is_dir():
        raise NotFoundError(f"模板不存在: {category}/{name}")
    ext, filename = validate_version_payload(payload)

    if not current_slug:
        # 顶层单版本：目录就是模板目录本身，位置固定
        if payload.name and payload.name.strip():
            raise BadRequestError("顶层版本不支持改名")
        version_dir = template_dir
        new_slug = ""
    else:
        # 副标签版本：版本目录 = 模板目录 / 副标签名
        version_dir = template_dir / current_slug
        if not version_dir.is_dir():
            raise NotFoundError(f"版本不存在: {category}/{name}/{current_slug}")
        new_slug = (
            validate_name(payload.name, "副标签")
            if payload.name and payload.name.strip()
            else current_slug
        )
        if new_slug != current_slug:
            # 副标签改名：先改名目录，再继续写内容
            new_dir = template_dir / new_slug
            if new_dir.exists():
                raise ConflictError(f"版本已存在: {category}/{name}/{new_slug}")
            os.rename(version_dir, new_dir)
            version_dir = new_dir

    # 代码文件：文件名变化时写新文件并删除旧文件，否则原子覆盖
    _atomic_write(version_dir / filename, payload.code)
    if current_file and current_file != filename:
        old_file = version_dir / current_file
        if old_file.is_file():
            old_file.unlink()  # 删除被替换掉的旧文件名

    # README：全量重写（表单即真相）；兼容历史上小写 readme.md 的情况
    readme = _find_readme(version_dir)
    _atomic_write(
        readme or (version_dir / "README.md"),
        render_readme(payload.meta, payload.body),
    )
    return new_slug


def delete_version_dir(
    content_dir: Path, category: str, name: str, current_slug: str, current_file: str
) -> None:
    """删除一个版本：副标签版本整目录删除；顶层版本只删代码与 README。"""
    template_dir = content_dir / category / name
    if not template_dir.is_dir():
        raise NotFoundError(f"模板不存在: {category}/{name}")
    if current_slug:
        # 副标签版本：整个版本目录递归删除
        version_dir = template_dir / current_slug
        if not version_dir.is_dir():
            raise NotFoundError(f"版本不存在: {category}/{name}/{current_slug}")
        shutil.rmtree(version_dir)
        return
    # 顶层单版本：删除代码文件与 README，模板目录留空（成为空主标签）
    code_file = template_dir / current_file
    if code_file.is_file():
        code_file.unlink()
    readme = _find_readme(template_dir)
    if readme is not None:
        readme.unlink()