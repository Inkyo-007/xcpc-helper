"""增量同步引擎：游标推进、去重合并、单账号锁、失败隔离。

adapter 拉取 → 领域转换（补 platform / handle）→ store 去重合并 → 游标推进。
单账号失败只降级为该账号的诊断（SyncStatus.error），不阻断其他账号，
遵循 conventions.md「诊断不阻断」哲学。
"""

import asyncio
import logging
from datetime import datetime

from adapters.base import AdapterError, PlatformAdapter
from core.exceptions import NotFoundError
from modules.activity import store as activity_store
from modules.activity.models import Account, Submission, SyncState, SyncStatus

logger = logging.getLogger("xcpc.activity.sync")


class SyncEngine:
    """账号同步调度（service 单例持有）。"""

    def __init__(
        self,
        store: activity_store.UserStore,
        adapters: dict[str, PlatformAdapter],
    ) -> None:
        self._store = store
        self._adapters = adapters
        # 内存态：账号同步状态与单账号并发锁（重启后按 profile 游标续增量）
        self._status: dict[tuple[str, str], SyncStatus] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    # ===== 状态查询 =====

    def statuses(self) -> list[SyncStatus]:
        return list(self._status.values())

    def status_of(self, platform: str, handle: str) -> SyncStatus:
        return self._status.get(
            (platform, handle), SyncStatus(platform=platform, handle=handle)
        )

    def drop_status(self, platform: str, handle: str) -> None:
        """解绑时清理该账号的运行时状态。"""
        self._status.pop((platform, handle), None)
        self._locks.pop((platform, handle), None)

    # ===== 同步 =====

    async def sync_account(self, platform: str, handle: str) -> SyncStatus:
        """同步单个账号（绑定首次同步 / 手动同步共用），返回最新状态。

        同账号并发触发串行化；已在同步中的触发直接返回 running 状态。
        """
        key = (platform, handle)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            current = self._status.get(key)
            if current is not None and current.state == SyncState.RUNNING:
                return current
            self._status[key] = SyncStatus(
                platform=platform, handle=handle, state=SyncState.RUNNING
            )
            try:
                await self._run_sync(platform, handle)
            except AdapterError as exc:
                # 平台故障（网络/限流/格式等）：降级为该账号诊断，不抛出
                logger.warning("同步失败 [%s/%s] %s", platform, handle, exc)
                self._status[key] = SyncStatus(
                    platform=platform,
                    handle=handle,
                    state=SyncState.ERROR,
                    error=str(exc),
                )
            return self._status[key]

    def mark_error(self, platform: str, handle: str, error: str) -> None:
        """把账号置为错误状态（service 兜底：sync_account 之外的意外异常）。"""
        self._status[(platform, handle)] = SyncStatus(
            platform=platform, handle=handle, state=SyncState.ERROR, error=error
        )

    async def _run_sync(self, platform: str, handle: str) -> None:
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise NotFoundError(f"不支持的平台: {platform}")
        profile = self._store.load_profile()
        account = next(
            (
                acc
                for acc in profile.accounts
                if acc.platform == platform and acc.handle == handle
            ),
            None,
        )
        if account is None:
            raise NotFoundError(f"账号未绑定: {platform}/{handle}")
        since = account.last_synced_at
        raw = await adapter.fetch_submissions(handle, since=since)
        submissions = [
            Submission(platform=platform, handle=handle, **item.model_dump())
            for item in raw
        ]
        self._store.merge_submissions(platform, handle, submissions)
        # 游标推进：取最大值防倒退；无新提交时保持原游标（空账号不落 0 游标）
        new_cursor = max((s.submitted_at for s in submissions), default=0)
        if new_cursor > (since or 0):
            self._store.save_account(
                Account(platform=platform, handle=handle, last_synced_at=new_cursor)
            )
        self._status[(platform, handle)] = SyncStatus(
            platform=platform,
            handle=handle,
            state=SyncState.IDLE,
            last_synced_at=datetime.now().astimezone(),
        )
