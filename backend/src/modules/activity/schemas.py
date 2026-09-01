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
    displayName: str | None = None  # 展示名（洛谷用户名等；空则前端回退 handle）
    lastSyncAt: datetime | None = None  # 最近一次成功同步的结束时间
    syncState: SyncStateOut = "idle"
    syncError: str | None = None
    syncErrorCode: str | None = None  # 结构化错误码（如 auth_expired），前端分处置路径
    syncProgress: float | None = None  # 同步进度 0~1（None = 总量未知，前端显示不定态）


class PlatformMetaOut(BaseModel):
    """平台元数据（平台页签与绑定弹窗由它驱动）。"""

    id: str
    name: str
    capabilities: list[Capability]
    auth: str
    browserLogin: bool = False  # 一键登录可用（cookie 平台 + 服务端具备 Playwright）
    homepageUrl: str = ""  # 平台主页 URL（前端跳转用）
    account: BoundAccountOut | None = None  # 该平台当前绑定账号（未绑定为 null）


class PlatformsOut(BaseModel):
    platforms: list[PlatformMetaOut]


class VerifyIn(BaseModel):
    platform: str
    handle: str
    credentials: dict[str, Any] | None = None  # cookie 授权平台验证需凭据（洛谷等）


class VerifyOut(BaseModel):
    """绑定验证回执（平台内用户基本信息）。"""

    platform: str
    handle: str
    displayName: str | None = None  # 展示名（与 API 主键分离；空回退 handle）
    avatar: str | None = None


class BindIn(BaseModel):
    platform: str
    handle: str
    displayName: str | None = None  # 验证回执带回的展示名，随绑定持久化
    credentials: dict[str, Any] | None = None  # cookie 授权平台必填（洛谷等）


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


# ===== 浏览器一键登录（cookie 平台） =====

BrowserLoginStateOut = Literal["waiting", "success", "canceled", "timeout", "error"]


class BrowserLoginStatusOut(BaseModel):
    """浏览器登录会话状态（前端轮询；成功后回执同 verify）。"""

    state: BrowserLoginStateOut
    handle: str | None = None  # 成功回执：API 主键（洛谷 uid）
    displayName: str | None = None  # 成功回执：展示名
    avatar: str | None = None
    error: str | None = None  # state=error 时的诊断信息


# ===== 精细化同步（REFINE_VERDICT 能力平台，§6.5） =====

RefineStateOut = Literal["idle", "running", "stopped", "done"]


class RefineStatusOut(BaseModel):
    """精化状态：idle 时 total = 存量 UNAC 数（供前端预估耗时）。"""

    state: RefineStateOut
    done: int = 0
    total: int = 0
    auto: bool = False  # 普通同步完成后自动启动精化


class RefineConfigIn(BaseModel):
    refineAuto: bool


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


class UpdateCredentialsIn(BaseModel):
    """更新账号凭据（仅 cookie 平台）：验证回执的 handle 必须与当前绑定一致。"""

    credentials: dict[str, Any] | None = None  # cookie 授权平台必填（一键登录时由后端消费暂存凭据）
