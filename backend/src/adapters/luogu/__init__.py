"""洛谷适配器（cookie 授权 + 反爬对抗，第三期；详见 docs/design/activity.md §5.6）。

传输层例外：洛谷 WAF 按 TLS/HTTP 指纹区分客户端（实测同 IP 同 cookie，
curl 通过、httpx 必被 Spilopelia 挑战），故本 adapter 不用共享
HttpFetcher，改用 curl_cffi（浏览器 TLS 指纹伪装）的 AsyncSession。
注册表构造签名不变（入参 fetcher 忽略）；会话按次创建（cookie 罐
吸收 C3VK 挑战与 __client_id 轮换），限流记账留在实例上跨次生效。

反爬处置：
- 302 + Set-Cookie C3VK：会话罐跟随自动通过；
- JS 挑战页 / 登录跳页（非 JSON 响应）：带凭据判 AuthExpiredError
  （重新授权是两种情况的共同正确动作），匿名判 PlatformError；
- 信封 code 401/403 +「请先登录/用户不可见」→ AuthExpiredError；
- 403 +「请求频繁」→ 应用层专项重试（RATE_LIMIT_RETRIES 次，
  RATE_LIMIT_BACKOFF 起步指数退避；clist 生产值 8 次 + 50s 附加延迟）。
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException
from pydantic import ValidationError

from adapters.base import (
    AuthExpiredError,
    AuthMode,
    Capability,
    Credentials,
    PlatformAdapter,
    PlatformError,
    PlatformSubmission,
    ProgressCallback,
    UserInfo,
    UserNotFoundError,
)
from adapters.luogu.api_models import (
    LgRecordListEnvelope,
    LgRecordRow,
    LgUserSearchResult,
    LgUserSummary,
)
from adapters.luogu.normalize import map_language, map_verdict, problem_url
from adapters.net import HttpFetcher

logger = logging.getLogger("xcpc.adapters.luogu")

BASE = "https://www.luogu.com.cn"
RECORD_LIST_URL = f"{BASE}/record/list"
USER_SEARCH_URL = f"{BASE}/api/user/search"

MAX_PAGES = 1000  # 安全护栏（perPage 20 × 1000 = 2 万条），正常路径不会触发
MAX_RETRIES = 3  # 传输异常 / 429 / 5xx 重试次数
RATE_LIMIT_RETRIES = 4  # 403「请求频繁」专项重试次数
RATE_LIMIT_BACKOFF = 30.0  # 专项重试起步退避（秒）

# 错误文案关键词（位置在错误体中不稳定，对原始体做包含扫描）
_RATE_LIMIT_HINT = "请求频繁"


class LuoguAdapter(PlatformAdapter):
    platform_id = "luogu"
    name = "洛谷"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.USER_INFO})
    auth = AuthMode.COOKIE
    min_interval = 5.0  # 反爬敏感平台：低频请求长期避开 JS 挑战升级

    def __init__(
        self,
        fetcher: HttpFetcher,  # 注册表契约入参；本 adapter 不用（见模块 docstring）
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._session_factory = session_factory or (
            lambda: AsyncSession(impersonate="chrome")
        )
        # 限流记账留在实例上（会话按次创建，跨次仍需保证请求间隔）
        self._lock = asyncio.Lock()
        self._last_request: float | None = None

    # ===== 绑定验证 =====

    async def verify(
        self, handle: str, credentials: Credentials | None = None
    ) -> UserInfo:
        """匿名 search 判存在性（精确匹配）→ 携凭据试拉记录第 1 页判有效性。

        handle 归一为 uid（API 主键），用户名作 display_name 展示。
        """
        async with self._session_factory() as session:
            data = await self._get_json(
                session, USER_SEARCH_URL, params={"keyword": handle}, anonymous=True
            )
            result = self._parse(data, LgUserSearchResult, "用户搜索")
            user = self._exact_match(result.users, handle)
            if user is None:
                raise UserNotFoundError(f"洛谷用户不存在: {handle}")
            if credentials is not None:
                # 凭据有效性试拉：绑定当下拦住死凭据（AuthExpiredError → 400）
                await self._get_json(
                    session,
                    RECORD_LIST_URL,
                    params={"user": str(user.uid), "page": 1, "_contentOnly": 1},
                    credentials=credentials,
                )
            return UserInfo(
                handle=str(user.uid),
                display_name=user.name or None,
                avatar=user.avatar,
            )

    @staticmethod
    def _exact_match(users: list[LgUserSummary], keyword: str) -> LgUserSummary | None:
        """search 为模糊匹配，取精确命中：uid 相等或用户名不区分大小写相等。"""
        keyword = keyword.strip()
        for u in users:
            if str(u.uid) == keyword or u.name.lower() == keyword.lower():
                return u
        return None

    # ===== 提交拉取 =====

    async def fetch_submissions(
        self,
        handle: str,
        *,
        since: int | None,
        credentials: Credentials | None = None,
        full_window_days: int,
        full_min_rows: int,
        progress_cb: ProgressCallback | None = None,
    ) -> list[PlatformSubmission]:
        """倒序回扫分页拉取（返回按时间倒序，语义对齐 CF 适配器）。

        - 增量（since 非空）：遇 ts < since 即停；游标当秒提交重复拉取，
          由 store 层按 submission_id 去重吸收；
        - 全量（since 为空）：拉到覆盖 full_window_days 窗口为止，窗口内
          不足 full_min_rows 条时继续拉满；首页信封 records.count 即
          全站总条数，经 progress_cb 逐页上报真实进度百分比；
        - 绝对护栏：最多 MAX_PAGES 页。
        """
        if credentials is None:
            raise AuthExpiredError("未配置洛谷凭据，请先绑定账号并授权")
        out: list[LgRecordRow] = []
        seen: set[int] = set()
        window_start = int(time.time()) - full_window_days * 86400
        async with self._session_factory() as session:
            for page in range(1, MAX_PAGES + 1):
                data = await self._get_json(
                    session,
                    RECORD_LIST_URL,
                    params={"user": handle, "page": page, "_contentOnly": 1},
                    credentials=credentials,
                )
                envelope = self._parse(data, LgRecordListEnvelope, "记录列表")
                page_data = envelope.currentData.records if envelope.currentData else None
                rows = page_data.result if page_data else []
                if not rows:
                    break
                for row in rows:
                    if since is not None and row.submitTime < since:
                        return [self._to_submission(r) for r in out]
                    if row.id not in seen:
                        seen.add(row.id)
                        out.append(row)
                # 进度上报：仅全量（总量 = 首页信封 count；增量子集总量不可知）
                if progress_cb is not None and since is None and page_data is not None:
                    progress_cb(len(out), page_data.count)
                last_ts = rows[-1].submitTime
                # 全量停止条件：已越过窗口起点且累计条数达标；或末页（不满 perPage）
                if (
                    since is None
                    and last_ts < window_start
                    and len(out) >= full_min_rows
                ):
                    break
                if len(rows) < (page_data.perPage if page_data else 20):
                    break
        return [self._to_submission(r) for r in out]

    # ===== 一键登录（browser-login，可选依赖 Playwright） =====

    def browser_login_available(self) -> bool:
        """一键登录是否可用（Playwright 可选依赖已安装）。"""
        from adapters.luogu import login as login_mod

        return login_mod.playwright_available()

    async def run_browser_login(
        self, timeout: float
    ) -> tuple[Credentials, UserInfo]:
        """拉起系统浏览器登录窗口，返回抓取的凭据与验证回执。

        登录成功（__client_id 出现）后立即用凭据完成验证（存在性 +
        有效性），失败语义与 verify 相同；用户关窗 / 超时分别抛
        LoginCancelledError / asyncio.TimeoutError。
        """
        from adapters.luogu import login as login_mod

        credentials = await login_mod.capture_credentials(timeout)
        info = await self.verify(credentials.cookies.get("_uid", ""), credentials)
        return credentials, info

    # ===== 内部：外呼 =====

    async def _get_json(
        self,
        session: Any,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        credentials: Credentials | None = None,
        anonymous: bool = False,
    ) -> dict:
        """curl_cffi GET + 信封判定：返回 code==200 的响应体（dict）。

        失败语义：传输异常 / 429 / 5xx 重试（退避基准不小于 min_interval）；
        非 JSON 响应（JS 挑战页 / 登录跳页）按是否匿名判 AuthExpiredError
        或 PlatformError；信封 403「请求频繁」专项长退避重试；其余
        code != 200 抛 PlatformError。
        """
        cookies = dict(credentials.cookies) if credentials else None
        async with self._lock:
            await self._pace()
            rate_retries = 0
            for attempt in range(MAX_RETRIES + 1):
                try:
                    resp = await session.get(
                        url,
                        params=params,
                        cookies=cookies,
                        timeout=15,
                        allow_redirects=True,
                    )
                except RequestException as exc:
                    if attempt >= MAX_RETRIES:
                        raise PlatformError(
                            f"洛谷请求重试 {MAX_RETRIES} 次仍失败: {exc}"
                        ) from exc
                    await self._backoff(attempt)
                    continue
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt >= MAX_RETRIES:
                        raise PlatformError(f"洛谷返回 HTTP {resp.status_code}")
                    await self._backoff(attempt)
                    continue
                if resp.status_code != 200:
                    raise PlatformError(f"洛谷返回 HTTP {resp.status_code}")
                body = resp.text
                try:
                    data = json.loads(body)
                except ValueError:
                    # JS 挑战页 / 登录跳页（非 JSON）：重导凭据是共同正确动作
                    if anonymous:
                        raise PlatformError(
                            "洛谷返回非 JSON 响应（可能被反爬拦截）"
                        ) from None
                    raise AuthExpiredError(
                        "洛谷凭据失效或被反爬拦截，请重新授权"
                    ) from None
                code = data.get("code", 200) if isinstance(data, dict) else 200
                if code == 200:
                    self._last_request = time.monotonic()
                    return data
                # 重新序列化为非转义文本再匹配（json 默认转义中文为 \uXXXX）
                text = json.dumps(data, ensure_ascii=False)
                if _RATE_LIMIT_HINT in text and rate_retries < RATE_LIMIT_RETRIES:
                    rate_retries += 1
                    await asyncio.sleep(RATE_LIMIT_BACKOFF * (2 ** (rate_retries - 1)))
                    continue
                if code in (401, 403) and not anonymous:
                    raise AuthExpiredError(f"洛谷凭据无效（code={code}），请重新授权")
                raise PlatformError(f"洛谷返回错误 code={code}")
            raise PlatformError(f"洛谷请求重试 {MAX_RETRIES} 次仍失败")

    async def _pace(self) -> None:
        """请求前补齐平台建议间隔（镜像 net 层语义，跨会话实例级记账）。"""
        if self._last_request is None:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)

    async def _backoff(self, attempt: int) -> None:
        """指数退避：基准不小于 min_interval（镜像 net 层公式）。"""
        await asyncio.sleep(max(0.5, self.min_interval) * (2**attempt))

    # ===== 内部：解析与归一化 =====

    @staticmethod
    def _parse(data: Any, model: Any, label: str) -> Any:
        """外部 JSON 第一时间转模型；格式异常统一抛 PlatformError。"""
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise PlatformError(f"洛谷 API {label}格式异常: {exc}") from exc

    @staticmethod
    def _to_submission(row: LgRecordRow) -> PlatformSubmission:
        return PlatformSubmission(
            submission_id=str(row.id),
            problem_key=row.problem.pid or "?",
            problem_name=row.problem.title,
            problem_url=problem_url(
                row.problem.pid, row.contest.id if row.contest else None
            ),
            difficulty=row.problem.difficulty,
            verdict=map_verdict(row.status),
            submitted_at=row.submitTime,
            language=map_language(row.language),
        )
