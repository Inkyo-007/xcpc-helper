"""外呼公共层：共享 httpx 客户端、按平台限流、指数退避重试、凭据统一应用。

所有 adapter 共用一个 AsyncClient（连接池复用）；限流按 platform 维度
串行（同一平台请求之间保证 min_interval 间隔），不同平台互不阻塞。
重试为手写指数退避（不引新库），统一在 request() 内处理：

- 传输异常 / 429 / 5xx 重试，4xx 抛 HttpStatusError（PlatformError 子类，
  携带 status_code，供 adapter 区分 404 用户不存在等语义）；
- should_retry 钩子供 adapter 声明"业务信封重试"（如 CF 以 200 返回的
  FAILED 信封，需解析 JSON 判定），由本层统一退避重试；
- 退避基准与平台限流间隔联动：backoff = max(base_backoff, min_interval) × 2^n，
  首次重试等满一个完整限流窗口（如 CF 2s 间隔下固定 0.5s 起步大概率再撞限流）；
- max_retries / base_backoff 支持单次调用覆盖全局默认（平台专项重试策略，
  如洛谷 403 长延迟重试，落地时按需传入）。

Credentials 统一应用：cookies 转为 Cookie 头（httpx 弃用了 per-request
cookies 参数）、headers 与调用方显式请求头合并（调用方优先），
adapter 不自行拼 Cookie 头。
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from adapters.base import Credentials, HttpStatusError, PlatformError

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

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        credentials: Credentials | None = None,
        platform: str,
        min_interval: float,
        max_retries: int | None = None,
        base_backoff: float | None = None,
        should_retry: Callable[[Any], bool] | None = None,
    ) -> httpx.Response:
        """HTTP 请求核心：按平台限流 + 退避重试，返回 2xx 的 Response。

        should_retry(data)：响应解析出的 JSON 若应重试（如 CF 的限流信封）
        返回 True，本层统一退避重试；响应体非 JSON 时不判定（不重试）。
        最终失败抛 PlatformError。
        """
        retries = self._max_retries if max_retries is None else max_retries
        backoff_base = self._base_backoff if base_backoff is None else base_backoff
        lock = self._locks.setdefault(platform, asyncio.Lock())
        async with lock:
            await self._pace(platform, min_interval)
            last_error: Exception | None = None
            for attempt in range(retries + 1):
                try:
                    resp = await self._client.request(
                        method,
                        url,
                        params=params,
                        headers=self._merged_headers(credentials, headers),
                        json=json,
                    )
                except _RETRYABLE_EXC as exc:
                    last_error = exc
                    await self._backoff(attempt, min_interval, backoff_base)
                    continue
                if resp.status_code in _RETRY_STATUS:
                    last_error = PlatformError(f"平台返回 HTTP {resp.status_code}")
                    await self._backoff(attempt, min_interval, backoff_base)
                    continue
                if resp.status_code >= 400:
                    raise HttpStatusError(
                        resp.status_code,
                        f"平台返回 HTTP {resp.status_code}: {resp.text[:200]}",
                    )
                if should_retry is not None and self._retryable_envelope(
                    resp, should_retry
                ):
                    last_error = PlatformError("平台返回失败信封（可重试）")
                    await self._backoff(attempt, min_interval, backoff_base)
                    continue
                self._last_request[platform] = time.monotonic()
                return resp
            raise PlatformError(f"平台请求重试 {retries} 次仍失败: {last_error}")

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        credentials: Credentials | None = None,
        platform: str,
        min_interval: float,
        max_retries: int | None = None,
        base_backoff: float | None = None,
        should_retry: Callable[[Any], bool] | None = None,
    ) -> Any:
        """GET + JSON 解析（request 的语法糖，含信封重试）。"""
        resp = await self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            credentials=credentials,
            platform=platform,
            min_interval=min_interval,
            max_retries=max_retries,
            base_backoff=base_backoff,
            should_retry=should_retry,
        )
        return resp.json()

    async def post_json(
        self,
        url: str,
        *,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        credentials: Credentials | None = None,
        platform: str,
        min_interval: float,
        max_retries: int | None = None,
        base_backoff: float | None = None,
        should_retry: Callable[[Any], bool] | None = None,
    ) -> Any:
        """POST + JSON 解析（GraphQL 等请求的语法糖，含信封重试）。"""
        resp = await self.request(
            "POST",
            url,
            headers=headers,
            json=json,
            credentials=credentials,
            platform=platform,
            min_interval=min_interval,
            max_retries=max_retries,
            base_backoff=base_backoff,
            should_retry=should_retry,
        )
        return resp.json()

    # ===== 内部 =====

    @staticmethod
    def _merged_headers(
        credentials: Credentials | None, headers: dict[str, str] | None
    ) -> dict[str, str] | None:
        """凭据 headers / cookies 与调用方显式 headers 合并（调用方优先）。

        cookies 转为 Cookie 头（httpx 弃用了 per-request cookies 参数）；
        无任何头时返回 None。
        """
        merged: dict[str, str] = {}
        if credentials is not None:
            merged.update(credentials.headers)
            if credentials.cookies:
                merged["Cookie"] = "; ".join(
                    f"{k}={v}" for k, v in credentials.cookies.items()
                )
        if headers:
            merged.update(headers)
        return merged or None

    @staticmethod
    def _retryable_envelope(
        resp: httpx.Response, should_retry: Callable[[Any], bool]
    ) -> bool:
        """解析响应 JSON 并判定是否信封重试；非 JSON 视为不可重试。"""
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001 - 非 JSON 响应不做信封判定
            return False
        return should_retry(data)

    async def _pace(self, platform: str, min_interval: float) -> None:
        """请求前补齐平台建议间隔（异步 sleep，不阻塞事件循环）。"""
        last = self._last_request.get(platform)
        if last is None:
            return
        elapsed = time.monotonic() - last
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)

    async def _backoff(
        self, attempt: int, min_interval: float, backoff_base: float
    ) -> None:
        """指数退避：基准取 max(全局/单次 base_backoff, 平台 min_interval)，
        保证首次重试已错开一个完整限流窗口。"""
        base = max(backoff_base, min_interval)
        await asyncio.sleep(base * (2**attempt))
