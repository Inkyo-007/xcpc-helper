"""VJudge 适配器测试：JSON 解析、分页、增量停止、verdict 映射。"""

import json
import time
from pathlib import Path

import httpx
import pytest

from adapters.base import (
    AuthExpiredError,
    PlatformSubmission,
    UserNotFoundError,
    Verdict,
)
from adapters.net import HttpFetcher
from adapters.vjudge import MAX_PAGE_SIZE, VJudgeAdapter
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
        if "user/submissions" in str(request.url):
            return httpx.Response(200, json=SAMPLE)
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        info = await adapter.verify("testuser", credentials=creds)
        assert info.handle == "testuser"
        assert info.display_name is None
    finally:
        await fetcher.aclose()


async def test_verify_no_credentials():
    adapter, fetcher = make_adapter(lambda r: httpx.Response(200))
    try:
        with pytest.raises(AuthExpiredError):
            await adapter.verify("testuser")
    finally:
        await fetcher.aclose()


async def test_verify_user_not_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "error": {"i18nKey": "user.error.not_exist", "trustable": False}
        })

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        with pytest.raises(UserNotFoundError):
            await adapter.verify("nonexistent", credentials=creds)
    finally:
        await fetcher.aclose()


async def test_verify_auth_expired():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "error": {"i18nKey": "user.error.login_required", "trustable": False}
        })

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        with pytest.raises(AuthExpiredError):
            await adapter.verify("testuser", credentials=creds)
    finally:
        await fetcher.aclose()


# ===== fetch_submissions =====


def _make_submission_row(run_id: int, ts_sec: int, result: str = "AC") -> list:
    """构造单条提交记录数组。"""
    return [
        run_id,           # 0: runId
        "Codeforces",     # 1: OJId
        "436B",           # 2: probNum
        result,           # 3: result
        "C++",            # 4: language
        100,              # 5: time(ms)
        256,              # 6: memory(KB)
        500,              # 7: length
        ts_sec * 1000,    # 8: submitTime(ms)
    ]


async def test_fetch_full_pages_until_short():
    """全量分页：拉到短页为止。"""
    now = int(time.time())
    # 第 1 页：满页 500 条（模拟）
    page1 = [_make_submission_row(500 + i, now - 86400 - i) for i in range(MAX_PAGE_SIZE)]
    # 第 2 页：短页 1 条 → 停止
    page2 = [_make_submission_row(1, now - 3 * 86400)]

    async def handler(request: httpx.Request) -> httpx.Response:
        max_id = request.url.params.get("maxId")
        if max_id is None:
            return httpx.Response(200, json={"data": page1})
        return httpx.Response(200, json={"data": page2})

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        # 使用 collect_all 替代 collect，收集所有 batch 包括 done=True 的
        all_batches = []
        async for batch in adapter.fetch_submissions(
            "testuser",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials=creds,
        ):
            all_batches.append(batch)
        # 第 1 页：500 条，done=False（满页）
        # 第 2 页：1 条，done=True（短页）
        assert len(all_batches) == 2
        assert len(all_batches[0].items) == MAX_PAGE_SIZE
        assert len(all_batches[1].items) == 1
        assert all_batches[1].done is True
        # 验证第一条数据
        assert all_batches[0].items[0].submission_id == "500"
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
        _make_submission_row(3, now - 86400),
        _make_submission_row(2, since_ts + 60),
        _make_submission_row(1, since_ts - 60),  # 旧于游标
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": page1})

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        items = await collect(
            adapter,
            "testuser",
            since=since_ts,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials=creds,
        )
        assert len(items) == 2
        assert [s.submission_id for s in items] == ["3", "2"]
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_repeats_cursor_second():
    """游标当秒的提交会被重复拉取（ts < since 才停），同秒多提交不丢失。"""
    since_ts = int(time.time()) - 2 * 86400
    page1 = [
        _make_submission_row(3, since_ts + 60),
        _make_submission_row(2, since_ts),  # 与游标同秒 → 应被拉取
        _make_submission_row(1, since_ts - 60),  # 旧于游标 → 停止
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": page1})

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        items = await collect(
            adapter,
            "testuser",
            since=since_ts,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials=creds,
        )
        assert len(items) == 2
        assert [s.submission_id for s in items] == ["3", "2"]
    finally:
        await fetcher.aclose()


async def test_fetch_empty_account():
    """0 提交用户：空数组 → done=True。"""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        items = await collect(
            adapter,
            "emptyuser",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials=creds,
        )
        assert items == []
    finally:
        await fetcher.aclose()


async def test_fetch_auth_expired():
    """凭据过期 → AuthExpiredError。"""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "error": {"i18nKey": "user.error.login_required", "trustable": False}
        })

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        with pytest.raises(AuthExpiredError):
            await collect(
                adapter,
                "testuser",
                since=None,
                full_window_days=FULL_WINDOW_DAYS,
                full_min_rows=FULL_MIN_ROWS,
                credentials=creds,
            )
    finally:
        await fetcher.aclose()


async def test_fetch_resume_from_checkpoint():
    """断点续传：resume_checkpoint 的 max_id 透传为起始游标。"""
    requested_max_ids: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_max_ids.append(request.url.params.get("maxId"))
        return httpx.Response(200, json={"data": []})

    adapter, fetcher = make_adapter(handler)
    try:
        from adapters.base import Credentials
        creds = Credentials(cookies={"JSESSIONID": "test", "JSESSlONID": "test"})
        items = await collect(
            adapter,
            "testuser",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials=creds,
            resume_checkpoint={"max_id": 9999, "fetched": 500},
        )
        assert items == []
        assert requested_max_ids == ["9999"]
    finally:
        await fetcher.aclose()


# ===== 归一化纯函数 =====


def test_verdict_mapping():
    assert map_verdict("AC") is Verdict.AC
    assert map_verdict("WA") is Verdict.WA
    assert map_verdict("TLE") is Verdict.TLE
    assert map_verdict("MLE") is Verdict.MLE
    assert map_verdict("RE") is Verdict.RE
    assert map_verdict("CE") is Verdict.CE
    assert map_verdict("OLE") is Verdict.OLE
    assert map_verdict("PE") is Verdict.UKE
    assert map_verdict("JUDGING") is Verdict.JG
    assert map_verdict("PENDING") is Verdict.JG
    assert map_verdict("RUNNING") is Verdict.JG
    assert map_verdict("WAITING") is Verdict.JG
    assert map_verdict("UNKNOWN") is Verdict.UKE
    assert map_verdict("") is Verdict.UKE


def test_problem_url():
    assert problem_url("Codeforces", "436B") == "https://vjudge.net/problem/Codeforces-436B"
    assert problem_url("POJ", "1000") == "https://vjudge.net/problem/POJ-1000"


def test_to_submission_row_mapping():
    """单条数组行 → PlatformSubmission 映射验证。"""
    now = int(time.time())
    row = _make_submission_row(42, now, "AC")
    adapter = VJudgeAdapter.__new__(VJudgeAdapter)
    s = adapter._to_submission(row, now)
    assert isinstance(s, PlatformSubmission)
    assert s.submission_id == "42"
    assert s.problem_key == "Codeforces-436B"
    assert s.problem_name == "436B"
    assert s.problem_url == "https://vjudge.net/problem/Codeforces-436B"
    assert s.difficulty is None
    assert s.verdict is Verdict.AC
    assert s.language == "C++"
    assert s.submitted_at == now


def test_timestamp_conversion():
    """毫秒级时间戳 → 秒级转换验证。"""
    adapter = VJudgeAdapter.__new__(VJudgeAdapter)
    row = [
        1, "Codeforces", "436B", "AC", "C++",
        100, 256, 500, 1500000000000,  # 毫秒级
    ]
    s = adapter._to_submission(row, 1500000000)
    assert s.submitted_at == 1500000000
