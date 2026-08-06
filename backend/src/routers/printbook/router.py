"""打印册 API 路由。

路由层保持薄：参数解析 + 调用 service。service 为同步实现
（文件读写），通过 asyncio.to_thread 避免阻塞事件循环。
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import FileResponse

from modules.printbook.schemas import (
    AssetUploadResponse,
    BlocksReplace,
    PrintBookCreate,
    PrintBookDetail,
    PrintBookSummary,
    PrintBookUpdate,
)
from services.printbook.service import PrintBookService, get_print_book_service

router = APIRouter(prefix="/api/print-books", tags=["printbook"])

ServiceDep = Annotated[PrintBookService, Depends(get_print_book_service)]


@router.get("", response_model=list[PrintBookSummary])
async def list_books(service: ServiceDep) -> list[PrintBookSummary]:
    return await asyncio.to_thread(service.list_books)


@router.post("", response_model=PrintBookDetail, status_code=status.HTTP_201_CREATED)
async def create_book(payload: PrintBookCreate, service: ServiceDep) -> PrintBookDetail:
    return await asyncio.to_thread(service.create_book, payload)


@router.get("/{name}", response_model=PrintBookDetail)
async def get_book(name: str, service: ServiceDep) -> PrintBookDetail:
    return await asyncio.to_thread(service.get_book, name)


@router.put("/{name}", response_model=PrintBookDetail)
async def update_book(
    name: str, payload: PrintBookUpdate, service: ServiceDep
) -> PrintBookDetail:
    return await asyncio.to_thread(service.update_book, name, payload)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(name: str, service: ServiceDep) -> None:
    await asyncio.to_thread(service.delete_book, name)


@router.put("/{name}/blocks", response_model=PrintBookDetail)
async def replace_blocks(
    name: str, payload: BlocksReplace, service: ServiceDep
) -> PrintBookDetail:
    """全量替换块列表（排序/增删整体提交），返回最新完整详情。"""
    return await asyncio.to_thread(service.replace_blocks, name, payload)


@router.post("/{name}/assets", response_model=AssetUploadResponse)
async def upload_asset(
    name: str, file: UploadFile, service: ServiceDep
) -> AssetUploadResponse:
    """上传图片（multipart 表单字段 file），返回可直接渲染的资源 URL。"""
    content = await file.read()
    filename = file.filename or "image.png"
    return await asyncio.to_thread(service.upload_asset, name, filename, content)


@router.get("/{name}/assets/{path:path}")
async def get_asset(name: str, path: str, service: ServiceDep) -> FileResponse:
    file_path = await asyncio.to_thread(service.asset_file, name, path)
    return FileResponse(file_path)
