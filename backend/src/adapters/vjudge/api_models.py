"""VJudge API 响应模型。

VJudge /status/data 返回 DataTables 格式 JSON：
{data: [...], recordsTotal: N, recordsFiltered: N, draw: 1}
data 为对象数组，每个对象是一条提交记录的各字段。
"""

from pydantic import BaseModel, Field


class VjSubmissionItem(BaseModel):
    """单条提交记录（/status/data 响应 data 数组的一项）。"""

    run_id: int = Field(alias="runId")
    oj: str
    prob_num: str = Field(alias="probNum")
    status: str
    language: str
    language_canonical: str = Field(alias="languageCanonical", default="")
    time: int  # 毫秒级时间戳
    memory: int
    runtime: int = Field(alias="runtime", default=0)
    source_length: int = Field(alias="sourceLength", default=0)
    user_name: str = Field(alias="userName", default="")
    user_id: int = Field(alias="userId", default=0)


class VjStatusDataEnvelope(BaseModel):
    """/status/data 响应信封（DataTables 格式）。"""

    data: list[dict] = Field(default_factory=list)
    records_total: int = Field(alias="recordsTotal", default=0)
    records_filtered: int = Field(alias="recordsFiltered", default=0)
    draw: int = 0
