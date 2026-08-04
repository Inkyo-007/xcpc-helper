"""自定义异常体系与全局异常处理器。

路由层与服务层只抛出 AppError 及其子类；
所有异常的堆栈记录与响应结构化统一由本模块的处理器完成。
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("xcpc")


class AppError(Exception):
    """业务异常基类。子类通过类属性声明 HTTP 状态码与错误码。"""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"


class ConflictError(AppError):
    """资源冲突（409）。例如新建的目录名已存在、删除非空模板。"""

    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


def _error_body(code: str, message: str, detail: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "detail": detail}}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    logger.warning("业务异常 [%s] %s", exc.code, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message, exc.detail),
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("internal_error", "服务器内部错误"),
    )


async def request_validation_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理 FastAPI 请求校验失败（请求体/查询参数不符合模型定义）。

    不交给兜底 500，而是结构化为 400，让前端能拿到可读的错误信息。
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(part) for part in first.get("loc", []))
    logger.warning("请求校验失败 [%s] %s", loc, first.get("msg"))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_body(
            "bad_request",
            f"请求参数校验失败: {loc} {first.get('msg', '')}".strip(),
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
