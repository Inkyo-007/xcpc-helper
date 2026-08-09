"""模板库的导出（标准化序列化）与导入识别（外来平铺结构适配）。

导出：以 scan_content 的扫描结果为事实来源，统一序列化为三层标准结构
（content/<分类>/<模板>/<版本>/code.ext + README.md），代码统一 UTF-8。

导入识别两种归档：
- 标准归档（含本软件 manifest 且 kind=templates）：content/ 子树按三层结构映射；
- 外来平铺结构：一级目录=分类，分类目录下每份代码文件=一份单版本模板；
  分类下的子目录、根部散落文件、白名单外扩展名一律列入警告并跳过。
"""

from dataclasses import dataclass, field
from pathlib import Path

from common.validation import FORBIDDEN_CHARS, MAX_NAME_LEN, RESERVED_NAMES
from core.exceptions import BadRequestError
from modules.template.models import TemplateNode
from modules.template.scanner import CODE_EXTENSIONS
from modules.template.schemas import VersionMetaInput
from modules.template.writer import render_readme
from modules.transfer.archive import build_manifest, read_manifest, write_archive
from modules.transfer.schemas import ArchiveKind, TemplateAnalyzeItem, TransferWarning

# ===== 导出 =====


def build_templates_archive(templates: list[TemplateNode]) -> bytes:
    """把扫描结果序列化为标准三层结构的 zip 字节流（导出即规范化）。"""
    files: list[tuple[str, bytes]] = []
    dir_entries: list[str] = []
    categories: set[str] = set()
    version_total = 0
    for tpl in templates:
        categories.add(tpl.category)
        base = f"content/{tpl.category}/{tpl.slug}"
        if not tpl.versions:
            # 空主标签：写显式目录条目，保证往返不丢
            dir_entries.append(base)
            continue
        used: set[str] = set()
        for version in tpl.versions:
            # 顶层单版本升格为三层结构：版本目录名取模板名，冲突时递增后缀
            vdir = version.slug or tpl.slug
            if vdir in used:
                n = 2
                while f"{vdir}-{n}" in used:
                    n += 1
                vdir = f"{vdir}-{n}"
            used.add(vdir)
            files.append((f"{base}/{vdir}/{version.file}", version.code.encode("utf-8")))
            meta = VersionMetaInput(
                updated=version.meta.updated,
                tags=version.meta.tags,
                source=version.meta.source,
                page=version.meta.page,
                priority=version.meta.priority,
            )
            readme = render_readme(meta, version.body)
            files.append((f"{base}/{vdir}/README.md", readme.encode("utf-8")))
            version_total += 1
    counts = {
        "categories": len(categories),
        "templates": len(templates),
        "versions": version_total,
    }
    files.append(("manifest.json", build_manifest("templates", counts)))
    return write_archive(files, dir_entries)


# ===== 导入识别 =====


@dataclass
class ImportVersionPlan:
    """一个待导入的版本：暂存区内的来源路径 + 落盘时的命名。"""

    dir_name: str  # 版本目录名（落盘统一三层结构）
    code_path: Path  # 暂存区内代码文件路径
    file_name: str  # 落盘代码文件名（原文件名非法时回退 code.<ext>）
    readme_path: Path | None = None  # 标准归档中的 README（外来模板为 None）


@dataclass
class ImportTemplatePlan:
    """一份待导入的模板。versions 为空表示空主标签（仅建目录）。"""

    category: str
    name: str
    renamed_from: str | None = None
    versions: list[ImportVersionPlan] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.category}/{self.name}"


def sanitize_name(raw: str) -> tuple[str, bool]:
    """把外来名称清洗为合法目录名（对齐 common.validation 的规则），返回 (名称, 是否改动)。"""
    name = "".join("_" if c in FORBIDDEN_CHARS else c for c in raw)
    name = name.replace("..", "_")
    name = name.strip(" .")
    if not name or name == "~" or name.upper() in RESERVED_NAMES:
        name = "未命名"
    if len(name) > MAX_NAME_LEN:
        name = name[:MAX_NAME_LEN].rstrip(" .")
    return name, name != raw


def _safe_code_filename(file_name: str, ext: str) -> str:
    """落盘代码文件名：原名含非法字符时回退为 code.<ext>。"""
    suffix = f".{ext}"
    stem = file_name[: -len(suffix)] if file_name.lower().endswith(suffix) else ""
    if (
        stem
        and not stem.startswith(".")
        and stem == stem.rstrip(" .")
        and ".." not in file_name
        and not set(file_name) & FORBIDDEN_CHARS
        and stem.upper() not in RESERVED_NAMES
    ):
        return file_name
    return f"code.{ext}"


def _list_dirs(path: Path) -> list[Path]:
    return sorted(
        (p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name.lower(),
    )


def _code_files(path: Path) -> list[Path]:
    return sorted(
        (p for p in path.iterdir() if p.is_file() and p.suffix.lower() in CODE_EXTENSIONS),
        key=lambda p: p.name.lower(),
    )


def _find_readme(path: Path) -> Path | None:
    for p in path.iterdir():
        if p.is_file() and p.name.lower() == "readme.md":
            return p
    return None


def analyze_templates_archive(
    root: Path,
) -> tuple[ArchiveKind, list[ImportTemplatePlan], list[TransferWarning]]:
    """识别暂存区根目录，返回 (归档类型, 导入计划, 警告清单)。kind 不匹配时抛 400。"""
    manifest = read_manifest(root)
    if manifest is not None:
        kind = manifest.get("kind")
        if kind == "books":
            raise BadRequestError("这是打印册归档，请到打印册页面导入")
        if kind == "templates":
            content_root = root / "content"
            if not content_root.is_dir():
                raise BadRequestError("模板库归档缺少 content/ 目录")
            plans = _analyze_standard(content_root)
            return "standard", plans, []
    return _analyze_foreign(root)


def _analyze_standard(content_root: Path) -> list[ImportTemplatePlan]:
    """标准归档：content/<分类>/<模板>/<版本>/ 三层结构直接映射。

    顶层直接含代码文件的模板目录也按单版本收容（落盘时升格为三层）；
    凑不出任何代码文件的非空模板目录跳过。
    """
    plans: list[ImportTemplatePlan] = []
    for category_dir in _list_dirs(content_root):
        for template_dir in _list_dirs(category_dir):
            versions: list[ImportVersionPlan] = []
            top_codes = _code_files(template_dir)
            if top_codes:
                code = top_codes[0]
                ext = code.suffix.lower().lstrip(".")
                versions.append(
                    ImportVersionPlan(
                        dir_name=template_dir.name,
                        code_path=code,
                        file_name=_safe_code_filename(code.name, ext),
                        readme_path=_find_readme(template_dir),
                    )
                )
            for sub in _list_dirs(template_dir):
                sub_codes = _code_files(sub)
                if not sub_codes:
                    continue
                code = sub_codes[0]
                ext = code.suffix.lower().lstrip(".")
                versions.append(
                    ImportVersionPlan(
                        dir_name=sub.name,
                        code_path=code,
                        file_name=_safe_code_filename(code.name, ext),
                        readme_path=_find_readme(sub),
                    )
                )
            has_content = any(template_dir.iterdir())
            if not versions and has_content:
                # 目录内有内容却凑不出代码文件（如只有 README）：跳过
                continue
            plans.append(
                ImportTemplatePlan(
                    category=category_dir.name, name=template_dir.name, versions=versions
                )
            )
    return plans


def _analyze_foreign(
    root: Path,
) -> tuple[ArchiveKind, list[ImportTemplatePlan], list[TransferWarning]]:
    """外来平铺结构：一级目录=分类，分类下每份代码文件=一份单版本模板。"""
    warnings: list[TransferWarning] = []
    plans: list[ImportTemplatePlan] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith("."):
            continue
        if entry.is_file():
            warnings.append(
                TransferWarning(path=entry.name, message="根部散落的文件无法归属分类，已跳过")
            )
            continue
        category, cat_changed = sanitize_name(entry.name)
        if cat_changed:
            warnings.append(
                TransferWarning(path=entry.name, message=f"分类名已清洗为「{category}」")
            )
        for sub in sorted(entry.iterdir(), key=lambda p: p.name.lower()):
            rel = f"{entry.name}/{sub.name}"
            if sub.is_dir():
                warnings.append(
                    TransferWarning(path=rel, message="分类下的子目录暂不支持识别，已跳过")
                )
                continue
            ext = sub.suffix.lower().lstrip(".")
            if f".{ext}" not in CODE_EXTENSIONS:
                warnings.append(TransferWarning(path=rel, message="不支持的扩展名，已跳过"))
                continue
            raw_name = sub.name[: -len(sub.suffix)]
            name, name_changed = sanitize_name(raw_name)
            if name_changed:
                warnings.append(TransferWarning(path=rel, message=f"模板名已清洗为「{name}」"))
            plans.append(
                ImportTemplatePlan(
                    category=category,
                    name=name,
                    renamed_from=raw_name if name_changed else None,
                    versions=[
                        ImportVersionPlan(
                            dir_name=name,
                            code_path=sub,
                            file_name=_safe_code_filename(sub.name, ext),
                        )
                    ],
                )
            )
    _dedupe_within_category(plans, warnings)
    return "foreign", plans, warnings


def _dedupe_within_category(
    plans: list[ImportTemplatePlan], warnings: list[TransferWarning]
) -> None:
    """同分类内重名模板自动改名（同主名多扩展名拆分、清洗撞名等），并记录警告。"""
    taken: set[tuple[str, str]] = set()
    for plan in plans:
        key = (plan.category, plan.name)
        if key not in taken:
            taken.add(key)
            continue
        base = plan.name
        n = 2
        while (plan.category, f"{base}-{n}") in taken:
            n += 1
        new_name = f"{base}-{n}"
        warnings.append(
            TransferWarning(
                path=f"{plan.category}/{plan.name}",
                message=f"归档内存在同名模板，已拆分为「{new_name}」",
            )
        )
        plan.renamed_from = plan.renamed_from or plan.name
        plan.name = new_name
        plan.versions[0].dir_name = new_name
        taken.add((plan.category, new_name))


def to_analyze_items(plans: list[ImportTemplatePlan]) -> list[TemplateAnalyzeItem]:
    """导入计划 → analyze 响应的只读预览项。"""
    return [
        TemplateAnalyzeItem(
            category=p.category,
            name=p.name,
            version_count=len(p.versions),
            renamed_from=p.renamed_from,
        )
        for p in plans
    ]
