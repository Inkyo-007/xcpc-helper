"""Codeforces 适配器（官方公开 API，匿名可取，第一期唯一平台）。

第一期范围：提交明细（SUBMISSIONS）+ 绑定验证（USER_INFO）；
rating / 比赛记录属后续增量（Capability.RATING 已预留，本期不实现）。
"""

import logging
import time
from typing import Any

from adapters.base import (
    AuthMode,
    Capability,
    Credentials,
    PlatformAdapter,
    PlatformError,
    PlatformSubmission,
    UserInfo,
    UserNotFoundError,
)
from adapters.codeforces.fixtures import (
    map_verdict,
    normalize_problem_url,
    problem_key,
    problem_url,
)
from adapters.net import HttpFetcher

logger = logging.getLogger("xcpc.adapters.codeforces")

API_BASE = "https://codeforces.com/api"
STATUS_URL = f"{API_BASE}/user.status"
INFO_URL = f"{API_BASE}/user.info"

PAGE_SIZE = 1000  # user.status 单页上限
MAX_PAGES = 200  # 安全护栏（20 万条），正常路径不会触发
FULL_WINDOW_DAYS = 370  # 全量窗口：对齐前端热力图窗口（近一年）
FULL_MIN_ROWS = 5000  # 全量至少拉取的条数（一年内提交不足 5000 时拉满该数）


class CodeforcesAdapter(PlatformAdapter):
    platform_id = "codeforces"
    name = "Codeforces"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.USER_INFO})
    auth = AuthMode.NONE
    min_interval = 2.0  # 官方建议请求间隔 ≥ 2 秒

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    # ===== 绑定验证 =====

    async def verify(self, handle: str) -> UserInfo:
        data = await self._fetcher.get_json(
            INFO_URL,
            params={"handles": handle},
            platform=self.platform_id,
            min_interval=self.min_interval,
            should_retry=self._should_retry_envelope,
        )
        if not isinstance(data, dict) or data.get("status") != "OK":
            comment = str(data.get("comment") or "") if isinstance(data, dict) else ""
            if "not found" in comment.lower():
                raise UserNotFoundError(f"Codeforces 用户不存在: {handle}")
            raise PlatformError(f"Codeforces API 返回失败: {comment}")
        results = data.get("result") or []
        if not results:
            raise UserNotFoundError(f"Codeforces 用户不存在: {handle}")
        user = results[0]
        return UserInfo(handle=str(user.get("handle") or handle), avatar=user.get("avatar"))

    # ===== 提交拉取 =====

    async def fetch_submissions(
        self,
        handle: str,
        *,
        since: int | None,
        credentials: Credentials | None = None,
    ) -> list[PlatformSubmission]:
        """按页拉取提交（返回按时间倒序）。

        - 增量（since 非空）：只取游标之后的提交，遇旧即停；
        - 全量（since 为空）：拉到覆盖近 370 天窗口为止，窗口内不足
          FULL_MIN_ROWS 条时继续拉满该数（为 all-time 总量留缓冲）；
        - 绝对护栏：最多 MAX_PAGES 页。
        """
        out: list[PlatformSubmission] = []
        window_start = int(time.time()) - FULL_WINDOW_DAYS * 86400
        for page in range(1, MAX_PAGES + 1):
            data = await self._fetcher.get_json(
                STATUS_URL,
                params={
                    "handle": handle,
                    "from": (page - 1) * PAGE_SIZE + 1,
                    "count": PAGE_SIZE,
                },
                platform=self.platform_id,
                min_interval=self.min_interval,
                should_retry=self._should_retry_envelope,
            )
            self._check_envelope(data)
            rows = data.get("result") or []
            if not rows:
                break
            for row in rows:
                ts = int(row.get("creationTimeSeconds") or 0)
                if since is not None and ts <= since:
                    return out
                out.append(self._to_submission(row, ts))
            last_ts = int(rows[-1].get("creationTimeSeconds") or 0)
            # 全量停止条件：已越过窗口起点且累计条数达标；或页不满
            if since is None and last_ts < window_start and len(out) >= FULL_MIN_ROWS:
                break
            if len(rows) < PAGE_SIZE:
                break
        return out

    # ===== 内部 =====

    def normalize_url(self, url: str) -> str:
        """旧格式 problemset 链接幂等转换为 contest/gym 格式。"""
        return normalize_problem_url(url)

    @staticmethod
    def _check_envelope(data: Any) -> None:
        """CF API 信封校验：status != OK 抛 PlatformError（可重试的限流信封
        已在 net 层经 should_retry 消化，走到这里的是不可重试失败）。"""
        if not isinstance(data, dict) or data.get("status") != "OK":
            comment = str(data.get("comment") or "") if isinstance(data, dict) else ""
            raise PlatformError(f"Codeforces API 返回失败: {comment}")

    @staticmethod
    def _should_retry_envelope(data: Any) -> bool:
        """限流信封（以 200 返回的 FAILED + Call limit exceeded）应重试。"""
        if not isinstance(data, dict) or data.get("status") == "OK":
            return False
        comment = str(data.get("comment") or "")
        return "call limit exceeded" in comment.lower()

    @staticmethod
    def _to_submission(row: dict[str, Any], ts: int) -> PlatformSubmission:
        problem = row.get("problem") or {}
        contest_id = problem.get("contestId")
        index = problem.get("index")
        return PlatformSubmission(
            submission_id=str(row.get("id")),
            problem_key=problem_key(contest_id, index, str(problem.get("name") or "")),
            problem_name=str(problem.get("name") or ""),
            problem_url=problem_url(contest_id, index),
            difficulty=problem.get("rating"),
            verdict=map_verdict(str(row.get("verdict") or "")),
            submitted_at=ts,
            language=str(row.get("programmingLanguage") or ""),
        )
