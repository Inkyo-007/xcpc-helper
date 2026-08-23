"""ActivityService 门面测试：绑定/换绑/解绑、同步触发、聚合读取（MockTransport 注入）。"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from adapters.base import (
    BrowserLoginCancelledError,
    Credentials,
    SyncBatch,
    UserInfo,
    Verdict,
)
from adapters.net import HttpFetcher
from core.config import Settings
from core.exceptions import (
    BadGatewayError,
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from modules.activity.models import Submission
from modules.activity.schemas import (
    BindIn,
    GroupCreateIn,
    GroupRenameIn,
    ProfileUpdateIn,
    VerifyIn,
)
from services.activity.service import ActivityService

FIXTURES = Path(__file__).resolve().parents[1] / "adapters" / "fixtures"
INFO_OK = json.loads((FIXTURES / "cf_user_info_ok.json").read_text(encoding="utf-8"))
INFO_NOT_FOUND = json.loads(
    (FIXTURES / "cf_user_info_not_found.json").read_text(encoding="utf-8")
)

SYS_TZ = datetime.now().astimezone().tzinfo


def ok_json(data: object) -> httpx.Response:
    return httpx.Response(200, json=data)


def cf_row(sid: int, ts: int, verdict: str = "OK", index: str = "A") -> dict:
    return {
        "id": sid,
        "contestId": 2245,
        "creationTimeSeconds": ts,
        "problem": {"contestId": 2245, "index": index, "name": "X Axis", "rating": 800},
        "programmingLanguage": "GNU C++17",
        "verdict": verdict,
    }


def sys_today_ts(days_ago: int, hour: int = 10, minute: int = 0) -> int:
    """系统本地时区"今天/昨天..."某时刻的 UTC 时间戳。"""
    d = datetime.now(SYS_TZ).date() - timedelta(days=days_ago)
    return int(datetime(d.year, d.month, d.day, hour, minute, tzinfo=SYS_TZ).timestamp())


def make_handler(user_info=INFO_OK, status_rows: list[dict] | None = None):
    """构造按 URL 分发的 MockTransport handler。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user.info"):
            return ok_json(user_info)
        if request.url.path.endswith("/user.status"):
            return ok_json({"status": "OK", "result": status_rows or []})
        return httpx.Response(404)

    return handler


@pytest.fixture
async def service(tmp_path):
    rows = [
        cf_row(1, sys_today_ts(0, 10), "OK", "A"),  # 今天 2245A AC
        cf_row(2, sys_today_ts(0, 11), "WRONG_ANSWER", "B"),  # 今天 2245B WA
        cf_row(3, sys_today_ts(1, 20), "OK", "C"),  # 昨天 2245C AC
        cf_row(4, sys_today_ts(10, 12), "TESTING", "D"),  # 10 天前 2245D JG
    ]
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler(status_rows=rows)),
        base_backoff=0.01,
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    yield svc
    await svc.aclose()


async def test_platforms_empty(service: ActivityService):
    out = service.platforms()
    assert [p.id for p in out.platforms] == ["codeforces", "atcoder", "luogu", "nowcoder", "leetcode-cn"]
    meta = out.platforms[0]
    assert meta.name == "Codeforces"
    assert "submissions" in [c.value for c in meta.capabilities]
    assert meta.account is None


async def test_verify_ok(service: ActivityService):
    out = await service.verify(VerifyIn(platform="codeforces", handle="tourist"))
    assert out.handle == "tourist"
    assert out.avatar


async def test_verify_accepts_credentials(service: ActivityService):
    """verify 契约预留 credentials（第一期 CF 匿名忽略；cookie 平台需要）。"""
    out = await service.verify(
        VerifyIn(
            platform="codeforces",
            handle="tourist",
            credentials={"cookies": {"_uid": "1", "__client_id": "2"}},
        )
    )
    assert out.handle == "tourist"


async def test_verify_user_not_found(tmp_path):
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler(user_info=INFO_NOT_FOUND)),
        base_backoff=0.01,
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        with pytest.raises(BadRequestError):
            await svc.verify(VerifyIn(platform="codeforces", handle="ghost"))
    finally:
        await svc.aclose()


async def test_verify_unsupported_platform(service: ActivityService):
    with pytest.raises(BadRequestError):
        await service.verify(VerifyIn(platform="unknown-platform", handle="demo"))


async def test_verify_platform_failure_is_bad_gateway(tmp_path):
    """平台网络故障（重试耗尽）转 502，前端可读。"""

    async def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    fetcher = HttpFetcher(
        transport=httpx.MockTransport(failing_handler), base_backoff=0.01
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    # 退避时长由 test_net 覆盖，此处只看异常转换（禁用真实限流等待）
    svc._adapters["codeforces"].min_interval = 0
    try:
        with pytest.raises(BadGatewayError):
            await svc.verify(VerifyIn(platform="codeforces", handle="tourist"))
    finally:
        await svc.aclose()


async def test_bind_triggers_first_sync(service: ActivityService):
    out = await service.bind(BindIn(platform="codeforces", handle="demo"))
    assert out.platform == "codeforces"
    assert out.handle == "demo"

    statuses = await wait_sync_done(service)
    acc = next(a for a in statuses if a.handle == "demo")
    assert acc.syncState == "idle"
    assert acc.syncError is None

    overview = service.overview(None)
    assert overview.totals.totalSubmissions == 4
    assert overview.totals.totalSolved == 2  # 2245A / 2245C
    assert overview.totals.todaySolved == 1  # 今天仅 2245A AC
    assert overview.daily[-1].submissions == 2


async def test_bind_persists_display_name(service: ActivityService):
    """绑定携带展示名：随账号持久化并在 platforms/同步状态透出。"""
    out = await service.bind(
        BindIn(platform="codeforces", handle="demo", displayName="演示账号")
    )
    assert out.displayName == "演示账号"
    await wait_sync_done(service)
    meta = next(p for p in service.platforms().platforms if p.id == "codeforces")
    assert meta.account is not None
    assert meta.account.displayName == "演示账号"


async def test_bind_rebind_replaces_account(service: ActivityService):
    await service.bind(BindIn(platform="codeforces", handle="demo"))
    await wait_sync_done(service)
    await service.bind(BindIn(platform="codeforces", handle="other"))
    await wait_sync_done(service)

    profile = service._store().load_profile()
    assert [a.handle for a in profile.accounts] == ["other"]
    # 旧账号数据文件已删除
    items, _ = service._store().load_submissions("codeforces", "demo")
    assert items == []


async def test_unbind(service: ActivityService):
    await service.bind(BindIn(platform="codeforces", handle="demo"))
    await wait_sync_done(service)
    service.unbind("codeforces", "demo")

    assert service.platforms().platforms[0].account is None
    with pytest.raises(NotFoundError):
        service.unbind("codeforces", "ghost")


async def test_overview_platform_filter_and_invalid(service: ActivityService):
    await service.bind(BindIn(platform="codeforces", handle="demo"))
    await wait_sync_done(service)

    out = service.overview("codeforces")
    assert out.totals.totalSubmissions == 4

    with pytest.raises(BadRequestError):
        service.overview("unknown-platform")


async def test_submissions_recent_and_by_date(service: ActivityService):
    await service.bind(BindIn(platform="codeforces", handle="demo"))
    await wait_sync_done(service)

    recent = service.submissions(date=None, platform=None)
    assert len(recent.items) == 4
    # 按 (日期, 时刻) 倒序（最新在前，跨天正确）
    keys = [f"{i.date} {i.time}" for i in recent.items]
    assert keys == sorted(keys, reverse=True)
    assert all(i.date for i in recent.items)

    today = datetime.now(SYS_TZ).date().isoformat()
    day = service.submissions(date=today, platform=None)
    assert len(day.items) == 2  # 今天 10:00 与 11:00 两条
    assert all(i.date == today for i in day.items)

    bad = service.submissions(date="2020-01-01", platform=None)
    assert bad.items == []


async def test_recent_limits_to_200(tmp_path):
    """近期提交最多返回最后 200 条（超过时按时间倒序截断）。"""
    rows = [cf_row(i, sys_today_ts(0, 10) - i * 60, "OK", "A") for i in range(205)]
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler(status_rows=rows)),
        base_backoff=0.01,
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        await svc.bind(BindIn(platform="codeforces", handle="demo"))
        await wait_sync_done(svc)
        recent = svc.submissions(date=None, platform=None)
        assert len(recent.items) == 200
        # 最新 200 条（sid 0 最新，最旧的 sid 200–204 被截断）
        assert recent.items[0].id == "0"
        assert recent.items[-1].id == "199"
    finally:
        await svc.aclose()


async def test_recent_includes_old_submissions(tmp_path):
    """很久以前的提交也出现在近期提交（不按时间窗口过滤）。"""
    rows = [cf_row(1, sys_today_ts(300, 10), "OK", "A")]
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler(status_rows=rows)),
        base_backoff=0.01,
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        await svc.bind(BindIn(platform="codeforces", handle="demo"))
        await wait_sync_done(svc)
        recent = svc.submissions(date=None, platform=None)
        assert len(recent.items) == 1
        assert recent.items[0].id == "1"
    finally:
        await svc.aclose()


async def test_sync_and_status(service: ActivityService):
    await service.bind(BindIn(platform="codeforces", handle="demo"))
    await wait_sync_done(service)

    # 再次手动触发同步（增量），游标已推进
    await service.sync("codeforces")
    statuses = await wait_sync_done(service)
    assert all(s.syncState == "idle" for s in statuses)


async def test_sync_unsupported_platform(service: ActivityService):
    with pytest.raises(BadRequestError):
        await service.sync("unknown-platform")


# ===== 用户组管理 =====


async def test_create_switch_rename_delete_group(tmp_path):
    """用户组完整生命周期：新建（自动切换）→ 切换 → 重命名 → 删除回退。"""
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler()), base_backoff=0.01
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        # 默认组存在（default 目录即使未显式创建，操作时按空档案处理）
        groups = svc.groups().groups
        assert any(g.name == "default" and g.current for g in groups)

        # 新建（中文组名）并自动切换
        out = svc.create_group(GroupCreateIn(name="第一组"))
        assert out.name == "第一组"
        assert out.current
        assert any(g.name == "第一组" and g.current for g in svc.groups().groups)

        # 切换回 default
        svc.switch_group("default")
        assert any(g.name == "default" and g.current for g in svc.groups().groups)

        # 重命名当前组（目录改名 + current 同步）
        svc.switch_group("第一组")
        result = svc.rename_group("第一组", GroupRenameIn(newName="第二组"))
        assert svc._current_group == "第二组"
        names = [g.name for g in result.groups]
        assert "第一组" not in names and "第二组" in names

        # 删除当前组 → 回退到剩余组
        svc.delete_group("第二组")
        assert svc._current_group != "第二组"
        assert all(g.name != "第二组" for g in svc.groups().groups)

        # 不允许删除最后一个组
        remaining = svc.groups().groups
        last = remaining[0].name
        for g in remaining[1:]:
            svc.delete_group(g.name)
        with pytest.raises(BadRequestError):
            svc.delete_group(last)

        # 删除不存在 / 切换不存在
        with pytest.raises(NotFoundError):
            svc.switch_group("不存在的组")
        with pytest.raises(NotFoundError):
            svc.delete_group("不存在的组")
    finally:
        await svc.aclose()


async def test_restart_does_not_recreate_deleted_default(tmp_path):
    """重启不再重建被删除/重命名的 default：仅一个组都不存在时才创建 default；
    已有组时当前组回落到现存首个组。"""
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler()), base_backoff=0.01
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        svc.create_group(GroupCreateIn(name="我的组"))  # 新建并自动切换为当前组
        svc.delete_group("default")  # 删除 default（当前组已是"我的组"）
    finally:
        await svc.aclose()

    # 模拟重启（新服务实例，同一数据目录）
    svc2 = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        groups = svc2.groups().groups
        assert [g.name for g in groups] == ["我的组"]  # default 未被重建
        assert next(g for g in groups if g.current).name == "我的组"
    finally:
        await svc2.aclose()


async def test_first_run_creates_default(tmp_path):
    """真正的首次运行（无任何用户组）才自动创建 default。"""
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler()), base_backoff=0.01
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        groups = svc.groups().groups
        assert [g.name for g in groups] == ["default"]
        assert groups[0].current
    finally:
        await svc.aclose()


async def test_group_data_isolated(tmp_path):
    """不同用户组的账号绑定与训练数据互相隔离。"""
    rows = [cf_row(1, sys_today_ts(0, 10), "OK", "A")]
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler(status_rows=rows)),
        base_backoff=0.01,
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        # 组 A 绑定账号并同步
        svc.create_group(GroupCreateIn(name="A"))
        await svc.bind(BindIn(platform="codeforces", handle="demo"))
        await wait_sync_done(svc)
        assert svc.overview(None).totals.totalSubmissions == 1

        # 切到组 B：无账号、无数据
        svc.create_group(GroupCreateIn(name="B"))
        assert svc.platforms().platforms[0].account is None
        assert svc.overview(None).totals.totalSubmissions == 0
        assert svc.submissions(date=None, platform=None).items == []

        # 切回组 A：数据仍在
        svc.switch_group("A")
        assert svc.platforms().platforms[0].account.handle == "demo"
        assert svc.overview(None).totals.totalSubmissions == 1
    finally:
        await svc.aclose()


async def test_profile_update_independent_of_group_name(tmp_path):
    """信息卡（ID/签名/头像）独立于组名存储与编辑。"""
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler()), base_backoff=0.01
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        svc.create_group(GroupCreateIn(name="组名"))
        # 信息卡 ID 初始为组名，但可独立修改（不与组名同步）
        p = svc.update_profile(
            ProfileUpdateIn(id="独立ID", signature="冲上紫名", avatar="data:image/png;base64,xx")
        )
        assert p.id == "独立ID"
        assert p.signature == "冲上紫名"

        # 重命名组不影响信息卡
        svc.rename_group("组名", GroupRenameIn(newName="新组名"))
        cur = svc.current_profile()
        assert cur.id == "独立ID"
        assert cur.signature == "冲上紫名"

        # 头像过大拒绝
        with pytest.raises(BadRequestError):
            svc.update_profile(ProfileUpdateIn(avatar="x" * 500_001))

        # 显式传 null 清除头像
        cleared = svc.update_profile(ProfileUpdateIn(avatar=None))
        assert cleared.avatar is None
    finally:
        await svc.aclose()


async def test_groups_are_persisted_dirs(tmp_path):
    """用户组即目录：服务创建后目录真实存在，重启（新服务实例）仍可列出。"""
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(make_handler()), base_backoff=0.01
    )
    svc = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    svc.create_group(GroupCreateIn(name="持久组"))
    await svc.aclose()

    svc2 = ActivityService(Settings(user_data_dir=tmp_path / "user"), fetcher)
    try:
        assert any(g.name == "持久组" for g in svc2.groups().groups)
    finally:
        await svc2.aclose()


async def wait_sync_done(service: ActivityService, timeout: float = 3.0):
    """等待后台同步任务真正完成：非 running 且已有同步结果（时间或错误）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = service.sync_status()
        if statuses:
            acc = statuses[0]
            if acc.syncState != "running" and (
                acc.lastSyncAt is not None or acc.syncError is not None
            ):
                return statuses
        await asyncio.sleep(0.02)
    raise AssertionError("同步未在超时内完成")


# ===== 浏览器一键登录（browser-login） =====

LUOGU_CREDS = Credentials(cookies={"_uid": "100000", "__client_id": "tok"}, headers={})


def stub_luogu(service: ActivityService, login_result=None, login_exc=None):
    """打桩洛谷 adapter 的 browser-login 可选契约与同步外呼（防真实网络）。"""
    adapter = service._adapters["luogu"]
    adapter.browser_login_available = lambda: True

    async def fake_login(timeout: float):
        if login_exc is not None:
            raise login_exc
        return login_result

    adapter.run_browser_login = fake_login

    async def no_network_fetch(handle, *, since, credentials, **kwargs):
        yield SyncBatch(done=True)

    adapter.fetch_submissions = no_network_fetch
    return adapter


async def wait_login_state(service: ActivityService, state: str, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = service.browser_login_status("luogu")
        if status.state == state:
            return status
        await asyncio.sleep(0.02)
    raise AssertionError(f"登录会话未进入 {state}")


async def test_browser_login_success_and_bind_consumes_stash(service: ActivityService):
    """一键登录成功：回执透出 + 凭据暂存，bind 无显式凭据时消费暂存并落 secrets。"""
    stub_luogu(
        service,
        login_result=(LUOGU_CREDS, UserInfo(handle="100000", display_name="demo_user")),
    )
    await service.start_browser_login("luogu")
    status = await wait_login_state(service, "success")
    assert status.handle == "100000"
    assert status.displayName == "demo_user"

    out = await service.bind(BindIn(platform="luogu", handle="100000", displayName="demo_user"))
    assert out.displayName == "demo_user"
    # 凭据已落 secrets.json（sync 将使用）
    stored = service._store().get_account_credentials("luogu", "100000")
    assert stored is not None
    assert stored.cookies["__client_id"] == "tok"
    await wait_sync_done(service)


async def test_browser_login_bind_without_stash_rejected(service: ActivityService):
    """cookie 平台绑定：无显式凭据且无暂存 → 400。"""
    stub_luogu(service)
    with pytest.raises(BadRequestError):
        await service.bind(BindIn(platform="luogu", handle="100000"))


async def test_browser_login_rejects_anonymous_platform(service: ActivityService):
    """匿名平台（CF）无需浏览器登录 → 400。"""
    with pytest.raises(BadRequestError):
        await service.start_browser_login("codeforces")


async def test_browser_login_conflict_while_waiting(service: ActivityService):
    """同平台登录会话互斥：waiting 中重复启动 → 409。"""
    adapter = service._adapters["luogu"]
    adapter.browser_login_available = lambda: True
    gate = asyncio.Event()

    async def blocking_login(timeout: float):
        await gate.wait()
        raise BrowserLoginCancelledError("测试收尾取消")

    adapter.run_browser_login = blocking_login
    await service.start_browser_login("luogu")
    with pytest.raises(ConflictError):
        await service.start_browser_login("luogu")
    gate.set()
    await wait_login_state(service, "canceled")


async def test_browser_login_canceled(service: ActivityService):
    """用户关闭登录窗口 → canceled。"""
    stub_luogu(service, login_exc=BrowserLoginCancelledError("登录窗口已关闭"))
    await service.start_browser_login("luogu")
    status = await wait_login_state(service, "canceled")
    assert status.state == "canceled"


async def test_browser_login_unavailable_without_playwright(service: ActivityService):
    """Playwright 不可用（探测打桩为 False）→ 400 且 /platforms 的
    browserLogin=false（前端据此隐藏一键登录按钮）。"""
    adapter = service._adapters["luogu"]
    adapter.browser_login_available = lambda: False  # 不依赖环境真实安装状态
    meta = next(p for p in service.platforms().platforms if p.id == "luogu")
    assert meta.browserLogin is False
    with pytest.raises(BadRequestError):
        await service.start_browser_login("luogu")


# ===== 精细化同步（UNAC refine） =====


def unac_row(sid: str, ts: int) -> Submission:
    return Submission(
        platform="luogu",
        handle="100000",
        submission_id=sid,
        problem_key="P1001",
        problem_name="X",
        problem_url="https://www.luogu.com.cn/problem/P1001",
        verdict=Verdict.UNAC,
        submitted_at=ts,
        language="C++20",
    )


async def wait_refine_done(service: ActivityService, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = service.refine_status("luogu", "100000")
        if st.state != "running":
            return st
        await asyncio.sleep(0.02)
    raise AssertionError("精化未在超时内结束")


async def test_refine_requires_capability(service: ActivityService):
    """无 REFINE_VERDICT 能力的平台（CF）启动精化 → 400。"""
    await service.bind(BindIn(platform="codeforces", handle="demo"))
    await wait_sync_done(service)
    with pytest.raises(BadRequestError):
        service.start_refine("codeforces", "demo")


async def test_refine_full_flow_and_done_state(service: ActivityService):
    """精化全链路：启动 → 进行中 409 → 完成后 done，存量 UNAC 被改写。"""
    adapter = stub_luogu(service)
    await service.bind(BindIn(platform="luogu", handle="100000", credentials={"cookies": {"_uid": "100000", "__client_id": "tok"}}))
    await wait_sync_done(service)
    service._store().merge_submissions("luogu", "100000", [unac_row("1", 1000)])

    gate = asyncio.Event()

    async def fake_refine(record_id, credentials=None):
        await gate.wait()
        return Verdict.TLE

    adapter.fetch_submission_verdict = fake_refine

    service.start_refine("luogu", "100000")
    with pytest.raises(ConflictError):
        service.start_refine("luogu", "100000")  # 进行中重复启动
    # total 由后台任务快照装配，轮询待其就位（gate 卡住保持 running）
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        st = service.refine_status("luogu", "100000")
        if st.state == "running" and st.total == 1:
            break
        await asyncio.sleep(0.02)
    assert st.state == "running"
    assert st.total == 1

    gate.set()
    st = await wait_refine_done(service)
    assert st.state == "done"  # 存量 UNAC 清零
    items, _ = service._store().load_submissions("luogu", "100000")
    assert items[0].verdict == Verdict.TLE


async def test_refine_auto_triggers_after_sync(service: ActivityService):
    """refine_auto 开启后，普通同步完成自动启动精化。"""
    adapter = stub_luogu(service)
    await service.bind(BindIn(platform="luogu", handle="100000", credentials={"cookies": {"_uid": "100000", "__client_id": "tok"}}))
    await wait_sync_done(service)
    service._store().merge_submissions("luogu", "100000", [unac_row("1", 1000)])

    refined: list[str] = []

    async def fake_refine(record_id, credentials=None):
        refined.append(record_id)
        return Verdict.WA

    adapter.fetch_submission_verdict = fake_refine

    out = service.set_refine_auto("luogu", "100000", True)
    assert out.auto is True
    # 档案持久化
    account = service._store().load_profile().accounts[0]
    assert account.refine_auto is True

    await service.sync("luogu")
    # 直接轮询终态：sync 任务调度与精化触发均异步，分段等待存在竞态
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not refined:
        await asyncio.sleep(0.02)
    st = await wait_refine_done(service)
    assert refined == ["1"]  # 同步完成后自动精化
    assert st.state == "done"


async def test_refine_stopped_total_reflects_remaining(service: ActivityService):
    """中止后返回的 total 按存量剩余重算（快照分母已过时），done 保留计数。"""
    adapter = stub_luogu(service)
    await service.bind(BindIn(platform="luogu", handle="100000", credentials={"cookies": {"_uid": "100000", "__client_id": "tok"}}))
    await wait_sync_done(service)
    service._store().merge_submissions(
        "luogu", "100000", [unac_row("1", 1000), unac_row("2", 2000), unac_row("3", 3000)]
    )

    gate = asyncio.Event()
    refine_calls: list[str] = []

    async def fake_refine(record_id, credentials=None):
        refine_calls.append(record_id)
        await gate.wait()
        return Verdict.WA

    adapter.fetch_submission_verdict = fake_refine

    service.start_refine("luogu", "100000")
    # 等第一条真正在飞后中止：状态立即翻转 stopped
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not refine_calls:
        await asyncio.sleep(0.02)
    service.stop_refine("luogu", "100000")
    gate.set()  # 释放在飞记录（完成第 1 条）
    # 等在飞记录的写入落盘（stop 已即时翻转状态，写盘随后完成）
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        items, _ = service._store().load_submissions("luogu", "100000")
        if any(s.verdict == Verdict.WA for s in items):
            break
        await asyncio.sleep(0.02)

    st = service.refine_status("luogu", "100000")
    assert st.state == "stopped"
    assert st.total == 2  # 剩余 2 条（第 1 条已精化）
    assert st.done == 1
