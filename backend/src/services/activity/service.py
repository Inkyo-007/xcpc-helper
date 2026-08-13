"""activity 业务编排门面：账号 CRUD / 绑定验证、触发同步、聚合读取。

依赖方向严格单向 routers → services → modules → adapters；
adapter 只允许被本服务与 modules/activity/sync.py 触碰。
第一期固定 default 用户组（存储层带 userid 维度，API 不暴露用户组管理）。
"""

import asyncio
import logging
from datetime import datetime, tzinfo

from adapters import REGISTRY, HttpFetcher
from adapters.base import PlatformAdapter, PlatformError, UserNotFoundError
from core.config import Settings, get_settings
from core.exceptions import BadGatewayError, BadRequestError, NotFoundError
from modules.activity import aggregate
from modules.activity import store as activity_store
from modules.activity.models import DEFAULT_USER_ID, Account, Submission
from modules.activity.schemas import (
    BindIn,
    BoundAccountOut,
    DayActivityOut,
    OverviewOut,
    OverviewTotalsOut,
    PlatformMetaOut,
    PlatformsOut,
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
        self._store = activity_store.UserStore(settings.user_data_dir, DEFAULT_USER_ID)
        self._engine = SyncEngine(self._store, self._adapters)

    async def aclose(self) -> None:
        await self._fetcher.aclose()

    def _adapter(self, platform: str) -> PlatformAdapter:
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise BadRequestError(f"不支持的平台: {platform}")
        return adapter

    # ===== 平台元数据 =====

    def platforms(self) -> PlatformsOut:
        profile = self._store.load_profile()
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
                    account=self._account_out(account) if account else None,
                )
            )
        return PlatformsOut(platforms=metas)

    def _account_out(self, account: Account) -> BoundAccountOut:
        status = self._engine.status_of(account.platform, account.handle)
        last_sync_at = status.last_synced_at
        if last_sync_at is None and account.last_synced_at:
            # 重启后内存状态缺失：以档案游标（最近成功同步的数据水位）近似展示
            last_sync_at = datetime.fromtimestamp(account.last_synced_at).astimezone()
        return BoundAccountOut(
            platform=account.platform,
            handle=account.handle,
            lastSyncAt=last_sync_at,
            syncState=status.state.value,
            syncError=status.error,
        )

    # ===== 绑定验证 =====

    async def verify(self, payload: VerifyIn) -> VerifyOut:
        adapter = self._adapter(payload.platform)
        handle = payload.handle.strip()
        if not handle:
            raise BadRequestError("请输入平台用户名")
        try:
            info = await adapter.verify(handle)
        except UserNotFoundError as exc:
            raise BadRequestError(str(exc)) from exc
        except PlatformError as exc:
            raise BadGatewayError(f"平台暂时不可用：{exc}") from exc
        return VerifyOut(platform=payload.platform, handle=info.handle, avatar=info.avatar)

    # ===== 绑定 / 解绑 =====

    async def bind(self, payload: BindIn) -> BoundAccountOut:
        self._adapter(payload.platform)
        handle = payload.handle.strip()
        if not handle:
            raise BadRequestError("请输入平台用户名")
        # 换绑：每个平台每用户组只保留一个账号，旧账号连同本地数据删除
        profile = self._store.load_profile()
        for acc in profile.accounts:
            if acc.platform == payload.platform:
                self._store.remove_account(acc.platform, acc.handle)
                self._engine.drop_status(acc.platform, acc.handle)
                break
        account = Account(platform=payload.platform, handle=handle)
        self._store.save_account(account)
        # 首次同步后台异步执行，前端轮询 /sync/status
        asyncio.create_task(self._safe_sync(payload.platform, handle))
        return self._account_out(account)

    def unbind(self, platform: str, handle: str) -> None:
        self._adapter(platform)
        handle = handle.strip()
        profile = self._store.load_profile()
        if not any(
            acc.platform == platform and acc.handle == handle
            for acc in profile.accounts
        ):
            raise NotFoundError(f"账号未绑定: {platform}/{handle}")
        self._store.remove_account(platform, handle)
        self._engine.drop_status(platform, handle)

    # ===== 聚合读取 =====

    def _submissions(self, platform: str | None) -> list[Submission]:
        """当前用户组全部账号（可按平台过滤）的提交合并。

        读取时经 adapter 规范化题目外链（历史旧格式幂等迁移，见
        PlatformAdapter.normalize_url），保证前端拿到当前格式链接。
        """
        profile = self._store.load_profile()
        out: list[Submission] = []
        for acc in profile.accounts:
            if platform is not None and acc.platform != platform:
                continue
            items, skipped = self._store.load_submissions(acc.platform, acc.handle)
            if skipped:
                logger.warning(
                    "提交数据 %d 行损坏被跳过 [%s/%s]",
                    skipped,
                    acc.platform,
                    acc.handle,
                )
            adapter = self._adapters.get(acc.platform)
            if adapter is not None:
                for s in items:
                    s.problem_url = adapter.normalize_url(s.problem_url)
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
                DayActivityOut(**d) for d in aggregate.daily_series(submissions, tz=tz)
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
        profile = self._store.load_profile()
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
            await self._engine.sync_account(platform, handle)
        except Exception as exc:  # 兜底降级，见 sync()
            logger.exception("同步意外异常 [%s/%s]", platform, handle)
            self._engine.mark_error(platform, handle, str(exc))

    def sync_status(self) -> list[BoundAccountOut]:
        profile = self._store.load_profile()
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
