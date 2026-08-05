"""模板功能的 API 请求/响应模型（对外契约）。

【初学者导读】
models.py 是程序内部用的结构，本文件是"给前端看"的结构。
两者分开的好处：内部结构随便改，对外接口保持稳定。
FastAPI 路由函数上的 response_model=... 就用这里的类，
返回的 JSON 字段名、类型都由这里决定。
本文件后半部分（可视化增删改的输入模型）则是前端发给后端的请求体结构。
"""

import datetime
from typing import Literal  # Literal：限定取值只能是某几个字面量

from pydantic import BaseModel

# 排序方式：只能是这三个字符串之一（前端传错会被 FastAPI 自动拒绝）
SortMode = Literal["updated", "name", "priority"]


class CategoryInfo(BaseModel):
    """分类信息：前端侧边栏每个分类项。"""

    id: str  # 分类目录名
    name: str  # 显示名（目前与目录名一致，预留中文显示名扩展）
    count: int  # 该分类下的模板数


class TemplateSummary(BaseModel):
    """列表页摘要：不含代码与说明正文。

    列表页一次要显示几十份模板，所以只返回概要字段，
    代码（code）和说明（body）要到详情页（TemplateDetail）才返回。
    """

    id: str  # 模板唯一标识，如 "数据结构/线段树"
    name: str  # 显示名（模板目录名）
    cat: str  # 所属分类
    lang: str | None  # 主版本语言；空模板（无版本）时为 None
    file: str | None  # 主版本文件名；空模板（无版本）时为 None
    tags: list[str]  # 所有版本标签的并集
    src: str | None  # 出处链接
    page: str | None  # 原文页面链接
    updated: datetime.date | None  # 最近更新日期
    priority: int  # 优先级（排序用）
    variant_count: int  # 版本数量（多版本时前端显示页签）


class TemplateVersion(BaseModel):
    """详情页中的一个版本（副标签）。body 为该版本 README 正文。"""

    id: str
    name: str
    lang: str
    file: str
    code: str  # 代码全文（详情页才返回）
    body: str  # 该版本的说明正文
    tags: list[str]
    src: str | None
    page: str | None
    updated: datetime.date | None
    priority: int


class TemplateDetail(TemplateSummary):
    """模板详情：继承摘要的全部字段，再补充说明正文与版本列表。

    class A(B) 是"继承"：TemplateDetail 自动拥有 TemplateSummary 的所有字段。
    """

    desc: str  # 主版本 README 正文（Markdown）
    variants: list[TemplateVersion]


class DiagnosticItem(BaseModel):
    """一条扫描诊断（前端"诊断"页面每行的结构）。"""

    level: Literal["error", "warning"]
    path: str
    message: str


class DiagnosticsResponse(BaseModel):
    """诊断列表接口的响应：{"items": [...]}"""

    items: list[DiagnosticItem]


class ReloadResponse(BaseModel):
    """手动重建索引接口的响应：模板数 + 诊断数。"""

    templates: int
    diagnostics: int


# ===== 可视化增删改的输入模型 =====

# 寻址"顶层单版本"（代码直接在模板目录下）时 URL 中使用的保留版本名。
# 顶层版本没有副标签名，但 URL 又必须有这个位置，
# 所以约定用 "~" 代替，服务层再把它翻译成空字符串 ""。
ROOT_VERSION_TOKEN = "~"


class TemplateCreate(BaseModel):
    """新建空主标签的请求体：仅需分类与模板名。"""

    category: str  # 分类名（目录名）
    name: str  # 模板名（目录名）


class TemplateRename(BaseModel):
    """主标签重命名/换分类的请求体。两个字段至少填一个。

    new_category：新的分类名；new_name：新的模板名。
    都为 None 时表示不改（写操作层会视为无操作）。
    """

    new_category: str | None = None
    new_name: str | None = None


class VersionMetaInput(BaseModel):
    """版本元数据输入：与 README front matter 一一对应。

    前端表单填的这些字段，会由 writer.render_readme() 转成 README 头部 YAML。
    """

    updated: datetime.date | None = None  # 更新日期，可留空
    tags: list[str] = []  # 标签列表
    source: str | None = None  # 出处链接（网站）
    page: str | None = None  # 原文页面链接
    priority: int = 2  # 优先级，默认 2


class VersionUpsert(BaseModel):
    """新建/更新版本的请求体。

    name：副标签名。新建时必填（一律建为副标签子目录）；
    更新时可选，用于副标签改名（顶层单版本不支持改名）。
    file：代码文件名，可选，默认为 code.<ext>。
    ext：代码扩展名（不含点，大小写不敏感），如 cpp / c / py / java。
    """

    name: str | None = None
    file: str | None = None
    ext: str
    code: str
    meta: VersionMetaInput = VersionMetaInput()
    body: str = ""