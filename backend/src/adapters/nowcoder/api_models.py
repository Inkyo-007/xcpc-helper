"""牛客 API 响应模型。

牛客 practice-coding 页面为服务端渲染 HTML，非 JSON。
本模块定义 HTML 解析结果的 Pydantic 模型，用于校验提取后的数据。
"""

from pydantic import BaseModel, Field


class NcSubmissionRow(BaseModel):
    """practice-coding 单条提交（解析 HTML 表格行后校验）。"""

    submission_id: str
    problem_id: str
    problem_name: str
    status_text: str
    language: str
    submitted_at_str: str  # YYYY-MM-DD HH:MM:SS（中国时区）


class NcRatingHistoryEntry(BaseModel):
    """rating-history 单条记录（仅用于验证接口回执结构）。"""

    contestId: int
    rating: float
    rank: int
    changeValue: float
    time: int  # ms
    contestName: str
    colorLevel: int


class NcRatingHistoryEnvelope(BaseModel):
    """rating-history 响应信封。"""

    msg: str = ""
    code: int = 0
    data: list[NcRatingHistoryEntry] = Field(default_factory=list)
