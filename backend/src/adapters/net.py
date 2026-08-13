"""外呼公共层：共享 httpx 客户端、按平台限流、指数退避重试。

所有 adapter 共用一个 AsyncClient（连接池复用）；限流按 platform 维度
串行（同一平台请求之间保证 min_interval 间隔），不同平台互不阻塞。
重试为手写指数退避（不引新库），should_retry 钩子供 adapter 声明
"业务信封重试"（如 CF 以 200 返回的 FAILED 信封，由 net 层统一重试，
避免各 adapter 各写一套重试循环）。

退避基准与平台限流间隔联动：backoff = max(base_backoff, min_interval) × 2^n。
第一次重试等满一个完整限流窗口，避免重试请求仍落在限流窗口内
（如 CF 建议间隔 2s，若按固定 0.5s 起步大概率再撞 "Call limit exceeded"）。
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from adapters.base import PlatformError

logger = logging.getLogger("xcpc.adapters.net")

# 触发重试的传输异常（超时 / 连接失败 / 读错误等均继承自 TransportError）
_RETRYABLE_EXC = (httpx.TransportError,)
# 触发重试的 HTTP 状态码：限流与瞬时服务端错误
_RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpFetcher:
    """平台外呼公共客户端（应用级单例，随 activity service 生命周期）。"""

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
        base_backoff: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            transport=transport,  # 测试注入 MockTransport
        )
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        # 按平台记账：互斥锁 + 上次请求时刻（monotonic）
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        platform: str,
        min_interval: float,
        should_retry: Callable[[Any], bool] | None = None,
    ) -> Any:
        """GET 请求并解析 JSON；失败按平台重试策略处理。

        should_retry(data)：解析出的 JSON 若应重试（如 CF 的限流信封）
        返回 True，net 层统一退避重试。最终失败抛 PlatformError。
        """
        lock = self._locks.setdefault(platform, asyncio.Lock())
        async with lock:
            await self._pace(platform, min_interval)
            last_error: Exception | None = None
            for attempt in range(self._max_retries + 1):
                try:
                    resp = await self._client.get(url, params=params, headers=headers)
                except _RETRYABLE_EXC as exc:
                    last_error = exc
                    await self._backoff(attempt, min_interval)
                    continue
                if resp.status_code in _RETRY_STATUS:
                    last_error = PlatformError(f"平台返回 HTTP {resp.status_code}")
                    await self._backoff(attempt, min_interval)
                    continue
                if resp.status_code >= 400:
                    raise PlatformError(
                        f"平台返回 HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                data = resp.json()
                if should_retry is not None and should_retry(data):
                    last_error = PlatformError("平台返回失败信封（可重试）")
                    await self._backoff(attempt, min_interval)
                    continue
                self._last_request[platform] = time.monotonic()
                return data
            raise PlatformError(f"平台请求重试 {self._max_retries} 次仍失败: {last_error}")

    async def _pace(self, platform: str, min_interval: float) -> None:
        """请求前补齐平台建议间隔（异步 sleep，不阻塞事件循环）。"""
        last = self._last_request.get(platform)
        if last is None:
            return
        elapsed = time.monotonic() - last
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)

    async def _backoff(self, attempt: int, min_interval: float) -> None:
        """指数退避：基准取 max(全局 base_backoff, 平台 min_interval)，
        保证首次重试已错开一个完整限流窗口。"""
        base = max(self._base_backoff, min_interval)
        await asyncio.sleep(base * (2**attempt))
