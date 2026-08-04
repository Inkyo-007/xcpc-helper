"""模板功能的 API 请求/响应模型（对外契约）。"""

import datetime
from typing import Literal

from pydantic import BaseModel

SortMode = Literal["updated", "name", "priority"]


class CategoryInfo(BaseModel):
    id: str  # 分类目录名
    name: str  # 显示名（目前与目录名一致，预留中文显示名扩展）
    count: int  # 该分类下的模板数


class TemplateSummary(BaseModel):
    """列表页摘要：不含代码与说明正文。"""

    id: str
    name: str
    cat: str
    lang: str | None  # 空模板（无版本）时为 None
    file: str | None  # 空模板（无版本）时为 None
    tags: list[str]
    src: str | None
    page: str | None
    updated: datetime.date | None
    priority: int
    variant_count: int


class TemplateVersion(BaseModel):
    """详情页中的一个版本（副标签）。body 为该版本 README 正文。"""

    id: str
    name: str
    lang: str
    file: str
    code: str
    body: str
    tags: list[str]
    src: str | None
    page: str | None
    updated: datetime.date | None
    priority: int


class TemplateDetail(TemplateSummary):
    desc: str  # 主版本 README 正文（Markdown）
    variants: list[TemplateVersion]


class DiagnosticItem(BaseModel):
    level: Literal["error", "warning"]
    path: str
    message: str


class DiagnosticsResponse(BaseModel):
    items: list[DiagnosticItem]


class ReloadResponse(BaseModel):
    templates: int
    diagnostics: int
