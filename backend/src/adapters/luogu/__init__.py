"""洛谷适配器（cookie 授权 + 反爬对抗，第三期；详见 docs/design/activity/luogu.md）。

传输层例外：洛谷 WAF 按 TLS/HTTP 指纹区分客户端（实测同 IP 同 cookie，
curl 通过、httpx 必被 Spilopelia 挑战），故本 adapter 不用共享
HttpFetcher，改用 curl_cffi（浏览器 TLS 指纹伪装）的 AsyncSession。
注册表构造签名不变（入参 fetcher 忽略）；会话按次创建（cookie 罐
吸收 C3VK 挑战与 __client_id 轮换），限流记账留在实例上跨次生效。

数据契约（2026-10 适配）：`_contentOnly=1` JSON 信封已下线，页面数据
改从 HTML 内嵌的 lentille-context（`{status, template, data}`）解析；
record 页面强制登录（匿名/失效凭据 401 错误页）。

反爬处置：
- 302 + Set-Cookie C3VK：会话罐跟随自动通过；
- 200 但无 lentille-context（JS 挑战页）：判 AuthExpiredError
  （重新授权是共同正确动作）；
- lentille 错误页 401/403（请先登录/用户不可见）→ AuthExpiredError；
- 错误消息含「请求频繁」→ 应用层专项重试（RATE_LIMIT_RETRIES 次，
  RATE_LIMIT_BACKOFF 起步指数退避；clist 生产值 8 次 + 50s 附加延迟）。
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Callable
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
    SyncBatch,
    UserInfo,
    UserNotFoundError,
    Verdict,
)
from adapters.luogu.api_models import (
    LENTILLE_CONTEXT_RE,
    LgLentilleContext,
    LgRecordListData,
    LgRecordRow,
    LgRecordShowData,
    LgUserSearchResult,
    LgUserSummary,
)
from adapters.luogu.normalize import (
    map_language,
    map_verdict,
    pick_verdict,
    problem_url,
)
from adapters.net import HttpFetcher

logger = logging.getLogger("xcpc.adapters.luogu")

BASE = "https://www.luogu.com.cn"
RECORD_LIST_URL = f"{BASE}/record/list"
RECORD_DETAIL_URL = f"{BASE}/record"  # /record/{id}
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
    capabilities = frozenset(
        {Capability.SUBMISSIONS, Capability.USER_INFO, Capability.REFINE_VERDICT}
    )
    auth = AuthMode.COOKIE
    min_interval = 5.0  # 反爬敏感平台：低频请求长期避开 JS 挑战升级
    homepage_url = "https://www.luogu.com.cn"

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
            data = await self._get_api_json(
                session, USER_SEARCH_URL, params={"keyword": handle}
            )
            result = self._parse(data, LgUserSearchResult, "用户搜索")
            user = self._exact_match(result.users, handle)
            if user is None:
                raise UserNotFoundError(f"洛谷用户不存在: {handle}")
            if credentials is not None:
                # 凭据有效性试拉：绑定当下拦住死凭据（AuthExpiredError → 400）
                await self._get_page_data(
                    session,
                    RECORD_LIST_URL,
                    params={"user": str(user.uid), "page": 1},
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
        resume_checkpoint: dict[str, Any] | None = None,
    ) -> AsyncIterator[SyncBatch]:
        """倒序回扫分页流式拉取（每页一批，按时间倒序）。

        - 增量（since 非空）：遇 ts < since 即停；游标当秒提交重复拉取，
          由 store 层按 submission_id 去重吸收；
        - 全量（since 为空）：拉到覆盖 full_window_days 窗口为止，窗口内
          不足 full_min_rows 条时继续拉满；断点 = {"page": 下一页页码,
          "fetched": 累计条数}（页码随新提交漂移由 store 去重吸收，多拉
          无代价）；首页信封 records.count 即全站总条数，经 progress_cb
          逐页上报真实进度百分比（累计口径，含续传前已拉取部分）；
        - 绝对护栏：最多 MAX_PAGES 页。
        """
        if credentials is None:
            raise AuthExpiredError("未配置洛谷凭据，请先绑定账号并授权")
        seen: set[int] = set()
        window_start = int(time.time()) - full_window_days * 86400
        page = 1
        fetched = 0
        if since is None and resume_checkpoint:
            page = int(resume_checkpoint.get("page", 1))
            fetched = int(resume_checkpoint.get("fetched", 0))
        async with self._session_factory() as session:
            for _ in range(page, MAX_PAGES + 1):
                data = await self._get_page_data(
                    session,
                    RECORD_LIST_URL,
                    params={"user": handle, "page": page},
                    credentials=credentials,
                )
                page_data = self._parse(data, LgRecordListData, "记录列表").records
                rows = page_data.result if page_data else []
                if not rows:
                    break
                batch: list[LgRecordRow] = []
                hit_old = False
                for row in rows:
                    if since is not None and row.submitTime < since:
                        hit_old = True
                        break
                    if row.id not in seen:
                        seen.add(row.id)
                        batch.append(row)
                fetched += len(batch)
                # 进度上报：仅全量（总量 = 首页信封 count；增量子集总量不可知）
                if progress_cb is not None and since is None and page_data is not None:
                    progress_cb(fetched, page_data.count)
                last_ts = rows[-1].submitTime
                # 全量停止条件：已越过窗口起点且累计条数达标；或末页（不满 perPage）
                full_done = (
                    last_ts < window_start and fetched >= full_min_rows
                )
                short_page = len(rows) < (page_data.perPage if page_data else 20)
                done = hit_old or short_page or (since is None and full_done)
                page += 1
                yield SyncBatch(
                    items=[self._to_submission(r) for r in batch],
                    checkpoint=(
                        None
                        if done or since is not None
                        else {"page": page, "fetched": fetched}
                    ),
                    done=done,
                )
                if done:
                    return
        yield SyncBatch(done=True)

    # ===== 单条精化（UNAC → 细分 verdict） =====

    async def fetch_submission_verdict(
        self, record_id: str, credentials: Credentials | None = None
    ) -> Verdict | None:
        """拉记录详情，从测试点状态按严重度取最重（RE>TLE>MLE>OLE>WA）。

        保守规则：无可参选测试点（全 AC / 仅 JG/UKE / 无测试点信息）返回
        None，调用方保持 UNAC（见 activity/luogu.md）。
        """
        if credentials is None:
            raise AuthExpiredError("未配置洛谷凭据，请先绑定账号并授权")
        async with self._session_factory() as session:
            data = await self._get_page_data(
                session,
                f"{RECORD_DETAIL_URL}/{record_id}",
                credentials=credentials,
            )
        show = self._parse(data, LgRecordShowData, "记录详情")
        judge = (
            show.record.detail.judgeResult if show.record.detail else None
        )
        if judge is None:
            return None
        statuses = [case.status for sub in judge.subtasks for case in sub.test_cases]
        return pick_verdict(statuses)

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

    async def _request(
        self,
        session: Any,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        credentials: Credentials | None = None,
    ) -> Any:
        """curl_cffi GET + 传输层重试（异常 / 429 / 5xx），返回响应对象。

        退避基准不小于 min_interval；凭据的 cookies 与 headers（UA 等）
        一并应用（Credentials 契约：headers 由调用方合并，本 adapter 不
        经共享 net 层，须自行应用——__client_id 与 UA 绑定，缺失会被
        判为失效会话）。
        """
        cookies = dict(credentials.cookies) if credentials else None
        headers = dict(credentials.headers) if credentials else None
        async with self._lock:
            await self._pace()
            for attempt in range(MAX_RETRIES + 1):
                try:
                    resp = await session.get(
                        url,
                        params=params,
                        cookies=cookies,
                        headers=headers,
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
                self._last_request = time.monotonic()
                return resp
            raise PlatformError(f"洛谷请求重试 {MAX_RETRIES} 次仍失败")

    async def _get_api_json(
        self, session: Any, url: str, *, params: dict[str, Any] | None = None
    ) -> dict:
        """裸 JSON API（api/user/search，匿名可用）：200 + JSON 返回体。

        非 JSON 响应（JS 挑战页）判 PlatformError（匿名场景不涉及凭据）。
        """
        resp = await self._request(session, url, params=params)
        if resp.status_code != 200:
            raise PlatformError(f"洛谷返回 HTTP {resp.status_code}")
        try:
            return json.loads(resp.text)
        except ValueError:
            raise PlatformError("洛谷返回非 JSON 响应（可能被反爬拦截）") from None

    async def _get_page_data(
        self,
        session: Any,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        credentials: Credentials | None = None,
    ) -> Any:
        """页面 GET + lentille-context 解析：返回 status==200 的 data 字段。

        失败语义：
        - 无 lentille-context 的 200 页面（JS 挑战页）→ AuthExpiredError
          （挑战与凭据失效的共同正确动作都是重新授权）；
        - lentille 错误页 401/403（请先登录/用户不可见）→ AuthExpiredError；
        - 错误消息含「请求频繁」→ 专项长退避重试（RATE_LIMIT_RETRIES 次）；
        - 其余 status != 200 → PlatformError。
        """
        rate_retries = 0
        while True:
            resp = await self._request(
                session, url, params=params, credentials=credentials
            )
            ctx = self._extract_lentille(resp.text)
            if ctx is None:
                if resp.status_code != 200:
                    raise PlatformError(f"洛谷返回 HTTP {resp.status_code}")
                raise AuthExpiredError("洛谷凭据失效或被反爬拦截，请重新授权")
            if ctx.status == 200:
                return ctx.data
            # 重新序列化为非转义文本再匹配（json 默认转义中文为 \uXXXX）
            text = json.dumps(ctx.data, ensure_ascii=False, default=str)
            if _RATE_LIMIT_HINT in text and rate_retries < RATE_LIMIT_RETRIES:
                rate_retries += 1
                await asyncio.sleep(RATE_LIMIT_BACKOFF * (2 ** (rate_retries - 1)))
                continue
            if ctx.status in (401, 403):
                raise AuthExpiredError(
                    f"洛谷凭据无效（HTTP {ctx.status}），请重新授权"
                )
            raise PlatformError(f"洛谷页面返回错误 status={ctx.status}")

    @staticmethod
    def _extract_lentille(body: str) -> LgLentilleContext | None:
        """从 HTML 提取 lentille-context；非页面响应（挑战页等）返回 None。"""
        m = LENTILLE_CONTEXT_RE.search(body)
        if m is None:
            return None
        try:
            return LgLentilleContext.model_validate(json.loads(m.group(1)))
        except (ValueError, ValidationError):
            return None

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
            problem_name=row.problem.name,
            problem_url=problem_url(
                row.problem.pid, row.contest.id if row.contest else None
            ),
            difficulty=row.problem.difficulty,
            verdict=map_verdict(row.status),
            submitted_at=row.submitTime,
            language=map_language(row.language),
        )
