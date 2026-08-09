"""模板库业务编排：索引重建、列表查询、详情组装、过滤排序。"""

import datetime
import json
import logging
import sqlite3
import threading

from core.config import Settings, get_settings
from core.exceptions import NotFoundError
from modules.template import repository, writer
from modules.template.models import Diagnostic, TemplateNode, VersionNode
from modules.template.scanner import scan_content
from modules.template.schemas import (
    ROOT_VERSION_TOKEN,
    CategoryInfo,
    SortMode,
    TemplateCreate,
    TemplateDetail,
    TemplateRename,
    TemplateSummary,
    TemplateVersion,
    VersionUpsert,
)

logger = logging.getLogger("xcpc.service.template")


class TemplateService:
    """模板库服务。读写均作用于 SQLite 缓存，rebuild 由扫描结果驱动。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._diagnostics: list[Diagnostic] = []
        # RLock：写操作需要在持锁状态下调用 rebuild（其内部再次拿锁）
        self._lock = threading.RLock()

    # 索引生命周期

    def rebuild(self) -> tuple[int, int]:
        """扫描 content/ 并全量重建索引，返回 (模板数, 诊断数)。"""
        scan = scan_content(self._settings.content_dir)
        with self._lock:
            repository.rebuild_index(self._settings.db_path, scan)
            self._diagnostics = scan.diagnostics
        return len(scan.templates), len(scan.diagnostics)

    def diagnostics(self) -> list[Diagnostic]:
        return list(self._diagnostics)

    # 查询

    def list_templates(
        self,
        *,
        category: str | None = None,
        tags: list[str] | None = None,
        keyword: str | None = None,
        sort: SortMode = "priority",
    ) -> list[TemplateSummary]:
        db = self._settings.db_path
        scores: dict[str, float] | None = None
        if keyword and keyword.strip():
            scores = repository.search_scores(db, keyword.strip())

        rows = repository.list_templates(db, category)
        summaries: list[TemplateSummary] = []
        for row in rows:
            if scores is not None and row["id"] not in scores:
                continue
            row_tags: list[str] = json.loads(row["tags"])
            if tags and not all(tag in row_tags for tag in tags):
                continue
            summaries.append(_row_to_summary(row))

        ordered = _sort_summaries(summaries, sort)
        if scores is not None:
            # 搜索时相关度恒为第一排序键；稳定排序保留用户所选排序作为同分决胜
            ordered.sort(key=lambda t: scores.get(t.id, 0.0), reverse=True)
        return ordered

    def get_detail(self, template_id: str) -> TemplateDetail:
        db = self._settings.db_path
        row = repository.get_template(db, template_id)
        if row is None:
            raise NotFoundError(f"模板不存在: {template_id}")
        versions = [
            TemplateVersion(
                id=v["id"],
                name=v["name"],
                lang=v["lang"],
                file=v["file"],
                code=v["code"],
                body=v["body"],
                tags=json.loads(v["tags"]),
                src=v["source"],
                page=v["page"],
                updated=(
                    datetime.date.fromisoformat(v["updated"]) if v["updated"] else None
                ),
                priority=v["priority"],
            )
            for v in repository.get_versions(db, template_id)
        ]
        return TemplateDetail(
            **_row_to_summary(row).model_dump(),
            desc=row["body"],
            variants=versions,
        )

    def list_categories(self) -> list[CategoryInfo]:
        rows = repository.category_counts(self._settings.db_path)
        return [
            CategoryInfo(id=row["category"], name=row["category"], count=row["count"])
            for row in rows
        ]

    # 可视化增删改（写操作）

    def _scan_for_write(self) -> list[TemplateNode]:
        """写操作前的现场扫描：拿最新的目录结构做存在性校验。"""
        return scan_content(self._settings.content_dir).templates

    @staticmethod
    def _find_node(
        templates: list[TemplateNode], category: str, name: str
    ) -> TemplateNode:
        for node in templates:
            if node.category == category and node.slug == name:
                return node
        raise NotFoundError(f"模板不存在: {category}/{name}")

    @staticmethod
    def _find_version(node: TemplateNode, slug: str) -> VersionNode:
        for version in node.versions:
            if version.slug == slug:
                return version
        label = slug or ROOT_VERSION_TOKEN
        raise NotFoundError(f"版本不存在: {node.id}/{label}")

    def create_template(self, payload: TemplateCreate) -> TemplateDetail:
        """新建空主标签目录并重建索引，返回新建模板的详情。"""
        with self._lock:
            category, name = writer.create_template_dir(
                self._settings.content_dir, payload.category, payload.name
            )
            self.rebuild()
        return self.get_detail(f"{category}/{name}")

    def rename_template(
        self, category: str, name: str, payload: TemplateRename
    ) -> TemplateDetail:
        """主标签重命名/换分类，返回新位置上的模板详情。"""
        with self._lock:
            new_category, new_name = writer.rename_template_dir(
                self._settings.content_dir,
                category,
                name,
                new_category=payload.new_category,
                new_name=payload.new_name,
            )
            self.rebuild()
        return self.get_detail(f"{new_category}/{new_name}")

    def delete_template(self, category: str, name: str) -> None:
        """删除空主标签目录（非空目录由 writer 拒绝）。"""
        with self._lock:
            writer.delete_template_dir(self._settings.content_dir, category, name)
            self.rebuild()

    def create_version(
        self, category: str, name: str, payload: VersionUpsert
    ) -> TemplateDetail:
        """在模板下新建副标签版本，返回整个模板的最新详情。"""
        with self._lock:
            writer.create_version_dir(
                self._settings.content_dir, category, name, payload
            )
            self.rebuild()
        return self.get_detail(f"{category}/{name}")

    def update_version(
        self, category: str, name: str, version_token: str, payload: VersionUpsert
    ) -> TemplateDetail:
        """更新版本内容（代码/元数据/正文/改名/换扩展名），返回模板最新详情。"""
        slug = "" if version_token == ROOT_VERSION_TOKEN else version_token
        with self._lock:
            node = self._find_node(self._scan_for_write(), category, name)
            current = self._find_version(node, slug)
            writer.update_version_dir(
                self._settings.content_dir,
                category,
                name,
                current.slug,
                current.file,
                payload,
            )
            self.rebuild()
        return self.get_detail(f"{category}/{name}")

    def delete_version(
        self, category: str, name: str, version_token: str
    ) -> TemplateDetail:
        """删除一个版本。删光后模板成为空主标签，返回模板最新详情。"""
        slug = "" if version_token == ROOT_VERSION_TOKEN else version_token
        with self._lock:
            node = self._find_node(self._scan_for_write(), category, name)
            current = self._find_version(node, slug)
            writer.delete_version_dir(
                self._settings.content_dir, category, name, current.slug, current.file
            )
            self.rebuild()
        return self.get_detail(f"{category}/{name}")


def _row_to_summary(row: sqlite3.Row) -> TemplateSummary:
    updated: datetime.date | None = (
        datetime.date.fromisoformat(row["updated"]) if row["updated"] else None
    )
    return TemplateSummary(
        id=row["id"],
        name=row["slug"],
        cat=row["category"],
        lang=row["lang"],
        file=row["file"],
        tags=json.loads(row["tags"]),
        src=row["source"],
        page=row["page"],
        updated=updated,
        priority=row["priority"],
        variant_count=row["variant_count"],
    )


def _sort_summaries(items: list[TemplateSummary], sort: SortMode) -> list[TemplateSummary]:
    if sort == "name":
        return sorted(items, key=lambda t: t.name.lower())
    if sort == "updated":
        return sorted(
            items,
            key=lambda t: (t.updated is not None, t.updated or datetime.date.min),
            reverse=True,
        )
    # priority：优先级降序，其次按更新日期
    return sorted(
        items,
        key=lambda t: (t.priority, t.updated or datetime.date.min),
        reverse=True,
    )


# 依赖注入

_service: TemplateService | None = None


def init_template_service(settings: Settings | None = None) -> TemplateService:
    """应用启动时调用：创建服务并完成首次索引构建。"""
    global _service
    _service = TemplateService(settings or get_settings())
    _service.rebuild()
    return _service


def get_template_service() -> TemplateService:
    """FastAPI 依赖：获取全局服务实例。"""
    if _service is None:
        raise RuntimeError("TemplateService 尚未初始化")
    return _service
