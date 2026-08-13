"""Codeforces 适配器测试：录制 JSON fixture 解析、分页、增量停止、全量窗口、信封处理。"""

import copy
import json
import time
from pathlib import Path

import httpx
import pytest

from adapters.base import PlatformError, PlatformSubmission, UserNotFoundError, Verdict
from adapters.codeforces import CodeforcesAdapter
from adapters.codeforces.api_models import CfSubmissionRow
from adapters.codeforces.normalize import map_verdict, problem_key, problem_url
from adapters.net import HttpFetcher

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE = json.loads((FIXTURES / "cf_user_status_sample.json").read_text(encoding="utf-8"))
INFO_OK = json.loads((FIXTURES / "cf_user_info_ok.json").read_text(encoding="utf-8"))
INFO_NOT_FOUND = json.loads(
    (FIXTURES / "cf_user_info_not_found.json").read_text(encoding="utf-8")
)

# 全量同步策略参数（生产由 Settings 注入，测试直接传）
FULL_WINDOW_DAYS = 370
FULL_MIN_ROWS = 5000


def make_fetcher(handler) -> HttpFetcher:
    return HttpFetcher(transport=httpx.MockTransport(handler), base_backoff=0.01)


def ok_json(data: object) -> httpx.Response:
    return httpx.Response(200, json=data)


def make_adapter(handler) -> tuple[CodeforcesAdapter, HttpFetcher]:
    fetcher = make_fetcher(handler)
    adapter = CodeforcesAdapter(fetcher)
    adapter.min_interval = 0  # 测试禁用真实限流等待（限流本身由 test_net 覆盖）
    return adapter, fetcher


def row(id_: int, ts: int, verdict: str = "OK", index: str = "F") -> dict:
    """基于录制样本复制一行并覆盖关键字段。"""
    r = copy.deepcopy(SAMPLE["result"][0])
    r["id"] = id_
    r["creationTimeSeconds"] = ts
    r["verdict"] = verdict
    r["problem"]["index"] = index
    return r


def now_minus(days: float) -> int:
    return int(time.time()) - int(days * 86400)


# ===== verify =====


async def test_verify_ok():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["handles"] == "tourist"
        return ok_json(INFO_OK)

    adapter, fetcher = make_adapter(handler)
    try:
        info = await adapter.verify("tourist")
        assert info.handle == "tourist"
        assert info.avatar == "https://userpic.codeforces.org/no-avatar.jpg"
    finally:
        await fetcher.aclose()


async def test_verify_user_not_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        return ok_json(INFO_NOT_FOUND)

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(UserNotFoundError):
            await adapter.verify("no_such_user_xyz")
    finally:
        await fetcher.aclose()


async def test_verify_empty_result_not_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        return ok_json({"status": "OK", "result": []})

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(UserNotFoundError):
            await adapter.verify("ghost")
    finally:
        await fetcher.aclose()


async def test_verify_envelope_failure_is_platform_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return ok_json({"status": "FAILED", "comment": "something broke"})

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError):
            await adapter.verify("tourist")
    finally:
        await fetcher.aclose()


async def test_verify_retries_call_limit_envelope():
    """限流信封（200 + FAILED + Call limit exceeded）重试后成功。"""
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ok_json({"status": "FAILED", "comment": "Call limit exceeded"})
        return ok_json(INFO_OK)

    adapter, fetcher = make_adapter(handler)
    try:
        info = await adapter.verify("tourist")
        assert info.handle == "tourist"
        assert calls == 2
    finally:
        await fetcher.aclose()


# ===== fetch_submissions =====


async def test_fetch_full_pages_until_empty(monkeypatch):
    """全量分页：拉到最后一页不满为止（模拟每页满 2 条）。"""
    monkeypatch.setattr("adapters.codeforces.PAGE_SIZE", 2)
    now = int(time.time())
    pages = [
        [row(3, now - 86400), row(2, now - 2 * 86400)],
        [row(1, now - 3 * 86400)],  # 不满页 → 停止
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        from_ = int(request.url.params["from"])
        count = int(request.url.params["count"])
        idx = (from_ - 1) // count
        if idx >= len(pages):
            return ok_json({"status": "OK", "result": []})
        return ok_json({"status": "OK", "result": pages[idx]})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await adapter.fetch_submissions(
            "example",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        assert [s.submission_id for s in items] == ["3", "2", "1"]
        assert items[0].verdict == Verdict.AC
        assert items[0].problem_key == "2245F"
        assert items[0].problem_url == "https://codeforces.com/contest/2245/problem/F"
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_stops_at_cursor():
    """增量：游标之前的旧提交不拉取。"""
    now = int(time.time())
    since = now_minus(2)
    pages = [
        [row(3, now - 86400), row(2, now - 2 * 86400 + 60)],
        [row(1, now - 3 * 86400)],  # 旧于游标，应触发停止
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        from_ = int(request.url.params["from"])
        idx = (from_ - 1) // 1000
        return ok_json({"status": "OK", "result": pages[idx]})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await adapter.fetch_submissions(
            "example",
            since=since,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        assert [s.submission_id for s in items] == ["3", "2"]
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_repeats_cursor_second():
    """游标当秒的提交会被重复拉取（ts < since 才停），同秒多提交不丢失。

    停止条件放宽后靠 store 按 submission_id 去重吸收重复，无漏拉风险。
    """
    since = now_minus(2)
    pages = [
        [row(3, since + 60), row(2, since)],  # 第二条与游标同秒 → 应被拉取
        [row(1, since - 60)],  # 旧于游标 → 停止
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        from_ = int(request.url.params["from"])
        idx = (from_ - 1) // 1000
        return ok_json({"status": "OK", "result": pages[idx]})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await adapter.fetch_submissions(
            "example",
            since=since,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        assert [s.submission_id for s in items] == ["3", "2"]
    finally:
        await fetcher.aclose()


async def test_fetch_full_stops_past_window_with_min_rows(monkeypatch):
    """全量：越过窗口起点且累计 ≥ full_min_rows 即停。"""
    monkeypatch.setattr("adapters.codeforces.PAGE_SIZE", 2)
    now = int(time.time())
    pages = [
        [row(4, now - 86400), row(3, now - 2 * 86400)],  # 窗口内
        [row(2, now - 400 * 86400), row(1, now - 401 * 86400)],  # 窗口外
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        from_ = int(request.url.params["from"])
        count = int(request.url.params["count"])
        idx = (from_ - 1) // count
        return ok_json({"status": "OK", "result": pages[idx]})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await adapter.fetch_submissions(
            "example",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=3,
        )
        assert [s.submission_id for s in items] == ["4", "3", "2", "1"]
    finally:
        await fetcher.aclose()


async def test_fetch_full_keeps_pulling_inside_window(monkeypatch):
    """全量：窗口内的数据即使超过 full_min_rows 也继续拉（保证热力图完整）。"""
    monkeypatch.setattr("adapters.codeforces.PAGE_SIZE", 2)
    now = int(time.time())
    pages = [
        [row(4, now - 86400), row(3, now - 2 * 86400)],
        [row(2, now - 3 * 86400), row(1, now - 4 * 86400)],  # 仍在窗口内
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        from_ = int(request.url.params["from"])
        count = int(request.url.params["count"])
        idx = (from_ - 1) // count
        if idx >= len(pages):
            return ok_json({"status": "OK", "result": []})
        return ok_json({"status": "OK", "result": pages[idx]})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await adapter.fetch_submissions(
            "example",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        assert [s.submission_id for s in items] == ["4", "3", "2", "1"]
    finally:
        await fetcher.aclose()


async def test_fetch_envelope_failure_raises():
    async def handler(request: httpx.Request) -> httpx.Response:
        return ok_json({"status": "FAILED", "comment": "limit exceeded"})

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError):
            await adapter.fetch_submissions(
                "example",
                since=None,
                full_window_days=FULL_WINDOW_DAYS,
                full_min_rows=FULL_MIN_ROWS,
            )
    finally:
        await fetcher.aclose()


# ===== 归一化纯函数 =====


def test_verdict_mapping():
    assert map_verdict("OK") is Verdict.AC
    assert map_verdict("WRONG_ANSWER") is Verdict.WA
    assert map_verdict("COMPILATION_ERROR") is Verdict.CE
    assert map_verdict("RUNTIME_ERROR") is Verdict.RE
    assert map_verdict("TIME_LIMIT_EXCEEDED") is Verdict.TLE
    assert map_verdict("MEMORY_LIMIT_EXCEEDED") is Verdict.MLE
    assert map_verdict("SUBMITTED") is Verdict.JG
    assert map_verdict("TESTING") is Verdict.JG
    assert map_verdict("CHALLENGED") is Verdict.UKE
    assert map_verdict("") is Verdict.UKE
    assert map_verdict("SOME_FUTURE_VERDICT") is Verdict.UKE


def test_problem_url_contest_vs_gym():
    # 主题库：四位数 contestId → /contest/ 页
    assert problem_url(2245, "F") == "https://codeforces.com/contest/2245/problem/F"
    # gym 题库：六位数 contestId → /gym/ 页
    assert problem_url(103091, "A") == "https://codeforces.com/gym/103091/problem/A"
    assert problem_url(100495, "B") == "https://codeforces.com/gym/100495/problem/B"
    # 缺失信息兜底平台主页
    assert problem_url(None, None) == "https://codeforces.com"
    assert problem_url(2245, None) == "https://codeforces.com"


def test_problem_key_fallback():
    assert problem_key(2245, "F", "X Axis") == "2245F"
    assert problem_key(None, None, "X Axis") == "X Axis"


def test_difficulty_accepts_str():
    """difficulty 保留平台原始值：CF 为分数（int），LeetCode/洛谷为档位（str）。"""
    s = PlatformSubmission(
        submission_id="1",
        problem_key="two-sum",
        problem_name="两数之和",
        problem_url="https://leetcode.cn/problems/two-sum/",
        difficulty="easy",
        verdict=Verdict.AC,
        submitted_at=1000,
        language="Python3",
    )
    assert s.difficulty == "easy"


def test_to_submission_row_mapping():
    row = CfSubmissionRow.model_validate(SAMPLE["result"][0])
    s = CodeforcesAdapter._to_submission(row, 1755100000)
    assert isinstance(s, PlatformSubmission)
    assert s.submission_id == "102938475"
    assert s.problem_key == "2245F"
    assert s.problem_name == "X Axis"
    assert s.difficulty == 800
    assert s.verdict is Verdict.AC
    assert s.language == "GNU C++17"
    assert s.submitted_at == 1755100000


async def test_fetch_malformed_row_raises_platform_error():
    """平台响应畸形（result 行类型不符）时抛 PlatformError，不静默吞错。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return ok_json(
            {"status": "OK", "result": [{"id": "not_an_int", "creationTimeSeconds": 1}]}
        )

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError):
            await adapter.fetch_submissions(
                "example",
                since=None,
                full_window_days=FULL_WINDOW_DAYS,
                full_min_rows=FULL_MIN_ROWS,
            )
    finally:
        await fetcher.aclose()
