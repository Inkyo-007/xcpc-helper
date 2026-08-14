"""可配置在线 LLM 客户端（OpenAI 兼容 chat/completions）。

只负责单次调用与响应解析，任何失败统一抛 LlmError；降级逻辑在 service 层。
transport 参数供测试注入 httpx.MockTransport，避免真实外呼。
"""

import httpx


class LlmError(Exception):
    """LLM 调用失败（网络异常 / 非 2xx / 响应结构异常）。"""


class LlmClient:
    """OpenAI 兼容 chat/completions 客户端（httpx，可注入 transport）。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float,
        max_tokens: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, messages: list[dict]) -> str:
        """调用 chat/completions，返回 choices[0].message.content。"""
        url = f"{self._base_url.rstrip('/')}/chat/completions"
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": 0.4,
        }
        try:
            resp = await self._client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LlmError(f"请求失败: {exc}") from exc
        if resp.status_code < 200 or resp.status_code >= 300:
            raise LlmError(f"LLM 返回 HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmError(f"响应结构异常: {exc}") from exc
        if not isinstance(content, str):
            raise LlmError("响应 content 非字符串")
        return content
