"""自定义异常体系与全局异常处理器。

路由层与服务层只抛出 AppError 及其子类；
所有异常的堆栈记录与响应结构化统一由本模块的处理器完成。

【本文件在全局中的位置】
1. main.py 启动时调用 register_exception_handlers(app) 注册三个处理器；
2. 之后任何层抛出 AppError（如 NotFoundError），FastAPI 会自动
   把异常交给 app_error_handler，返回统一结构的 JSON 错误响应；
3. 请求参数校验失败交给 request_validation_handler（返回 400）；
4. 其他意料之外的异常由 unhandled_error_handler 兜底返回 500。
业务代码因此完全不需要自己写 try/except 拼错误 JSON。
"""

import logging
from typing import Any  # 类型：Any 表示"什么类型都可以"

from fastapi import FastAPI, Request, status  # status 提供 HTTP 状态码常量，如 status.HTTP_404_NOT_FOUND
from fastapi.exceptions import RequestValidationError  # FastAPI 在请求参数校验失败时抛出的异常
from fastapi.responses import JSONResponse  # FastAPI 的 JSON 响应类

logger = logging.getLogger("xcpc")  # 拿到名为 "xcpc" 的日志器，用于记录异常


class AppError(Exception):
    """业务异常基类。子类通过类属性声明 HTTP 状态码与错误码。

    设计思路：业务代码只负责抛出"发生了什么错"（如 NotFoundError），
    具体"转成哪个 HTTP 状态码、什么 JSON 格式"由子类的类属性 +
    下面的全局处理器统一决定，业务代码不用关心。
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR  # 默认 500，子类覆盖
    code: str = "internal_error"  # 错误码字符串，子类覆盖

    def __init__(self, message: str, *, detail: Any = None) -> None:
        # super().__init__(message) 调用父类 Exception 的构造函数
        # * 后面的参数只能用关键字传入，即必须写 detail=xxx
        super().__init__(message)
        self.message = message  # 给人看的错误描述
        self.detail = detail    # 额外的错误细节（可选）


class NotFoundError(AppError):
    """资源不存在（404）。例如 service 找不到某个模板 id 时抛出。"""

    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class BadRequestError(AppError):
    """请求参数有误（400）。"""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"


class ConflictError(AppError):
    """资源冲突（409）。例如新建的目录名已存在、删除非空模板。"""

    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


def _error_body(code: str, message: str, detail: Any = None) -> dict[str, Any]:
    """拼出统一的错误响应结构：
    {"error": {"code": ..., "message": ..., "detail": ...}}
    """
    return {"error": {"code": code, "message": message, "detail": detail}}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """处理业务异常（AppError 及其子类）。

    第一个参数 _ 是 FastAPI 传入的请求对象，这里用不到，
    变量名以下划线开头表示"刻意忽略"。
    """
    # 业务异常只记录 warning 级别，不需要打印堆栈
    logger.warning("业务异常 [%s] %s", exc.code, exc.message)
    return JSONResponse(
        status_code=exc.status_code,  # 从异常对象的类属性拿 HTTP 状态码
        content=_error_body(exc.code, exc.message, exc.detail),
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """兜底处理器：所有未被业务代码预料的异常都会走到这里。"""
    # logger.exception 会记录完整堆栈，方便排查真正的 bug
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
    # exc.errors() 返回所有校验错误的列表；这里只取第一条展示给用户
    errors = exc.errors()
    first = errors[0] if errors else {}
    # loc 是出错字段的路径，例如 ['body', 'name']，这里用 "." 拼成 "body.name"
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
    """把三个处理器注册到 FastAPI 应用上（main.py 在启动时调用一次）。"""
    # add_exception_handler(异常类型, 处理函数)：
    # 以后任何层抛出该类型异常，FastAPI 都会自动调用对应的处理函数
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)