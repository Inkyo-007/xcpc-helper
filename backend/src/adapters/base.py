"""平台适配层统一契约。

平台知识只允许集中在两处：后端本目录（adapters/）与前端平台组件注册表；
router / service / modules 主干保持平台无关（不出现 if platform == "xxx" 分支）。

依赖方向严格单向：adapters 不反向依赖任何功能域（modules / services / routers）。
共享模型定义在本层，由同步引擎转换为 modules 的领域模型。

新增平台的后端成本 = 一个 adapter 目录 + adapters/__init__.py 注册一行，主干零改动。
"""

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    """判题结果（平台无关，由 adapter 完成归一化）。

    JG 表示评测中（如 Codeforces 的 SUBMITTED / TESTING）。
    """

    AC = "AC"
    WA = "WA"
    CE = "CE"
    RE = "RE"
    TLE = "TLE"
    MLE = "MLE"
    OLE = "OLE"
    UKE = "UKE"
    JG = "JG"


class Capability(str, Enum):
    """adapter 提供的数据区块能力。"""

    SUBMISSIONS = "submissions"  # 提交明细（第一期核心）
    USER_INFO = "user_info"  # 用户基本信息（绑定验证回执）
    RATING = "rating"  # rating 历史（后续增量，结构已预留）


class AuthMode(str, Enum):
    """凭据需求分类（对齐 ojhunt-lite 的 LoginType 思路）。"""

    NONE = "none"  # 匿名可取
    COOKIE = "cookie"  # 用户粘贴 cookie 授权（洛谷 / QOJ 等后续平台）


class PlatformSubmission(BaseModel):
    """平台提交记录（归一化后；不含 platform / handle，由调用方注入）。"""

    submission_id: str  # 平台内唯一提交 id（去重依据）
    problem_key: str  # 平台内题目标识（CF "2245F" / AT "abc001_a"）
    problem_name: str
    problem_url: str
    difficulty: int | None = None  # 原始难度值，不做跨平台归一
    verdict: Verdict
    submitted_at: int  # UTC 秒级时间戳
    language: str


class UserInfo(BaseModel):
    """绑定验证回执（第一期仅 handle；avatar 备用字段）。"""

    handle: str
    avatar: str | None = None


class Credentials(BaseModel):
    """平台凭据（第一期匿名平台恒为空；cookie 授权平台预留）。"""

    cookies: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


class AdapterError(Exception):
    """适配层异常基类。"""


class UserNotFoundError(AdapterError):
    """用户不存在（绑定验证失败，service 转 400）。"""


class PlatformError(AdapterError):
    """平台接口故障（限流 / 格式异常 / 网络等），sync 转该账号诊断（不阻断其他账号）。"""


class PlatformAdapter(ABC):
    """平台适配器协议。

    子类通过类属性声明元数据；verify / fetch_submissions 是全部能力的入口，
    是否具备由 capabilities 声明，service 按 capabilities 决定调用。
    """

    platform_id: str  # 注册键（与前端 PlatformId 对齐）
    name: str
    capabilities: frozenset[Capability]
    auth: AuthMode
    min_interval: float  # 平台建议请求间隔（秒），net 层限流用

    @abstractmethod
    async def verify(self, handle: str) -> UserInfo:
        """绑定验证；用户不存在抛 UserNotFoundError。仅具备 USER_INFO 能力时实现。"""

    @abstractmethod
    async def fetch_submissions(
        self,
        handle: str,
        *,
        since: int | None,
        credentials: Credentials | None = None,
    ) -> list[PlatformSubmission]:
        """拉取提交：since 为 UTC 秒级游标（None 表示全量）。

        增量语义由各平台自行解释（CF 按时间过滤、AtCoder 透传 from_second）。
        失败抛 PlatformError。
        """
