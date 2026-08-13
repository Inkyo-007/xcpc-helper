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
