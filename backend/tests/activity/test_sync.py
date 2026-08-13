"""同步引擎测试：游标推进、去重合并、失败隔离、未绑定防护。"""

import pytest

from adapters.base import (
    AuthExpiredError,
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
        full_window_days: int,
        full_min_rows: int,
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

    await engine.sync_account(USER, "codeforces", "demo")

    assert adapter.calls == [2000]
    assert store.load_profile().accounts[0].last_synced_at == 2000  # 游标不变
    assert engine.status_of(USER, "codeforces", "demo").state is SyncState.IDLE


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
