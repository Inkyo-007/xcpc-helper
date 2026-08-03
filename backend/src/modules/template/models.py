"""模板功能的内部领域模型（扫描/解析产物）。

这些模型描述 content/ 目录被解析后的内存结构，
与 API 对外契约（schemas.py）和索引存储（repository.py）分离。
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DEFAULT_PRIORITY = 2


class ReadmeMeta(BaseModel):
    """README.md front matter 元数据。

    除规范字段外允许额外字段（如 cplx），保证向前兼容。
    """

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    updated: datetime.date | None = None
    tags: list[str] = []
    source: str | None = None
    page: str | None = None
    priority: int = DEFAULT_PRIORITY
    cplx: str | None = None


class VersionNode(BaseModel):
    """一个模板版本（副标签）。单版本模板同样用一个 VersionNode 表示。"""

    slug: str  # 副标签目录名；单版本（文件直接在模板目录下）时为空字符串
    name: str  # 显示名：副标签目录名，单版本时为模板目录名
    lang: str
    file: str
    code: str
    meta: ReadmeMeta
    body: str  # README 正文（front matter 之后的 Markdown）


class TemplateNode(BaseModel):
    """一份模板（主标签），id 为 "<分类目录名>/<模板目录名>"。"""

    id: str
    category: str
    slug: str  # 模板目录名（主标签）
    versions: list[VersionNode]


class Diagnostic(BaseModel):
    """扫描诊断：格式问题不阻断整体加载，逐条上报给前端。"""

    level: Literal["error", "warning"]
    path: str  # 相对 content/ 的路径
    message: str


class ScanResult(BaseModel):
    templates: list[TemplateNode]
    diagnostics: list[Diagnostic]
