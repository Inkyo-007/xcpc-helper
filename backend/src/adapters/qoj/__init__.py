"""QOJ 适配器（cookie 授权 + HTML 解析）。

设计见 docs/design/activity/qoj-research.md：
- 提交记录：/submissions?submitter=<handle>&page=<n>，服务端渲染 HTML；
- 绑定验证：/user/profile/<handle> 检查 "No Such User"；
- 凭据验证：携 cookie 试拉 /submissions 检查是否被重定向；
- 时区：UTC+8 转 UTC（参照 nowcoder CHINA_TZ）；
- Playwright 一键登录可选（参照 luogu/login.py）。
"""

import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

from adapters.base import (
    AuthExpiredError,
    AuthMode,
    Capability,
    Credentials,
    PlatformAdapter,
    PlatformSubmission,
    ProgressCallback,
    SyncBatch,
    UserInfo,
    UserNotFoundError,
)
from adapters.base import (
    BrowserLoginCancelledError as BrowserLoginCancelledError,
)
from adapters.base import (
    PlatformError as PlatformError,
)
from adapters.net import HttpFetcher
from adapters.qoj.api_models import QojSubmissionRow
from adapters.qoj.normalize import map_verdict

logger = logging.getLogger("xcpc.adapters.qoj")

BASE = "http://qoj.ac"
SUBMISSIONS_URL = f"{BASE}/submissions"
PROFILE_URL = f"{BASE}/user/profile/{{handle}}"

PAGE_SIZE = 10  # QOJ 每页固定 10 条
MAX_PAGES = 5000  # 安全护栏（5000 页 = 5 万条）
CHINA_TZ = timezone(timedelta(hours=8))  # 中国时区 UTC+8

# HTML 提取正则
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
# 提交 ID：链接文本如 "#2600866"
_SID_RE = re.compile(r'href="#/submission/(\d+)">#(\d+)</a>')
# 题目：链接文本如 "#14809. Chi Fan"
_PROB_RE = re.compile(r'href="#/contest/(\d+)/problem/(\d+)">#(\d+)\.\s*([^<]*)</a>')
# 结果文本（可能包含 data-score/data-full 属性）
_RESULT_RE = re.compile(
    r'<span[^>]*class="[^"]*uoj-result[^"]*"[^>]*?(?:data-score="([^"]*)"[^>]*?)?(?:data-full="([^"]*)"[^>]*?)?>(.*?)</span>',
    re.DOTALL,
)
# 语言
_LANG_RE = re.compile(r">([^<]*)</a>")
# 时间戳
_TIME_RE = re.compile(r">([^<]*)</a>")
_TAG_RE = re.compile(r"<[^>]+>")


class QOJAdapter(PlatformAdapter):
    platform_id = "qoj"
    name = "QOJ"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.USER_INFO})
    auth = AuthMode.COOKIE
    min_interval = 1.0

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    # ===== 绑定验证 =====

    async def verify(
        self, handle: str, credentials: Credentials | None = None
    ) -> UserInfo:
        """验证用户存在性并获取展示名。

        1. 访问 /user/profile/<handle> 检查 "No Such User"；
        2. 从页面提取 data-nickname 作为展示名；
        3. 如有凭据，试拉 /submissions 确认有效性。
        """
        # 步骤 1：存在性验证（携带浏览器标识头规避 Cloudflare）
        resp = await self._fetcher.request(
            "GET",
            PROFILE_URL.format(handle=handle),
            headers=self._browser_headers(),
            platform=self.platform_id,
            min_interval=self.min_interval,
        )
        html = resp.text
        if "No Such User" in html or "No such user" in html:
            raise UserNotFoundError(f"QOJ 用户不存在: {handle}")

        # 步骤 2：获取展示名
        display_name = self._extract_nickname(html)

        # 步骤 3：凭据有效性验证（如有）
        if credentials is not None:
            await self._verify_credentials(handle, credentials)

        return UserInfo(handle=handle, display_name=display_name)

    @staticmethod
    def _extract_nickname(html: str) -> str | None:
        """从个人主页 HTML 提取昵称（data-nickname 属性）。"""
        m = re.search(r'data-nickname="([^"]*)"', html)
        if m:
            name = m.group(1).strip()
            if name:
                return name
        return None

    async def _verify_credentials(self, handle: str, credentials: Credentials) -> None:
        """携 cookie 试拉 /submissions 检查是否被重定向到登录页。"""
        try:
            resp = await self._fetcher.request(
                "GET",
                SUBMISSIONS_URL,
                params={"submitter": handle, "page": "1"},
                headers=self._browser_headers(),
                credentials=credentials,
                platform=self.platform_id,
                min_interval=self.min_interval,
            )
            html = resp.text
            # 被重定向到登录页时页面包含登录表单
            if "login" in html.lower() and "<table" not in html:
                raise AuthExpiredError("QOJ 凭据已失效，请重新授权")
        except AuthExpiredError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.debug("QOJ 凭据验证请求失败: %s", exc)

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
        """按页流式拉取提交（每页一批，按时间倒序）。

        QOJ 无总量字段，不上报进度（progress_cb 为契约参数，本平台忽略）。

        - 增量（since 非空）：遇 ts < since 即停；游标当秒提交重复拉取，
          由 store 层按 submission_id 去重吸收；
        - 全量（since 为空）：拉到覆盖 full_window_days 窗口为止，窗口内
          不足 full_min_rows 条时继续拉满；断点 = {"page": 下一页页码,
          "fetched": 累计条数}；
        - 绝对护栏：最多 MAX_PAGES 页。
        """
        if credentials is None:
            raise AuthExpiredError("未配置 QOJ 凭据，请先绑定账号并授权")

        page = 1
        fetched = 0
        if since is None and resume_checkpoint:
            page = int(resume_checkpoint.get("page", 1))
            fetched = int(resume_checkpoint.get("fetched", 0))

        for _ in range(page, MAX_PAGES + 1):
            html = await self._fetch_html(handle, page, credentials)
            rows = self._parse_rows(html)
            if not rows:
                yield SyncBatch(done=True)
                return

            batch: list[PlatformSubmission] = []
            hit_old = False
            for row in rows:
                ts_utc = self.to_utc_seconds(row.submitted_at_str)
                if since is not None and ts_utc < since:
                    hit_old = True
                    break
                batch.append(self.to_submission(row, ts_utc))

            fetched += len(batch)
            done = hit_old or len(rows) < PAGE_SIZE
            yield SyncBatch(
                items=batch,
                checkpoint=(
                    None
                    if done or since is not None
                    else {"page": page + 1, "fetched": fetched}
                ),
                done=done,
            )
            if done:
                return
            page += 1

        yield SyncBatch(done=True)

    # ===== 内部：HTTP =====

    async def _fetch_html(
        self, handle: str, page: int, credentials: Credentials
    ) -> str:
        """获取提交记录页面 HTML。"""
        resp = await self._fetcher.request(
            "GET",
            SUBMISSIONS_URL,
            params={"submitter": handle, "page": str(page)},
            headers=self._browser_headers(),
            credentials=credentials,
            platform=self.platform_id,
            min_interval=self.min_interval,
        )
        return resp.text

    @staticmethod
    def _browser_headers() -> dict[str, str]:
        """浏览器标识头（Cloudflare 403 规避）。"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    # ===== 内部：解析 =====

    @staticmethod
    def _parse_rows(html: str) -> list[QojSubmissionRow]:
        """从 HTML 中提取提交行列表。"""
        rows: list[QojSubmissionRow] = []
        raw_rows = _ROW_RE.findall(html)
        # 跳过表头行（第一个 <tr>）
        for raw in raw_rows[1:]:
            tds = _TD_RE.findall(raw)
            if len(tds) < 9:
                continue

            # 提交 ID（第 1 列）
            sid_match = _SID_RE.search(tds[0])
            if not sid_match:
                continue
            submission_id = sid_match.group(1)

            # 题目（第 2 列）
            prob_match = _PROB_RE.search(tds[1])
            if not prob_match:
                continue
            problem_id = prob_match.group(2)
            problem_name = prob_match.group(4).strip()

            # 结果（第 4 列）—— 可能包含 data-score/data-full
            score: float | None = None
            full_score: float | None = None
            result_text = ""
            result_match = _RESULT_RE.search(tds[3])
            if result_match:
                score_str = result_match.group(1)
                full_str = result_match.group(2)
                result_text = _TAG_RE.sub("", result_match.group(3)).strip()
                if score_str is not None:
                    try:
                        score = float(score_str)
                    except ValueError:
                        pass
                if full_str is not None:
                    try:
                        full_score = float(full_str)
                    except ValueError:
                        pass
            else:
                # 兜底：直接提取文本
                result_text = _TAG_RE.sub("", tds[3]).strip()

            # 语言（第 7 列）
            lang_match = _LANG_RE.search(tds[6])
            language = lang_match.group(1).strip() if lang_match else ""

            # 提交时间（第 9 列）
            time_match = _TIME_RE.search(tds[8])
            timestamp = time_match.group(1).strip() if time_match else ""

            try:
                row = QojSubmissionRow(
                    submission_id=submission_id,
                    problem_id=problem_id,
                    problem_name=problem_name,
                    result_text=result_text,
                    language=language,
                    submitted_at_str=timestamp,
                    score=score,
                    full_score=full_score,
                )
            except Exception as exc:  # noqa: BLE001 - 单行解析失败跳过，不阻断整批
                logger.debug("QOJ HTML 单行解析失败: %s", exc)
                continue
            rows.append(row)
        return rows

    @staticmethod
    def to_utc_seconds(ts_str: str) -> int:
        """中国时区时间字符串 → UTC 秒级时间戳。"""
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CHINA_TZ)
        return int(dt.timestamp())

    @staticmethod
    def to_submission(row: QojSubmissionRow, ts_utc: int) -> PlatformSubmission:
        return PlatformSubmission(
            submission_id=row.submission_id,
            problem_key=row.problem_id,
            problem_name=row.problem_name,
            problem_url=f"{BASE}/contest/0/problem/{row.problem_id}",
            difficulty=None,  # QOJ 无难度信息
            verdict=map_verdict(row.result_text, row.score, row.full_score),
            submitted_at=ts_utc,
            language=row.language,
        )

    # ===== 一键登录（browser-login，可选依赖 Playwright） =====

    def browser_login_available(self) -> bool:
        """一键登录是否可用（Playwright 可选依赖已安装）。"""
        from adapters.qoj import login as login_mod

        return login_mod.playwright_available()

    async def run_browser_login(
        self, timeout: float
    ) -> tuple[Credentials, UserInfo]:
        """拉起系统浏览器登录窗口，返回抓取的凭据与验证回执。

        登录成功（UOJSESSID 出现）后立即用凭据完成验证（存在性 +
        有效性），失败语义与 verify 相同；用户关窗 / 超时分别抛
        LoginCancelledError / asyncio.TimeoutError。
        """
        from adapters.qoj import login as login_mod

        credentials = await login_mod.capture_credentials(timeout)
        info = await self.verify(credentials.cookies.get("uoj_username", ""), credentials)
        return credentials, info
