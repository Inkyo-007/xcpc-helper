"""activity 领域模型（存储层）。

activity 不使用 SQLite（业务数据以 git 管理的文件目录为事实来源，
SQLite 仅作索引/缓存用途），故 models.py 存放 Pydantic 领域模型，
对外 API 契约见 schemas.py。
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from adapters.base import Verdict

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
    """已绑定账号；last_synced_at 兼作增量同步游标（数据水位，UTC 秒）。"""

    platform: str
    handle: str
    last_synced_at: int | None = None  # null = 从未同步成功


class Profile(BaseModel):
    """用户组档案 + 账号绑定（profile.json）。"""

    id: str
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
