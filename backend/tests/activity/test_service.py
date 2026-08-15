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
    PlatformError,
    UserInfo,
)
from adapters.net import HttpFetcher
from core.config import Settings
from core.exceptions import (
    BadGatewayError,
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from modules.activity.models import Account
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
    assert [p.id for p in out.platforms] == ["codeforces", "atcoder", "luogu"]
    meta = out.platforms[0]
    assert meta.name == "Codeforces"
    assert "submissions" in [c.value for c in meta.capabilities]
    assert meta.account is None


async def test_verify_ok(service: ActivityService):
    out = await service.verify(VerifyIn(platform="codeforces", handle="ToUrIsT"))
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
    assert out.userInfoReady is True

    statuses = await wait_sync_done(service)
    acc = next(a for a in statuses if a.handle == "demo")
    assert acc.syncState == "idle"
    assert acc.syncError is None

    overview = service.overview(None)
    assert overview.totals.totalSubmissions == 4
    assert overview.totals.totalSolved == 2  # 2245A / 2245C
    assert overview.totals.todaySolved == 1  # 今天仅 2245A AC
    assert overview.daily[-1].submissions == 2


async def test_bind_persists_user_info(service: ActivityService):
    """验证回执中的规范用户名与头像在绑定、同步和重载后不丢失。"""
    receipt = await service.verify(
        VerifyIn(platform="codeforces", handle="ToUrIsT")
    )
    out = await service.bind(
        BindIn(
            platform=receipt.platform,
            handle=receipt.handle,
            displayName=receipt.displayName,
            avatar=receipt.avatar,
        )
    )
    assert out.handle == "tourist"
    assert out.avatar == receipt.avatar
    await wait_sync_done(service)

    # 从 profile.json 重新读取，覆盖 Account 默认值兼容与同步游标推进链路。
    stored = service._store().load_profile().accounts[0]
    assert stored.handle == "tourist"
    assert stored.avatar == receipt.avatar
    meta = next(p for p in service.platforms().platforms if p.id == "codeforces")
    assert meta.account is not None
    assert meta.account.handle == "tourist"
    assert meta.account.avatar == receipt.avatar
    assert meta.account.userInfoReady is True

    # 平台账号资料与用户组信息卡分离，绑定不应改写后者。
    profile = service.current_profile()
    assert profile.id == "default"
    assert profile.avatar is None


async def test_refresh_account_info_backfills_legacy_account(
    service: ActivityService,
):
    """旧账号保留原 handle/文件键，只用 canonical handle 补展示名。"""
    store = service._store()
    store.save_account(Account(platform="codeforces", handle="ToUrIsT"))

    await service.refresh_account_info()

    account = store.load_profile().accounts[0]
    assert account.handle == "ToUrIsT"
    assert account.display_name == "tourist"
    assert account.avatar == "https://userpic.codeforces.org/no-avatar.jpg"
    assert account.user_info_refreshed_at is not None
    meta = next(p for p in service.platforms().platforms if p.id == "codeforces")
    assert meta.account is not None
    assert meta.account.userInfoReady is True


async def test_refresh_account_info_isolates_adapter_failure(
    service: ActivityService, monkeypatch: pytest.MonkeyPatch
):
    store = service._store()
    store.save_account(Account(platform="codeforces", handle="broken"))
    store.save_account(Account(platform="atcoder", handle="AtUser"))
    credentials = Credentials(cookies={"session": "legacy"})
    store.save_account_secrets("atcoder", "AtUser", credentials)

    async def fail_verify(handle: str, credentials: Credentials | None):
        raise PlatformError("Codeforces 暂时不可用")

    async def ok_verify(handle: str, received: Credentials | None):
        assert handle == "AtUser"
        assert received == credentials
        return UserInfo(handle="atuser", avatar="https://example.com/avatar.png")

    monkeypatch.setattr(service._adapters["codeforces"], "verify", fail_verify)
    monkeypatch.setattr(service._adapters["atcoder"], "verify", ok_verify)

    await service.refresh_account_info()

    accounts = {
        account.platform: account for account in store.load_profile().accounts
    }
    assert accounts["codeforces"].user_info_refreshed_at is None
    assert accounts["atcoder"].user_info_refreshed_at is not None
    assert accounts["atcoder"].handle == "AtUser"
    assert accounts["atcoder"].display_name == "atuser"
    assert accounts["atcoder"].avatar == "https://example.com/avatar.png"
    # 资料回填与训练同步是两条链路；失败不得污染同步状态。
    assert service._engine.status_of("default", "codeforces", "broken").error is None


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
        return []

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
    avatar = "https://cdn.luogu.com.cn/upload/usericon/100000.png"
    stub_luogu(
        service,
        login_result=(
            LUOGU_CREDS,
            UserInfo(handle="100000", display_name="demo_user", avatar=avatar),
        ),
    )
    await service.start_browser_login("luogu")
    status = await wait_login_state(service, "success")
    assert status.handle == "100000"
    assert status.displayName == "demo_user"
    assert status.avatar == avatar

    out = await service.bind(
        BindIn(
            platform="luogu",
            handle=status.handle,
            displayName=status.displayName,
            avatar=status.avatar,
        )
    )
    assert out.displayName == "demo_user"
    assert out.avatar == avatar
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
