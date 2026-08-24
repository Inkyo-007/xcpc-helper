"""VJudge 适配器测试：JSON 解析、分页、增量停止、verdict 映射。"""

import json
import time
from pathlib import Path

import httpx
import pytest

from adapters.base import PlatformSubmission, UserNotFoundError, Verdict
from adapters.net import HttpFetcher
from adapters.vjudge import PAGE_SIZE, VJudgeAdapter
from adapters.vjudge.normalize import map_verdict, problem_url

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE = json.loads((FIXTURES / "vj_submissions_sample.json").read_text(encoding="utf-8"))

FULL_WINDOW_DAYS = 370
FULL_MIN_ROWS = 5000


def make_fetcher(handler) -> HttpFetcher:
    return HttpFetcher(transport=httpx.MockTransport(handler), base_backoff=0.01)


def make_adapter(handler) -> tuple[VJudgeAdapter, HttpFetcher]:
    fetcher = make_fetcher(handler)
    adapter = VJudgeAdapter(fetcher)
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
        if "status/data" in str(request.url):
            return httpx.Response(200, json=SAMPLE)
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        info = await adapter.verify("Inkyo")
        assert info.handle == "Inkyo"
        assert info.display_name is None
    finally:
        await fetcher.aclose()


async def test_verify_user_not_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "recordsTotal": 9999999, "recordsFiltered": 9999999, "draw": 1})

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(UserNotFoundError):
            await adapter.verify("nonexistent")
    finally:
        await fetcher.aclose()


# ===== fetch_submissions =====


def _make_submission_item(run_id: int, ts_ms: int, status: str = "Accepted") -> dict:
    """构造单条提交记录对象（/status/data 格式）。"""
    return {
        "runId": run_id,
        "oj": "Codeforces",
        "probNum": "436B",
        "status": status,
        "language": "GNU G++20 13.2",
        "languageCanonical": "CPP",
        "time": ts_ms,
        "memory": 100,
        "runtime": 218,
        "sourceLength": 500,
        "userName": "testuser",
        "userId": 12345,
    }


async def test_fetch_full_pages_until_short():
    """全量分页：拉到短页为止。"""
    now_ms = int(time.time()) * 1000
    # 第 1 页：满页 100 条（模拟）
    page1 = [_make_submission_item(100 + i, now_ms - 86400000 - i * 1000) for i in range(PAGE_SIZE)]
    # 第 2 页：短页 1 条 → 停止
    page2 = [_make_submission_item(1, now_ms - 3 * 86400000)]

    async def handler(request: httpx.Request) -> httpx.Response:
        start = request.url.params.get("start")
        if start == "0":
            return httpx.Response(200, json={"data": page1, "recordsTotal": 9999999, "recordsFiltered": 9999999, "draw": 1})
        return httpx.Response(200, json={"data": page2, "recordsTotal": 9999999, "recordsFiltered": 9999999, "draw": 1})

    adapter, fetcher = make_adapter(handler)
    try:
        all_batches = []
        async for batch in adapter.fetch_submissions(
            "testuser",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        ):
            all_batches.append(batch)
        # 第 1 页：100 条，done=False（满页）
        # 第 2 页：1 条，done=True（短页）
        assert len(all_batches) == 2
        assert len(all_batches[0].items) == PAGE_SIZE
        assert len(all_batches[1].items) == 1
        assert all_batches[1].done is True
        # 验证第一条数据
        assert all_batches[0].items[0].submission_id == "100"
        assert all_batches[0].items[0].verdict == Verdict.AC
        assert all_batches[0].items[0].problem_key == "Codeforces-436B"
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_stops_at_cursor():
    """增量：游标之前的旧提交不拉取。"""
    now = int(time.time())
    since_ts = now - 2 * 86400
    # 第 1 页：2 条新提交 + 1 条旧提交（触发停止）
    page1 = [
        _make_submission_item(3, (now - 86400) * 1000),
        _make_submission_item(2, (since_ts + 60) * 1000),
        _make_submission_item(1, (since_ts - 60) * 1000),  # 旧于游标
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": page1, "recordsTotal": 9999999, "recordsFiltered": 9999999, "draw": 1})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "testuser",
            since=since_ts,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        assert len(items) == 2
        assert [s.submission_id for s in items] == ["3", "2"]
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_repeats_cursor_second():
    """游标当秒的提交会被重复拉取（ts < since 才停），同秒多提交不丢失。"""
    since_ts = int(time.time()) - 2 * 86400
    page1 = [
        _make_submission_item(3, (since_ts + 60) * 1000),
        _make_submission_item(2, since_ts * 1000),  # 与游标同秒 → 应被拉取
        _make_submission_item(1, (since_ts - 60) * 1000),  # 旧于游标 → 停止
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": page1, "recordsTotal": 9999999, "recordsFiltered": 9999999, "draw": 1})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "testuser",
            since=since_ts,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        assert len(items) == 2
        assert [s.submission_id for s in items] == ["3", "2"]
    finally:
        await fetcher.aclose()


async def test_fetch_empty_account():
    """0 提交用户：空数组 → done=True。"""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [], "recordsTotal": 9999999, "recordsFiltered": 9999999, "draw": 1})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "emptyuser",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
        )
        assert items == []
    finally:
        await fetcher.aclose()


async def test_fetch_resume_from_checkpoint():
    """断点续传：resume_checkpoint 的 start 透传为起始偏移。"""
    requested_starts: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_starts.append(request.url.params.get("start"))
        return httpx.Response(200, json={"data": [], "recordsTotal": 9999999, "recordsFiltered": 9999999, "draw": 1})

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "testuser",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            resume_checkpoint={"start": 500, "fetched": 1000},
        )
        assert items == []
        assert requested_starts == ["500"]
    finally:
        await fetcher.aclose()


# ===== 归一化纯函数 =====


def test_verdict_mapping():
    # /status/data 完整字符串
    assert map_verdict("Accepted") is Verdict.AC
    assert map_verdict("Wrong Answer") is Verdict.WA
    assert map_verdict("Time Limit Exceeded") is Verdict.TLE
    assert map_verdict("Memory Limit Exceeded") is Verdict.MLE
    assert map_verdict("Runtime Error") is Verdict.RE
    assert map_verdict("Compilation Error") is Verdict.CE
    assert map_verdict("Output Limit Exceeded") is Verdict.OLE
    assert map_verdict("Presentation Error") is Verdict.WA  # PE → WA
    # 缩写形式（兼容）
    assert map_verdict("AC") is Verdict.AC
    assert map_verdict("WA") is Verdict.WA
    assert map_verdict("TLE") is Verdict.TLE
    assert map_verdict("MLE") is Verdict.MLE
    assert map_verdict("RE") is Verdict.RE
    assert map_verdict("CE") is Verdict.CE
    assert map_verdict("OLE") is Verdict.OLE
    assert map_verdict("PE") is Verdict.WA  # PE → WA
    # 评测中
    assert map_verdict("Judging") is Verdict.JG
    assert map_verdict("Pending") is Verdict.JG
    assert map_verdict("Running") is Verdict.JG
    assert map_verdict("Compiling") is Verdict.JG
    assert map_verdict("Waiting") is Verdict.JG
    # 未知
    assert map_verdict("UNKNOWN") is Verdict.UKE
    assert map_verdict("") is Verdict.UKE


def test_problem_url():
    assert problem_url("Codeforces", "436B") == "https://vjudge.net/problem/Codeforces-436B"
    assert problem_url("POJ", "1000") == "https://vjudge.net/problem/POJ-1000"


def test_to_submission_mapping():
    """单条对象 → PlatformSubmission 映射验证。"""
    now_sec = int(time.time())
    row = {
        "runId": 42,
        "oj": "Codeforces",
        "probNum": "436B",
        "status": "Accepted",
        "language": "GNU G++20 13.2",
        "languageCanonical": "CPP",
        "time": now_sec * 1000,
        "memory": 100,
        "runtime": 218,
        "sourceLength": 500,
        "userName": "testuser",
        "userId": 12345,
    }
    adapter = VJudgeAdapter.__new__(VJudgeAdapter)
    s = adapter._to_submission(row, now_sec)
    assert isinstance(s, PlatformSubmission)
    assert s.submission_id == "42"
    assert s.problem_key == "Codeforces-436B"
    assert s.problem_name == "436B"
    assert s.problem_url == "https://vjudge.net/problem/Codeforces-436B"
    assert s.difficulty is None
    assert s.verdict is Verdict.AC
    assert s.language == "CPP"
    assert s.submitted_at == now_sec


def test_timestamp_conversion():
    """毫秒级时间戳 → 秒级转换验证。"""
    adapter = VJudgeAdapter.__new__(VJudgeAdapter)
    row = {
        "runId": 1,
        "oj": "Codeforces",
        "probNum": "436B",
        "status": "AC",
        "language": "C++",
        "languageCanonical": "CPP",
        "time": 1500000000000,
        "memory": 100,
        "runtime": 218,
        "sourceLength": 500,
    }
    s = adapter._to_submission(row, 1500000000)
    assert s.submitted_at == 1500000000
