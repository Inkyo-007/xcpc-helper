"""导入/导出业务编排：暂存区管理、识别与落盘、导入后索引重建。

依赖方向严格单向 transfer -> template / printbook；
模板写操作一律经 modules/template/writer，落盘统一为三层标准结构；
apply 允许部分成功，逐项记录去向（延续"诊断不阻断"的鲁棒哲学）。
"""

import logging
import re
import shutil
import threading
import time
from pathlib import Path
from uuid import uuid4

from core.config import Settings, get_settings
from core.exceptions import AppError, BadRequestError
from modules.printbook import store as book_store
from modules.template import writer
from modules.template.models import Diagnostic
from modules.template.parser import parse_readme_file
from modules.template.scanner import scan_content
from modules.template.schemas import VersionMetaInput, VersionUpsert
from modules.transfer import books_io, templates_io
from modules.transfer.archive import extract_archive
from modules.transfer.schemas import (
    BookAnalyzeResult,
    FailedEntry,
    ImportApplyInput,
    ImportReport,
    RenamedEntry,
    TemplateAnalyzeResult,
)
from services.template.service import TemplateService, get_template_service

logger = logging.getLogger("xcpc.service.transfer")

_STAGING_ID_RE = re.compile(r"[0-9a-f]{32}")


def _clear_directory(path: Path) -> None:
    """清空目录下全部内容（保留目录本身）。目录不存在则无操作。"""
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)


class TransferService:
    """导入/导出服务。导出直接读磁盘事实来源；导入经暂存区两阶段完成。"""

    def __init__(self, settings: Settings, templates: TemplateService) -> None:
        self._settings = settings
        self._templates = templates
        self._lock = threading.RLock()

    # ===== 导出 =====

    def export_templates(self) -> bytes:
        """以当前扫描结果为事实来源，导出标准化三层结构的模板库 zip。"""
        scan = scan_content(self._settings.content_dir)
        return templates_io.build_templates_archive(scan.templates)

    def export_books(self, name: str | None = None) -> bytes:
        """导出打印册 zip：name 为 None 时导出所有册，否则导出单册（不存在 404）。"""
        books_dir = self._settings.books_dir
        if name is not None:
            book_store.load_book(books_dir, name)  # 存在性与可读性校验（404/400）
            names = [name]
        else:
            names = [info.name for info in book_store.list_books(books_dir)]
        return books_io.build_books_archive(books_dir, names)

    # ===== 模板导入 =====

    def analyze_templates(self, data: bytes) -> TemplateAnalyzeResult:
        """上传 zip → 解压至暂存区 → 返回识别结果 + 警告清单 + 冲突清单。"""
        staging_id, root = self._new_staging(data)
        try:
            kind, plans, warnings = templates_io.analyze_templates_archive(root)
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            raise
        if not plans:
            shutil.rmtree(root, ignore_errors=True)
            raise BadRequestError("压缩包中没有可识别的模板，请检查目录结构")
        existing = self._existing_template_ids()
        conflicts = sorted(p.id for p in plans if p.id in existing)
        return TemplateAnalyzeResult(
            staging_id=staging_id,
            kind=kind,
            category_count=len({p.category for p in plans}),
            template_count=len(plans),
            templates=templates_io.to_analyze_items(plans),
            warnings=warnings,
            conflicts=conflicts,
        )

    def apply_templates(self, payload: ImportApplyInput) -> ImportReport:
        """按冲突策略执行模板导入，返回逐项报告；完成后统一重建索引。"""
        with self._lock:
            root = self._staging_root(payload.staging_id)
            try:
                _kind, plans, _warnings = templates_io.analyze_templates_archive(root)
                report = ImportReport()
                taken = self._existing_template_ids()
                if payload.strategy == "overwrite":
                    # 全量替代：先清空整个 content/（含目录，避免残留空目录告警），
                    # 再把归档内容写入空库
                    report.overwritten = sorted(taken)
                    _clear_directory(self._settings.content_dir)
                    taken = set()
                for plan in plans:
                    self._apply_template(plan, payload.strategy, taken, report)
                self._templates.rebuild()
                return report
            finally:
                shutil.rmtree(root, ignore_errors=True)

    # ===== 打印册导入 =====

    def analyze_books(self, data: bytes) -> BookAnalyzeResult:
        """上传 zip → 解压至暂存区 → 返回册清单 + 警告 + 冲突清单。"""
        staging_id, root = self._new_staging(data)
        try:
            plans, warnings = books_io.analyze_books_archive(root)
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            raise
        if not plans:
            shutil.rmtree(root, ignore_errors=True)
            raise BadRequestError("压缩包中没有可导入的打印册")
        existing = self._existing_book_names()
        conflicts = sorted(p.name for p in plans if p.name in existing)
        return BookAnalyzeResult(
            staging_id=staging_id,
            books=books_io.to_book_items(plans),
            warnings=warnings,
            conflicts=conflicts,
        )

    def apply_books(self, payload: ImportApplyInput) -> ImportReport:
        """按冲突策略执行册导入（整册目录原子就位），返回逐项报告。"""
        with self._lock:
            root = self._staging_root(payload.staging_id)
            try:
                plans, _warnings = books_io.analyze_books_archive(root)
                report = ImportReport()
                taken = self._existing_book_names()
                if payload.strategy == "overwrite":
                    # 全量替代：先清空整个 books/，再把归档册写入
                    report.overwritten = sorted(taken)
                    _clear_directory(self._settings.books_dir)
                    taken = set()
                for plan in plans:
                    self._apply_book(plan, payload.strategy, taken, report)
                return report
            finally:
                shutil.rmtree(root, ignore_errors=True)

    def _apply_book(
        self,
        plan: books_io.ImportBookPlan,
        strategy: str,
        taken: set[str],
        report: ImportReport,
    ) -> None:
        books_dir = self._settings.books_dir
        name = plan.name
        try:
            created = True
            if name in taken:
                if strategy == "skip":
                    report.skipped.append(name)
                    return
                if strategy == "rename":
                    n = 2
                    while f"{name}-{n}" in taken:
                        n += 1
                    new_name = f"{name}-{n}"
                    report.renamed.append(RenamedEntry(source=name, target=new_name))
                    name = new_name
                else:  # overwrite
                    book_store.delete_book(books_dir, name)
                    report.overwritten.append(name)
                    created = False
            book_store.place_book_tree(books_dir, name, plan.source_dir)
            if created:
                report.created.append(name)
            taken.add(name)
        except (AppError, OSError) as exc:
            message = exc.message if isinstance(exc, AppError) else str(exc)
            logger.warning("导入打印册失败 [%s] %s", plan.name, message)
            report.failed.append(FailedEntry(id=plan.name, message=message))

    def _apply_template(
        self,
        plan: templates_io.ImportTemplatePlan,
        strategy: str,
        taken: set[str],
        report: ImportReport,
    ) -> None:
        content_dir = self._settings.content_dir
        category, name = plan.category, plan.name
        target_id = plan.id
        try:
            created = True
            if target_id in taken:
                if strategy == "skip":
                    report.skipped.append(target_id)
                    return
                if strategy == "rename":
                    n = 2
                    while f"{category}/{name}-{n}" in taken:
                        n += 1
                    new_name = f"{name}-{n}"
                    report.renamed.append(
                        RenamedEntry(source=target_id, target=f"{category}/{new_name}")
                    )
                    name = new_name
                    target_id = f"{category}/{name}"
                else:  # overwrite
                    writer.delete_template_tree(content_dir, category, name)
                    report.overwritten.append(target_id)
                    created = False
            writer.create_template_dir(content_dir, category, name)
            for version in plan.versions:
                writer.create_version_dir(
                    content_dir, category, name, self._version_payload(plan, version, name)
                )
            if created:
                report.created.append(target_id)
            taken.add(target_id)
        except (AppError, OSError, UnicodeDecodeError) as exc:
            message = exc.message if isinstance(exc, AppError) else str(exc)
            logger.warning("导入模板失败 [%s] %s", plan.id, message)
            report.failed.append(FailedEntry(id=plan.id, message=message))

    def _version_payload(
        self,
        plan: templates_io.ImportTemplatePlan,
        version: templates_io.ImportVersionPlan,
        template_name: str,
    ) -> VersionUpsert:
        """由导入计划组装版本写入载荷：代码按 UTF-8/GBK 读取，元数据解析 README。"""
        try:
            code = version.code_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            code = version.code_path.read_text(encoding="gbk", errors="replace")
        meta = VersionMetaInput()
        body = ""
        if version.readme_path is not None:
            diags: list[Diagnostic] = []
            parsed_meta, body = parse_readme_file(
                version.readme_path, version.readme_path.name, diags
            )
            meta = VersionMetaInput(
                updated=parsed_meta.updated,
                tags=parsed_meta.tags,
                source=parsed_meta.source,
                page=parsed_meta.page,
                priority=parsed_meta.priority,
            )
        ext = version.file_name.rsplit(".", 1)[-1]
        # 外来模板的版本目录名取清洗后的模板名（analyze 保证与 plan.name 同步改名）；
        # 冲突 rename 策略下落盘模板名变化时版本目录跟随，保持"单子目录折叠"形态
        dir_name = version.dir_name
        if dir_name == plan.name and template_name != plan.name:
            dir_name = template_name
        return VersionUpsert(
            name=dir_name,
            file=version.file_name,
            ext=ext,
            code=code,
            meta=meta,
            body=body,
        )

    # ===== 暂存区 =====

    def _new_staging(self, data: bytes) -> tuple[str, Path]:
        """解压上传的 zip 到新的暂存目录，返回 (暂存 id, 根路径)。"""
        max_bytes = self._settings.transfer_max_total_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise BadRequestError(
                f"压缩包大小超过 {self._settings.transfer_max_total_mb}MB 上限"
            )
        self._purge_staging()
        staging_id = uuid4().hex
        root = self._settings.staging_dir / f"transfer-{staging_id}"
        root.mkdir(parents=True)
        try:
            extract_archive(
                data,
                root,
                max_entries=self._settings.transfer_max_entries,
                max_total_mb=self._settings.transfer_max_total_mb,
                max_file_mb=self._settings.transfer_max_file_mb,
            )
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            raise
        return staging_id, root

    def _staging_root(self, staging_id: str) -> Path:
        """解析暂存 id 对应目录；id 非法或目录不存在（已过期/已消费）抛 400。"""
        if not _STAGING_ID_RE.fullmatch(staging_id):
            raise BadRequestError("无效的暂存 id，请重新上传压缩包")
        root = self._settings.staging_dir / f"transfer-{staging_id}"
        if not root.is_dir():
            raise BadRequestError("上传已过期，请重新选择压缩包")
        return root

    def _purge_staging(self) -> None:
        """清理超过 TTL 的暂存目录（analyze 时顺带执行）。"""
        staging = self._settings.staging_dir
        if not staging.is_dir():
            return
        deadline = time.time() - self._settings.transfer_staging_ttl_seconds
        for entry in staging.iterdir():
            if not entry.is_dir() or not entry.name.startswith("transfer-"):
                continue
            try:
                if entry.stat().st_mtime < deadline:
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                continue

    def _existing_template_ids(self) -> set[str]:
        """当前库中全部模板 id（直接扫磁盘事实来源，不依赖索引新鲜度）。"""
        return {t.id for t in scan_content(self._settings.content_dir).templates}

    def _existing_book_names(self) -> set[str]:
        """当前 books/ 下全部册名（含配置损坏的册，目录名即身份）。"""
        return {info.name for info in book_store.list_books(self._settings.books_dir)}


# 依赖注入

_service: TransferService | None = None


def init_transfer_service(
    settings: Settings | None = None,
    templates: TemplateService | None = None,
) -> TransferService:
    """应用启动时调用：创建导入/导出服务。"""
    global _service
    _service = TransferService(settings or get_settings(), templates or get_template_service())
    return _service


def get_transfer_service() -> TransferService:
    """FastAPI 依赖：获取全局服务实例。"""
    if _service is None:
        raise RuntimeError("TransferService 尚未初始化")
    return _service
