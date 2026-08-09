"""导入/导出 API 路由。

路由层保持薄：上传读取字节流、下载拼 Content-Disposition，
业务全部在 service（同步实现，经 asyncio.to_thread 避免阻塞事件循环）。
"""

import asyncio
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Response, UploadFile

from modules.transfer.schemas import (
    BookAnalyzeResult,
    ImportApplyInput,
    ImportReport,
    TemplateAnalyzeResult,
)
from services.transfer.service import TransferService, get_transfer_service

router = APIRouter(prefix="/api/transfer", tags=["transfer"])

ServiceDep = Annotated[TransferService, Depends(get_transfer_service)]


def _zip_response(data: bytes, stem: str) -> Response:
    """zip 下载响应：文件名带日期，Content-Disposition 按 RFC 5987 编码。"""
    filename = f"{stem}-{datetime.now(UTC).astimezone():%Y%m%d}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/export/templates")
async def export_templates(service: ServiceDep) -> Response:
    """GET /api/transfer/export/templates：导出模板库 zip（标准三层结构）。"""
    data = await asyncio.to_thread(service.export_templates)
    return _zip_response(data, "xcpc-templates")


@router.get("/export/books")
async def export_books(service: ServiceDep) -> Response:
    """GET /api/transfer/export/books：导出所有打印册 zip。"""
    data = await asyncio.to_thread(service.export_books)
    return _zip_response(data, "xcpc-books")


@router.get("/export/books/{name}")
async def export_book(name: str, service: ServiceDep) -> Response:
    """GET /api/transfer/export/books/{name}：导出单册 zip。"""
    data = await asyncio.to_thread(service.export_books, name)
    return _zip_response(data, f"xcpc-book-{name}")


@router.post("/import/templates/analyze", response_model=TemplateAnalyzeResult)
async def analyze_templates(
    service: ServiceDep, file: Annotated[UploadFile, File()]
) -> TemplateAnalyzeResult:
    """POST .../import/templates/analyze：上传 zip，返回识别结果与暂存 id。"""
    data = await file.read()
    return await asyncio.to_thread(service.analyze_templates, data)


@router.post("/import/templates/apply", response_model=ImportReport)
async def apply_templates(
    payload: ImportApplyInput, service: ServiceDep
) -> ImportReport:
    """POST .../import/templates/apply：按冲突策略执行导入，返回报告。"""
    return await asyncio.to_thread(service.apply_templates, payload)


@router.post("/import/books/analyze", response_model=BookAnalyzeResult)
async def analyze_books(
    service: ServiceDep, file: Annotated[UploadFile, File()]
) -> BookAnalyzeResult:
    """POST .../import/books/analyze：上传册包，返回册清单与暂存 id。"""
    data = await file.read()
    return await asyncio.to_thread(service.analyze_books, data)


@router.post("/import/books/apply", response_model=ImportReport)
async def apply_books(payload: ImportApplyInput, service: ServiceDep) -> ImportReport:
    """POST .../import/books/apply：按冲突策略执行册导入，返回报告。"""
    return await asyncio.to_thread(service.apply_books, payload)
