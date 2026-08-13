"""同步引擎测试：游标推进、去重合并、失败隔离、未绑定防护。"""

import pytest

from adapters.base import (
    AuthMode,
    Capability,
    Credentials,
    PlatformAdapter,
    PlatformError,
    PlatformSubmission,
    UserInfo,
)
from core.exceptions import NotFoundError
from modules.activity.models import Account, SyncState
from modules.activity.store import UserStore
from modules.activity.sync import SyncEngine


class FakeAdapter(PlatformAdapter):
    """按调用次数返回预设页；记录每次收到的 since 游标。"""

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
    ) -> list[PlatformSubmission]:
        self.calls.append(since)
        if self.fail_with is not None:
            raise self.fail_with
        if self.pages:
            return self.pages.pop(0)
        return []


def item(sid: str, ts: int) -> PlatformSubmission:
    return PlatformSubmission(
        submission_id=sid,
        problem_key="2245A",
        problem_name="X",
        problem_url="https://codeforces.com/problemset/problem/2245/A",
        verdict="AC",
        submitted_at=ts,
        language="GNU C++17",
    )


def make_engine(tmp_path, adapter: FakeAdapter) -> tuple[SyncEngine, UserStore]:
    store = UserStore(tmp_path / "user", "default")
    return SyncEngine(store, {"codeforces": adapter}), store


async def test_first_sync_advances_cursor(tmp_path):
    adapter = FakeAdapter(pages=[[item("1", 1000), item("2", 2000)]])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    status = await engine.sync_account("codeforces", "demo")

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

    status = await engine.sync_account("codeforces", "demo")

    assert adapter.calls == [2000]  # 增量带游标
    assert status.state is SyncState.IDLE
    assert store.load_profile().accounts[0].last_synced_at == 3000


async def test_no_new_submissions_keeps_cursor(tmp_path):
    adapter = FakeAdapter(pages=[[]])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(
        Account(platform="codeforces", handle="demo", last_synced_at=2000)
    )

    await engine.sync_account("codeforces", "demo")

    assert adapter.calls == [2000]
    assert store.load_profile().accounts[0].last_synced_at == 2000  # 游标不变
    assert engine.status_of("codeforces", "demo").state is SyncState.IDLE


async def test_failure_degrades_to_diagnostic(tmp_path):
    adapter = FakeAdapter()
    adapter.fail_with = PlatformError("Codeforces API 返回失败: limit")
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))

    # 失败不抛出，只降级为该账号诊断
    status = await engine.sync_account("codeforces", "demo")

    assert status.state is SyncState.ERROR
    assert "limit" in (status.error or "")
    assert store.load_profile().accounts[0].last_synced_at is None


async def test_unbound_account_raises_not_found(tmp_path):
    adapter = FakeAdapter()
    engine, _store = make_engine(tmp_path, adapter)

    with pytest.raises(NotFoundError):
        await engine.sync_account("codeforces", "ghost")


async def test_unsupported_platform_raises(tmp_path):
    adapter = FakeAdapter()
    engine, _store = make_engine(tmp_path, adapter)

    with pytest.raises(NotFoundError):
        await engine.sync_account("luogu", "demo")


async def test_drop_status_clears_runtime(tmp_path):
    adapter = FakeAdapter(pages=[[item("1", 1000)]])
    engine, store = make_engine(tmp_path, adapter)
    store.save_account(Account(platform="codeforces", handle="demo"))
    await engine.sync_account("codeforces", "demo")

    engine.drop_status("codeforces", "demo")
    st = engine.status_of("codeforces", "demo")
    assert st.state is SyncState.IDLE
    assert st.last_synced_at is None
