"""增量同步引擎：游标推进、去重合并、单账号锁、失败隔离（按用户组隔离）。

adapter 拉取 → 领域转换（补 platform / handle）→ store 去重合并 → 游标推进。
单账号失败只降级为该账号的诊断（SyncStatus.error），不阻断其他账号，
遵循 conventions.md「诊断不阻断」哲学。

运行时状态（SyncStatus / 并发锁）按 (user_id, platform, handle) 隔离，
不同用户组互不干扰；store 按组目录动态构造。
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from adapters.base import AdapterError, AuthExpiredError, PlatformAdapter
from core.exceptions import NotFoundError
from modules.activity import store as activity_store
from modules.activity.models import Account, Submission, SyncState, SyncStatus

logger = logging.getLogger("xcpc.activity.sync")


class SyncEngine:
    """账号同步调度（service 单例持有）。"""

    def __init__(
        self,
        store_root: Path,
        adapters: dict[str, PlatformAdapter],
        *,
        full_window_days: int = 370,
        full_min_rows: int = 5000,
    ) -> None:
        self._root = store_root
        self._adapters = adapters
        # 全量同步策略（来自上层配置，默认对齐热力图窗口；adapter 不内置）
        self._full_window_days = full_window_days
        self._full_min_rows = full_min_rows
        # 内存态：账号同步状态与单账号并发锁（键含 user_id，按组隔离）
        self._status: dict[tuple[str, str, str], SyncStatus] = {}
        self._locks: dict[tuple[str, str, str], asyncio.Lock] = {}

    def _store(self, user_id: str) -> activity_store.UserStore:
        return activity_store.UserStore(self._root, user_id)

    # ===== 状态查询 =====

    def statuses(self) -> list[SyncStatus]:
        return list(self._status.values())

    def status_of(self, user_id: str, platform: str, handle: str) -> SyncStatus:
        return self._status.get(
            (user_id, platform, handle),
            SyncStatus(platform=platform, handle=handle),
        )

    def drop_status(self, user_id: str, platform: str, handle: str) -> None:
        """解绑时清理该账号的运行时状态。"""
        self._status.pop((user_id, platform, handle), None)
        self._locks.pop((user_id, platform, handle), None)

    def drop_user(self, user_id: str) -> None:
        """删除用户组时清理其全部运行时状态。"""
        stale = [key for key in self._status if key[0] == user_id]
        for key in stale:
            self._status.pop(key, None)
            self._locks.pop(key, None)

    # ===== 同步 =====

    async def sync_account(
        self, user_id: str, platform: str, handle: str
    ) -> SyncStatus:
        """同步单个账号（绑定首次同步 / 手动同步共用），返回最新状态。

        同账号并发触发串行化；已在同步中的触发直接返回 running 状态。
        """
        key = (user_id, platform, handle)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            current = self._status.get(key)
            if current is not None and current.state == SyncState.RUNNING:
                return current
            self._status[key] = SyncStatus(
                platform=platform, handle=handle, state=SyncState.RUNNING
            )
            try:
                await self._run_sync(user_id, platform, handle)
            except AuthExpiredError as exc:
                # 凭据过期：与平台故障处置路径不同，单独标记引导重新授权
                logger.warning("同步失败（凭据过期） [%s/%s/%s] %s", user_id, platform, handle, exc)
                self._status[key] = SyncStatus(
                    platform=platform,
                    handle=handle,
                    state=SyncState.ERROR,
                    error=str(exc),
                    error_code="auth_expired",
                )
            except AdapterError as exc:
                # 平台故障（网络/限流/格式等）：降级为该账号诊断，不抛出
                logger.warning("同步失败 [%s/%s/%s] %s", user_id, platform, handle, exc)
                self._status[key] = SyncStatus(
                    platform=platform,
                    handle=handle,
                    state=SyncState.ERROR,
                    error=str(exc),
                )
            return self._status[key]

    def mark_error(
        self, user_id: str, platform: str, handle: str, error: str
    ) -> None:
        """把账号置为错误状态（service 兜底：sync_account 之外的意外异常）。"""
        self._status[(user_id, platform, handle)] = SyncStatus(
            platform=platform, handle=handle, state=SyncState.ERROR, error=error
        )

    async def _run_sync(self, user_id: str, platform: str, handle: str) -> None:
        key = (user_id, platform, handle)
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise NotFoundError(f"不支持的平台: {platform}")
        store = self._store(user_id)
        profile = store.load_profile()
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
        # cookie 授权平台：从 secrets.json 加载凭据（匿名平台为 None）
        credentials = store.get_account_credentials(platform, handle)

        def _on_progress(fetched: int, total: int | None) -> None:
            """adapter 进度回调：更新 running 状态的进度（0~1，封顶防漂移）。"""
            st = self._status.get(key)
            if st is not None and st.state == SyncState.RUNNING:
                st.progress = min(fetched / total, 1.0) if total else None

        raw = await adapter.fetch_submissions(
            handle,
            since=since,
            credentials=credentials,
            full_window_days=self._full_window_days,
            full_min_rows=self._full_min_rows,
            progress_cb=_on_progress,
        )
        submissions = [
            Submission(platform=platform, handle=handle, **item.model_dump())
            for item in raw
        ]
        store.merge_submissions(platform, handle, submissions)
        # 游标推进：取最大值防倒退；无新提交时保持原游标（空账号不落 0 游标）
        new_cursor = max((s.submitted_at for s in submissions), default=0)
        if new_cursor > (since or 0):
            store.save_account(
                Account(
                    platform=platform,
                    handle=handle,
                    last_synced_at=new_cursor,
                    display_name=account.display_name,  # 游标推进不丢展示名
                )
            )
        self._status[(user_id, platform, handle)] = SyncStatus(
            platform=platform,
            handle=handle,
            state=SyncState.IDLE,
            last_synced_at=datetime.now().astimezone(),
        )
