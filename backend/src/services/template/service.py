"""模板库业务编排：索引重建、列表查询、详情组装、过滤排序。"""

import datetime
import json
import logging
import sqlite3
import threading

from core.config import Settings, get_settings
from core.exceptions import NotFoundError
from modules.template import repository
from modules.template.models import Diagnostic
from modules.template.scanner import scan_content
from modules.template.schemas import (
    CategoryInfo,
    SortMode,
    TemplateDetail,
    TemplateSummary,
    TemplateVersion,
)

logger = logging.getLogger("xcpc.service.template")


class TemplateService:
    """模板库服务。读写均作用于 SQLite 缓存，rebuild 由扫描结果驱动。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._diagnostics: list[Diagnostic] = []
        self._lock = threading.Lock()

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
        matched_ids: set[str] | None = None
        if keyword and keyword.strip():
            matched_ids = repository.search_ids(db, keyword.strip())

        rows = repository.list_templates(db, category)
        summaries: list[TemplateSummary] = []
        for row in rows:
            if matched_ids is not None and row["id"] not in matched_ids:
                continue
            row_tags: list[str] = json.loads(row["tags"])
            if tags and not all(tag in row_tags for tag in tags):
                continue
            summaries.append(_row_to_summary(row))

        return _sort_summaries(summaries, sort)

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


def _row_to_summary(row: sqlite3.Row) -> TemplateSummary:
    updated: datetime.date | None = (
        datetime.date.fromisoformat(row["updated"]) if row["updated"] else None
    )
    return TemplateSummary(
        id=row["id"],
        name=row["title"],
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
