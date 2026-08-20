"""牛客竞赛（NowCoder）适配器。

数据源：practice-coding 分页 HTML（服务端渲染）+ rating-history JSON API（绑定验证）。
详见 docs/design/activity/nowcoder.md。
"""

import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

from adapters.base import (
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
)
from adapters.net import HttpFetcher
from adapters.nowcoder.api_models import NcRatingHistoryEnvelope, NcSubmissionRow
from adapters.nowcoder.normalize import map_verdict

logger = logging.getLogger("xcpc.adapters.nowcoder")

BASE = "https://ac.nowcoder.com"
PRACTICE_CODING_URL = f"{BASE}/acm/contest/profile/{{uid}}/practice-coding"
RATING_HISTORY_URL = f"{BASE}/acm/contest/rating-history"

PAGE_SIZE = 50  # 经实测，200 有重复页 bug，50 稳定
MAX_PAGES = 100  # 安全护栏
CHINA_TZ = timezone(timedelta(hours=8))  # 中国时区 UTC+8

# 个人主页 HTML 提取正则（提取用户名/昵称）
_CODER_NAME_RE = re.compile(
    r'<a[^>]*class="coder-name[^"]*"[^>]*>([^<]*)</a>'
)
_TITLE_NAME_RE = re.compile(r'<title>([^<]*)的比赛主页</title>')
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
_SID_RE = re.compile(r"submissionId=(\d+)")
_PROB_RE = re.compile(r'href="/acm/problem/([^"]+)"[^>]*>([^<]*)</a>')
_STATUS_RE = re.compile(r">([^<]*)</a>")
_TAG_RE = re.compile(r"<[^>]+>")


class NowcoderAdapter(PlatformAdapter):
    platform_id = "nowcoder"
    name = "牛客竞赛"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.USER_INFO})
    auth = AuthMode.NONE
    min_interval = 1.0  # 保守限流

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    # ===== 绑定验证 =====

    async def verify(
        self, handle: str, credentials: Credentials | None = None
    ) -> UserInfo:
        """验证用户存在性并获取展示名。

        1. rating-history API 判存在性（data 非空即存在）；
        2. 个人主页 HTML 提取用户名（coder-name 标签或 title）。
        """
        # 步骤 1：存在性验证
        data = await self._fetcher.get_json(
            RATING_HISTORY_URL,
            params={"uid": handle},
            platform=self.platform_id,
            min_interval=self.min_interval,
        )
        try:
            envelope = NcRatingHistoryEnvelope.model_validate(data)
        except Exception as exc:
            raise PlatformError(f"牛客 rating-history 响应格式异常: {exc}") from exc
        if envelope.code != 0:
            raise PlatformError(f"牛客返回错误 code={envelope.code}")
        if not envelope.data:
            raise UserNotFoundError(f"牛客用户不存在: {handle}")

        # 步骤 2：获取展示名（用户名）
        display_name = await self._fetch_display_name(handle)
        return UserInfo(handle=handle, display_name=display_name)

    async def _fetch_display_name(self, handle: str) -> str | None:
        """从个人主页 HTML 提取用户名/昵称。"""
        try:
            url = f"{BASE}/acm/contest/profile/{handle}"
            resp = await self._fetcher.request(
                "GET", url, platform=self.platform_id, min_interval=self.min_interval
            )
            html = resp.text

            # 优先：coder-name 标签（如 <a class="coder-name rate-score7">UESTC_Vici</a>）
            m = _CODER_NAME_RE.search(html)
            if m:
                name = m.group(1).strip()
                if name:
                    return name

            #  fallback：title 标签（如 <title>UESTC_Vici的比赛主页</title>）
            m = _TITLE_NAME_RE.search(html)
            if m:
                name = m.group(1).strip()
                if name and name != "比赛主页":
                    return name
        except Exception as exc:  # noqa: BLE001
            logger.debug("牛客获取用户名失败: %s", exc)
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
        """按页流式拉取提交（每页一批，按时间倒序）。

        牛客无总量字段，不上报进度（progress_cb 为契约参数，本平台忽略）。

        - 增量（since 非空）：遇 ts < since 即停；游标当秒提交重复拉取，
          由 store 层按 submission_id 去重吸收；
        - 全量（since 为空）：拉到覆盖 full_window_days 窗口为止，窗口内
          不足 full_min_rows 条时继续拉满；断点 = {"page": 下一页页码,
          "fetched": 累计条数}；
        - 绝对护栏：最多 MAX_PAGES 页。
        """
        page = 1
        fetched = 0
        if since is None and resume_checkpoint:
            page = int(resume_checkpoint.get("page", 1))
            fetched = int(resume_checkpoint.get("fetched", 0))

        for _ in range(page, MAX_PAGES + 1):
            html = await self._fetch_html(handle, page)
            rows = self._parse_rows(html)
            if not rows:
                yield SyncBatch(done=True)
                return

            batch: list[PlatformSubmission] = []
            hit_old = False
            for row in rows:
                ts = row.submitted_at_str
                ts_utc = self.to_utc_seconds(ts)
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

    async def _fetch_html(self, handle: str, page: int) -> str:
        """获取 practice-coding 页面 HTML。"""
        url = PRACTICE_CODING_URL.format(uid=handle)
        resp = await self._fetcher.request(
            "GET",
            url,
            params={
                "pageSize": PAGE_SIZE,
                "statusTypeFilter": -1,
                "languageCategoryFilter": -1,
                "orderType": "DESC",
                "page": page,
            },
            platform=self.platform_id,
            min_interval=self.min_interval,
        )
        return resp.text

    # ===== 内部：解析 =====

    @staticmethod
    def _parse_rows(html: str) -> list[NcSubmissionRow]:
        """从 HTML 中提取提交行列表。"""
        rows: list[NcSubmissionRow] = []
        raw_rows = _ROW_RE.findall(html)
        # 跳过表头行（第一个 <tr>）
        for raw in raw_rows[1:]:
            tds = _TD_RE.findall(raw)
            if len(tds) < 9:
                continue
            # 提交 ID
            sid_match = _SID_RE.search(tds[0])
            if not sid_match:
                continue
            submission_id = sid_match.group(1)
            # 题目
            prob_match = _PROB_RE.search(tds[1])
            if not prob_match:
                continue
            problem_id = prob_match.group(1)
            problem_name = prob_match.group(2).strip()
            # 状态
            status_match = _STATUS_RE.search(tds[2])
            status_text = status_match.group(1).strip() if status_match else ""
            # 语言
            language = _TAG_RE.sub("", tds[7]).strip()
            # 时间
            timestamp = _TAG_RE.sub("", tds[8]).strip()
            try:
                row = NcSubmissionRow(
                    submission_id=submission_id,
                    problem_id=problem_id,
                    problem_name=problem_name,
                    status_text=status_text,
                    language=language,
                    submitted_at_str=timestamp,
                )
            except Exception as exc:  # noqa: BLE001 - 单行解析失败跳过，不阻断整批
                logger.debug("牛客 HTML 单行解析失败: %s", exc)
                continue
            rows.append(row)
        return rows

    @staticmethod
    def to_utc_seconds(ts_str: str) -> int:
        """中国时区时间字符串 → UTC 秒级时间戳。"""
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CHINA_TZ)
        return int(dt.timestamp())

    @staticmethod
    def to_submission(row: NcSubmissionRow, ts_utc: int) -> PlatformSubmission:
        return PlatformSubmission(
            submission_id=row.submission_id,
            problem_key=row.problem_id,
            problem_name=row.problem_name,
            problem_url=f"https://ac.nowcoder.com/acm/problem/{row.problem_id}",
            difficulty=None,  # 牛客无难度信息
            verdict=map_verdict(row.status_text),
            submitted_at=ts_utc,
            language=row.language,
        )
