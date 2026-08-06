"""打印册功能的内部领域模型（books/ 目录存储结构）。

与 API 对外契约（schemas.py）分离：存储模型不含解析产物
（template 块的 resolved 不持久化，每次读取实时解析）；
字段缺省即默认，YAML 保持干净；规范之外的字段静默忽略
（与模板 README 元数据的约定一致）。
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class BookCover(BaseModel):
    """封面配置（固定版式）；title 缺省时由服务层回填为册名。"""

    model_config = ConfigDict(extra="ignore")

    title: str = ""
    subtitle: str | None = None
    author: str | None = None
    logo: str | None = None  # 相对册目录的路径（assets/...）


class BookOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    include_toc: bool = True
    include_meta: bool = True
    include_body: bool = True
    h1_page_break: bool = True


class BlockBase(BaseModel):
    """块公共字段。id 为前端渲染键，手改 yaml 可缺省（读取时按位置生成）。"""

    model_config = ConfigDict(extra="ignore")

    id: str = ""


class HeadingBlockNode(BlockBase):
    """章节标题块。"""

    type: Literal["heading"] = "heading"
    title: str
    heading_level: int = 2


class TemplateBlockNode(BlockBase):
    """模板引用块：只存引用不存内容。

    version 语义：null=主版本（第一个版本，跟随模板变化）；
    '~'=显式顶层单版本；其余为副标签名。
    """

    type: Literal["template"] = "template"
    template: str  # 模板 id（<分类>/<模板名>）
    version: str | None = None
    title: str | None = None  # 册内显示名覆盖；null=用模板原名
    heading_level: int = 3
    include_body: bool | None = None  # null=跟随册级 options.include_body


class MarkdownBlockNode(BlockBase):
    """自由文字 / 文章片段块（内联 Markdown）。"""

    type: Literal["markdown"] = "markdown"
    title: str | None = None
    content: str = ""


class ImageBlockNode(BlockBase):
    """图片块。src 为相对册目录的路径（assets/...）或外部 URL。"""

    type: Literal["image"] = "image"
    src: str
    caption: str | None = None
    width: str = "80%"


class PageBreakBlockNode(BlockBase):
    """显式分页标记，无字段。"""

    type: Literal["page_break"] = "page_break"


BookBlockNode = Annotated[
    HeadingBlockNode
    | TemplateBlockNode
    | MarkdownBlockNode
    | ImageBlockNode
    | PageBreakBlockNode,
    Field(discriminator="type"),
]


class BookConfig(BaseModel):
    """book.yaml 的根结构。"""

    model_config = ConfigDict(extra="ignore")

    cover: BookCover = Field(default_factory=BookCover)
    options: BookOptions = Field(default_factory=BookOptions)
    blocks: list[BookBlockNode] = Field(default_factory=list)


class StoredBookInfo(BaseModel):
    """list_books 的逐册扫描结果；配置损坏时 config 为 None 并携带 error。"""

    name: str
    config: BookConfig | None
    error: str | None
    updated: datetime
