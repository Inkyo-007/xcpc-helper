"""LeetCode CN 适配器测试：GraphQL 解析、batch query、verdict 映射、进度回调。"""

import json
from pathlib import Path

import httpx
import pytest

from adapters.base import (
    AuthExpiredError,
    UserNotFoundError,
    Verdict,
)
from adapters.leetcode_cn import LeetCodeCNAdapter
from adapters.leetcode_cn.normalize import map_verdict, problem_url
from adapters.net import HttpFetcher

FIXTURES = Path(__file__).parent / "fixtures"

FULL_WINDOW_DAYS = 370
FULL_MIN_ROWS = 5000


def make_fetcher(handler) -> HttpFetcher:
    return HttpFetcher(transport=httpx.MockTransport(handler), base_backoff=0.01)


def make_adapter(handler) -> tuple[LeetCodeCNAdapter, HttpFetcher]:
    fetcher = make_fetcher(handler)
    adapter = LeetCodeCNAdapter(fetcher)
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
        body = json.loads(request.content)
        if "userProfilePublicProfile" in body.get("query", ""):
            return httpx.Response(200, json={
                "data": {
                    "userProfilePublicProfile": {
                        "username": "TestUser",
                        "siteRanking": 100,
                        "profile": {
                            "userSlug": "test-user",
                            "realName": "",
                            "userAvatar": "https://example.com/avatar.png",
                        },
                    }
                }
            })
        if "userProgressQuestionList" in body.get("query", ""):
            return httpx.Response(200, json={
                "data": {
                    "userProgressQuestionList": {
                        "totalNum": 10,
                        "questions": [{"frontendId": "1"}],
                    }
                }
            })
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        info = await adapter.verify("test-user")
        assert info.handle == "test-user"
        assert info.display_name == "TestUser"
        assert info.avatar == "https://example.com/avatar.png"
    finally:
        await fetcher.aclose()


async def test_verify_user_not_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "userProfilePublicProfile" in body.get("query", ""):
            return httpx.Response(200, json={"data": {"userProfilePublicProfile": None}})
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(UserNotFoundError):
            await adapter.verify("nonexistent")
    finally:
        await fetcher.aclose()


async def test_verify_auth_expired():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "userProfilePublicProfile" in body.get("query", ""):
            return httpx.Response(200, json={
                "data": {
                    "userProfilePublicProfile": {
                        "username": "TestUser",
                        "siteRanking": 100,
                        "profile": {"userSlug": "test-user", "realName": "", "userAvatar": ""},
                    }
                }
            })
        if "userProgressQuestionList" in body.get("query", ""):
            return httpx.Response(200, json={
                "errors": [{"message": "User not authenticated"}]
            })
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(AuthExpiredError):
            await adapter.verify("test-user", credentials={"cookies": {"LEETCODE_SESSION": "invalid"}})
    finally:
        await fetcher.aclose()


# ===== fetch_submissions =====


async def test_fetch_full_batch():
    """全量同步：获取题目清单 + batch 查询提交。"""
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        body = json.loads(request.content)
        query = body.get("query", "")

        if "userProgressQuestionList" in query:
            return httpx.Response(200, json={
                "data": {
                    "userProgressQuestionList": {
                        "totalNum": 2,
                        "questions": [
                            {
                                "frontendId": "1",
                                "title": "Two Sum",
                                "titleSlug": "two-sum",
                                "lastSubmittedAt": "2025-06-10T10:00:00+00:00",
                                "questionStatus": "SOLVED",
                                "lastResult": "AC",
                            },
                            {
                                "frontendId": "2",
                                "title": "Add Two Numbers",
                                "titleSlug": "add-two-numbers",
                                "lastSubmittedAt": "2025-06-11T10:00:00+00:00",
                                "questionStatus": "SOLVED",
                                "lastResult": "AC",
                            },
                        ],
                    }
                }
            })

        if "BatchSubmissions" in query or "submissionList" in query:
            return httpx.Response(200, json={
                "data": {
                    "two_sum": {"submissions": [{"id": "1001", "statusDisplay": "Accepted", "lang": "cpp", "timestamp": "1749540000"}]},
                    "add_two_numbers": {
                        "submissions": [
                            {"id": "1002", "statusDisplay": "Wrong Answer", "lang": "python3", "timestamp": "1749626400"},
                            {"id": "1003", "statusDisplay": "Accepted", "lang": "python3", "timestamp": "1749626500"},
                        ]
                    },
                }
            })

        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "test-user",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials={"cookies": {"LEETCODE_SESSION": "test", "csrftoken": "test"}},
        )
        assert len(items) == 3
        assert items[0].submission_id == "1001"
        assert items[0].verdict == Verdict.AC
        assert items[0].problem_key == "1"  # frontendId
        assert items[0].problem_name == "Two Sum"
        assert items[1].verdict == Verdict.WA
        assert items[1].problem_key == "2"  # frontendId
        assert items[1].problem_name == "Add Two Numbers"
        assert items[2].verdict == Verdict.AC
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_since():
    """增量同步：只拉 since 之后的题目。"""
    since_ts = 1749540000  # 2025-06-10 10:00:00 UTC

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        query = body.get("query", "")

        if "userProgressQuestionList" in query:
            return httpx.Response(200, json={
                "data": {
                    "userProgressQuestionList": {
                        "totalNum": 2,
                        "questions": [
                            {
                                "frontendId": "1",
                                "title": "Two Sum",
                                "titleSlug": "two-sum",
                                "lastSubmittedAt": "2025-06-10T09:00:00+00:00",  # 早于 since
                                "questionStatus": "SOLVED",
                                "lastResult": "AC",
                            },
                            {
                                "frontendId": "2",
                                "title": "Add Two Numbers",
                                "titleSlug": "add-two-numbers",
                                "lastSubmittedAt": "2025-06-11T10:00:00+00:00",  # 晚于 since
                                "questionStatus": "SOLVED",
                                "lastResult": "AC",
                            },
                        ],
                    }
                }
            })

        if "BatchSubmissions" in query or "submissionList" in query:
            # 使用 title_slug 作为别名（连字符替换为下划线）
            return httpx.Response(200, json={
                "data": {
                    "add_two_numbers": {
                        "submissions": [
                            {"id": "2001", "statusDisplay": "Accepted", "lang": "java", "timestamp": "1749626400"},
                        ]
                    },
                }
            })

        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "test-user",
            since=since_ts,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials={"cookies": {"LEETCODE_SESSION": "test", "csrftoken": "test"}},
        )
        assert len(items) == 1
        assert items[0].submission_id == "2001"
        # 增量过滤后只剩 add-two-numbers，problem_key 用 frontendId
        assert items[0].problem_key == "2"
    finally:
        await fetcher.aclose()


async def test_fetch_no_credentials():
    """无凭据时抛 AuthExpiredError。"""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(AuthExpiredError):
            await collect(adapter, "test-user", since=None, full_window_days=FULL_WINDOW_DAYS, full_min_rows=FULL_MIN_ROWS)
    finally:
        await fetcher.aclose()


async def test_fetch_empty_questions():
    """0 题用户：空数组，done=True。"""
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "userProgressQuestionList" in body.get("query", ""):
            return httpx.Response(200, json={
                "data": {"userProgressQuestionList": {"totalNum": 0, "questions": []}}
            })
        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        items = await collect(
            adapter,
            "test-user",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials={"cookies": {"LEETCODE_SESSION": "test", "csrftoken": "test"}},
        )
        assert items == []
    finally:
        await fetcher.aclose()


async def test_fetch_progress_callback():
    """进度回调按题目数上报。"""
    progress_calls = []

    def progress_cb(fetched: int, total: int | None) -> None:
        progress_calls.append((fetched, total))

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        query = body.get("query", "")

        if "userProgressQuestionList" in query:
            return httpx.Response(200, json={
                "data": {
                    "userProgressQuestionList": {
                        "totalNum": 3,
                        "questions": [
                            {"frontendId": "1", "title": "A", "titleSlug": "a", "lastSubmittedAt": "2025-06-10T10:00:00+00:00", "questionStatus": "SOLVED", "lastResult": "AC"},
                            {"frontendId": "2", "title": "B", "titleSlug": "b", "lastSubmittedAt": "2025-06-10T10:00:00+00:00", "questionStatus": "SOLVED", "lastResult": "AC"},
                            {"frontendId": "3", "title": "C", "titleSlug": "c", "lastSubmittedAt": "2025-06-10T10:00:00+00:00", "questionStatus": "SOLVED", "lastResult": "AC"},
                        ],
                    }
                }
            })

        if "BatchSubmissions" in query:
            return httpx.Response(200, json={
                "data": {
                    "a": {"submissions": [{"id": "1", "statusDisplay": "Accepted", "lang": "cpp", "timestamp": "1749540000"}]},
                    "b": {"submissions": [{"id": "2", "statusDisplay": "Accepted", "lang": "cpp", "timestamp": "1749540000"}]},
                    "c": {"submissions": [{"id": "3", "statusDisplay": "Accepted", "lang": "cpp", "timestamp": "1749540000"}]},
                }
            })

        return httpx.Response(404)

    adapter, fetcher = make_adapter(handler)
    try:
        items = []
        async for batch in adapter.fetch_submissions(
            "test-user",
            since=None,
            full_window_days=FULL_WINDOW_DAYS,
            full_min_rows=FULL_MIN_ROWS,
            credentials={"cookies": {"LEETCODE_SESSION": "test", "csrftoken": "test"}},
            progress_cb=progress_cb,
        ):
            items.extend(batch.items)

        assert len(items) == 3
        assert len(progress_calls) == 1  # 3 题在一个 batch 内完成
        assert progress_calls[0] == (3, 3)
    finally:
        await fetcher.aclose()


# ===== 归一化纯函数 =====


def test_verdict_mapping():
    assert map_verdict("Accepted") is Verdict.AC
    assert map_verdict("Wrong Answer") is Verdict.WA
    assert map_verdict("Runtime Error") is Verdict.RE
    assert map_verdict("Compile Error") is Verdict.CE
    assert map_verdict("Time Limit Exceeded") is Verdict.TLE
    assert map_verdict("Memory Limit Exceeded") is Verdict.MLE
    assert map_verdict("Output Limit Exceeded") is Verdict.OLE
    assert map_verdict("Unknown") is Verdict.UKE
    assert map_verdict("") is Verdict.UKE


def test_problem_url():
    assert problem_url("two-sum") == "https://leetcode.cn/problems/two-sum/"


# ===== 工具方法 =====


def test_parse_iso():
    adapter = LeetCodeCNAdapter.__new__(LeetCodeCNAdapter)
    dt = adapter._parse_iso("2025-06-10T10:00:00+00:00")
    assert dt.year == 2025
    assert dt.month == 6
    assert dt.day == 10
    assert dt.hour == 10


def test_extract_user_slug_from_session():
    """从 JWT payload 提取 user_slug。"""
    import base64
    import json

    payload = {"user_slug": "test-user", "id": 12345}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    token = f"header.{payload_b64}.signature"

    adapter = LeetCodeCNAdapter.__new__(LeetCodeCNAdapter)
    assert adapter._extract_user_slug_from_session(token) == "test-user"
    assert adapter._extract_user_slug_from_session("invalid") is None
    assert adapter._extract_user_slug_from_session("") is None
