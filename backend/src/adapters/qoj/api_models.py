"""QOJ API 响应模型。

QOJ 提交记录页面为服务端渲染 HTML，非 JSON。
本模块定义 HTML 解析结果的 Pydantic 模型，用于校验提取后的数据。
"""

from pydantic import BaseModel


class QojSubmissionRow(BaseModel):
    """提交记录单条（解析 HTML 表格行后校验）。"""

    submission_id: str
    problem_id: str
    problem_name: str
    result_text: str
    language: str
    submitted_at_str: str  # YYYY-MM-DD HH:MM:SS（中国时区）
    score: float | None = None  # data-score 属性（子任务评分题）
    full_score: float | None = None  # data-full 属性（子任务评分题）
