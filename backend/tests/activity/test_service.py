"""ActivityService 门面测试：绑定/换绑/解绑、同步触发、聚合读取（MockTransport 注入）。"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from adapters.net import HttpFetcher
from core.config import Settings
from core.exceptions import BadGatewayError, BadRequestError, NotFoundError
from modules.activity.schemas import BindIn, VerifyIn
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
    assert [p.id for p in out.platforms] == ["codeforces"]
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
        await service.verify(VerifyIn(platform="luogu", handle="demo"))


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


async def test_bind_rebind_replaces_account(service: ActivityService):
    await service.bind(BindIn(platform="codeforces", handle="demo"))
    await wait_sync_done(service)
    await service.bind(BindIn(platform="codeforces", handle="other"))
    await wait_sync_done(service)

    profile = service._store.load_profile()
    assert [a.handle for a in profile.accounts] == ["other"]
    # 旧账号数据文件已删除
    items, _ = service._store.load_submissions("codeforces", "demo")
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
        service.overview("luogu")


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
        await service.sync("luogu")


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
