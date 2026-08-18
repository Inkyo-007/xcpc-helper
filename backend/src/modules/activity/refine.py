"""精细化同步引擎：把存量 UNAC 记录逐条拉详情改写为细分结果（activity.md §6.5）。

规则与纪律：
- 启动时快照存量 UNAC（按 submitted_at 升序，从旧往新），total 固定为快照
  条数（精化途中新增的 UNAC 留下轮，进度不倒退）；
- 剩余 UNAC 即待办：中止/中断后无需额外游标，下次启动重扫自动续传；
- 每条记录处理前获取该账号的同步锁（SyncEngine 单账号锁）——普通同步
  持锁期间精化自然暂停，结束后自动继续（普通同步优先，对话确认）；
- 请求节奏由 adapter 实例级 min_interval 保证（与同步共用同一限流通道）；
- update_verdicts 是"磁盘优先不覆盖"规则的唯一受控例外（仅本引擎调用）。

状态为运行时内存态（done/total 进度），中止/完成不落库；「已完成」按
存量 UNAC 清零计算（重启后自动恢复正确形态）。
"""

import asyncio
import logging
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from adapters.base import (
    AdapterError,
    AuthExpiredError,
    Capability,
    PlatformAdapter,
    Verdict,
)
from modules.activity import store as activity_store
from modules.activity.sync import SyncEngine

logger = logging.getLogger("xcpc.activity.refine")

# 连续平台故障容忍度：单条失败跳过本条，连续失败达到上限判系统性故障中止本轮
MAX_CONSECUTIVE_FAILURES = 3


class RefineState(str, Enum):
    """精化运行状态（运行时内存态；「已完成」由存量清零推断，不在此列）。"""

    IDLE = "idle"  # 未运行（含从未启动与中止后的静态）
    RUNNING = "running"
    STOPPED = "stopped"  # 本轮被中止（保留进度；再次启动自动续扫）


class RefineProgress(BaseModel):
    """精化进度（对外 DTO 由 schemas 组装）。"""

    state: RefineState = RefineState.IDLE
    done: int = 0
    total: int = 0
    error: str | None = None


class RefineEngine:
    """按账号的精化调度（service 单例持有；与 SyncEngine 共享账号锁）。"""

    def __init__(
        self,
        store_root: Path,
        adapters: dict[str, PlatformAdapter],
        sync_engine: SyncEngine,
    ) -> None:
        self._root = store_root
        self._adapters = adapters
        self._sync = sync_engine
        self._progress: dict[tuple[str, str, str], RefineProgress] = {}
        self._stop_flags: dict[tuple[str, str, str], asyncio.Event] = {}
        self._tasks: dict[tuple[str, str, str], asyncio.Task] = {}

    def _store(self, user_id: str) -> activity_store.UserStore:
        return activity_store.UserStore(self._root, user_id)

    # ===== 状态查询 =====

    def progress_of(self, user_id: str, platform: str, handle: str) -> RefineProgress:
        """运行态进度；未运行时按存量 UNAC 计算 total（供前端预估耗时）。"""
        key = (user_id, platform, handle)
        current = self._progress.get(key)
        if current is not None:
            return current
        store = self._store(user_id)
        items, _ = store.load_submissions(platform, handle)
        remaining = sum(1 for s in items if s.verdict == Verdict.UNAC)
        return RefineProgress(state=RefineState.IDLE, done=0, total=remaining)

    # ===== 启动 / 中止 =====

    def is_running(self, user_id: str, platform: str, handle: str) -> bool:
        return self.progress_of(user_id, platform, handle).state == RefineState.RUNNING

    def start(self, user_id: str, platform: str, handle: str) -> bool:
        """启动精化（已在运行返回 False；否则后台任务，返回 True）。

        能力校验由调用方（service）完成；快照与扫描在任务内进行。
        """
        key = (user_id, platform, handle)
        if self.is_running(user_id, platform, handle):
            return False
        self._stop_flags[key] = asyncio.Event()
        self._progress[key] = RefineProgress(state=RefineState.RUNNING, done=0, total=0)
        self._tasks[key] = asyncio.create_task(self._run(user_id, platform, handle))
        return True

    def stop(self, user_id: str, platform: str, handle: str) -> None:
        """中止：状态立即翻转为 stopped（前端即时反馈），后台任务在记录粒度
        退出（在飞的一条最多多完成一次写入，无害）；未运行为空操作。"""
        key = (user_id, platform, handle)
        flag = self._stop_flags.get(key)
        if flag is not None:
            flag.set()
        progress = self._progress.get(key)
        if progress is not None and progress.state == RefineState.RUNNING:
            progress.state = RefineState.STOPPED

    def drop_account(self, user_id: str, platform: str, handle: str) -> None:
        """解绑/换绑时清理该账号的精化运行时状态。"""
        self.stop(user_id, platform, handle)
        key = (user_id, platform, handle)
        self._progress.pop(key, None)
        self._stop_flags.pop(key, None)
        self._tasks.pop(key, None)

    def drop_user(self, user_id: str) -> None:
        """删除用户组时清理其全部精化运行时状态。"""
        stale = [key for key in self._progress if key[0] == user_id]
        for _u, platform, handle in stale:
            self.drop_account(user_id, platform, handle)

    # ===== 执行 =====

    async def _run(self, user_id: str, platform: str, handle: str) -> None:
        key = (user_id, platform, handle)
        adapter = self._adapters.get(platform)
        store = self._store(user_id)
        progress = self._progress[key]
        stop = self._stop_flags[key]
        try:
            if adapter is None or Capability.REFINE_VERDICT not in adapter.capabilities:
                raise AdapterError(f"平台 {platform} 不支持精细化同步")
            credentials = store.get_account_credentials(platform, handle)
            # 快照存量 UNAC（从旧往新；total 固定，途中新增留下轮）
            items, _ = store.load_submissions(platform, handle)
            todos = [
                s.submission_id
                for s in sorted(items, key=lambda s: s.submitted_at)
                if s.verdict == Verdict.UNAC
            ]
            progress.total = len(todos)
            failures = 0
            for sid in todos:
                if stop.is_set():
                    progress.state = RefineState.STOPPED
                    return
                # 与普通同步协同：逐条获取账号锁（普通同步持锁则精化暂停）
                async with self._sync.account_lock(user_id, platform, handle):
                    if stop.is_set():
                        progress.state = RefineState.STOPPED
                        return
                    try:
                        verdict = await adapter.fetch_submission_verdict(
                            sid, credentials
                        )
                    except AuthExpiredError:
                        raise  # 凭据失效直接中止（与同步同处置：重新授权）
                    except AdapterError as exc:
                        # 单条失败跳过本条；连续失败判系统性故障中止本轮
                        failures += 1
                        logger.warning(
                            "精化单条失败 [%s/%s] %s: %s", platform, handle, sid, exc
                        )
                        if failures >= MAX_CONSECUTIVE_FAILURES:
                            raise
                        progress.done += 1
                        continue
                failures = 0
                if verdict is not None:
                    store.update_verdicts(platform, handle, {sid: verdict})
                progress.done += 1
            # 快照全部处理完
            progress.state = RefineState.IDLE
            progress.error = None
        except AdapterError as exc:
            logger.warning("精化中止 [%s/%s/%s] %s", user_id, platform, handle, exc)
            progress.state = RefineState.STOPPED
            progress.error = str(exc)
        except Exception as exc:  # 兜底降级，不让后台任务悬空
            logger.exception("精化意外异常 [%s/%s/%s]", user_id, platform, handle)
            progress.state = RefineState.STOPPED
            progress.error = str(exc)
        finally:
            # 防陈旧任务覆写：stop 后可能已 restart（新 progress/新 task 在档），
            # 仅当注册的还是本任务时才移除
            if self._tasks.get(key) is asyncio.current_task():
                self._tasks.pop(key, None)
