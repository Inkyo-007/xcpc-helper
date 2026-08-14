"""平台适配层统一契约。

平台知识只允许集中在两处：后端本目录（adapters/）与前端平台组件注册表；
router / service / modules 主干保持平台无关（不出现 if platform == "xxx" 分支）。

依赖方向严格单向：adapters 不反向依赖任何功能域（modules / services / routers）。
共享模型定义在本层，由同步引擎转换为 modules 的领域模型。

新增平台的后端成本 = 一个 adapter 目录 + adapters/__init__.py 注册一行，主干零改动。

能力方法（verify / fetch_submissions / fetch_rating_history / fetch_contests）
均为普通方法，基类默认抛 CapabilityNotSupportedError：能力残缺的平台只实现
capabilities 声明的方法，不被迫写空壳；正常路径由 service 按 capabilities
决定调用，触发默认抛错即编程错误，直接暴露。
"""

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
    CONTESTS = "contests"  # 比赛信息（平台级，未来 contest 功能消费）


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
    difficulty: int | str | None = None  # 原始难度值，不做跨平台归一（CF 分数 / LC 档位）
    verdict: Verdict
    submitted_at: int  # UTC 秒级时间戳
    language: str


class UserInfo(BaseModel):
    """绑定验证回执（handle 为平台内 API 主键，display_name 为展示名）。

    洛古等平台 API 主键（uid 数字）与展示名（用户名）分离；
    无分离需求的平台不填 display_name，前端回退显示 handle。
    """

    handle: str
    display_name: str | None = None
    avatar: str | None = None


class RatingPoint(BaseModel):
    """平台 rating 历史单点（CF user.rating / AtCoder history/json 均能归一）。"""

    time: int  # UTC 秒级时间戳（该场比赛）
    rating: int  # 该场比赛后的 rating
    contest_name: str  # 比赛名


class ContestInfo(BaseModel):
    """平台比赛信息（平台级数据，无 handle）。"""

    contest_id: str
    name: str
    start_time: int  # UTC 秒
    duration_seconds: int  # 比赛时长（秒）
    url: str | None = None


class Credentials(BaseModel):
    """平台凭据（第一期匿名平台恒为空；cookie 授权平台预留）。

    cookies 由 net 层统一应用到请求（httpx cookies 参数），
    headers 与调用方显式传入的请求头合并（调用方优先），
    adapter 不自行拼 Cookie 头。
    """

    cookies: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


class AdapterError(Exception):
    """适配层异常基类。"""


class UserNotFoundError(AdapterError):
    """用户不存在（绑定验证失败，service 转 400）。"""


class PlatformError(AdapterError):
    """平台接口故障（限流 / 格式异常 / 网络等），sync 转该账号诊断（不阻断其他账号）。"""


class HttpStatusError(PlatformError):
    """平台返回 4xx 等不可重试 HTTP 状态码（net 层抛出）。

    携带 status_code，供 adapter 区分语义：如 AtCoder 用户主页 404 表示
    用户不存在（转 UserNotFoundError），其余 4xx 维持平台故障处置。
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthExpiredError(AdapterError):
    """平台凭据失效（cookie 过期等），需引导用户重新授权（与平台故障处置路径不同）。"""


class CapabilityNotSupportedError(AdapterError):
    """平台未声明对应能力却调用了该方法（契约违约，正常路径不触发）。"""


class PlatformAdapter:
    """平台适配器协议。

    子类通过类属性声明元数据；能力方法是否可用由 capabilities 声明，
    service / sync 按 capabilities 决定调用。基类默认实现抛
    CapabilityNotSupportedError，子类只覆盖自己声明过的能力。
    """

    platform_id: str  # 注册键（与前端 PlatformId 对齐）
    name: str
    capabilities: frozenset[Capability]
    auth: AuthMode
    min_interval: float  # 平台建议请求间隔（秒），net 层限流用

    async def verify(
        self, handle: str, credentials: Credentials | None = None
    ) -> UserInfo:
        """绑定验证；用户不存在抛 UserNotFoundError。仅具备 USER_INFO 能力时实现。"""
        raise CapabilityNotSupportedError(f"{self.platform_id} 不支持绑定验证")

    async def fetch_submissions(
        self,
        handle: str,
        *,
        since: int | None,
        credentials: Credentials | None = None,
        full_window_days: int,
        full_min_rows: int,
    ) -> list[PlatformSubmission]:
        """拉取提交：since 为 UTC 秒级游标（None 表示全量）。

        增量语义由各平台自行解释（CF 按时间过滤、AtCoder 透传 from_second）。
        full_window_days / full_min_rows 为同步策略（来自上层配置，
        如热力图窗口），由调用方传入，adapter 不内置产品策略。
        失败抛 PlatformError。仅具备 SUBMISSIONS 能力时实现。
        """
        raise CapabilityNotSupportedError(f"{self.platform_id} 不支持提交明细")

    async def fetch_rating_history(
        self, handle: str, credentials: Credentials | None = None
    ) -> list[RatingPoint]:
        """rating 历史（后续增量）。仅具备 RATING 能力时实现。"""
        raise CapabilityNotSupportedError(f"{self.platform_id} 不支持 rating 历史")

    async def fetch_contests(self) -> list[ContestInfo]:
        """比赛信息（平台级数据，未来 contest 功能消费）。仅具备 CONTESTS 能力时实现。"""
        raise CapabilityNotSupportedError(f"{self.platform_id} 不支持比赛信息")
