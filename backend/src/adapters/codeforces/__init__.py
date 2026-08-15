"""Codeforces 适配器（官方公开 API，匿名可取，第一期唯一平台）。

第一期范围：提交明细（SUBMISSIONS）+ 绑定验证（USER_INFO）；
rating / 比赛记录属后续增量（Capability.RATING 已预留，本期不实现）。
"""

import logging
import time
from typing import Any, TypeVar

from pydantic import ValidationError

from adapters.base import (
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
from adapters.codeforces.api_models import (
    CfEnvelope,
    CfSubmissionRow,
    CfUserInfo,
)
from adapters.codeforces.normalize import map_verdict, problem_key, problem_url
from adapters.net import HttpFetcher

logger = logging.getLogger("xcpc.adapters.codeforces")

T = TypeVar("T")

API_BASE = "https://codeforces.com/api"
STATUS_URL = f"{API_BASE}/user.status"
INFO_URL = f"{API_BASE}/user.info"

PAGE_SIZE = 1000  # user.status 单页上限
MAX_PAGES = 200  # 安全护栏（20 万条），正常路径不会触发


class CodeforcesAdapter(PlatformAdapter):
    platform_id = "codeforces"
    name = "Codeforces"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.USER_INFO})
    auth = AuthMode.NONE
    min_interval = 2.0  # 官方建议请求间隔 ≥ 2 秒

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher

    # ===== 绑定验证 =====

    async def verify(
        self, handle: str, credentials: Credentials | None = None
    ) -> UserInfo:
        data = await self._fetcher.get_json(
            INFO_URL,
            params={"handles": handle},
            platform=self.platform_id,
            min_interval=self.min_interval,
            should_retry=self._should_retry_envelope,
        )
        envelope = self._parse_envelope(data, CfUserInfo)
        if envelope.status != "OK":
            if "not found" in envelope.comment.lower():
                raise UserNotFoundError(f"Codeforces 用户不存在: {handle}")
            raise PlatformError(f"Codeforces API 返回失败: {envelope.comment}")
        if not envelope.result:
            raise UserNotFoundError(f"Codeforces 用户不存在: {handle}")
        user = envelope.result[0]
        return UserInfo(handle=user.handle or handle, avatar=user.avatar)

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
        """按页拉取提交（返回按时间倒序）。

        CF user.status 无总量字段，不上报进度（progress_cb 为契约参数，
        本平台忽略，前端显示不定态）。

        - 增量（since 非空）：只取游标之后的提交，遇旧即停；停止条件为
          ts < since，游标当秒的提交会重复拉取，由 store 层按
          submission_id 去重吸收（避免同秒多提交被永久漏掉）；
        - 全量（since 为空）：拉到覆盖 full_window_days 窗口为止，窗口内
          不足 full_min_rows 条时继续拉满该数（为 all-time 总量留缓冲）；
        - 绝对护栏：最多 MAX_PAGES 页。

        full_window_days / full_min_rows 为同步策略，由调用方（sync 引擎）
        按上层配置传入，见 core/config.py 的 activity_window_days 等。
        """
        out: list[PlatformSubmission] = []
        window_start = int(time.time()) - full_window_days * 86400
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
            envelope = self._parse_envelope(data, CfSubmissionRow)
            self._check_envelope(envelope)
            rows = envelope.result
            if not rows:
                break
            for row in rows:
                ts = row.creationTimeSeconds
                if since is not None and ts < since:
                    return out
                out.append(self._to_submission(row, ts))
            last_ts = rows[-1].creationTimeSeconds
            # 全量停止条件：已越过窗口起点且累计条数达标；或页不满
            if since is None and last_ts < window_start and len(out) >= full_min_rows:
                break
            if len(rows) < PAGE_SIZE:
                break
        return out

    # ===== 内部 =====

    @staticmethod
    def _parse_envelope(data: Any, item_type: type[T]) -> CfEnvelope[T]:
        """外部 JSON 第一时间转信封模型；格式异常统一抛 PlatformError。"""
        try:
            return CfEnvelope[item_type].model_validate(data)
        except ValidationError as exc:
            raise PlatformError(f"Codeforces API 响应格式异常: {exc}") from exc

    @staticmethod
    def _check_envelope(envelope: CfEnvelope[Any]) -> None:
        """信封校验：status != OK 抛 PlatformError（可重试的限流信封
        已在 net 层经 should_retry 消化，走到这里的是不可重试失败）。"""
        if envelope.status != "OK":
            raise PlatformError(f"Codeforces API 返回失败: {envelope.comment}")

    @staticmethod
    def _should_retry_envelope(data: Any) -> bool:
        """限流信封（以 200 返回的 FAILED + Call limit exceeded）应重试。

        net 层回调传入原始 JSON；无法识别为信封时返回 False，
        交由 _parse_envelope 的格式校验抛错。
        """
        try:
            envelope = CfEnvelope[Any].model_validate(data)
        except ValidationError:
            return False
        return (
            envelope.status != "OK"
            and "call limit exceeded" in envelope.comment.lower()
        )

    @staticmethod
    def _to_submission(row: CfSubmissionRow, ts: int) -> PlatformSubmission:
        problem = row.problem
        contest_id = problem.contestId if problem else None
        index = problem.index if problem else None
        # problem.name 可能为 null：收敛为空串，避免 None 传入 PlatformSubmission
        # 的 str 字段抛 ValidationError 逃逸 AdapterError 契约
        name = (problem.name or "") if problem else ""
        return PlatformSubmission(
            submission_id=str(row.id),
            problem_key=problem_key(contest_id, index, name),
            problem_name=name,
            problem_url=problem_url(contest_id, index),
            difficulty=problem.rating if problem else None,
            verdict=map_verdict(row.verdict),
            submitted_at=ts,
            language=row.programmingLanguage,
        )
