"""FastAPI 应用入口。

开发：cd backend && uv run uvicorn --app-dir src main:app --reload
生产：前端构建后由本应用托管 frontend/dist，一行启动。
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import get_settings
from core.exceptions import register_exception_handlers
from core.logging import setup_logging
from modules.template.watcher import ContentWatcher
from routers.printbook.router import router as printbook_router
from routers.template.router import router as template_router
from services.printbook.service import init_print_book_service
from services.template.service import init_template_service

logger = logging.getLogger("xcpc")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging()

    service = init_template_service(settings)
    logger.info("模板索引构建完成，诊断 %d 条", len(service.diagnostics()))

    init_print_book_service(settings, service)

    watcher: ContentWatcher | None = None
    if settings.watch_enabled:
        watcher = ContentWatcher(
            settings.content_dir,
            service.rebuild,
            settings.watch_debounce_seconds,
        )
        watcher.start()

    yield

    if watcher is not None:
        watcher.stop()


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
    app.include_router(template_router)
    app.include_router(printbook_router)

    # 前端构建产物存在时由后端托管（生产/桌面模式）
    if settings.frontend_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.frontend_dist, html=True),
            name="frontend",
        )

    return app


app = create_app()
