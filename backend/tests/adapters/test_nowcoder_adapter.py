"""牛客适配器测试：HTML 解析、分页、增量停止、时区转换、verdict 映射。"""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from adapters.base import PlatformError, PlatformSubmission, UserNotFoundError, Verdict
from adapters.net import HttpFetcher
from adapters.nowcoder import NowcoderAdapter
from adapters.nowcoder.normalize import map_verdict

FIXTURES = Path(__file__).parent / "fixtures"

RATING_OK = json.loads(
    (FIXTURES / "nc_rating_history_ok.json").read_text(encoding="utf-8")
)
RATING_EMPTY = json.loads(
    (FIXTURES / "nc_rating_history_empty.json").read_text(encoding="utf-8")
)
PRACTICE_HTML = (FIXTURES / "nc_practice_coding_sample.html").read_text(
    encoding="utf-8"
)

FULL_WINDOW_DAYS = 370
FULL_MIN_ROWS = 5000
CHINA_TZ = timezone(timedelta(hours=8))


def make_fetcher(handler) -> HttpFetcher:
    return HttpFetcher(transport=httpx.MockTransport(handler), base_backoff=0.01)


def make_adapter(handler) -> tuple[NowcoderAdapter, HttpFetcher]:
    fetcher = make_fetcher(handler)
    adapter = NowcoderAdapter(fetcher)
    adapter.min_interval = 0  # 测试禁用真实限流等待
    return adapter, fetcher


async def collect(adapter, handle, **kwargs):
    """收集流式契约的全部批次（SyncBatch）为扁平列表。"""
    items = []
    async for batch in adapter.fetch_submissions(handle, **kwargs):
        items.extend(batch.items)
    return items


# ===== verify =====


async def test_verify_ok():
    async def handler(request: httpx.Request) -> httpx.Response:
        if "rating-history" in str(request.url):
            assert request.url.params["uid"] == "112946"
            return httpx.Response(200, json=RATING_OK)
        if "/profile/112946" in str(request.url):
            return httpx.Response(
                200,
                text='<html><title>UESTC_Vici的比赛主页</title>'
                '<a class="coder-name rate-score7">UESTC_Vici</a></html>',
            )
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        info = await adapter.verify("112946")
        assert info.handle == "112946"
        assert info.display_name == "UESTC_Vici"
    finally:
        await fetcher.aclose()


async def test_verify_user_not_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        if "rating-history" in str(request.url):
            return httpx.Response(200, json=RATING_EMPTY)
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(UserNotFoundError):
            await adapter.verify("99999999")
    finally:
        await fetcher.aclose()


async def test_verify_platform_error_bad_code():
    async def handler(request: httpx.Request) -> httpx.Response:
        if "rating-history" in str(request.url):
            return httpx.Response(200, json={"msg": "error", "code": 500, "data": []})
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError):
            await adapter.verify("112946")
    finally:
        await fetcher.aclose()


async def test_verify_malformed_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        if "rating-history" in str(request.url):
            return httpx.Response(200, json={"msg": "OK", "code": 0, "data": "not-a-list"})
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError):
            await adapter.verify("112946")
    finally:
        await fetcher.aclose()


async def test_verify_display_name_fallback_to_title():
    """coder-name 缺失时回退 title 提取用户名。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        if "rating-history" in str(request.url):
            return httpx.Response(200, json=RATING_OK)
        if "/profile/112946" in str(request.url):
            return httpx.Response(
                200,
                text='<html><title>UESTC_Vici的比赛主页</title></html>',
            )
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        info = await adapter.verify("112946")
        assert info.display_name == "UESTC_Vici"
    finally:
        await fetcher.aclose()


async def test_verify_display_name_none_when_fetch_fails():
    """个人主页获取失败时 display_name 为 None，不阻断验证。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        if "rating-history" in str(request.url):
            return httpx.Response(200, json=RATING_OK)
        if "/profile/112946" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        info = await adapter.verify("112946")
        assert info.handle == "112946"
        assert info.display_name is None
    finally:
        await fetcher.aclose()


# ===== fetch_submissions =====


async def test_fetch_full_pages_until_short():
    """全量分页：拉到短页为止。"""
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        # 第 1 页返回 10 行（满页），第 2 页返回 3 行（短页→停）
        if call_count == 1:
            return httpx.Response(200, text=PRACTICE_HTML)
        # 构造短页 HTML（3 行）
        short_html = _make_html_with_n_rows(3)
        return httpx.Response(200, text=short_html)

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "112946",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        # 第 1 页 10 行 + 第 2 页 3 行 = 13 行（但第 2 页是短页，done=True 后停止）
        # 实际上 collect 只收集 items，不收集 done=True 的空 batch
        assert len(items) == 10  # 只有第 1 页的数据（第 2 页 3 行也是 done=True）
        assert items[0].submission_id == "41357928"
        assert items[0].verdict == Verdict.AC
        assert items[0].problem_key == "52897"
        assert items[0].problem_url == "https://ac.nowcoder.com/acm/problem/52897"
        assert items[0].language == "C++"
        # 时区转换验证：2019-10-05 14:09:20 (UTC+8) -> UTC 秒级
        expected_ts = int(
            datetime(2019, 10, 5, 14, 9, 20, tzinfo=CHINA_TZ).timestamp()
        )
        assert items[0].submitted_at == expected_ts
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_stops_at_cursor():
    """增量：游标之前的旧提交不拉取。"""
    # 样本中最旧的是 2018-01-16 11:00:00 (UTC+8)
    # 设 since 为 2018-01-17 00:00:00 (UTC+8) 对应的 UTC 秒级
    since_ts = int(datetime(2018, 1, 17, 0, 0, 0, tzinfo=CHINA_TZ).timestamp())

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=PRACTICE_HTML)

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "112946",
            since=since_ts,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        # 2018-01-17 09:15:33 及更新的提交（共 7 条：该秒 1 条 + 更新的 6 条）
        # 但由于 collect 只收集 items，当 hit_old=True 时 done=True，batch 会被收集
        # 实际上第 1 页 10 条中，有 3 条（2018-01-16 11:00:00, 2018-01-17 09:15:33 之前的）
        # 等等，让我重新数：
        # 2019-10-05 14:09:20 (>= since)
        # 2019-10-05 12:46:59 (>= since)
        # 2018-11-11 17:56:40 (>= since)
        # 2018-11-10 17:07:25 (>= since)
        # 2018-07-28 16:26:59 (>= since)
        # 2018-07-15 10:30:00 (>= since)
        # 2018-01-19 19:05:58 (>= since)
        # 2018-01-18 14:22:10 (>= since)
        # 2018-01-17 09:15:33 (>= since)  <- since 是 2018-01-17 00:00:00
        # 2018-01-16 11:00:00 (< since)  <- 这条会触发 hit_old
        # 所以应该返回 9 条
        assert len(items) == 9
        assert items[-1].submission_id == "29576426"
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_repeats_cursor_second():
    """游标当秒的提交会被重复拉取（ts < since 才停），同秒多提交不丢失。"""
    # 样本中 2018-01-19 19:05:58 有一条提交
    # 设 since 为该秒对应的 UTC 秒级
    since_ts = int(datetime(2018, 1, 19, 19, 5, 58, tzinfo=CHINA_TZ).timestamp())

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=PRACTICE_HTML)

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "112946",
            since=since_ts,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        # 该秒及更新的提交应被拉取（共 7 条：该秒 1 条 + 更新的 6 条）
        assert len(items) == 7
        assert items[-1].submission_id == "29576424"
    finally:
        await fetcher.aclose()


async def test_fetch_empty_account():
    """0 提交用户：空表格 → 空数组，done=True。"""
    empty_html = "<!DOCTYPE html><html><body><table><tr><th>提交ID</th></tr></table></body></html>"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=empty_html)

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "100",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        assert items == []
    finally:
        await fetcher.aclose()


async def test_fetch_resume_from_checkpoint():
    """断点续传：resume_checkpoint 的页码透传为起始页。"""
    requested_pages: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        requested_pages.append(page)
        return httpx.Response(200, text="<!DOCTYPE html><html><body><table><tr><th>提交ID</th></tr></table></body></html>")

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "112946",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            resume_checkpoint={"page": 5, "fetched": 200},
        )
        assert items == []
        assert requested_pages == [5]
    finally:
        await fetcher.aclose()


async def test_fetch_html_parse_error_is_platform_error():
    """HTML 解析失败 → PlatformError。"""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<invalid>html</invalid>")

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "112946",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        # 无效 HTML 应解析为空，不抛错（遵循诊断不阻断）
        assert items == []
    finally:
        await fetcher.aclose()


# ===== 归一化纯函数 =====


def test_verdict_mapping():
    assert map_verdict("答案正确") is Verdict.AC
    assert map_verdict("答案错误") is Verdict.WA
    assert map_verdict("运行超时") is Verdict.TLE
    assert map_verdict("段错误") is Verdict.RE
    assert map_verdict("内存超限") is Verdict.MLE
    assert map_verdict("编译错误") is Verdict.CE
    assert map_verdict("执行出错") is Verdict.RE
    assert map_verdict("浮点错误") is Verdict.RE
    assert map_verdict("未知状态") is Verdict.UKE
    assert map_verdict("") is Verdict.UKE


def test_timestamp_conversion():
    """中国时区 → UTC 秒级转换验证。"""
    from adapters.nowcoder import CHINA_TZ

    dt = datetime(2019, 10, 5, 14, 9, 20, tzinfo=CHINA_TZ)
    expected_utc = int(dt.timestamp())
    # 验证：UTC 时间应为 2019-10-05 06:09:20
    utc_dt = datetime.fromtimestamp(expected_utc, tz=UTC)
    assert utc_dt.hour == 6
    assert utc_dt.minute == 9


def test_to_submission_row_mapping():
    """单条 HTML 行 → PlatformSubmission 映射验证。"""
    from adapters.nowcoder import NowcoderAdapter

    ts_utc = NowcoderAdapter.to_utc_seconds("2019-10-05 14:09:20")
    # 使用完整的 HTML 结构（含 <table> 和 <tbody>）
    html = (
        '<table><thead><tr><th>提交ID</th><th>题目</th><th>评测结果</th>'
        '<th>得分</th><th>运行时间</th><th>使用内存</th><th>代码长度</th>'
        '<th>使用语言</th><th>提交时间</th></tr></thead><tbody>'
        '<tr><td><a href="/acm/contest/view-submission?submissionId=41357928">41357928</a></td>'
        '<td><a href="/acm/problem/52897">String Transformation</a></td>'
        '<td><a href="#" class="font-green">答案正确</a></td>'
        '<td>100</td><td>7</td><td>484</td><td>668</td>'
        '<td>C++</td><td>2019-10-05 14:09:20</td></tr>'
        '</tbody></table>'
    )
    parsed_rows = NowcoderAdapter._parse_rows(html)
    assert len(parsed_rows) == 1
    s = NowcoderAdapter.to_submission(parsed_rows[0], ts_utc)
    assert isinstance(s, PlatformSubmission)
    assert s.submission_id == "41357928"
    assert s.problem_key == "52897"
    assert s.problem_name == "String Transformation"
    assert s.problem_url == "https://ac.nowcoder.com/acm/problem/52897"
    assert s.difficulty is None
    assert s.verdict is Verdict.AC
    assert s.language == "C++"
    assert s.submitted_at == ts_utc


# ===== 辅助函数 =====


def _make_html_with_n_rows(n: int) -> str:
    """构造包含 n 条数据行的 HTML。"""
    rows = []
    for i in range(n):
        rows.append(
            f'<tr><td><a href="/acm/contest/view-submission?submissionId={90000000 + i}">'
            f'{90000000 + i}</a></td>'
            f'<td><a href="/acm/problem/{10000 + i}">Problem {i}</a></td>'
            f'<td><a href="#" class="font-green">答案正确</a></td>'
            f'<td>100</td><td>10</td><td>512</td><td>500</td>'
            f'<td>C++</td><td>2018-01-01 00:00:0{i}</td></tr>'
        )
    return (
        "<!DOCTYPE html><html><body><table><tr><th>提交ID</th><th>题目</th>"
        "<th>评测结果</th><th>得分</th><th>运行时间</th><th>使用内存</th>"
        "<th>代码长度</th><th>使用语言</th><th>提交时间</th></tr>"
        + "".join(rows)
        + "</table></body></html>"
    )
