"""VJudge 适配器（匿名模式，/status/data 端点）。

设计见 docs/design/activity/vjudge.md：
- 使用共享 HttpFetcher（httpx），请求需携带浏览器标识头（Cloudflare 403 规避）；
- /status/data 无需登录即可查询用户提交记录；
- DataTables 分页（start + length），每页最大 100 条，倒序返回；
- 时间戳为毫秒级，需转秒。
"""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from adapters.base import (
    AuthMode,
    Capability,
    PlatformAdapter,
    PlatformSubmission,
    ProgressCallback,
    SyncBatch,
    UserInfo,
    UserNotFoundError,
)
from adapters.net import HttpFetcher
from adapters.vjudge.normalize import map_verdict, problem_url

logger = logging.getLogger("xcpc.adapters.vjudge")

HOSTNAME = "vjudge.net"
STATUS_DATA_URL = f"https://{HOSTNAME}/status/data"

PAGE_SIZE = 100  # /status/data 服务端硬限制


class VJudgeAdapter(PlatformAdapter):
    platform_id = "vjudge"
    name = "VJudge"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.USER_INFO})
    auth = AuthMode.NONE
    min_interval = 2.0  # 保守限流

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    # ===== 绑定验证 =====

    async def verify(self, handle: str, credentials: Any | None = None) -> UserInfo:
        """验证用户存在性（试拉提交第 1 页判有效性）。"""
        data = await self._fetch_page(handle, start=0)
        rows = data.get("data", [])
        if not rows:
            raise UserNotFoundError(f"VJudge 用户不存在或无任何提交: {handle}")
        return UserInfo(handle=handle, display_name=None)

    # ===== 提交拉取 =====

    async def fetch_submissions(
        self,
        handle: str,
        *,
        since: int | None,
        credentials: Any | None = None,
        full_window_days: int,
        full_min_rows: int,
        progress_cb: ProgressCallback | None = None,
        resume_checkpoint: dict[str, Any] | None = None,
    ) -> AsyncIterator[SyncBatch]:
        """按页流式拉取提交（每页一批，按时间倒序）。

        VJudge 无可靠总量字段，不上报进度（progress_cb 为契约参数，本平台忽略）。

        - 增量（since 非空）：遇 ts < since 即停；游标当秒提交重复拉取，
          由 store 层按 submission_id 去重吸收；
        - 全量（since 为空）：拉到覆盖 full_window_days 窗口为止，窗口内
          不足 full_min_rows 条时继续拉满；断点 = {"start": 下一页偏移,
          "fetched": 累计条数}；
        - 不设绝对页数护栏：单个用户提交量实际不会过于多。
        """
        start = 0
        fetched = 0
        if since is None and resume_checkpoint:
            start = int(resume_checkpoint.get("start", 0))
            fetched = int(resume_checkpoint.get("fetched", 0))

        window_start = int(time.time()) - full_window_days * 86400

        while True:
            data = await self._fetch_page(handle, start=start)
            rows = data.get("data", [])
            if not rows:
                yield SyncBatch(done=True)
                return

            batch: list[PlatformSubmission] = []
            hit_old = False
            for row in rows:
                ts_sec = int(row["time"]) // 1000
                if since is not None and ts_sec < since:
                    hit_old = True
                    break
                batch.append(self._to_submission(row, ts_sec))

            fetched += len(batch)

            # 全量停止条件：已越过窗口起点且累计条数达标
            last_ts = int(rows[-1]["time"]) // 1000
            full_done = (
                since is None
                and (last_ts < window_start and fetched >= full_min_rows)
            )
            done = hit_old or len(rows) < PAGE_SIZE or full_done

            start += len(rows)

            yield SyncBatch(
                items=batch,
                checkpoint=(
                    None
                    if done or since is not None
                    else {"start": start, "fetched": fetched}
                ),
                done=done,
            )
            if done:
                return

    # ===== 内部：HTTP =====

    async def _fetch_page(self, handle: str, start: int) -> dict:
        """获取单页提交数据（/status/data）。"""
        params: dict[str, str] = {
            "draw": "1",
            "start": str(start),
            "length": str(PAGE_SIZE),
            "un": handle,
            "OJId": "All",
            "probNum": "",
            "res": "all",
            "language": "",
            "onlyFollowee": "false",
        }
        # Cloudflare 要求浏览器标识头，否则返回 403 challenge
        headers: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://vjudge.net/status",
            "X-Requested-With": "XMLHttpRequest",
        }

        return await self._fetcher.get_json(
            STATUS_DATA_URL,
            params=params,
            headers=headers,
            platform=self.platform_id,
            min_interval=self.min_interval,
        )

    # ===== 内部：解析与归一化 =====

    @staticmethod
    def _to_submission(row: dict, ts_sec: int) -> PlatformSubmission:
        oj = str(row.get("oj", ""))
        prob_num = str(row.get("probNum", ""))
        return PlatformSubmission(
            submission_id=str(row.get("runId", "")),
            problem_key=f"{oj}-{prob_num}",
            problem_name=prob_num,
            problem_url=problem_url(oj, prob_num),
            difficulty=None,
            verdict=map_verdict(str(row.get("status", ""))),
            submitted_at=ts_sec,
            language=str(row.get("languageCanonical", row.get("language", ""))),
        )
