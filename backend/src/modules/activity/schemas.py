"""activity API 出入参 DTO（对外契约）。

字段名与前端 features/activity/types.ts 对齐（camelCase），
避免 alias 转换开销；与内部存储模型（models.py）分离。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from adapters.base import Capability, Verdict

SyncStateOut = Literal["idle", "running", "error"]


class BoundAccountOut(BaseModel):
    """已绑定账号 + 同步状态（platforms / sync/status 共用）。"""

    platform: str
    handle: str
    lastSyncAt: datetime | None = None  # 最近一次成功同步的结束时间
    syncState: SyncStateOut = "idle"
    syncError: str | None = None
    syncErrorCode: str | None = None  # 结构化错误码（如 auth_expired），前端分处置路径


class PlatformMetaOut(BaseModel):
    """平台元数据（平台页签与绑定弹窗由它驱动）。"""

    id: str
    name: str
    capabilities: list[Capability]
    auth: str
    account: BoundAccountOut | None = None  # 该平台当前绑定账号（未绑定为 null）


class PlatformsOut(BaseModel):
    platforms: list[PlatformMetaOut]


class VerifyIn(BaseModel):
    platform: str
    handle: str
    credentials: dict[str, Any] | None = None  # 预留（cookie 授权平台验证需凭据）


class VerifyOut(BaseModel):
    """绑定验证回执（平台内用户基本信息）。"""

    platform: str
    handle: str
    avatar: str | None = None


class BindIn(BaseModel):
    platform: str
    handle: str
    credentials: dict[str, Any] | None = None  # 预留（cookie 授权平台；第一期恒为空）


class DayActivityOut(BaseModel):
    date: str  # YYYY-MM-DD（本地时区）
    submissions: int
    solved: int  # 当天 AC 的不同题目数


class OverviewTotalsOut(BaseModel):
    totalSolved: int
    totalSubmissions: int
    todaySolved: int
    weekSolved: int
    streakDays: int


class OverviewOut(BaseModel):
    totals: OverviewTotalsOut
    daily: list[DayActivityOut]  # 近约 370 天日序列，升序，末尾为今天


class SubmissionOut(BaseModel):
    """提交条目（近期提交与当日明细共用；date 字段供前端跨天合并展示）。"""

    id: str
    platform: str
    problemKey: str
    problemName: str
    problemUrl: str
    verdict: Verdict
    language: str
    time: str  # HH:mm（本地时区）
    date: str  # YYYY-MM-DD（本地时区）


class SubmissionsOut(BaseModel):
    items: list[SubmissionOut]


class SyncIn(BaseModel):
    platform: str | None = None  # 为空则同步全部账号


# ===== 用户组与信息卡 =====


class GroupOut(BaseModel):
    name: str  # 用户组名（目录名）
    current: bool


class GroupsOut(BaseModel):
    groups: list[GroupOut]


class GroupCreateIn(BaseModel):
    name: str


class GroupRenameIn(BaseModel):
    newName: str


class ProfileOut(BaseModel):
    """信息卡：显示 ID（与组名分离）/ 签名 / 头像（data URL 或 null）。"""

    id: str
    signature: str
    avatar: str | None = None


class ProfileUpdateIn(BaseModel):
    id: str | None = None
    signature: str | None = None
    avatar: str | None = None


# ===== 技能树 =====


class SkillOut(BaseModel):
    """技能节点（一个 CF 标签）。"""

    key: str  # 原 CF 标签
    name: str  # 中文名（未命中映射时为原标签）
    tag: str  # 原 CF 标签（与 key 一致，语义冗余供前端直接展示）
    proficiency: float  # 掌握度 0..1
    acCount: int  # 去重后的 AC 题数
    maxDifficulty: int | None = None  # 最高原始难度（CF rating）


class SkillDomainOut(BaseModel):
    """技能域节点。"""

    key: str
    name: str
    proficiency: float
    acCount: int
    maxDifficulty: int | None = None
    skills: list[SkillOut]


class SkillTreeTotalsOut(BaseModel):
    """技能树总计（根节点展示）。"""

    acCount: int
    proficiency: float
    maxDifficulty: int | None = None


class SkillTreeOut(BaseModel):
    domains: list[SkillDomainOut]
    totals: SkillTreeTotalsOut


# ===== 训练分析 =====


class DifficultyBandOut(BaseModel):
    """难度分档统计（label/min/max 对应 DIFFICULTY_BANDS）。"""

    label: str
    min: int | None
    max: int | None
    solvedCount: int  # 去重 AC 题数
    attemptCount: int  # 去重尝试题数（任意 verdict）
    submissionCount: int  # 该档提交总数
    passRate: float  # solvedCount / attemptCount（无尝试为 0）


class VerdictCountOut(BaseModel):
    verdict: Verdict
    count: int
    share: float  # count / total（total 为 0 时为 0）


class WeekActivityOut(BaseModel):
    weekStart: str  # 该周周一 YYYY-MM-DD（本地时区）
    solved: int  # 去重 AC 题数
    attempts: int  # 提交总数
    activeDays: int  # 有提交的不同本地日期数


class HourActivityOut(BaseModel):
    hour: int  # 0..23
    count: int  # 该小时提交数


class RhythmOut(BaseModel):
    weeks: list[WeekActivityOut]  # 近 12 周（含本周），升序，末尾为本周期
    hours: list[HourActivityOut]  # 0..23 共 24 项


class WeakPointOut(BaseModel):
    """技能薄弱点（一个 CF 标签；口径与技能树一致）。"""

    key: str  # 原 CF 标签
    name: str  # 中文名（未命中映射时为原标签）
    domainKey: str
    domainName: str
    solvedCount: int  # 去重 AC 题数
    attemptCount: int  # 去重尝试题数（任意 verdict）
    passRate: float  # solvedCount / attemptCount
    proficiency: float  # 掌握度 0..1（复用 skill_tree.proficiency）
    maxDifficulty: int | None = None  # AC 题最高原始难度
    suggestion: str  # 规则化训练建议


class AnalysisOut(BaseModel):
    difficulty: list[DifficultyBandOut]
    verdicts: list[VerdictCountOut]
    rhythm: RhythmOut
    weakPoints: list[WeakPointOut]
