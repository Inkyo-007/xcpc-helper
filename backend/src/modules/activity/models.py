"""activity 领域模型（存储层）。

activity 不使用 SQLite（业务数据以 git 管理的文件目录为事实来源，
SQLite 仅作索引/缓存用途），故 models.py 存放 Pydantic 领域模型，
对外 API 契约见 schemas.py。
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from adapters.base import Credentials, Verdict

# 第一期固定用户组（服务层与 API 不暴露用户组管理，存储层带维度）
DEFAULT_USER_ID = "default"


class Submission(BaseModel):
    """归一化提交记录（存储与 API 共用，JSONL 每行一条）。"""

    platform: str
    handle: str
    submission_id: str  # 平台内唯一提交 id（去重依据）
    problem_key: str
    problem_name: str
    problem_url: str
    difficulty: int | None = None
    verdict: Verdict
    submitted_at: int  # UTC 秒级时间戳
    language: str


class Account(BaseModel):
    """已绑定账号；last_synced_at 兼作增量同步游标（数据水位，UTC 秒）。

    handle 为平台内 API 主键（洛谷为 uid 数字），display_name 为展示名
    （洛谷用户名等，仅展示用途，可为空则前端回退显示 handle）。

    注意区分两个时间：last_synced_at 是**数据水位**（已拉取数据新到
    哪个时刻，用于增量游标），last_sync_ok_at 是**最近一次同步成功的
    真实时刻**（用于"xx 前同步"展示）——混用会让重启后/同步中的
    标签显示成数据水龄（如 71 天前最后一次提交被显示为 71 天前同步）。
    """

    platform: str
    handle: str
    last_synced_at: int | None = None  # null = 从未同步成功
    display_name: str | None = None  # 展示名（与 API 主键分离）
    last_sync_ok_at: int | None = None  # 最近一次同步成功时刻（UTC 秒；与游标分离）


class Secrets(BaseModel):
    """账号凭据（secrets.json，gitignore 仅存本机）：platform → handle → 凭据。

    与 profile.json 分离存储：账号元数据可入档，凭据永不入 git；
    解绑/换绑/删除用户组时同步清理。
    """

    platforms: dict[str, dict[str, Credentials]] = Field(default_factory=dict)


class Profile(BaseModel):
    """用户组档案（profile.json）：信息卡 ID/签名/头像 + 账号绑定。

    信息栏 ID（id 字段）与用户组名称（目录名）分离：新建组时初始化为
    目录名，之后独立编辑，重命名组不改变信息卡 ID。
    """

    id: str = ""  # 信息栏显示 ID（独立于目录名）
    signature: str = ""
    avatar: str | None = None
    accounts: list[Account] = Field(default_factory=list)


class SyncState(str, Enum):
    """账号同步状态（运行时内存态，不入库）。"""

    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


class SyncStatus(BaseModel):
    """单账号同步状态（service 内存态，供 /sync/status 与 /platforms 组装）。"""

    platform: str
    handle: str
    state: SyncState = SyncState.IDLE
    last_synced_at: datetime | None = None  # 最近一次同步结束时间（本地时区）
    error: str | None = None
    error_code: str | None = None  # 结构化错误码（如 auth_expired，供前端分处置路径）
    progress: float | None = None  # 同步进度 0~1（总量可知的平台上报；None = 不定态）
