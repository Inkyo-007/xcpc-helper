"""精细化同步引擎测试：扫描顺序、锁协同暂停、中止续扫、失败分级、auto 联动。

RefineEngine 与 SyncEngine 共享账号锁（普通同步优先）；
adapter 为假的 REFINE_VERDICT 能力平台，不触网。
"""

import asyncio
from collections.abc import AsyncIterator

from adapters.base import (
    AuthMode,
    Capability,
    PlatformAdapter,
    PlatformError,
    SyncBatch,
    UserInfo,
    Verdict,
)
from modules.activity.models import Account, Submission
from modules.activity.refine import RefineEngine, RefineState
from modules.activity.store import UserStore
from modules.activity.sync import SyncEngine

USER = "default"


class FakeRefineAdapter(PlatformAdapter):
    """REFINE_VERDICT 能力假平台：verdicts 表驱动，记录调用顺序。"""

    platform_id = "fake"
    name = "Fake"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.REFINE_VERDICT})
    auth = AuthMode.NONE
    min_interval = 0.0

    def __init__(self, verdicts: dict[str, Verdict | None]) -> None:
        self.verdicts = verdicts
        self.calls: list[str] = []
        self.gate: asyncio.Event | None = None  # 设置后每次调用前等待（暂停测试用）

    async def verify(self, handle: str) -> UserInfo:
        return UserInfo(handle=handle)

    async def fetch_submissions(self, handle, **kwargs) -> AsyncIterator[SyncBatch]:
        yield SyncBatch(done=True)

    async def fetch_submission_verdict(self, record_id, credentials=None):
        self.calls.append(record_id)  # 先记账再等闸（否则闸外等不到调用发生）
        if self.gate is not None:
            await self.gate.wait()
        result = self.verdicts.get(record_id)
        if isinstance(result, Exception):
            raise result
        return result


def make_env(tmp_path, adapter: FakeRefineAdapter):
    root = tmp_path / "user"
    store = UserStore(root, USER)
    sync = SyncEngine(root, {adapter.platform_id: adapter})
    refine = RefineEngine(root, {adapter.platform_id: adapter}, sync)
    return refine, sync, store


def seed_unac(store: UserStore, rows: list[tuple[str, int]]) -> None:
    """写入 (sid, ts) 的 UNAC 记录（platform/handle 与 fake 对齐）。"""
    store.save_account(Account(platform="fake", handle="demo"))
    store.merge_submissions(
        "fake",
        "demo",
        [
            Submission(
                platform="fake",
                handle="demo",
                submission_id=sid,
                problem_key="P1",
                problem_name="X",
                problem_url="https://example.com",
                verdict=Verdict.UNAC,
                submitted_at=ts,
                language="C++",
            )
            for sid, ts in rows
        ],
    )


async def wait_idle(refine: RefineEngine, timeout: float = 3.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        p = refine.progress_of(USER, "fake", "demo")
        if p.state != RefineState.RUNNING:
            return p
        await asyncio.sleep(0.02)
    raise AssertionError("精化未在超时内结束")


async def test_refine_all_oldest_first(tmp_path):
    """从旧往新逐条精化，全部完成后状态回 idle、存量清零。"""
    adapter = FakeRefineAdapter({"1": Verdict.WA, "2": Verdict.RE, "3": None})
    refine, _sync, store = make_env(tmp_path, adapter)
    seed_unac(store, [("1", 3000), ("2", 1000), ("3", 2000)])  # 乱序写入

    assert refine.start(USER, "fake", "demo")
    p = await wait_idle(refine)

    assert adapter.calls == ["2", "3", "1"]  # 按 submitted_at 升序（从旧往新）
    assert p.done == 3 and p.total == 3
    items, _ = store.load_submissions("fake", "demo")
    by_id = {s.submission_id: s for s in items}
    assert by_id["1"].verdict == Verdict.WA
    assert by_id["2"].verdict == Verdict.RE
    assert by_id["3"].verdict == Verdict.UNAC  # None 保持原样（保守规则）


async def test_refine_start_while_running_rejected(tmp_path):
    adapter = FakeRefineAdapter({"1": Verdict.WA})
    adapter.gate = asyncio.Event()  # 卡住第一条
    refine, _sync, store = make_env(tmp_path, adapter)
    seed_unac(store, [("1", 1000)])

    assert refine.start(USER, "fake", "demo")
    assert not refine.start(USER, "fake", "demo")  # 进行中重复启动被拒
    adapter.gate.set()
    await wait_idle(refine)


async def test_refine_stop_and_resume(tmp_path):
    """中止保留进度；再次启动重扫剩余自动续扫。"""
    adapter = FakeRefineAdapter({"1": Verdict.WA, "2": Verdict.TLE, "3": Verdict.RE})
    adapter.gate = asyncio.Event()
    refine, _sync, store = make_env(tmp_path, adapter)
    seed_unac(store, [("1", 1000), ("2", 2000), ("3", 3000)])

    refine.start(USER, "fake", "demo")
    while not adapter.calls:  # 等第一条在飞
        await asyncio.sleep(0.01)
    refine.stop(USER, "fake", "demo")
    # 即时反馈：状态立即翻转 stopped（不等在飞记录完成，防用户误以为未点到）
    assert refine.progress_of(USER, "fake", "demo").state == RefineState.STOPPED
    adapter.gate.set()
    p = await wait_idle(refine)
    assert p.state == RefineState.STOPPED
    assert adapter.calls == ["1"]  # 只完成了第一条

    adapter.gate = None
    refine.start(USER, "fake", "demo")
    p = await wait_idle(refine)
    assert adapter.calls == ["1", "2", "3"]  # 续扫剩余两条
    assert p.done == 2 and p.total == 2  # 新一轮快照只含剩余 UNAC


async def test_refine_pauses_during_normal_sync(tmp_path):
    """普通同步持锁期间精化暂停，释放后自动继续。"""
    adapter = FakeRefineAdapter({"1": Verdict.WA})
    refine, sync, store = make_env(tmp_path, adapter)
    seed_unac(store, [("1", 1000)])

    # 模拟普通同步全程持锁
    lock = sync.account_lock(USER, "fake", "demo")
    await lock.acquire()
    refine.start(USER, "fake", "demo")
    await asyncio.sleep(0.15)
    assert adapter.calls == []  # 被锁阻塞，未拉取

    lock.release()
    await wait_idle(refine)
    assert adapter.calls == ["1"]


async def test_refine_consecutive_failures_abort(tmp_path):
    """连续平台故障达上限中止本轮（系统性故障，非单条问题）。"""
    adapter = FakeRefineAdapter({sid: PlatformError("平台故障") for sid in "12345"})
    refine, _sync, store = make_env(tmp_path, adapter)
    seed_unac(store, [(sid, i * 1000) for i, sid in enumerate("12345", 1)])

    refine.start(USER, "fake", "demo")
    p = await wait_idle(refine)
    assert p.state == RefineState.STOPPED
    assert p.error is not None
    assert adapter.calls == ["1", "2", "3"]  # 连续 3 次失败后中止


async def test_refine_auth_expired_aborts_immediately(tmp_path):
    """凭据失效（AuthExpiredError）立即中止，不做连续失败计数。"""
    from adapters.base import AuthExpiredError

    adapter = FakeRefineAdapter({"1": AuthExpiredError("凭据失效")})
    refine, _sync, store = make_env(tmp_path, adapter)
    seed_unac(store, [("1", 1000), ("2", 2000)])

    refine.start(USER, "fake", "demo")
    p = await wait_idle(refine)
    assert p.state == RefineState.STOPPED
    assert "凭据失效" in (p.error or "")
    assert adapter.calls == ["1"]


async def test_progress_of_idle_reports_remaining(tmp_path):
    """未运行时 total = 存量 UNAC 数（供前端预估耗时）。"""
    adapter = FakeRefineAdapter({})
    refine, _sync, store = make_env(tmp_path, adapter)
    seed_unac(store, [("1", 1000), ("2", 2000)])
    store.update_verdicts("fake", "demo", {"1": Verdict.WA})  # 一条已精化

    p = refine.progress_of(USER, "fake", "demo")
    assert p.state == RefineState.IDLE
    assert p.total == 1  # 仅剩一条 UNAC


async def test_unjudgeable_marked_attempted_and_never_retried(tmp_path):
    """无法判定的记录打 attempted 终止标记：后续轮次不再重试（防重试循环）。

    回归场景：仅 UKE 测点的记录曾被保守规则无限重试（永远"待精化 N 条"）。
    """
    adapter = FakeRefineAdapter({"1": Verdict.WA, "2": None})  # 2 无法判定
    refine, _sync, store = make_env(tmp_path, adapter)
    seed_unac(store, [("1", 1000), ("2", 2000)])

    refine.start(USER, "fake", "demo")
    await wait_idle(refine)
    items, _ = store.load_submissions("fake", "demo")
    by_id = {s.submission_id: s for s in items}
    assert by_id["1"].verdict == Verdict.WA
    assert by_id["2"].verdict == Verdict.UNAC  # 保持 UNAC
    assert by_id["2"].refine_attempted is True  # 但已打终止标记

    # 再次启动：2 号不再出现在待办（total 只含未尝试过的）
    refine.start(USER, "fake", "demo")
    p = await wait_idle(refine)
    assert adapter.calls.count("2") == 1  # 仅首轮拉过一次
    assert p.total == 0
    # idle 口径同样排除 attempted
    assert refine.progress_of(USER, "fake", "demo").total == 0
