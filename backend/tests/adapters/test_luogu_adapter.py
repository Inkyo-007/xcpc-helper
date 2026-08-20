"""洛谷适配器测试：录制 JSON fixture 解析、倒序分页、增量停止、信封语义、反爬分级、凭据。

洛谷走 curl_cffi 会话（TLS 指纹伪装，见 activity/luogu.md），测试注入
FakeSession 替代真实会话；fixture 为真实响应脱敏（抹除身份字段）。
"""

import copy
import json
import time
from pathlib import Path

import pytest

from adapters.base import (
    AuthExpiredError,
    Credentials,
    PlatformError,
    UserNotFoundError,
    Verdict,
)
from adapters.luogu import LuoguAdapter
from adapters.luogu.normalize import (
    map_language,
    map_verdict,
    pick_verdict,
    problem_url,
)

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE = json.loads(
    (FIXTURES / "lg_record_list_sample.json").read_text(encoding="utf-8")
)

# 全量同步策略参数（生产由 Settings 注入，测试直接传）
FULL_WINDOW_DAYS = 370
FULL_MIN_ROWS = 5000

CREDS = Credentials(cookies={"_uid": "100000", "__client_id": "fake-token"})


class FakeResponse:
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.text = body


class FakeSession:
    """最小 curl_cffi 会话替身：记录请求、按 handler 分发响应。"""

    def __init__(self, handler) -> None:
        self._handler = handler
        self.requests: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def get(self, url, *, params=None, cookies=None, timeout=None, allow_redirects=None):
        self.requests.append({"url": url, "params": dict(params or {}), "cookies": cookies})
        return self._handler(url, params or {})


def make_adapter(handler) -> LuoguAdapter:
    adapter = LuoguAdapter(None, session_factory=lambda: FakeSession(handler))  # type: ignore[arg-type]
    adapter.min_interval = 0  # 测试禁用真实限流等待
    return adapter


def row(id_: int, ts: int, status: int = 12, pid: str = "P1001") -> dict:
    """基于录制样本复制一行并覆盖关键字段。"""
    r = copy.deepcopy(SAMPLE["currentData"]["records"]["result"][0])
    r["id"] = id_
    r["submitTime"] = ts
    r["status"] = status
    r["problem"]["pid"] = pid
    return r


def envelope(rows: list[dict], per_page: int = 20) -> str:
    return json.dumps(
        {
            "code": 200,
            "currentTemplate": "RecordList",
            "currentData": {
                "records": {"result": rows, "count": 9999, "perPage": per_page}
            },
        }
    )


def now_minus(days: float) -> int:
    return int(time.time()) - int(days * 86400)


async def fetch(adapter: LuoguAdapter, since=None, min_rows=FULL_MIN_ROWS):
    """收集流式契约的全部批次（SyncBatch）为扁平列表。"""
    items = []
    async for batch in adapter.fetch_submissions(
        "100000",
        since=since,
        credentials=CREDS,
        full_window_days=FULL_WINDOW_DAYS,
        full_min_rows=min_rows,
    ):
        items.extend(batch.items)
    return items


# ===== verify =====


async def test_verify_ok_exact_match_by_name():
    """用户名精确匹配（不区分大小写）→ handle 归一为 uid，带回展示名与头像。"""

    def handler(url, params):
        if "search" in url:
            assert params["keyword"] == "Demo_User"
            return FakeResponse(
                200,
                json.dumps(
                    {
                        "users": [
                            {"uid": 999, "name": "demo_user2"},
                            {"uid": 100000, "name": "demo_user", "avatar": "https://cdn.luogu.com.cn/upload/usericon/100000.png"},
                        ]
                    }
                ),
            )
        # 凭据有效性试拉
        assert params["user"] == "100000"
        return FakeResponse(200, envelope([row(1, int(time.time()))]))

    adapter = make_adapter(handler)
    info = await adapter.verify("Demo_User", CREDS)
    assert info.handle == "100000"
    assert info.display_name == "demo_user"
    assert info.avatar == "https://cdn.luogu.com.cn/upload/usericon/100000.png"


async def test_verify_ok_exact_match_by_uid():
    def handler(url, params):
        return FakeResponse(
            200, json.dumps({"users": [{"uid": 100000, "name": "demo_user"}]})
        )

    adapter = make_adapter(handler)
    info = await adapter.verify("100000")
    assert info.handle == "100000"
    assert info.display_name == "demo_user"


async def test_verify_fuzzy_only_is_not_found():
    """search 为模糊匹配：无精确命中（仅相似名）判用户不存在。"""

    def handler(url, params):
        return FakeResponse(
            200, json.dumps({"users": [{"uid": 999, "name": "demo_user2"}]})
        )

    adapter = make_adapter(handler)
    with pytest.raises(UserNotFoundError):
        await adapter.verify("demo_user")


async def test_verify_dead_credentials_raise_auth_expired():
    """凭据试拉遇到登录跳页（非 JSON）→ AuthExpiredError（service 转 400）。"""

    def handler(url, params):
        if "search" in url:
            return FakeResponse(200, json.dumps({"users": [{"uid": 100000, "name": "demo_user"}]}))
        return FakeResponse(200, "<html>登录页</html>")

    adapter = make_adapter(handler)
    with pytest.raises(AuthExpiredError):
        await adapter.verify("demo_user", CREDS)


# ===== fetch_submissions =====


async def test_fetch_maps_real_fixture_fields():
    """录制 fixture 字段归一化：题名/难度内嵌、verdict、语言、contest URL。"""

    def handler(url, params):
        if int(params["page"]) == 1:
            return FakeResponse(200, json.dumps(SAMPLE))
        return FakeResponse(200, envelope([]))

    adapter = make_adapter(handler)
    items = await fetch(adapter)
    assert len(items) == 20
    first = items[0]
    assert first.submission_id == "289883201"
    assert first.problem_key == "T601462"
    assert first.problem_name == "树上转移（6）"
    assert first.problem_url == "https://www.luogu.com.cn/problem/T601462"
    assert first.difficulty == 0
    assert first.verdict is Verdict.AC
    assert first.language == "C++20"
    # 比赛内提交拼 contestId；status 14（Unaccepted）→ UNAC（细分未知）
    second = items[1]
    assert second.problem_url == "https://www.luogu.com.cn/problem/P16967?contestId=330287"
    assert second.difficulty == 6
    assert items[2].verdict is Verdict.UNAC


async def test_fetch_paginates_until_short_page():
    now = int(time.time())
    pages = {
        1: [row(i, now - i * 60) for i in range(1, 21)],  # 满页 20 条
        2: [row(21, now - 1300)],  # 短页 → 停止
    }

    def handler(url, params):
        return FakeResponse(200, envelope(pages.get(int(params["page"]), [])))

    adapter = make_adapter(handler)
    items = await fetch(adapter, min_rows=1)
    assert len(items) == 21
    assert items[-1].submission_id == "21"


async def test_fetch_incremental_stops_at_cursor():
    """增量：游标之前的旧提交不拉取；游标当秒提交重复拉（去重靠 store）。"""
    since = now_minus(2)
    pages = {
        1: [row(3, since + 120), row(2, since)],  # 第二条与游标同秒 → 应被拉取
        2: [row(1, since - 60)],  # 旧于游标 → 停止（不会请求到）
    }
    requested = []

    def handler(url, params):
        requested.append(int(params["page"]))
        return FakeResponse(200, envelope(pages[int(params["page"])]))

    adapter = make_adapter(handler)
    items = await fetch(adapter, since=since)
    assert [s.submission_id for s in items] == ["3", "2"]
    assert requested == [1]  # 第一页内命中旧提交即停，不再翻页


async def test_fetch_full_keeps_pulling_until_min_rows_past_window():
    """全量：越过窗口起点但条数不足 full_min_rows 时继续拉（为 all-time 留缓冲）。"""
    now = int(time.time())
    pages = {
        1: [row(i, now - i * 86400) for i in range(1, 21)],  # 窗口内满页
        2: [row(i, now - (i - 20) * 86400 - 400 * 86400) for i in range(21, 41)],  # 窗口外满页
        3: [],  # 拉空为止
    }

    def handler(url, params):
        return FakeResponse(200, envelope(pages[int(params["page"])]))

    adapter = make_adapter(handler)
    items = await fetch(adapter, min_rows=5000)
    assert len(items) == 40  # 条数不足时不因越过窗口而提前停


async def test_fetch_full_stops_past_window_with_enough_rows():
    """全量：越过窗口起点且累计 ≥ full_min_rows 即停。"""
    now = int(time.time())
    pages = {
        1: [row(i, now - i * 60) for i in range(1, 21)],
        2: [row(40, now - 400 * 86400)],  # 窗口外短页
    }

    def handler(url, params):
        return FakeResponse(200, envelope(pages[int(params["page"])]))

    adapter = make_adapter(handler)
    items = await fetch(adapter, min_rows=20)
    assert len(items) == 21


async def test_fetch_resume_from_checkpoint():
    """断点续传：resume_checkpoint 的页码透传为起始页。"""
    requested_pages: list[int] = []

    def handler(url, params):
        requested_pages.append(int(params["page"]))
        return FakeResponse(200, envelope([]))

    adapter = make_adapter(handler)
    items = []
    async for batch in adapter.fetch_submissions(
        "100000",
        since=None,
        credentials=CREDS,
        full_window_days=FULL_WINDOW_DAYS,
        full_min_rows=FULL_MIN_ROWS,
        resume_checkpoint={"page": 3, "fetched": 40},
    ):
        items.extend(batch.items)
    assert items == []
    assert requested_pages == [3]  # 从断点页码续拉，不回头


async def test_fetch_without_credentials_raises_auth_expired():
    adapter = make_adapter(lambda url, params: FakeResponse(200, envelope([])))
    with pytest.raises(AuthExpiredError):
        async for _batch in adapter.fetch_submissions(
            "100000",
            since=None,
            credentials=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        ):
            pass


async def test_fetch_non_json_with_credentials_is_auth_expired():
    """JS 挑战页 / 登录跳页（非 JSON）+ 带凭据 → 引导重新授权。"""
    adapter = make_adapter(lambda url, params: FakeResponse(200, "<html>Welcome - Luogu Spilopelia</html>"))
    with pytest.raises(AuthExpiredError):
        await fetch(adapter)


async def test_fetch_non_json_anonymous_is_platform_error():
    """匿名路径（search）遇挑战页 → PlatformError 而非凭据错误。"""

    def handler(url, params):
        return FakeResponse(200, "<html>Welcome - Luogu Spilopelia</html>")

    adapter = make_adapter(handler)
    with pytest.raises(PlatformError) as exc_info:
        await adapter.verify("demo_user")
    assert not isinstance(exc_info.value, AuthExpiredError)


async def test_fetch_rate_limit_403_retries_then_succeeds(monkeypatch):
    """403 +「请求频繁」→ 专项长退避重试后可恢复。"""
    monkeypatch.setattr("adapters.luogu.RATE_LIMIT_BACKOFF", 0.01)
    calls = 0

    def handler(url, params):
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeResponse(200, json.dumps({"code": 403, "currentData": {"errorMessage": "请求频繁，请稍候再试"}}))
        return FakeResponse(200, envelope([row(1, int(time.time()))]))

    adapter = make_adapter(handler)
    items = await fetch(adapter)
    assert len(items) == 1
    assert calls == 2


async def test_fetch_auth_error_403_raises_auth_expired():
    """403 非限流（请先登录/用户不可见）→ AuthExpiredError。"""
    adapter = make_adapter(
        lambda url, params: FakeResponse(
            200, json.dumps({"code": 403, "currentData": {"errorMessage": "请先登录"}})
        )
    )
    with pytest.raises(AuthExpiredError):
        await fetch(adapter)


async def test_fetch_other_error_code_is_platform_error():
    adapter = make_adapter(
        lambda url, params: FakeResponse(200, json.dumps({"code": 500, "currentData": {}}))
    )
    with pytest.raises(PlatformError):
        await fetch(adapter)


async def test_fetch_row_missing_submit_time_raises():
    """记录行缺 submitTime：必填校验失败抛 PlatformError（防增量静默漏数据）。"""

    def handler(url, params):
        bad = row(1, 0)
        del bad["submitTime"]
        return FakeResponse(200, envelope([bad]))

    adapter = make_adapter(handler)
    with pytest.raises(PlatformError):
        await fetch(adapter)


async def test_fetch_retries_5xx(monkeypatch):
    """5xx 走通用退避重试。"""
    calls = 0

    def handler(url, params):
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeResponse(503, "busy")
        return FakeResponse(200, envelope([row(1, int(time.time()))]))

    adapter = make_adapter(handler)
    items = await fetch(adapter)
    assert len(items) == 1
    assert calls == 2


# ===== 归一化纯函数 =====


def test_verdict_mapping():
    """官方常量表校准（/_lfe/config/auth）：注意 4=MLE、5=TLE 与直觉相反。"""
    assert map_verdict(12) is Verdict.AC
    assert map_verdict(6) is Verdict.WA
    assert map_verdict(14) is Verdict.UNAC  # Unaccepted（列表口径无细分）
    assert map_verdict(2) is Verdict.CE
    assert map_verdict(7) is Verdict.RE
    assert map_verdict(5) is Verdict.TLE
    assert map_verdict(4) is Verdict.MLE
    assert map_verdict(3) is Verdict.OLE
    assert map_verdict(0) is Verdict.JG
    assert map_verdict(1) is Verdict.JG
    assert map_verdict(11) is Verdict.UKE
    assert map_verdict(21) is Verdict.UKE  # Hack 系列
    assert map_verdict(-1) is Verdict.UKE
    assert map_verdict(999) is Verdict.UKE


def test_language_mapping():
    assert map_language(27) == "C++20"
    assert map_language(7) == "Python 3"
    assert map_language(0) == ""  # Invalid
    assert map_language(999) == ""


def test_pick_verdict_severity_priority():
    """严重度取最重：RE > TLE > MLE > OLE > WA（对话确认）。"""
    assert pick_verdict([12, 12, 6]) is Verdict.WA  # 全 AC + 一个 WA
    assert pick_verdict([6, 5]) is Verdict.TLE  # WA 与 TLE 并存取 TLE
    assert pick_verdict([5, 7, 6]) is Verdict.RE  # 多重错误取 RE
    assert pick_verdict([3, 4]) is Verdict.MLE  # OLE 与 MLE 取 MLE
    assert pick_verdict([6, 6, 6]) is Verdict.WA


def test_pick_verdict_conservative_rules():
    """保守规则与 UKE 层级（实测形态：纯 UKE / UKE+AC 混合判 UKE）。"""
    assert pick_verdict([]) is None  # 无测试点信息
    assert pick_verdict([12, 12]) is None  # 全 AC 但整题 UNAC
    assert pick_verdict([0, 1]) is None  # JG 不参选
    assert pick_verdict([11]) is Verdict.UKE  # 纯 UKE（评测方故障）
    assert pick_verdict([12, 11, 12]) is Verdict.UKE  # AC 多数 + 个别 UKE
    assert pick_verdict([11, 6]) is Verdict.WA  # UKE 与用户错误并存取用户错误
    assert pick_verdict([2]) is None  # CE 不经精化


async def test_fetch_submission_verdict_maps_detail():
    """精化：record/:id 详情测试点 → 严重度归一。"""

    def handler(url, params):
        assert url.endswith("/record/280413653")
        return FakeResponse(
            200,
            json.dumps(
                {
                    "code": 200,
                    "currentTemplate": "RecordShow",
                    "currentData": {
                        "record": {
                            "detail": {
                                "judgeResult": {
                                    "subtasks": [
                                        {"testCases": [{"status": 12}, {"status": 5}]},
                                        {"testCases": {"0": {"status": 6}}},  # dict 形态兼容
                                    ]
                                }
                            }
                        }
                    },
                }
            ),
        )

    adapter = make_adapter(handler)
    verdict = await adapter.fetch_submission_verdict("280413653", CREDS)
    assert verdict is Verdict.TLE  # 5(TLE) 与 6(WA) 并存取 TLE


async def test_fetch_submission_verdict_conservative_none():
    """测试点全 AC / 无详情 → None（保持 UNAC）。"""

    def handler(url, params):
        return FakeResponse(
            200,
            json.dumps(
                {
                    "code": 200,
                    "currentData": {"record": {"detail": {"judgeResult": {"subtasks": [{"testCases": [{"status": 12}]}]}}}},
                }
            ),
        )

    adapter = make_adapter(handler)
    assert await adapter.fetch_submission_verdict("1", CREDS) is None

    # 无 detail 字段 → None
    adapter2 = make_adapter(
        lambda url, params: FakeResponse(200, json.dumps({"code": 200, "currentData": {"record": {}}}))
    )
    assert await adapter2.fetch_submission_verdict("2", CREDS) is None


def test_problem_url():
    assert problem_url("P1001", None) == "https://www.luogu.com.cn/problem/P1001"
    assert (
        problem_url("P16967", 330287)
        == "https://www.luogu.com.cn/problem/P16967?contestId=330287"
    )
    assert problem_url("", None) == "https://www.luogu.com.cn"


async def test_fetch_reports_progress_with_total_on_full_sync():
    """全量同步逐页上报进度：fetched 累计、total 取首页信封 count。"""
    now = int(time.time())
    pages = {
        1: [row(i, now - i * 60) for i in range(1, 21)],
        2: [row(21, now - 1300)],
    }

    def handler(url, params):
        return FakeResponse(200, envelope(pages.get(int(params["page"]), [])))

    adapter = make_adapter(handler)
    calls: list[tuple[int, int | None]] = []
    async for _batch in adapter.fetch_submissions(
        "100000",
        since=None,
        credentials=CREDS,
        full_window_days=FULL_WINDOW_DAYS,
        full_min_rows=1,
        progress_cb=lambda fetched, total: calls.append((fetched, total)),
    ):
        pass
    assert calls == [(20, 9999), (21, 9999)]  # envelope() 固定 count=9999


async def test_fetch_no_progress_on_incremental():
    """增量同步总量不可知，不上报进度。"""
    since = now_minus(1)

    def handler(url, params):
        return FakeResponse(200, envelope([row(1, since + 60)]))

    adapter = make_adapter(handler)
    calls: list[tuple[int, int | None]] = []
    async for _batch in adapter.fetch_submissions(
        "100000",
        since=since,
        credentials=CREDS,
        full_window_days=FULL_WINDOW_DAYS,
        full_min_rows=FULL_MIN_ROWS,
        progress_cb=lambda fetched, total: calls.append((fetched, total)),
    ):
        pass
    assert calls == []
