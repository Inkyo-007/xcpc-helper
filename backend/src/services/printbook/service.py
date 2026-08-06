"""打印册业务编排：册配置落盘 + 引用解析，依赖模板服务取最新内容。

依赖方向严格单向 printbook -> template；模板侧不感知打印册。
"""

import threading
from pathlib import Path

from core.config import Settings, get_settings
from modules.printbook import document, store
from modules.printbook.models import BookCover, BookOptions
from modules.printbook.schemas import (
    AssetUploadResponse,
    BlocksReplace,
    PrintBookCreate,
    PrintBookDetail,
    PrintBookSummary,
    PrintBookUpdate,
)
from services.template.service import TemplateService, get_template_service


class PrintBookService:
    """打印册服务。读写均作用于 books/ 目录，无缓存（文件即事实来源）。"""

    def __init__(self, settings: Settings, templates: TemplateService) -> None:
        self._settings = settings
        self._templates = templates
        self._lock = threading.RLock()

    # 查询

    def list_books(self) -> list[PrintBookSummary]:
        infos = store.list_books(self._settings.books_dir)
        return [
            PrintBookSummary(
                name=info.name,
                title=(info.config.cover.title or info.name)
                if info.config
                else info.name,
                block_count=len(info.config.blocks) if info.config else 0,
                updated=info.updated.isoformat(timespec="seconds"),
                error=info.error,
            )
            for info in infos
        ]

    def get_book(self, name: str) -> PrintBookDetail:
        config = store.load_book(self._settings.books_dir, name)
        return document.to_api_book(name, config, self._templates.get_detail)

    # 写操作

    def create_book(self, payload: PrintBookCreate) -> PrintBookDetail:
        with self._lock:
            name, config = store.create_book(
                self._settings.books_dir, payload.name, payload.title
            )
            return document.to_api_book(name, config, self._templates.get_detail)

    def update_book(self, name: str, payload: PrintBookUpdate) -> PrintBookDetail:
        """更新封面/选项，支持改名（new_name）。返回最新详情。"""
        with self._lock:
            config = store.load_book(self._settings.books_dir, name)
            if payload.cover is not None:
                config.cover = BookCover(
                    title=payload.cover.title,
                    subtitle=payload.cover.subtitle,
                    author=payload.cover.author,
                    logo=(
                        document.normalize_asset_src(name, payload.cover.logo)
                        if payload.cover.logo
                        else None
                    ),
                )
            if payload.options is not None:
                config.options = BookOptions(**payload.options.model_dump())
            new_name = name
            if payload.new_name and payload.new_name.strip() != name:
                new_name = store.rename_book(
                    self._settings.books_dir, name, payload.new_name
                )
            store.save_book(self._settings.books_dir, new_name, config)
            return document.to_api_book(new_name, config, self._templates.get_detail)

    def delete_book(self, name: str) -> None:
        with self._lock:
            store.delete_book(self._settings.books_dir, name)

    def replace_blocks(self, name: str, payload: BlocksReplace) -> PrintBookDetail:
        """全量替换块列表（排序/增删混合操作整体提交），返回最新详情。"""
        with self._lock:
            config = store.load_book(self._settings.books_dir, name)
            config.blocks = document.to_storage_blocks(name, payload.blocks)
            store.save_book(self._settings.books_dir, name, config)
            return document.to_api_book(name, config, self._templates.get_detail)

    # 图片资源

    def upload_asset(
        self, name: str, filename: str, content: bytes
    ) -> AssetUploadResponse:
        with self._lock:
            src = store.save_asset(self._settings.books_dir, name, filename, content)
        return AssetUploadResponse(src=document.expand_asset_url(name, src))

    def asset_file(self, name: str, rel: str) -> Path:
        return store.asset_file(self._settings.books_dir, name, rel)


# 依赖注入

_service: PrintBookService | None = None


def init_print_book_service(
    settings: Settings | None = None, templates: TemplateService | None = None
) -> PrintBookService:
    """应用启动时调用：在模板服务初始化之后创建打印册服务。"""
    global _service
    _service = PrintBookService(
        settings or get_settings(), templates or get_template_service()
    )
    return _service


def get_print_book_service() -> PrintBookService:
    """FastAPI 依赖：获取全局服务实例。"""
    if _service is None:
        raise RuntimeError("PrintBookService 尚未初始化")
    return _service
