"""导入/导出功能的 API 请求/响应模型（对外契约）。"""

from typing import Literal

from pydantic import BaseModel

# 冲突处理策略：跳过 / 覆盖 / 自动重命名
ConflictStrategy = Literal["skip", "overwrite", "rename"]

# 归档识别类型：本软件导出的标准归档 / 外来平铺结构
ArchiveKind = Literal["standard", "foreign"]


class TransferWarning(BaseModel):
    """导入分析阶段的警告项，path 为归档内相对路径。"""

    path: str
    message: str


class TemplateAnalyzeItem(BaseModel):
    """识别出的一份模板（analyze 只读预览项）。version_count 为 0 表示空主标签。"""

    category: str
    name: str
    version_count: int
    renamed_from: str | None = None  # 名称被清洗/拆分时记录归档中的原名


class TemplateAnalyzeResult(BaseModel):
    staging_id: str
    kind: ArchiveKind
    category_count: int
    template_count: int
    templates: list[TemplateAnalyzeItem]
    warnings: list[TransferWarning]
    conflicts: list[str]  # 与现有库重名的模板 id（<分类>/<模板名>）


class BookAnalyzeItem(BaseModel):
    """识别出的一册（analyze 只读预览项）。"""

    name: str
    title: str


class BookAnalyzeResult(BaseModel):
    staging_id: str
    books: list[BookAnalyzeItem]
    warnings: list[TransferWarning]
    conflicts: list[str]  # 与现有册重名的册名


class ImportApplyInput(BaseModel):
    staging_id: str
    strategy: ConflictStrategy = "skip"


class RenamedEntry(BaseModel):
    source: str  # 归档中的标识
    target: str  # 实际落盘的标识


class FailedEntry(BaseModel):
    id: str
    message: str


class ImportReport(BaseModel):
    """导入执行报告：允许部分成功，逐项记录去向。"""

    created: list[str] = []
    skipped: list[str] = []
    overwritten: list[str] = []
    renamed: list[RenamedEntry] = []
    failed: list[FailedEntry] = []
