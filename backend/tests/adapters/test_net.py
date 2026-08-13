"""HttpFetcher 外呼公共层测试：限流、退避重试、信封重试、失败抛错。"""

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest

from adapters.base import Credentials, PlatformError
from adapters.net import HttpFetcher

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_fetcher(handler) -> HttpFetcher:
    transport = httpx.MockTransport(handler)
    return HttpFetcher(transport=transport, max_retries=3, base_backoff=0.01)


def ok_json(data: object) -> httpx.Response:
    return httpx.Response(200, json=data)


async def test_get_json_returns_parsed_body():
    async def handler(request: httpx.Request) -> httpx.Response:
        return ok_json({"status": "OK", "result": [1, 2]})

    fetcher = make_fetcher(handler)
    try:
        data = await fetcher.get_json(
            "https://example.com/api", platform="p", min_interval=0
        )
        assert data == {"status": "OK", "result": [1, 2]}
    finally:
        await fetcher.aclose()


async def test_retries_on_429_then_succeeds():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429)
        return ok_json({"ok": True})

    fetcher = make_fetcher(handler)
    try:
        data = await fetcher.get_json(
            "https://example.com/api", platform="p", min_interval=0
        )
        assert data == {"ok": True}
        assert calls == 2
    finally:
        await fetcher.aclose()


async def test_retries_on_5xx():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503) if calls < 3 else ok_json({"ok": True})

    fetcher = make_fetcher(handler)
    try:
        data = await fetcher.get_json(
            "https://example.com/api", platform="p", min_interval=0
        )
        assert data == {"ok": True}
        assert calls == 3
    finally:
        await fetcher.aclose()


async def test_retries_on_transport_error():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection refused")
        return ok_json({"ok": True})

    fetcher = make_fetcher(handler)
    try:
        data = await fetcher.get_json(
            "https://example.com/api", platform="p", min_interval=0
        )
        assert data == {"ok": True}
        assert calls == 2
    finally:
        await fetcher.aclose()


async def test_retries_on_envelope_hook():
    """业务信封重试：should_retry 返回 True 时统一退避重试。"""
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ok_json({"status": "FAILED", "comment": "Call limit exceeded"})
        return ok_json({"status": "OK", "result": []})

    fetcher = make_fetcher(handler)
    try:
        data = await fetcher.get_json(
            "https://example.com/api",
            platform="p",
            min_interval=0,
            should_retry=lambda d: isinstance(d, dict)
            and d.get("status") == "FAILED"
            and "call limit" in str(d.get("comment", "")).lower(),
        )
        assert data["status"] == "OK"
        assert calls == 2
    finally:
        await fetcher.aclose()


async def test_raises_platform_error_when_retries_exhausted():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    fetcher = make_fetcher(handler)
    try:
        with pytest.raises(PlatformError):
            await fetcher.get_json("https://example.com/api", platform="p", min_interval=0)
        assert calls == 4  # 1 次初试 + 3 次重试
    finally:
        await fetcher.aclose()


async def test_4xx_not_retried():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, text="bad")

    fetcher = make_fetcher(handler)
    try:
        with pytest.raises(PlatformError):
            await fetcher.get_json("https://example.com/api", platform="p", min_interval=0)
        assert calls == 1
    finally:
        await fetcher.aclose()


async def test_backoff_respects_min_interval():
    """重试退避基准不小于平台限流间隔：首次重试错开一个完整限流窗口。

    防止重试请求仍落在限流窗口内（如 CF 2s 间隔下固定 0.5s 起步大概率再撞限流）。
    """
    min_interval = 0.05
    timestamps: list[float] = []
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        timestamps.append(time.monotonic())
        calls += 1
        if calls == 1:
            return httpx.Response(429)
        return ok_json({"ok": True})

    fetcher = make_fetcher(handler)  # base_backoff=0.01 < min_interval
    try:
        data = await fetcher.get_json(
            "https://example.com/api", platform="p", min_interval=min_interval
        )
        assert data == {"ok": True}
        elapsed = timestamps[1] - timestamps[0]
        assert elapsed >= min_interval - 0.005
    finally:
        await fetcher.aclose()


async def test_credentials_cookies_applied():
    """凭据 cookies 统一应用到请求（adapter 不自行拼 Cookie 头）。"""
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["cookie"] = request.headers.get("cookie", "")
        return ok_json({"ok": True})

    fetcher = make_fetcher(handler)
    try:
        creds = Credentials(cookies={"_uid": "123", "__client_id": "abc"})
        await fetcher.get_json(
            "https://example.com/api",
            platform="p",
            min_interval=0,
            credentials=creds,
        )
        assert "_uid=123" in seen["cookie"]
        assert "__client_id=abc" in seen["cookie"]
    finally:
        await fetcher.aclose()


async def test_credentials_headers_merged_caller_wins():
    """凭据 headers 与调用方显式 headers 合并，调用方优先。"""
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent", "")
        seen["x"] = request.headers.get("x-token", "")
        return ok_json({"ok": True})

    fetcher = make_fetcher(handler)
    try:
        creds = Credentials(headers={"User-Agent": "cred-ua", "X-Token": "from-cred"})
        await fetcher.get_json(
            "https://example.com/api",
            platform="p",
            min_interval=0,
            credentials=creds,
            headers={"X-Token": "from-caller"},
        )
        assert seen["ua"] == "cred-ua"  # 仅凭据提供
        assert seen["x"] == "from-caller"  # 调用方覆盖
    finally:
        await fetcher.aclose()


async def test_post_json_sends_body():
    """post_json 语法糖：POST + JSON body（GraphQL 平台用）。"""
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = request.content.decode()
        return ok_json({"data": {"ok": True}})

    fetcher = make_fetcher(handler)
    try:
        data = await fetcher.post_json(
            "https://example.com/graphql",
            json={"query": "{ me { id } }"},
            platform="p",
            min_interval=0,
        )
        assert data == {"data": {"ok": True}}
        assert seen["method"] == "POST"
        assert "query" in seen["body"]
    finally:
        await fetcher.aclose()


async def test_per_call_max_retries_override():
    """单次调用可覆盖全局重试次数（平台专项策略）。"""
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    fetcher = HttpFetcher(
        transport=httpx.MockTransport(handler),
        max_retries=3,
        base_backoff=0.01,
    )
    try:
        with pytest.raises(PlatformError):
            await fetcher.get_json(
                "https://example.com/api", platform="p", min_interval=0, max_retries=1
            )
        assert calls == 2  # 1 次初试 + 1 次重试（覆盖全局 3 次）
    finally:
        await fetcher.aclose()


async def test_rate_limit_paces_requests_per_platform():
    """同平台请求间隔不小于 min_interval；不同平台互不阻塞。"""
    MIN_INTERVAL = 0.05

    async def handler(request: httpx.Request) -> httpx.Response:
        return ok_json({"ok": True})

    fetcher = make_fetcher(handler)
    try:
        t0 = time.monotonic()
        await fetcher.get_json(
            "https://example.com/a", platform="p", min_interval=MIN_INTERVAL
        )
        await fetcher.get_json(
            "https://example.com/b", platform="p", min_interval=MIN_INTERVAL
        )
        elapsed = time.monotonic() - t0
        assert elapsed >= MIN_INTERVAL - 0.01

        # 不同平台串行执行时不互相等待
        t0 = time.monotonic()
        async def two_platforms() -> None:
            await asyncio.gather(
                fetcher.get_json("https://example.com/c", platform="p", min_interval=0),
                fetcher.get_json("https://example.com/d", platform="q", min_interval=0),
            )
        await two_platforms()
        assert time.monotonic() - t0 < MIN_INTERVAL
    finally:
        await fetcher.aclose()
