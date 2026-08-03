"""模板库 API 路由。

路由层保持薄：参数解析 + 调用 service。service 为同步实现
（SQLite 同步驱动），通过 asyncio.to_thread 避免阻塞事件循环。
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from modules.template.schemas import (
    CategoryInfo,
    DiagnosticItem,
    DiagnosticsResponse,
    ReloadResponse,
    SortMode,
    TemplateDetail,
    TemplateSummary,
)
from services.template.service import TemplateService, get_template_service

router = APIRouter(prefix="/api", tags=["template"])

ServiceDep = Annotated[TemplateService, Depends(get_template_service)]


@router.get("/templates", response_model=list[TemplateSummary])
async def list_templates(
    service: ServiceDep,
    category: Annotated[str | None, Query(description="分类目录名")] = None,
    tags: Annotated[list[str], Query(description="标签过滤，多值取交集")] = [],
    keyword: Annotated[str | None, Query(description="关键词，搜标题/标签/说明/代码")] = None,
    sort: Annotated[SortMode, Query(description="排序方式")] = "priority",
) -> list[TemplateSummary]:
    return await asyncio.to_thread(
        service.list_templates,
        category=category,
        tags=tags or None,
        keyword=keyword,
        sort=sort,
    )


@router.get("/templates/{template_id:path}", response_model=TemplateDetail)
async def get_template(template_id: str, service: ServiceDep) -> TemplateDetail:
    return await asyncio.to_thread(service.get_detail, template_id)


@router.post("/templates/reload", response_model=ReloadResponse)
async def reload_templates(service: ServiceDep) -> ReloadResponse:
    templates, diagnostics = await asyncio.to_thread(service.rebuild)
    return ReloadResponse(templates=templates, diagnostics=diagnostics)


@router.get("/categories", response_model=list[CategoryInfo])
async def list_categories(service: ServiceDep) -> list[CategoryInfo]:
    return await asyncio.to_thread(service.list_categories)


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def get_diagnostics(service: ServiceDep) -> DiagnosticsResponse:
    items = await asyncio.to_thread(service.diagnostics)
    return DiagnosticsResponse(
        items=[DiagnosticItem(**item.model_dump()) for item in items]
    )
