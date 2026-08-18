"""同步引擎测试：游标推进、断点续传、去重合并、失败隔离、未绑定防护。"""

import time
from collections.abc import AsyncIterator

import pytest

from adapters.base import (
    AuthExpiredError,
    AuthMode,
    Capability,
    Credentials,
    PlatformAdapter,
    PlatformError,
    PlatformSubmission,
    SyncBatch,
    UserInfo,
)
from core.exceptions import NotFoundError
from modules.activity.models import Account, SyncState
from modules.activity.store import UserStore
from modules.activity.sync import SyncEngine


class FakeAdapter(PlatformAdapter):
    """按调用次数返回预设页（单批 done）；记录每次收到的 since 游标。"""

    platform_id = "codeforces"
    name = "Codeforces"
    capabilities = frozenset({Capability.SUBMISSIONS})
    auth = AuthMode.NONE
    min_interval = 0.0

    def __init__(self, pages: list[list[PlatformSubmission]] | None = None) -> None:
        self.pages = pages or []
        self.calls: list[int | None] = []
        self.fail_with: Exception | None = None

    async def verify(self, handle: str) -> UserInfo:
        return UserInfo(handle=handle)

    async def fetch_submissions(
        self,
        handle: str,
        *,
        since: int | None,
        credentials: Credentials | None = None,
        full_window_days: int,
        full_min_rows: int,
        progress_cb=None,
        resume_checkpoint: dict | None = None,
    ) -> AsyncIterator[SyncBatch]:
        self.calls.append(since)
        if self.fail_with is not None:
            raise self.fail_with
        if self.pages:
            yield SyncBatch(items=self.pages.pop(0), done=True)
        else:
            yield SyncBatch(done=True)


def item(sid: str, ts: int) -> PlatformSubmission:
    return PlatformSubmission(
        submission_id=sid,
        problem_key="2245A",
        problem_name="X",
        problem_url="https://codeforces.com/contest/2245/problem/A",
        verdict="AC",
        submitted_at=ts,
        language="GNU C++17",
    )


def make_engine(tmp_path, adapter: FakeAdapter) -> tuple[SyncEngine, UserStore]:
    root = tmp_path / "user"
    store = UserStore(root, "default")
    return SyncEngine(root, {"codeforces": adapter}), store


USER = "default"


async def test_first_sync_advances_cursor(tmp_path):
    adapter = FakeAdapter(pages=[[item("1", 1000), item("2", 2000)]])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    status = await engine.sync_account(USER, "codeforces", "demo")

    assert adapter.calls == [None]  # 首次全量
    assert status.state is SyncState.IDLE
    assert store.load_profile().accounts[0].last_synced_at == 2000
    items, skipped = store.load_submissions("codeforces", "demo")
    assert skipped == 0
    assert len(items) == 2


async def test_incremental_sync_uses_cursor(tmp_path):
    adapter = FakeAdapter(pages=[[item("3", 3000)]])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(
        Account(platform="codeforces", handle="demo", last_synced_at=2000)
    )

    status = await engine.sync_account(USER, "codeforces", "demo")

    assert adapter.calls == [2000]  # 增量带游标
    assert status.state is SyncState.IDLE
    assert store.load_profile().accounts[0].last_synced_at == 3000


async def test_no_new_submissions_keeps_cursor(tmp_path):
    adapter = FakeAdapter(pages=[[]])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(
        Account(platform="codeforces", handle="demo", last_synced_at=2000)
    )

    before = int(time.time())
    await engine.sync_account(USER, "codeforces", "demo")

    assert adapter.calls == [2000]
    account = store.load_profile().accounts[0]
    assert account.last_synced_at == 2000  # 游标不变
    # 无新提交也记录本次同步成功时刻（与数据水位游标分离）
    assert account.last_sync_ok_at is not None
    assert account.last_sync_ok_at >= before
    assert engine.status_of(USER, "codeforces", "demo").state is SyncState.IDLE


async def test_sync_records_ok_time_and_failure_keeps_old(tmp_path):
    """同步成功写入 last_sync_ok_at；失败保留旧值（供"xx 前同步"回退展示）。"""
    adapter = FakeAdapter(pages=[[item("1", 1000)]])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    before = int(time.time())
    await engine.sync_account(USER, "codeforces", "demo")
    account = store.load_profile().accounts[0]
    assert account.last_synced_at == 1000  # 游标 = 数据水位
    assert account.last_sync_ok_at is not None
    assert account.last_sync_ok_at >= before  # 同步时刻 = 真实时间

    adapter.fail_with = PlatformError("平台故障")
    await engine.sync_account(USER, "codeforces", "demo")
    account = store.load_profile().accounts[0]
    assert account.last_sync_ok_at is not None
    assert account.last_sync_ok_at >= before  # 失败不覆盖上次成功时刻
    assert account.last_sync_ok_at < int(time.time()) + 2


async def test_sync_progress_reported_and_cleared(tmp_path):
    """adapter 经 progress_cb 上报进度：running 状态可见 0~1，完成后清空。"""
    engine, store = make_engine(tmp_path, FakeAdapter())
    store.save_account(Account(platform="codeforces", handle="demo"))
    mid: dict[str, float | None] = {}

    class ProgressAdapter(FakeAdapter):
        async def fetch_submissions(self, handle, *, since, progress_cb=None, **kw):
            if progress_cb is not None:
                progress_cb(1, 2)
                mid["value"] = engine.status_of(USER, "codeforces", "demo").progress
            yield SyncBatch(done=True)

    engine._adapters["codeforces"] = ProgressAdapter()
    status = await engine.sync_account(USER, "codeforces", "demo")

    assert mid["value"] == 0.5  # 同步中进度
    assert status.progress is None  # 完成后清空（idle 不带进度）


async def test_failure_degrades_to_diagnostic(tmp_path):
    adapter = FakeAdapter()
    adapter.fail_with = PlatformError("Codeforces API 返回失败: limit")
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    # 失败不抛出，只降级为该账号诊断
    status = await engine.sync_account(USER, "codeforces", "demo")

    assert status.state is SyncState.ERROR
    assert "limit" in (status.error or "")
    assert store.load_profile().accounts[0].last_synced_at is None


async def test_auth_expired_marked_with_error_code(tmp_path):
    """凭据过期单独标记 error_code=auth_expired，与平台故障处置路径分开。"""
    adapter = FakeAdapter()
    adapter.fail_with = AuthExpiredError("cookie 已过期，请重新授权")
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    status = await engine.sync_account(USER, "codeforces", "demo")

    assert status.state is SyncState.ERROR
    assert status.error_code == "auth_expired"
    assert "cookie" in (status.error or "")


async def test_unbound_account_raises_not_found(tmp_path):
    adapter = FakeAdapter()
    engine, _store = make_engine(tmp_path, adapter)

    with pytest.raises(NotFoundError):
        await engine.sync_account(USER, "codeforces", "ghost")


async def test_unsupported_platform_raises(tmp_path):
    adapter = FakeAdapter()
    engine, _store = make_engine(tmp_path, adapter)

    with pytest.raises(NotFoundError):
        await engine.sync_account(USER, "luogu", "demo")


async def test_drop_status_clears_runtime(tmp_path):
    adapter = FakeAdapter(pages=[[item("1", 1000)]])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))
    await engine.sync_account(USER, "codeforces", "demo")

    engine.drop_status(USER, "codeforces", "demo")
    st = engine.status_of(USER, "codeforces", "demo")
    assert st.state is SyncState.IDLE
    assert st.last_synced_at is None


async def test_status_isolated_per_user_group(tmp_path):
    """同步状态按用户组隔离：组 A 同步不影响组 B 的状态查询。"""
    adapter = FakeAdapter(pages=[[item("1", 1000)]])
    root = tmp_path / "user"
    UserStore(root, "groupA").save_account(
        Account(platform="codeforces", handle="demo")
    )
    engine = SyncEngine(root, {"codeforces": adapter})

    await engine.sync_account("groupA", "codeforces", "demo")

    assert engine.status_of("groupA", "codeforces", "demo").state is SyncState.IDLE
    # 组 B 无任何同步记录（默认 idle、无同步时间）
    st_b = engine.status_of("groupB", "codeforces", "demo")
    assert st_b.state is SyncState.IDLE
    assert st_b.last_synced_at is None


async def test_drop_user_clears_runtime(tmp_path):
    """删除用户组时清理其全部运行时状态。"""
    adapter = FakeAdapter(pages=[[item("1", 1000)]])
    root = tmp_path / "user"
    UserStore(root, "groupA").save_account(
        Account(platform="codeforces", handle="demo")
    )
    engine = SyncEngine(root, {"codeforces": adapter})
    await engine.sync_account("groupA", "codeforces", "demo")

    engine.drop_user("groupA")
    st = engine.status_of("groupA", "codeforces", "demo")
    assert st.state is SyncState.IDLE
    assert st.last_synced_at is None


# ===== 断点续传（全量回填流式落盘） =====


class BatchAdapter(FakeAdapter):
    """按预设批次流式产出（items + checkpoint）；fail_at 批次处抛错模拟中断。"""

    def __init__(
        self,
        batches: list[tuple[list[PlatformSubmission], dict]],
        fail_at: int | None = None,
    ) -> None:
        super().__init__()
        self.batches = batches
        self.fail_at = fail_at
        self.resume_seen: list[dict | None] = []

    async def fetch_submissions(
        self, handle, *, since, resume_checkpoint=None, **kw
    ) -> AsyncIterator[SyncBatch]:
        self.calls.append(since)
        self.resume_seen.append(resume_checkpoint)
        for i, (items, checkpoint) in enumerate(self.batches):
            if self.fail_at is not None and i == self.fail_at:
                raise PlatformError("模拟中断（进程退出/平台故障）")
            yield SyncBatch(items=items, checkpoint=checkpoint, done=False)
        yield SyncBatch(done=True)


async def test_backfill_streams_batches_and_clears_checkpoint(tmp_path):
    """全量回填：每批落盘 + 断点推进，完成后清除断点并推进游标。"""
    adapter = BatchAdapter([
        ([item("1", 1000), item("2", 2000)], {"page": 2, "fetched": 2}),
        ([item("3", 500)], {"page": 3, "fetched": 3}),
    ])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    status = await engine.sync_account(USER, "codeforces", "demo")

    assert status.state is SyncState.IDLE
    assert adapter.resume_seen == [None]  # 首次全量无断点
    account = store.load_profile().accounts[0]
    assert account.sync_checkpoint is None  # 完成即清除
    assert account.last_synced_at == 2000  # 游标 = 落盘数据最大时间戳
    items, _ = store.load_submissions("codeforces", "demo")
    assert len(items) == 3


async def test_backfill_interrupt_and_resume(tmp_path):
    """中断后续传：断点透传 adapter、游标不动、重叠由 store 去重吸收。"""
    adapter = BatchAdapter(
        [
            ([item("1", 1000), item("2", 2000)], {"page": 2, "fetched": 2}),
            # 第 2 批处中断（fail_at=1）：剩余历史未拉
            ([item("3", 500)], {"page": 3, "fetched": 3}),
        ],
        fail_at=1,
    )
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    status = await engine.sync_account(USER, "codeforces", "demo")
    assert status.state is SyncState.ERROR  # 降级为诊断
    account = store.load_profile().accounts[0]
    assert account.sync_checkpoint == {"page": 2, "fetched": 2}  # 断点保留
    assert account.last_synced_at is None  # 游标绝不在中途推进
    items, _ = store.load_submissions("codeforces", "demo")
    assert len(items) == 2  # 已落盘批次安全保留

    # 续传：断点透传；批次含一条重叠记录（页码漂移），由 store 去重吸收
    adapter2 = BatchAdapter([
        ([item("2", 2000), item("3", 500)], {"page": 3, "fetched": 4}),
    ])
    engine2, _ = make_engine(tmp_path, adapter2)
    status2 = await engine2.sync_account(USER, "codeforces", "demo")

    assert status2.state is SyncState.IDLE
    assert adapter2.resume_seen == [{"page": 2, "fetched": 2}]  # 断点续传
    account = store.load_profile().accounts[0]
    assert account.sync_checkpoint is None
    assert account.last_synced_at == 2000
    items, _ = store.load_submissions("codeforces", "demo")
    assert len(items) == 3  # 重叠的 id=2 未重复堆积


async def test_incremental_does_not_touch_checkpoint(tmp_path):
    """增量模式：整批一次落盘，不写断点（增量段短，无断点需求）。"""
    adapter = BatchAdapter([([item("3", 3000)], {"page": 2, "fetched": 1})])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(
        Account(platform="codeforces", handle="demo", last_synced_at=2000)
    )

    status = await engine.sync_account(USER, "codeforces", "demo")

    assert status.state is SyncState.IDLE
    assert adapter.resume_seen == [None]
    account = store.load_profile().accounts[0]
    assert account.sync_checkpoint is None
    assert account.last_synced_at == 3000


async def test_backfill_empty_account_no_cursor_no_checkpoint(tmp_path):
    """空账号全量：不落 0 游标、不留断点（与增量空账号口径一致）。"""
    adapter = BatchAdapter([])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    await engine.sync_account(USER, "codeforces", "demo")

    account = store.load_profile().accounts[0]
    assert account.last_synced_at is None
    assert account.sync_checkpoint is None
    assert account.last_sync_ok_at is not None
