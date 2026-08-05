"""模板库 API 路由。

路由层保持薄：参数解析 + 调用 service。service 为同步实现
（SQLite 同步驱动），通过 asyncio.to_thread 避免阻塞事件循环。

【初学者导读】
本文件定义了 5 个 HTTP 接口（都以 /api 开头）：
- GET  /api/templates            模板列表（支持过滤、排序）
- GET  /api/templates/{id}       模板详情（含代码）
- POST /api/templates/reload     手动重建索引
- GET  /api/categories           分类列表
- GET  /api/diagnostics          扫描诊断列表

关键概念——async/await：
FastAPI 用 async 函数处理请求，同一个进程可以同时服务很多请求。
但 SQLite 是同步库，直接调用会卡住整个服务，
所以每个接口都用 await asyncio.to_thread(...) 把同步代码
丢到线程池执行，主事件循环继续处理其他请求。
"""

import asyncio
from typing import Annotated  # Annotated：把类型和附加信息（如 Query）组合在一起

from fastapi import APIRouter, Depends, Query, status

from modules.template.schemas import (
    CategoryInfo,
    DiagnosticItem,
    DiagnosticsResponse,
    ReloadResponse,
    SortMode,
    TemplateCreate,
    TemplateDetail,
    TemplateRename,
    TemplateSummary,
    VersionUpsert,
)
from services.template.service import TemplateService, get_template_service

# APIRouter：一组相关路由的集合，最后在 main.py 里 include 进应用。
# prefix="/api"：本文件所有接口的 URL 都以 /api 开头。
router = APIRouter(prefix="/api", tags=["template"])

# ServiceDep 是"依赖注入"的简写：
# 路由参数写 service: ServiceDep 时，FastAPI 会自动调用
# get_template_service() 拿到全局服务实例传进来。
# Annotated[类型, 元数据]：给类型附加额外信息，这里附加的是 Depends(...)。
ServiceDep = Annotated[TemplateService, Depends(get_template_service)]


@router.get("/templates", response_model=list[TemplateSummary])
async def list_templates(
    service: ServiceDep,
    category: Annotated[str | None, Query(description="分类目录名")] = None,
    tags: Annotated[list[str], Query(description="标签过滤，多值取交集")] = [],
    keyword: Annotated[str | None, Query(description="关键词，搜标题/标签/说明/代码")] = None,
    sort: Annotated[SortMode, Query(description="排序方式")] = "priority",
) -> list[TemplateSummary]:
    """GET /api/templates：模板列表。

    参数上的 Query(...) 告诉 FastAPI 这是 URL 查询参数，
    例如 /api/templates?category=数据结构&keyword=线段树。
    等号右边是默认值：不传该参数时用什么。
    """
    return await asyncio.to_thread(
        service.list_templates,
        category=category,
        tags=tags or None,  # 空列表视为"没传标签"，统一转成 None
        keyword=keyword,
        sort=sort,
    )


@router.get("/templates/{template_id:path}", response_model=TemplateDetail)
async def get_template(template_id: str, service: ServiceDep) -> TemplateDetail:
    """GET /api/templates/{template_id}：模板详情。

    URL 里的 {template_id} 是路径参数，:path 表示允许包含斜杠，
    这样才能匹配 "数据结构/线段树" 这种带 / 的模板 id。
    """
    return await asyncio.to_thread(service.get_detail, template_id)


@router.post("/templates/reload", response_model=ReloadResponse)
async def reload_templates(service: ServiceDep) -> ReloadResponse:
    """POST /api/templates/reload：手动触发一次索引重建。"""
    templates, diagnostics = await asyncio.to_thread(service.rebuild)
    return ReloadResponse(templates=templates, diagnostics=diagnostics)


@router.get("/categories", response_model=list[CategoryInfo])
async def list_categories(service: ServiceDep) -> list[CategoryInfo]:
    """GET /api/categories：分类列表（侧边栏用）。"""
    return await asyncio.to_thread(service.list_categories)


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def get_diagnostics(service: ServiceDep) -> DiagnosticsResponse:
    """GET /api/diagnostics：最近一次扫描的诊断列表。"""
    items = await asyncio.to_thread(service.diagnostics)
    return DiagnosticsResponse(
        # 列表推导式：把内部 Diagnostic 对象转成对外契约 DiagnosticItem
        # **item.model_dump()：把对象的字段摊开成关键字参数
        items=[DiagnosticItem(**item.model_dump()) for item in items]
    )


# ===== 可视化增删改 =====
# 写路由一律用 {category}/{name} 双路径段（名称校验已禁止名称内含 "/"），
# 不使用 :path 转换器，避免与版本子路由产生匹配歧义。
# 顶层单版本（代码直接在模板目录下）在 URL 中用保留字 "~" 寻址。


@router.post(
    "/templates", response_model=TemplateDetail, status_code=status.HTTP_201_CREATED
)
async def create_template(
    payload: TemplateCreate, service: ServiceDep
) -> TemplateDetail:
    """POST /api/templates：新建空主标签（仅分类 + 模板名）。"""
    return await asyncio.to_thread(service.create_template, payload)


@router.put("/templates/{category}/{name}", response_model=TemplateDetail)
async def rename_template(
    category: str, name: str, payload: TemplateRename, service: ServiceDep
) -> TemplateDetail:
    """PUT /api/templates/{category}/{name}：主标签重命名/换分类。"""
    return await asyncio.to_thread(service.rename_template, category, name, payload)


@router.delete("/templates/{category}/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(category: str, name: str, service: ServiceDep) -> None:
    """DELETE /api/templates/{category}/{name}：删除空主标签。"""
    await asyncio.to_thread(service.delete_template, category, name)


@router.post(
    "/templates/{category}/{name}/versions",
    response_model=TemplateDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    category: str, name: str, payload: VersionUpsert, service: ServiceDep
) -> TemplateDetail:
    """POST .../versions：在模板下新建副标签版本。"""
    return await asyncio.to_thread(service.create_version, category, name, payload)


@router.put(
    "/templates/{category}/{name}/versions/{version}", response_model=TemplateDetail
)
async def update_version(
    category: str, name: str, version: str, payload: VersionUpsert, service: ServiceDep
) -> TemplateDetail:
    """PUT .../versions/{version}：更新版本（"~" 表示顶层单版本）。"""
    return await asyncio.to_thread(
        service.update_version, category, name, version, payload
    )


@router.delete(
    "/templates/{category}/{name}/versions/{version}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_version(
    category: str, name: str, version: str, service: ServiceDep
) -> None:
    """DELETE .../versions/{version}：删除版本（"~" 表示顶层单版本）。"""
    await asyncio.to_thread(service.delete_version, category, name, version)
