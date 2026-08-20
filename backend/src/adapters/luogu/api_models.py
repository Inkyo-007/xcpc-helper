"""洛谷 API 响应模型。

外部系统数据第一时间转化为 Pydantic 模型（见 docs/rules/backend.md）。
洛谷信封（`_contentOnly=1` 纯 JSON 模式）：`{code, currentTemplate,
currentData, ...}`；错误响应同为 `{code: 4xx, currentData: {...}}` 形态，
错误消息位置不稳定，adapter 对原始体做关键词扫描判语义。

容错语义：可选字段用默认值 / None 承载；类型不匹配校验失败，由 adapter
统一转为 PlatformError（平台格式异常，不阻断其他账号）。

必填字段：id（去重依据）与 submitTime（增量游标语义）——缺失即校验失败
暴露平台格式变化（submitTime 若默认 0，增量拉取会把它当作"旧于游标"
提前终止，静默丢弃后续新提交）。
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class LgProblemSummary(BaseModel):
    """记录行内嵌题目信息（difficulty 0-7 档直接内嵌，无需额外请求）。"""

    pid: str = ""
    title: str = ""
    difficulty: int | None = None


class LgContestSummary(BaseModel):
    """记录行内嵌比赛信息（非比赛内提交为 null）。"""

    id: int | None = None
    name: str = ""


class LgRecordRow(BaseModel):
    """record/list 单条记录（仅解析需要的字段，多余字段忽略）。"""

    id: int
    submitTime: int
    status: int = -1  # 缺失视为未知（-1 Unshown）→ UKE
    language: int = 0
    problem: LgProblemSummary = Field(default_factory=LgProblemSummary)
    contest: LgContestSummary | None = None
    score: int | None = None


class LgRecordPage(BaseModel):
    """records 分页容器（perPage 由服务端告知，写死会丢数据）。"""

    result: list[LgRecordRow] = Field(default_factory=list)
    count: int = 0
    perPage: int = 20


class LgRecordListData(BaseModel):
    records: LgRecordPage = Field(default_factory=LgRecordPage)


class LgRecordListEnvelope(BaseModel):
    """record/list 信封；错误体 currentData 结构不定，仅成功态强类型。"""

    code: int = 0
    currentTemplate: str = ""
    currentData: LgRecordListData | None = None


class LgUserSummary(BaseModel):
    """api/user/search 单个用户（仅解析验证需要的字段）。"""

    uid: int
    name: str = ""
    avatar: str | None = None


class LgUserSearchResult(BaseModel):
    """api/user/search 响应（裸 JSON，无信封）。"""

    users: list[LgUserSummary] = Field(default_factory=list)


# ===== 记录详情（精化用，record/:id） =====


def _normalize_nodes(data: Any) -> list[Any]:
    """subtasks / testCases 可能是数组或按编号键的 dict（d.ts 双重声明），统一为列表。"""
    if isinstance(data, dict):
        return list(data.values())
    if isinstance(data, list):
        return data
    return []


class LgTestCase(BaseModel):
    """单个测试点（status 与列表同一套官方状态码）。"""

    status: int = -1


class LgSubtask(BaseModel):
    """子任务：仅关心测试点列表（字段名为 testCases，兼容数组/dict 两种形态）。"""

    model_config = {"populate_by_name": True}

    test_cases: list[LgTestCase] = Field(default_factory=list, alias="testCases")

    @field_validator("test_cases", mode="before")
    @classmethod
    def _normalize_cases(cls, data: Any) -> list[Any]:
        return _normalize_nodes(data)


class LgJudgeResult(BaseModel):
    """评测结果：subtasks 兼容数组/dict 两种形态。"""

    subtasks: list[LgSubtask] = Field(default_factory=list)

    @field_validator("subtasks", mode="before")
    @classmethod
    def _normalize_subtasks(cls, data: Any) -> list[Any]:
        return _normalize_nodes(data)


class LgRecordDetail(BaseModel):
    """record.detail：仅取评测结果（sourceCode 等大字段忽略）。"""

    judgeResult: LgJudgeResult | None = None


class LgRecordShow(BaseModel):
    detail: LgRecordDetail | None = None


class LgRecordShowData(BaseModel):
    record: LgRecordShow = Field(default_factory=LgRecordShow)


class LgRecordDetailEnvelope(BaseModel):
    """record/:id 信封（精化只需 detail 链路）。"""

    code: int = 0
    currentData: LgRecordShowData | None = None
