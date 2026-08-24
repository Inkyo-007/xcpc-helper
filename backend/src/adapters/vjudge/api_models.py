"""VJudge API 响应模型。

VJudge /user/submissions 返回 JSON 信封 {data: [...], error: null}，
data 为二维数组，每行是提交记录的各字段。
"""

from pydantic import BaseModel, Field


class VjSubmissionRow(BaseModel):
    """单条提交记录（VJudge data 数组的一行）。

    VJudge 返回的数组顺序（从 ojhunt-lite 参考实现确认）：
    [0] runId, [1] OJId, [2] probNum, [3] result, [4] language,
    [5] time(ms), [6] memory(KB), [7] length, [8] submitTime(ms), ...
    """

    run_id: int = Field(alias="runId")
    oj_id: str = Field(alias="ojId")
    prob_num: str = Field(alias="probNum")
    result: str
    language: str
    time_ms: int = Field(alias="timeMs")
    memory_kb: int = Field(alias="memoryKb")
    length: int
    submit_time_ms: int = Field(alias="submitTimeMs")


class VjSubmissionsEnvelope(BaseModel):
    """/user/submissions 响应信封。"""

    data: list[list] = Field(default_factory=list)
    error: dict | None = None
