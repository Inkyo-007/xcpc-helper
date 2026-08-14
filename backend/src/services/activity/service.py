"""activity 业务编排门面：用户组管理、账号 CRUD / 绑定验证、触发同步、聚合读取。

依赖方向严格单向 routers → services → modules → adapters；
adapter 只允许被本服务与 modules/activity/sync.py 触碰。

用户组 = data/user/<user_id>/ 目录（目录名即组名，支持中文）；
服务层维护"当前用户组"（单机本地应用，内存态，默认 default），
其余 API 一律作用于当前组。信息卡（ID/签名/头像）存于组内 profile.json，
与组名分离、独立编辑。
"""

import asyncio
import logging
import time
from datetime import datetime, tzinfo

from adapters import REGISTRY, HttpFetcher
from adapters.base import (
    AuthExpiredError,
    AuthMode,
    BrowserLoginCancelledError,
    Capability,
    Credentials,
    PlatformAdapter,
    PlatformError,
    UserNotFoundError,
)
from core.config import Settings, get_settings
from core.exceptions import (
    BadGatewayError,
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from modules.activity import aggregate
from modules.activity import store as activity_store
from modules.activity.models import DEFAULT_USER_ID, Account, Submission
from modules.activity.schemas import (
    BindIn,
    BoundAccountOut,
    BrowserLoginStatusOut,
    DayActivityOut,
    GroupCreateIn,
    GroupOut,
    GroupRenameIn,
    GroupsOut,
    OverviewOut,
    OverviewTotalsOut,
    PlatformMetaOut,
    PlatformsOut,
    ProfileOut,
    ProfileUpdateIn,
    SubmissionOut,
    SubmissionsOut,
    VerifyIn,
    VerifyOut,
)
from modules.activity.sync import SyncEngine

logger = logging.getLogger("xcpc.service.activity")

# 近期提交条数上限：全部历史按时间倒序取最后 N 条，
# 不按时间窗口过滤（保证"近期没做题"的账号也能看到最近记录）
RECENT_LIMIT = 200
# 信息卡头像 data URL 长度上限（512px JPEG 约 40-80KB，base64 后留足余量）
AVATAR_MAX_CHARS = 500_000
# browser-login 抓取到的凭据暂存 TTL（bind 消费，凭据不经前端）
PENDING_CREDENTIALS_TTL = 600.0
# browser-login 用户登录操作超时（秒）
BROWSER_LOGIN_TIMEOUT = 180.0


class ActivityService:
    """训练统计服务。读写均作用于 data/user/<userid>/ 文件事实来源。"""

    def __init__(
        self, settings: Settings, fetcher: HttpFetcher | None = None
    ) -> None:
        self._settings = settings
        # 测试可注入 MockTransport 的 fetcher，避免真实外呼
        self._fetcher = fetcher or HttpFetcher()
        self._adapters: dict[str, PlatformAdapter] = {
            pid: cls(self._fetcher) for pid, cls in REGISTRY.items()
        }
        self._engine = SyncEngine(
            settings.user_data_dir,
            self._adapters,
            full_window_days=settings.activity_window_days,
            full_min_rows=settings.activity_full_min_rows,
        )
        # 确保默认用户组目录存在（惰性初始化，幂等）
        if DEFAULT_USER_ID not in activity_store.list_groups(settings.user_data_dir):
            activity_store.create_group(settings.user_data_dir, DEFAULT_USER_ID)
        # 当前用户组（内存态；单机本地应用，前端切组时切换）
        self._current_group = DEFAULT_USER_ID
        # browser-login 会话状态（按平台互斥）与待消费凭据暂存（内存态，凭据不经前端）
        self._browser_logins: dict[str, BrowserLoginStatusOut] = {}
        self._pending_credentials: dict[tuple[str, str], tuple[Credentials, float]] = {}

    async def aclose(self) -> None:
        await self._fetcher.aclose()

    def _adapter(self, platform: str) -> PlatformAdapter:
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise BadRequestError(f"不支持的平台: {platform}")
        return adapter

    def _store(self) -> activity_store.UserStore:
        """当前用户组的 store。"""
        return activity_store.UserStore(
            self._settings.user_data_dir, self._current_group
        )

    def _require_group(self, name: str) -> None:
        """组存在性校验（目录即组）。"""
        if name not in activity_store.list_groups(self._settings.user_data_dir):
            raise NotFoundError(f"用户组不存在: {name}")

    # ===== 用户组管理 =====

    def groups(self) -> GroupsOut:
        root = self._settings.user_data_dir
        return GroupsOut(
            groups=[
                GroupOut(name=g, current=(g == self._current_group))
                for g in activity_store.list_groups(root)
            ]
        )

    def create_group(self, payload: GroupCreateIn) -> GroupOut:
        """新建用户组并切换过去（信息卡 ID 初始为组名，之后独立编辑）。"""
        name = activity_store.create_group(
            self._settings.user_data_dir, payload.name.strip()
        )
        self._current_group = name
        return GroupOut(name=name, current=True)

    def rename_group(self, name: str, payload: GroupRenameIn) -> GroupsOut:
        """用户组目录改名（数据归属不变）；当前组被改名时同步切换。"""
        new_name = activity_store.rename_group(
            self._settings.user_data_dir, name, payload.newName.strip()
        )
        if self._current_group == name:
            self._current_group = new_name
        return self.groups()

    def delete_group(self, name: str) -> None:
        """物理删除用户组（含全部数据）；当前组被删则回退到剩余组。"""
        remaining = activity_store.list_groups(self._settings.user_data_dir)
        if len(remaining) <= 1 and name in remaining:
            raise BadRequestError("至少保留一个用户组")
        activity_store.delete_group(self._settings.user_data_dir, name)
        self._engine.drop_user(name)
        if self._current_group == name:
            rest = activity_store.list_groups(self._settings.user_data_dir)
            self._current_group = rest[0] if rest else DEFAULT_USER_ID

    def switch_group(self, name: str) -> GroupOut:
        """切换当前用户组。"""
        self._require_group(name)
        self._current_group = name
        return GroupOut(name=name, current=True)

    # ===== 信息卡（profile）=====

    def current_profile(self) -> ProfileOut:
        profile = self._store().load_profile()
        return ProfileOut(
            id=profile.id, signature=profile.signature, avatar=profile.avatar
        )

    def update_profile(self, payload: ProfileUpdateIn) -> ProfileOut:
        profile = self._store().load_profile()
        if payload.id is not None:
            profile.id = payload.id.strip()
        if payload.signature is not None:
            profile.signature = payload.signature.strip()
        # avatar 用 fields_set 判断：显式传 null 表示清除头像
        if "avatar" in payload.model_fields_set:
            avatar = payload.avatar
            if avatar is not None and len(avatar) > AVATAR_MAX_CHARS:
                raise BadRequestError("头像文件过大，请换一张小一点的图片")
            profile.avatar = avatar or None
        self._store().save_profile(profile)
        return ProfileOut(
            id=profile.id, signature=profile.signature, avatar=profile.avatar
        )

    # ===== 平台元数据 =====

    def platforms(self) -> PlatformsOut:
        profile = self._store().load_profile()
        metas: list[PlatformMetaOut] = []
        for pid, adapter in self._adapters.items():
            account = next(
                (acc for acc in profile.accounts if acc.platform == pid), None
            )
            metas.append(
                PlatformMetaOut(
                    id=pid,
                    name=adapter.name,
                    capabilities=sorted(adapter.capabilities, key=lambda c: c.value),
                    auth=adapter.auth.value,
                    browserLogin=self._browser_login_available(adapter),
                    account=self._account_out(account) if account else None,
                )
            )
        return PlatformsOut(platforms=metas)

    @staticmethod
    def _browser_login_available(adapter: PlatformAdapter) -> bool:
        """一键登录可用 = cookie 平台 + adapter 实现可选契约 + Playwright 已安装。"""
        if adapter.auth != AuthMode.COOKIE:
            return False
        probe = getattr(adapter, "browser_login_available", None)
        return bool(probe and probe())

    def _account_out(self, account: Account) -> BoundAccountOut:
        status = self._engine.status_of(
            self._current_group, account.platform, account.handle
        )
        last_sync_at = status.last_synced_at
        if last_sync_at is None and account.last_synced_at:
            # 重启后内存状态缺失：以档案游标（最近成功同步的数据水位）近似展示
            last_sync_at = datetime.fromtimestamp(account.last_synced_at).astimezone()
        return BoundAccountOut(
            platform=account.platform,
            handle=account.handle,
            displayName=account.display_name,
            lastSyncAt=last_sync_at,
            syncState=status.state.value,
            syncError=status.error,
            syncErrorCode=status.error_code,
        )

    # ===== 绑定验证 =====

    async def verify(self, payload: VerifyIn) -> VerifyOut:
        adapter = self._adapter(payload.platform)
        if Capability.USER_INFO not in adapter.capabilities:
            raise BadRequestError(f"平台 {payload.platform} 不支持绑定验证")
        handle = payload.handle.strip()
        if not handle:
            raise BadRequestError("请输入平台用户名")
        credentials = (
            Credentials.model_validate(payload.credentials)
            if payload.credentials
            else None
        )
        # cookie 授权平台：验证即需凭据（存在性校验 + 凭据有效性试拉）
        if adapter.auth == AuthMode.COOKIE and credentials is None:
            raise BadRequestError(f"平台 {payload.platform} 需要登录凭据（cookie）")
        try:
            info = await adapter.verify(handle, credentials)
        except UserNotFoundError as exc:
            raise BadRequestError(str(exc)) from exc
        except AuthExpiredError as exc:
            # 凭据在绑定当下即无效：转 400 引导重新录入，不放行死凭据
            raise BadRequestError(str(exc)) from exc
        except PlatformError as exc:
            raise BadGatewayError(f"平台暂时不可用：{exc}") from exc
        return VerifyOut(
            platform=payload.platform,
            handle=info.handle,
            displayName=info.display_name,
            avatar=info.avatar,
        )

    # ===== 浏览器一键登录（cookie 平台） =====

    async def start_browser_login(self, platform: str) -> None:
        """启动浏览器登录会话（202 立即返回，前端轮询 status）。

        会话按平台互斥；凭据抓取成功后由 adapter 完成验证并暂存
        （PENDING_CREDENTIALS_TTL），bind 时消费——凭据不经前端。
        """
        adapter = self._adapter(platform)
        if adapter.auth != AuthMode.COOKIE:
            raise BadRequestError(f"平台 {platform} 无需浏览器登录")
        runner = getattr(adapter, "run_browser_login", None)
        if runner is None:
            raise BadRequestError(f"平台 {platform} 不支持浏览器登录")
        if not self._browser_login_available(adapter):
            raise BadRequestError(
                "一键登录不可用（未安装 browser-login 依赖），请改用手动粘贴 cookie"
            )
        current = self._browser_logins.get(platform)
        if current is not None and current.state == "waiting":
            raise ConflictError("已有进行中的登录会话，请先完成或关闭登录窗口")
        self._browser_logins[platform] = BrowserLoginStatusOut(state="waiting")
        asyncio.create_task(self._run_browser_login(platform, adapter))

    def browser_login_status(self, platform: str) -> BrowserLoginStatusOut:
        """查询登录会话状态（无会话时返回 error 引导重新发起）。"""
        self._adapter(platform)
        return self._browser_logins.get(
            platform,
            BrowserLoginStatusOut(state="error", error="无进行中的登录会话"),
        )

    async def _run_browser_login(self, platform: str, adapter: PlatformAdapter) -> None:
        try:
            credentials, info = await adapter.run_browser_login(  # type: ignore[attr-defined]
                timeout=BROWSER_LOGIN_TIMEOUT
            )
            key = (platform, info.handle)
            self._pending_credentials[key] = (
                credentials,
                time.monotonic() + PENDING_CREDENTIALS_TTL,
            )
            self._browser_logins[platform] = BrowserLoginStatusOut(
                state="success",
                handle=info.handle,
                displayName=info.display_name,
                avatar=info.avatar,
            )
        except BrowserLoginCancelledError:
            self._browser_logins[platform] = BrowserLoginStatusOut(state="canceled")
        except TimeoutError:
            self._browser_logins[platform] = BrowserLoginStatusOut(state="timeout")
        except PlatformError as exc:
            logger.warning("浏览器登录失败 [%s] %s", platform, exc)
            self._browser_logins[platform] = BrowserLoginStatusOut(
                state="error", error=str(exc)
            )
        except Exception as exc:  # 兜底降级，不让后台任务悬空
            logger.exception("浏览器登录意外异常 [%s]", platform)
            self._browser_logins[platform] = BrowserLoginStatusOut(
                state="error", error=str(exc)
            )

    def _take_pending_credentials(
        self, platform: str, handle: str
    ) -> Credentials | None:
        """消费 browser-login 暂存凭据（一次性；过期即弃）。"""
        key = (platform, handle)
        entry = self._pending_credentials.pop(key, None)
        if entry is None:
            return None
        credentials, expires_at = entry
        if time.monotonic() > expires_at:
            return None
        return credentials

    # ===== 绑定 / 解绑 =====

    async def bind(self, payload: BindIn) -> BoundAccountOut:
        adapter = self._adapter(payload.platform)
        handle = payload.handle.strip()
        if not handle:
            raise BadRequestError("请输入平台用户名")
        credentials = (
            Credentials.model_validate(payload.credentials)
            if payload.credentials
            else None
        )
        # cookie 授权平台：显式凭据优先，否则消费 browser-login 暂存凭据
        if adapter.auth == AuthMode.COOKIE and credentials is None:
            credentials = self._take_pending_credentials(payload.platform, handle)
        if adapter.auth == AuthMode.COOKIE and credentials is None:
            raise BadRequestError(
                f"平台 {payload.platform} 需要登录凭据（一键登录或粘贴 cookie）"
            )
        store = self._store()
        # 换绑：每个平台每用户组只保留一个账号，旧账号连同本地数据与凭据删除
        profile = store.load_profile()
        for acc in profile.accounts:
            if acc.platform == payload.platform:
                store.remove_account(acc.platform, acc.handle)
                self._engine.drop_status(
                    self._current_group, acc.platform, acc.handle
                )
                break
        account = Account(
            platform=payload.platform,
            handle=handle,
            display_name=(payload.displayName or "").strip() or None,
        )
        store.save_account(account)
        if credentials is not None:
            store.save_account_secrets(payload.platform, handle, credentials)
        # 首次同步后台异步执行，前端轮询 /sync/status
        asyncio.create_task(self._safe_sync(payload.platform, handle))
        return self._account_out(account)

    def unbind(self, platform: str, handle: str) -> None:
        self._adapter(platform)
        handle = handle.strip()
        store = self._store()
        profile = store.load_profile()
        if not any(
            acc.platform == platform and acc.handle == handle
            for acc in profile.accounts
        ):
            raise NotFoundError(f"账号未绑定: {platform}/{handle}")
        store.remove_account(platform, handle)
        self._engine.drop_status(self._current_group, platform, handle)

    # ===== 聚合读取 =====

    def _submissions(self, platform: str | None) -> list[Submission]:
        """当前用户组全部账号（可按平台过滤）的提交合并。"""
        store = self._store()
        profile = store.load_profile()
        out: list[Submission] = []
        for acc in profile.accounts:
            if platform is not None and acc.platform != platform:
                continue
            items, skipped = store.load_submissions(acc.platform, acc.handle)
            if skipped:
                logger.warning(
                    "提交数据 %d 行损坏被跳过 [%s/%s]",
                    skipped,
                    acc.platform,
                    acc.handle,
                )
            out.extend(items)
        return out

    def overview(self, platform: str | None) -> OverviewOut:
        if platform is not None:
            self._adapter(platform)
        submissions = self._submissions(platform)
        tz = datetime.now().astimezone().tzinfo
        return OverviewOut(
            totals=OverviewTotalsOut(**aggregate.overview_stats(submissions, tz=tz)),
            daily=[
                DayActivityOut(**d)
                for d in aggregate.daily_series(
                    submissions, tz=tz, days=self._settings.activity_window_days
                )
            ],
        )

    def submissions(
        self, *, date: str | None, platform: str | None
    ) -> SubmissionsOut:
        if platform is not None:
            self._adapter(platform)
        submissions = self._submissions(platform)
        tz = datetime.now().astimezone().tzinfo
        if date is not None:
            # 当日明细（按本地日期过滤）
            items = [
                s
                for s in submissions
                if datetime.fromtimestamp(s.submitted_at, tz=tz).strftime("%Y-%m-%d")
                == date
            ]
        else:
            # 近期提交：全部历史按时间倒序，取最后 RECENT_LIMIT 条
            items = sorted(
                submissions, key=lambda s: s.submitted_at, reverse=True
            )[:RECENT_LIMIT]
        return SubmissionsOut(items=[self._submission_out(s, tz) for s in items])

    @staticmethod
    def _submission_out(s: Submission, tz: tzinfo) -> SubmissionOut:
        dt = datetime.fromtimestamp(s.submitted_at, tz=tz)
        return SubmissionOut(
            id=s.submission_id,
            platform=s.platform,
            problemKey=s.problem_key,
            problemName=s.problem_name,
            problemUrl=s.problem_url,
            verdict=s.verdict,
            language=s.language,
            time=dt.strftime("%H:%M"),
            date=dt.strftime("%Y-%m-%d"),
        )

    # ===== 同步 =====

    async def sync(self, platform: str | None) -> None:
        if platform is not None:
            self._adapter(platform)
        profile = self._store().load_profile()
        targets = [
            (acc.platform, acc.handle)
            for acc in profile.accounts
            if platform is None or acc.platform == platform
        ]
        for p, h in targets:
            # 兜底包装：任何意外异常都降级为该账号诊断，不让后台任务悬空
            asyncio.create_task(self._safe_sync(p, h))

    async def _safe_sync(self, platform: str, handle: str) -> None:
        try:
            await self._engine.sync_account(self._current_group, platform, handle)
        except Exception as exc:  # 兜底降级，见 sync()
            logger.exception("同步意外异常 [%s/%s]", platform, handle)
            self._engine.mark_error(self._current_group, platform, handle, str(exc))

    def sync_status(self) -> list[BoundAccountOut]:
        profile = self._store().load_profile()
        return [self._account_out(acc) for acc in profile.accounts]


# 依赖注入

_service: ActivityService | None = None


def init_activity_service(settings: Settings | None = None) -> ActivityService:
    """应用启动时调用：创建服务与适配器实例。"""
    global _service
    _service = ActivityService(settings or get_settings())
    return _service


def get_activity_service() -> ActivityService:
    """FastAPI 依赖：获取全局服务实例。"""
    if _service is None:
        raise RuntimeError("ActivityService 尚未初始化")
    return _service
