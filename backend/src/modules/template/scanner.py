"""content/ 目录扫描。

目录约定：
    content/<分类>/<模板>/                      模板目录（主标签）
    content/<分类>/<模板>/<code>.<ext> + README.md   单版本模板
    content/<分类>/<模板>/<副标签>/<code>.<ext> + README.md  多版本模板

仅含一个副标签子目录的模板也折叠为单版本（前端不显示副标签页签）。
目录与文件名为中文时必须正常工作（Python pathlib 原生支持 Unicode）。

【初学者导读】
本文件是"扫描器"：把磁盘上的目录结构翻译成 models.py 里的对象。
扫描流程是自下而上的三层：
    scan_content()        遍历 content/ 下每个分类
      -> _scan_template() 遍历分类下每个模板
        -> _scan_version() 扫描一个版本目录（一份代码 + 一份 README）
每个函数把发现的格式问题记进 diags（诊断列表），不抛异常。
"""

import logging
from pathlib import Path

from modules.template.models import (
    Diagnostic,
    ReadmeMeta,
    ScanResult,
    TemplateNode,
    VersionNode,
)
from modules.template.parser import parse_readme_file

logger = logging.getLogger("xcpc.scanner")

# 扩展名 -> 语言简称的对照表。
# 扫描时通过这个字典判断文件是不是代码文件、属于哪种语言。
CODE_EXTENSIONS: dict[str, str] = {
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "cpp",
    ".hpp": "cpp",
    ".py": "py",
    ".java": "java",
}


def _list_dirs(path: Path) -> list[Path]:
    """列出目录下的所有子目录，忽略隐藏目录（以 . 开头），按名称排序。

    (p for p in ...) 是生成器表达式，等价于一个紧凑的 for 循环；
    sorted(..., key=lambda p: p.name.lower()) 按目录名小写排序，
    lambda 是匿名函数，表示"按目录名排序"。
    """
    return sorted(
        (p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name.lower(),
    )


def _find_readme(path: Path) -> Path | None:
    """在目录里找 README.md（大小写不敏感），找不到返回 None。"""
    for p in path.iterdir():
        if p.is_file() and p.name.lower() == "readme.md":
            return p
    return None


def _find_code_file(path: Path, rel: str, diags: list[Diagnostic]) -> Path | None:
    """在目录里找第一个代码文件；多个时记 warning 并选按名称排序的第一个。"""
    # p.suffix 是扩展名（含点），.lower() 转小写后查表
    code_files = sorted(
        (
            p
            for p in path.iterdir()
            if p.is_file() and p.suffix.lower() in CODE_EXTENSIONS
        ),
        key=lambda p: p.name.lower(),
    )
    if not code_files:
        return None
    if len(code_files) > 1:
        # ", ".join(...)：把多个文件名用逗号拼成一个字符串
        names = ", ".join(p.name for p in code_files)
        diags.append(
            Diagnostic(
                level="warning",
                path=rel,
                message=f"版本目录包含多个代码文件（{names}），已选用 {code_files[0].name}",
            )
        )
    return code_files[0]


def _scan_version(
    version_dir: Path,
    *,
    slug: str,
    name: str,
    content_root: Path,
    diags: list[Diagnostic],
) -> VersionNode | None:
    """扫描一个版本目录：一份代码文件 + 一份 README.md（可缺失，缺失时告警兜底）。

    参数里单独的 * 表示：后面的参数必须用关键字传入（如 slug=...），
    防止传参顺序弄错。扫描失败（没有代码文件）时返回 None。
    """
    # relative_to 算出相对 content/ 的路径，as_posix 统一用 / 分隔
    # 例如 "数据结构/线段树"
    rel = version_dir.relative_to(content_root).as_posix()

    code_file = _find_code_file(version_dir, rel, diags)
    if code_file is None:
        # 没有代码文件的目录不能算一个版本：记 error 并跳过
        diags.append(Diagnostic(level="error", path=rel, message="版本目录缺少代码文件，已跳过"))
        return None

    readme = _find_readme(version_dir)
    if readme is None:
        # 没有 README 也能用：元数据全用默认值，正文为空
        diags.append(Diagnostic(level="warning", path=rel, message="缺少 README.md，已按默认元数据处理"))
        meta, body = ReadmeMeta(), ""
    else:
        # 交给 parser.py 解析，返回 (元数据, 正文)
        meta, body = parse_readme_file(readme, f"{rel}/README.md", diags)

    try:
        code = code_file.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        diags.append(
            Diagnostic(level="warning", path=rel, message="代码文件不是 UTF-8 编码，已尝试按 GBK 读取")
        )
        code = code_file.read_text(encoding="gbk", errors="replace")
    except OSError as exc:
        diags.append(Diagnostic(level="error", path=rel, message=f"代码文件读取失败: {exc}，已跳过"))
        return None

    # 把散落的字段组装成一个 VersionNode 对象返回
    return VersionNode(
        slug=slug,
        name=name,
        lang=CODE_EXTENSIONS[code_file.suffix.lower()],
        file=code_file.name,
        code=code,
        meta=meta,
        body=body,
    )


def _scan_template(
    category: str,
    template_dir: Path,
    content_root: Path,
    diags: list[Diagnostic],
) -> TemplateNode | None:
    """扫描一个模板目录：自身可能是单版本，子目录是额外版本。"""
    rel = template_dir.relative_to(content_root).as_posix()
    sub_dirs = _list_dirs(template_dir)
    # any(...)：只要目录下存在任意一个代码文件，就算"单版本"
    has_top_code = any(
        p.is_file() and p.suffix.lower() in CODE_EXTENSIONS for p in template_dir.iterdir()
    )

    versions: list[VersionNode] = []

    if has_top_code:
        # 代码文件直接在模板目录下：单版本（或与子目录版本并存）
        # 单版本的 slug 约定为空字符串，name 用模板目录名
        version = _scan_version(
            template_dir,
            slug="",
            name=template_dir.name,
            content_root=content_root,
            diags=diags,
        )
        if version is not None:
            versions.append(version)
        if sub_dirs:
            diags.append(
                Diagnostic(
                    level="warning",
                    path=rel,
                    message="模板目录同时包含代码文件与副标签子目录，两者都会作为版本载入",
                )
            )

    # 每个子目录视为一个"副标签"版本
    for sub in sub_dirs:
        version = _scan_version(
            sub,
            slug=sub.name,
            name=sub.name,
            content_root=content_root,
            diags=diags,
        )
        if version is not None:
            versions.append(version)

    if not versions:
        # 目录里有内容（代码读取失败、只有 README、子目录都缺代码等）却凑不出
        # 一个版本：属于格式错误，记 error 并跳过。
        # 完全空的目录则是刻意的"空主标签"（前端可视化新建的占位模板），
        # 正常载入、不产生诊断。
        # 隐藏文件（如 .gitkeep）不算内容，与 _list_dirs 忽略点开头目录一致
        has_any_content = (
            has_top_code
            or sub_dirs
            or any(not p.name.startswith(".") for p in template_dir.iterdir())
        )
        if has_any_content:
            diags.append(Diagnostic(level="error", path=rel, message="模板目录下未找到任何可用版本，已跳过"))
            return None
        return TemplateNode(
            id=f"{category}/{template_dir.name}",
            category=category,
            slug=template_dir.name,
            versions=[],
        )

    # id 形如 "数据结构/线段树"，作为这份模板的唯一标识
    return TemplateNode(
        id=f"{category}/{template_dir.name}",
        category=category,
        slug=template_dir.name,
        versions=versions,
    )


def scan_content(content_dir: Path) -> ScanResult:
    """扫描整个 content/ 目录。目录不存在时返回空结果并给出诊断。

    这是本文件对外的唯一入口，由 services/template/service.py 调用。
    """
    diags: list[Diagnostic] = []
    templates: list[TemplateNode] = []

    if not content_dir.is_dir():
        diags.append(
            Diagnostic(level="error", path=".", message=f"内容目录不存在: {content_dir}")
        )
        return ScanResult(templates=[], diagnostics=diags)

    try:
        category_dirs = _list_dirs(content_dir)
    except OSError as exc:
        diags.append(Diagnostic(level="error", path=".", message=f"内容目录读取失败: {exc}"))
        return ScanResult(templates=[], diagnostics=diags)

    for category_dir in category_dirs:
        category = category_dir.name
        try:
            for template_dir in _list_dirs(category_dir):
                node = _scan_template(category, template_dir, content_root=content_dir, diags=diags)
                if node is not None:
                    templates.append(node)
        except OSError as exc:
            diags.append(
                Diagnostic(level="error", path=category_dir.name, message=f"分类目录读取失败: {exc}")
            )

    return ScanResult(templates=templates, diagnostics=diags)
