"""FastAPI 应用入口。

开发：cd backend && uv run uvicorn --app-dir src main:app --reload
生产：前端构建后由本应用托管 frontend/dist，一行启动。
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import get_settings
from core.exceptions import register_exception_handlers
from core.logging import setup_logging
from modules.template.watcher import ContentWatcher
from routers.activity.router import router as activity_router
from routers.printbook.router import router as printbook_router
from routers.template.router import router as template_router
from routers.transfer.router import router as transfer_router
from services.activity.service import init_activity_service
from services.printbook.service import init_print_book_service
from services.template.service import init_template_service
from services.transfer.service import init_transfer_service

logger = logging.getLogger("xcpc")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging()

    service = init_template_service(settings)
    logger.info("模板索引构建完成，诊断 %d 条", len(service.diagnostics()))

    init_print_book_service(settings, service)
    init_transfer_service(settings, service)
    activity = init_activity_service(settings)
    # 启动时自动同步当前用户组全部账号（后台执行；本地应用不常驻，
    # 启动即同步保证数据新鲜度；单账号失败降级为诊断，不阻断启动）
    if settings.activity_sync_on_startup:
        await activity.sync(None)

    watcher: ContentWatcher | None = None
    if settings.watch_enabled:
        watcher = ContentWatcher(
            settings.content_dir,
            service.rebuild,
            settings.watch_debounce_seconds,
        )
        watcher.start()

    yield

    await activity.aclose()
    if watcher is not None:
        watcher.stop()


async def spa_fallback_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """SPA 回退：非 /api 的 GET 请求 404 时返回 index.html，交给前端路由处理。

    前端使用 history 模式路由后，刷新 /template/library 之类的深链接
    会直接打到后端；静态托管找不到对应文件会抛 404，这里回退到入口页。
    /api 路径保持 JSON 错误响应，与全局异常结构一致。
    """
    index = get_settings().frontend_dist / "index.html"
    if (
        exc.status_code == 404
        and request.method == "GET"
        and not request.url.path.startswith("/api")
        and index.is_file()
    ):
        return FileResponse(index)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": str(exc.detail), "detail": None}},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="XCPC Helper", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.add_exception_handler(StarletteHTTPException, spa_fallback_handler)
    app.include_router(activity_router)
    app.include_router(template_router)
    app.include_router(printbook_router)
    app.include_router(transfer_router)

    # 前端构建产物存在时由后端托管（生产/桌面模式）
    if settings.frontend_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.frontend_dist, html=True),
            name="frontend",
        )

    return app


app = create_app()
