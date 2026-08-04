"""跨功能通用响应模型。

【本文件在全局中的位置】
core/exceptions.py 中的 _error_body() 拼出的错误 JSON，
结构就和这里的 ErrorResponse 一模一样：
{"error": {"code": ..., "message": ..., "detail": ...}}
前端拿到任何错误响应，都按这个结构解析。
"""

from typing import Any  # Any 表示"任意类型"的注解

from pydantic import BaseModel  # Pydantic：数据校验与序列化库


class ErrorBody(BaseModel):
    """错误内容：错误码 + 描述 + 可选细节。

    BaseModel 会自动检查字段类型：比如 code 必须是字符串。
    """

    code: str        # 机器可读的错误码，如 "not_found"
    message: str     # 给人看的错误描述
    detail: Any = None  # 额外细节（可选，默认 None）


class ErrorResponse(BaseModel):
    """最外层的错误响应：{"error": {...}}"""

    error: ErrorBody
