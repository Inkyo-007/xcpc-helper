"""模板功能的内部领域模型（扫描/解析产物）。

这些模型描述 content/ 目录被解析后的内存结构，
与 API 对外契约（schemas.py）和索引存储（repository.py）分离。

【初学者导读】
扫描器（scanner.py）读完磁盘上的模板文件后，在内存里长什么样？
就由本文件的 5 个类来描述。可以把它理解为"程序内部的草稿纸格式"：
scanner 往里面填数据，repository 再从里面取数据写进数据库。
"""

import datetime
from typing import Literal  # Literal：限定取值只能是某几个字面量

from pydantic import BaseModel, ConfigDict

DEFAULT_PRIORITY = 2  # README 没写 priority 时用的默认优先级


class ReadmeMeta(BaseModel):
    """README.md front matter 元数据。

    每个模板目录下的 README.md 开头可以有一段 YAML 元数据，例如：

        ---
        updated: 2026-08-01
        tags: [数据结构, 区间查询]
        priority: 5
        source: https://example.com
        page: https://example.com/article
        ---

    显示名取自目录名，无需 title 字段；允许规范之外的额外字段，保证向前兼容。
    """

    # extra="allow"：README 里写了模型之外的字段也不报错（比如未来新增字段）
    model_config = ConfigDict(extra="allow")

    updated: datetime.date | None = None  # 最近更新日期，可留空
    tags: list[str] = []  # 标签列表，可留空
    source: str | None = None  # 出处链接（网站）
    page: str | None = None  # 原文页面链接
    priority: int = DEFAULT_PRIORITY  # 排序优先级，越大越靠前


class VersionNode(BaseModel):
    """一个模板版本（副标签）。单版本模板同样用一个 VersionNode 表示。"""

    slug: str  # 副标签目录名；单版本（文件直接在模板目录下）时为空字符串
    name: str  # 显示名：副标签目录名，单版本时为模板目录名
    lang: str  # 语言，如 cpp / py / java
    file: str  # 代码文件名，如 segtree_lazy.cpp
    code: str  # 代码全文
    meta: ReadmeMeta  # 该版本 README 里的元数据
    body: str  # README 正文（front matter 之后的 Markdown）


class TemplateNode(BaseModel):
    """一份模板（主标签），id 为 "<分类目录名>/<模板目录名>"。

    例如 content/数据结构/线段树/ 扫描后得到的 id 是 "数据结构/线段树"。
    一份模板可以有多个版本（versions）。
    """

    id: str
    category: str  # 分类目录名，如 "数据结构"
    slug: str  # 模板目录名（主标签），如 "线段树"
    versions: list[VersionNode]


class Diagnostic(BaseModel):
    """扫描诊断：格式问题不阻断整体加载，逐条上报给前端。

    设计原则：某个模板文件格式有问题，不应该让整个服务起不来，
    而是记一条诊断继续扫描，前端可以在"诊断"页面看到并修复。
    """

    level: Literal["error", "warning"]  # 严重级别：只能是 "error" 或 "warning"
    path: str  # 相对 content/ 的路径，指出问题发生在哪
    message: str  # 具体的问题描述


class ScanResult(BaseModel):
    """一次完整扫描的最终产物：模板列表 + 诊断列表。"""

    templates: list[TemplateNode]
    diagnostics: list[Diagnostic]
