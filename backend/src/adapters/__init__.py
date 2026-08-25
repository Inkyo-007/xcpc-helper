"""平台适配层（顶层，跨功能复用：未来比赛功能共用）。

显式注册表：新增平台 = 一个 adapter 目录 + 此处注册一行，静态可查、不用自动发现。
adapter 只允许被 modules/activity/sync.py 与 services/activity/service.py 触碰。
"""

from adapters.atcoder import AtCoderAdapter
from adapters.base import (
    AdapterError,
    AuthMode,
    Capability,
    Credentials,
    HttpStatusError,
    PlatformAdapter,
    PlatformError,
    PlatformSubmission,
    SyncBatch,
    UserInfo,
    UserNotFoundError,
    Verdict,
)
from adapters.codeforces import CodeforcesAdapter
from adapters.leetcode_cn import LeetCodeCNAdapter
from adapters.luogu import LuoguAdapter
from adapters.net import HttpFetcher
from adapters.nowcoder import NowcoderAdapter
from adapters.qoj import QOJAdapter
from adapters.vjudge import VJudgeAdapter

REGISTRY: dict[str, type[PlatformAdapter]] = {
    CodeforcesAdapter.platform_id: CodeforcesAdapter,
    AtCoderAdapter.platform_id: AtCoderAdapter,
    LuoguAdapter.platform_id: LuoguAdapter,
    NowcoderAdapter.platform_id: NowcoderAdapter,
    LeetCodeCNAdapter.platform_id: LeetCodeCNAdapter,
    VJudgeAdapter.platform_id: VJudgeAdapter,
    QOJAdapter.platform_id: QOJAdapter,
}

__all__ = [
    "REGISTRY",
    "AdapterError",
    "AtCoderAdapter",
    "AuthMode",
    "Capability",
    "CodeforcesAdapter",
    "Credentials",
    "HttpFetcher",
    "HttpStatusError",
    "LeetCodeCNAdapter",
    "LuoguAdapter",
    "NowcoderAdapter",
    "PlatformAdapter",
    "PlatformError",
    "PlatformSubmission",
    "QOJAdapter",
    "SyncBatch",
    "UserInfo",
    "UserNotFoundError",
    "VJudgeAdapter",
    "Verdict",
]
