"""洛古 API 响应模型。

外部系统数据第一时间转化为 Pydantic 模型（见 docs/rules/backend.md）。
洛古信封（`_contentOnly=1` 纯 JSON 模式）：`{code, currentTemplate,
currentData, ...}`；错误响应同为 `{code: 4xx, currentData: {...}}` 形态，
错误消息位置不稳定，adapter 对原始体做关键词扫描判语义。

容错语义：可选字段用默认值 / None 承载；类型不匹配校验失败，由 adapter
统一转为 PlatformError（平台格式异常，不阻断其他账号）。

必填字段：id（去重依据）与 submitTime（增量游标语义）——缺失即校验失败
暴露平台格式变化（submitTime 若默认 0，增量拉取会把它当作"旧于游标"
提前终止，静默丢弃后续新提交）。
"""

from pydantic import BaseModel, Field


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
