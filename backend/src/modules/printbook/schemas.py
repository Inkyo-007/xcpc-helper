"""打印册功能的 API 请求/响应模型（对外契约，与前端 types.ts 对齐）。"""

import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ResolvedTemplateInfo(BaseModel):
    """template 块解析后携带的渲染素材（实时解析，不持久化）。"""

    name: str
    cat: str
    version_name: str
    lang: str
    file: str
    code: str
    body: str
    tags: list[str]
    src: str | None
    page: str | None
    updated: datetime.date | None
    priority: int


class HeadingBlock(BaseModel):
    id: str
    type: Literal["heading"] = "heading"
    title: str
    heading_level: int


class TemplateBlock(BaseModel):
    id: str
    type: Literal["template"] = "template"
    template: str
    version: str | None = None
    title: str | None = None
    heading_level: int
    include_body: bool | None = None
    resolved: ResolvedTemplateInfo | None = None


class MarkdownBlock(BaseModel):
    id: str
    type: Literal["markdown"] = "markdown"
    title: str | None = None
    content: str = ""


class ImageBlock(BaseModel):
    id: str
    type: Literal["image"] = "image"
    src: str
    caption: str | None = None
    width: str = "80%"


class PageBreakBlock(BaseModel):
    id: str
    type: Literal["page_break"] = "page_break"


BookBlock = Annotated[
    HeadingBlock | TemplateBlock | MarkdownBlock | ImageBlock | PageBreakBlock,
    Field(discriminator="type"),
]


class CoverPayload(BaseModel):
    title: str
    subtitle: str | None = None
    author: str | None = None
    logo: str | None = None


class OptionsPayload(BaseModel):
    include_toc: bool = True
    include_meta: bool = True
    include_body: bool = True
    h1_page_break: bool = True


class PrintBookDetail(BaseModel):
    name: str
    cover: CoverPayload
    options: OptionsPayload
    blocks: list[BookBlock]


class PrintBookSummary(BaseModel):
    name: str
    title: str
    block_count: int
    updated: str  # book.yaml 的修改时间（ISO 格式）
    error: str | None  # 配置损坏时的错误信息；不阻断列表


class PrintBookCreate(BaseModel):
    name: str
    title: str | None = None


class PrintBookUpdate(BaseModel):
    """封面/选项更新与改名；各字段独立可选。"""

    cover: CoverPayload | None = None
    options: OptionsPayload | None = None
    new_name: str | None = None


class BlocksReplace(BaseModel):
    """全量替换块列表；template 块的 resolved 会被忽略（以服务端解析为准）。"""

    blocks: list[BookBlock] = Field(default_factory=list)


class AssetUploadResponse(BaseModel):
    src: str  # 可直接渲染的资源 URL（/api/print-books/<册>/assets/...）
