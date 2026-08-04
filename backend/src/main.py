"""FastAPI 应用入口。

开发：cd backend && uv run uvicorn --app-dir src main:app --reload
生产：前端构建后由本应用托管 frontend/dist，一行启动。

【初学者导读】
这是整个后端第一个被执行的文件（uvicorn 启动时会找到本文件的 app 变量）。
阅读顺序建议：
1. 先看最下面 create_app()：搭出应用骨架（中间件、异常处理、路由）
2. 再看 lifespan()：应用启动和关闭时各做什么
3. 最后看 import 进来的各层模块（core/ -> services/ -> routers/）
"""

import logging
from collections.abc import AsyncIterator  # 异步迭代器类型（lifespan 返回类型注解用）
from contextlib import asynccontextmanager  # 装饰器：把异步生成器函数变成"异步上下文管理器"

from fastapi import FastAPI  # Web 框架本体：FastAPI 应用类
from fastapi.middleware.cors import CORSMiddleware  # 跨域中间件
from fastapi.staticfiles import StaticFiles  # 静态文件托管（托管前端构建产物）

from core.config import get_settings
from core.exceptions import register_exception_handlers
from core.logging import setup_logging
from modules.template.watcher import ContentWatcher
from routers.template.router import router as template_router
from services.template.service import init_template_service

logger = logging.getLogger("xcpc")


# @asynccontextmanager：异步版的 @contextmanager。
# lifespan 是 FastAPI 的"生命周期钩子"：
# yield 之前的代码在应用启动时执行，yield 之后的代码在应用关闭时执行。
# async/await 是异步语法，表示这个函数执行中可以"让出"去处理其他请求。
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用启动/关闭时各做什么（FastAPI 自动调用）。

    启动：初始化日志 -> 创建模板服务并首次建索引 -> 启动文件监听
    关闭：停止文件监听
    """
    settings = get_settings()
    setup_logging()

    # 创建全局服务实例，并完成首次扫描 + 索引重建（第一个请求不必等待建索引）
    service = init_template_service(settings)
    logger.info("模板索引构建完成，诊断 %d 条", len(service.diagnostics()))

    watcher: ContentWatcher | None = None
    if settings.watch_enabled:
        # 创建监听器：content/ 目录变化时调用 service.rebuild 重建索引
        watcher = ContentWatcher(
            settings.content_dir,
            service.rebuild,
            settings.watch_debounce_seconds,
        )
        watcher.start()

    yield  # 应用正常运行期间，函数停在这里

    # 应用关闭时（Ctrl+C 等）继续执行到这里：先停掉监听线程，干净退出
    if watcher is not None:
        watcher.stop()


def create_app() -> FastAPI:
    """搭出 FastAPI 应用：中间件、异常处理器、路由、静态文件。"""
    settings = get_settings()
    # FastAPI 应用的标题会显示在自动生成的 API 文档页（/docs）
    app = FastAPI(title="XCPC Helper", lifespan=lifespan)

    # CORS 中间件：浏览器默认禁止跨域请求，
    # 这里显式允许前端开发服务器（localhost:5173）访问本后端
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],  # 允许所有 HTTP 方法（GET/POST/...）
        allow_headers=["*"],  # 允许所有请求头
    )
    # 注册全局异常处理器（见 core/exceptions.py）：
    # 任何层抛出异常，都会变成统一格式的 JSON 错误响应
    register_exception_handlers(app)
    # 挂载模板路由：/api/templates、/api/categories 等接口全部生效
    app.include_router(template_router)

    # 前端构建产物存在时由后端托管（生产/桌面模式）：
    # 访问 / 时直接返回 frontend/dist 里的页面，前后端共用一个端口
    if settings.frontend_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.frontend_dist, html=True),
            name="frontend",
        )

    return app


# uvicorn 启动命令里写的是 main:app，指向的就是这个变量
app = create_app()
