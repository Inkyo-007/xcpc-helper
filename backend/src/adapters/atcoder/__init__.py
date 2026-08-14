"""AtCoder 适配器（kenkoooo API + 官方用户主页验证，匿名可取，第二期）。

数据源（详见 docs/design/activity.md §5.5）：

- 提交明细：kenkoooo v3 user/submissions（升序、单页 ≤500、from_second 含边界）；
- 题目目录：kenkoooo problems.json（题名）+ problem-models.json（难度），
  实例内内存缓存 + TTL，不落盘；
- 绑定验证：官方用户主页 404 判定（history/json 与 kenkoooo user_info 对
  不存在用户均返回 200，实测确认不可用于存在性判断）。

第二期范围：提交明细（SUBMISSIONS）+ 绑定验证（USER_INFO）；
rating 属后续增量（官方 history/json 端点已探明，本期不声明 RATING）。
"""

import logging
import time
from typing import Any

from pydantic import ValidationError

from adapters.atcoder import api_models
from adapters.atcoder.api_models import AtProblem, AtProblemModel, AtSubmissionRow
from adapters.atcoder.normalize import map_verdict, problem_url
from adapters.base import (
    AuthMode,
    Capability,
    Credentials,
    HttpStatusError,
    PlatformAdapter,
    PlatformError,
    PlatformSubmission,
    UserInfo,
    UserNotFoundError,
)
from adapters.net import HttpFetcher

logger = logging.getLogger("xcpc.adapters.atcoder")

KENKOOOO_BASE = "https://kenkoooo.com/atcoder"
SUBMISSIONS_URL = f"{KENKOOOO_BASE}/atcoder-api/v3/user/submissions"
PROBLEMS_URL = f"{KENKOOOO_BASE}/resources/problems.json"
PROBLEM_MODELS_URL = f"{KENKOOOO_BASE}/resources/problem-models.json"
PROFILE_URL = "https://atcoder.jp/users"

PAGE_LIMIT = 500  # kenkoooo 单页返回上限
MAX_PAGES = 400  # 安全护栏（20 万条），正常路径不会触发
CATALOG_TTL_SECONDS = 24 * 3600  # 题目目录内存缓存有效期（不落盘）


class AtCoderAdapter(PlatformAdapter):
    platform_id = "atcoder"
    name = "AtCoder"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.USER_INFO})
    auth = AuthMode.NONE
    min_interval = 1.0  # kenkoooo 公益接口要求请求间隔 ≥ 1 秒

    def __init__(self, fetcher: HttpFetcher) -> None:
        self._fetcher = fetcher
        # 题目目录内存缓存（adapter 为 service 级单例，随进程生命周期）
        self._problems: dict[str, AtProblem] | None = None
        self._models: dict[str, AtProblemModel] = {}
        self._catalog_loaded_at: float = 0.0

    # ===== 绑定验证 =====

    async def verify(
        self, handle: str, credentials: Credentials | None = None
    ) -> UserInfo:
        """官方用户主页 404 判定用户存在性（响应为 HTML，仅看状态码）。"""
        try:
            await self._fetcher.request(
                "GET",
                f"{PROFILE_URL}/{handle}",
                platform=self.platform_id,
                min_interval=self.min_interval,
            )
        except HttpStatusError as exc:
            if exc.status_code == 404:
                raise UserNotFoundError(f"AtCoder 用户不存在: {handle}") from exc
            raise
        return UserInfo(handle=handle)

    # ===== 提交拉取 =====

    async def fetch_submissions(
        self,
        handle: str,
        *,
        since: int | None,
        credentials: Credentials | None = None,
        full_window_days: int,
        full_min_rows: int,
    ) -> list[PlatformSubmission]:
        """升序翻页拉取提交（返回按时间升序）。

        - 增量（since 非空）：from_second = since（含边界，游标当秒的提交
          重复拉取，由 store 层按 submission_id 去重吸收）；
        - 全量（since 为空）：先拉 full_window_days 窗口；窗口内不足
          full_min_rows 条时退到 from_second=0 拉全部历史（两步策略）；
        - 页间去重与防停滞：from_second 含边界 ⇒ 翻页下一页与上页末条
          同秒重叠，按 id 集合去重；单页无新 id 即停（防同秒满页死循环）；
        - 绝对护栏：最多 MAX_PAGES 页。

        full_window_days / full_min_rows 为同步策略，由调用方（sync 引擎）
        按上层配置传入，见 core/config.py 的 activity_window_days 等。
        """
        await self._ensure_catalog()
        start = since
        if start is None:
            start = max(0, int(time.time()) - full_window_days * 86400)
        seen: set[int] = set()
        rows: list[AtSubmissionRow] = []
        await self._collect(handle, start, seen, rows)
        if since is None and len(rows) < full_min_rows and start > 0:
            # 全量窗口内条数不足：回拉全部历史（为 all-time 总量留缓冲）
            await self._collect(handle, 0, seen, rows)
        return [self._to_submission(row) for row in rows]

    # ===== 内部：翻页 =====

    async def _collect(
        self,
        handle: str,
        start: int,
        seen: set[int],
        out: list[AtSubmissionRow],
    ) -> None:
        """从 start（含）升序翻页，新提交按 id 去重后追加到 out。"""
        current = start
        for _ in range(MAX_PAGES):
            data = await self._get_json(
                SUBMISSIONS_URL,
                params={"user": handle, "from_second": current},
            )
            page = self._parse(data, api_models.SUBMISSIONS, "提交列表")
            if not page:
                return
            new_rows = [row for row in page if row.id not in seen]
            for row in new_rows:
                seen.add(row.id)
                out.append(row)
            # 短页（未达上限）即最后一页；满页但无新 id 说明同秒重叠停滞
            if len(page) < PAGE_LIMIT or not new_rows:
                return
            current = page[-1].epoch_second

    # ===== 内部：题目目录 =====

    async def _ensure_catalog(self) -> None:
        """加载题目目录（内存缓存 + TTL）。

        失败语义分级：problems.json 失败抛 PlatformError（题名为核心展示
        字段，宁可本次同步降级重试不落库坏数据）；problem-models.json 失败
        记告警并以空难度继续（非关键字段）。
        """
        if (
            self._problems is not None
            and time.monotonic() - self._catalog_loaded_at < CATALOG_TTL_SECONDS
        ):
            return
        problems_data = await self._get_json(PROBLEMS_URL)
        problems = self._parse(problems_data, api_models.PROBLEMS, "题目目录")
        models: dict[str, AtProblemModel] = {}
        try:
            models_data = await self._get_json(PROBLEM_MODELS_URL)
            models = self._parse(
                models_data, api_models.PROBLEM_MODELS, "难度模型"
            )
        except PlatformError as exc:
            logger.warning("AtCoder 难度模型拉取失败，difficulty 置空继续: %s", exc)
        self._problems = {p.id: p for p in problems}
        self._models = models
        self._catalog_loaded_at = time.monotonic()

    # ===== 内部：解析与归一化 =====

    async def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        """get_json 包装：响应体非 JSON（ValueError）统一收敛为 PlatformError。

        kenkoooo 为裸 JSON（无信封），无需 should_retry 信封钩子；
        网关异常时可能返回 HTML 错误页，必须收敛进 AdapterError 契约，
        否则 sync 的 PlatformError 降级路径接不住。
        """
        try:
            return await self._fetcher.get_json(
                url,
                params=params,
                platform=self.platform_id,
                min_interval=self.min_interval,
            )
        except ValueError as exc:
            raise PlatformError(f"AtCoder API 响应非 JSON: {exc}") from exc

    @staticmethod
    def _parse(data: Any, validator: Any, label: str) -> Any:
        """外部 JSON 第一时间转模型；格式异常统一抛 PlatformError。"""
        try:
            return validator.validate_python(data)
        except ValidationError as exc:
            raise PlatformError(f"AtCoder API {label}格式异常: {exc}") from exc

    def _to_submission(self, row: AtSubmissionRow) -> PlatformSubmission:
        problems = self._problems or {}
        problem = problems.get(row.problem_id)
        model = self._models.get(row.problem_id)
        return PlatformSubmission(
            submission_id=str(row.id),
            problem_key=row.problem_id or "?",
            # 目录缺题时兜底 problem_id，不向 str 字段传 None
            problem_name=(problem.name if problem else "") or row.problem_id,
            problem_url=problem_url(row.contest_id, row.problem_id),
            difficulty=model.difficulty if model else None,
            verdict=map_verdict(row.result),
            submitted_at=row.epoch_second,
            language=row.language,
        )
