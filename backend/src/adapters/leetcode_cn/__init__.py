"""LeetCode CN 适配器（Cookie 授权 + GraphQL Batch Query）。

设计见 docs/design/activity/leetcode-cn.md：
- 使用共享 HttpFetcher（httpx），无 WAF 指纹挑战；
- GraphQL batch query 一次获取多题提交历史（200 题/batch）；
- 进度按题目数上报（总量 = userProgressQuestionList.totalNum）；
- Playwright 一键登录复用洛谷模式。
"""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

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
)
from adapters.leetcode_cn.api_models import (
    LcPublicProfileData,
    LcQuestion,
)
from adapters.leetcode_cn.normalize import map_verdict, problem_url
from adapters.net import HttpFetcher

logger = logging.getLogger("xcpc.adapters.leetcode_cn")

GRAPHQL_URL = "https://leetcode.cn/graphql/"
# 用户存在性验证端点（匿名可用）
PUBLIC_PROFILE_URL = "https://leetcode.cn/graphql/"

BATCH_SIZE = 200  # 每批查询的题目数（实测 200 稳定，~9 秒响应）
MAX_PAGES = 1000  # 安全护栏


class LeetCodeCNAdapter(PlatformAdapter):
    platform_id = "leetcode-cn"
    name = "LeetCode CN"
    capabilities = frozenset({Capability.SUBMISSIONS, Capability.USER_INFO})
    auth = AuthMode.COOKIE
    min_interval = 9.0  # 参考 glsync 实测：60 请求/10 分钟窗口

    def __init__(
        self,
        fetcher: HttpFetcher,
        session_factory: Any | None = None,
    ) -> None:
        self._fetcher = fetcher

    # ===== 绑定验证 =====

    async def verify(
        self, handle: str, credentials: Credentials | None = None
    ) -> UserInfo:
        """验证用户存在性（匿名）→ 携凭据试拉题目列表判有效性。

        handle 为 userSlug（URL 标识）。
        """
        # Step 1: 匿名验证用户存在性
        query = {
            "query": "query userProfilePublicProfile($userSlug: String!) { userProfilePublicProfile(userSlug: $userSlug) { username siteRanking profile { userSlug realName userAvatar } } }",
            "variables": {"userSlug": handle},
        }
        data = await self._post_graphql(query, anonymous=True)
        profile_data = data.get("data", {}).get("userProfilePublicProfile")
        if profile_data is None:
            raise UserNotFoundError(f"LeetCode CN 用户不存在: {handle}")

        # Step 2: 凭据有效性验证（如有凭据）
        if credentials is not None:
            probe = {
                "query": "query userProgressQuestionList($filters: UserProgressQuestionListInput) { userProgressQuestionList(filters: $filters) { totalNum questions { frontendId } } }",
                "variables": {"filters": {"skip": 0, "limit": 1}},
                "operationName": "userProgressQuestionList",
            }
            try:
                await self._post_graphql(probe, credentials=credentials)
            except AuthExpiredError:
                raise
            except Exception as exc:
                raise AuthExpiredError(
                    f"LeetCode CN 凭据无效，请重新授权: {exc}"
                ) from exc

        profile = LcPublicProfileData.model_validate(profile_data)
        # realName 是更可靠的显示名（username 可能等于 userSlug）
        display_name = profile.profile.real_name or profile.username or None
        return UserInfo(
            handle=profile.profile.user_slug,
            display_name=display_name,
            avatar=profile.profile.user_avatar or None,
        )

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
        """流式拉取提交：先获取题目清单，再 batch 查询提交历史。

        - 增量（since 非空）：只拉 lastSubmittedAt > since 的题目；
        - 全量（since 为空）：拉全部已解决题目；
        - 进度按题目数上报（processed / total_problems）。
        """
        if credentials is None:
            raise AuthExpiredError("未配置 LeetCode CN 凭据，请先绑定账号并授权")

        # Step 1: 获取已解决题目清单
        all_questions = await self._fetch_solved_questions(credentials)

        # 增量过滤
        if since is not None:
            since_dt = datetime.fromtimestamp(since, tz=UTC)
            questions = [
                q for q in all_questions
                if q.last_submitted_at is not None
                and self._parse_iso(q.last_submitted_at) > since_dt
            ]
        else:
            questions = all_questions

        total = len(questions)
        if total == 0:
            yield SyncBatch(done=True)
            return

        # Step 2: Batch 查询提交历史
        processed = 0
        for i in range(0, total, BATCH_SIZE):
            batch_questions = questions[i : i + BATCH_SIZE]
            submissions = await self._fetch_batch_submissions(
                batch_questions, credentials
            )

            items = [self._to_submission(s, q) for q in batch_questions for s in submissions.get(q.title_slug, [])]
            processed += len(batch_questions)

            if progress_cb is not None:
                progress_cb(processed, total)

            # 增量模式下，如果本批无新提交且已处理完，提前结束
            done = (i + BATCH_SIZE) >= total
            yield SyncBatch(
                items=items,
                checkpoint=None,
                done=done,
            )

    async def _fetch_solved_questions(self, credentials: Credentials) -> list[LcQuestion]:
        """获取全部已解决题目（支持分页）。"""
        questions: list[LcQuestion] = []
        skip = 0
        limit = 500

        while True:
            query = {
                "query": "query userProgressQuestionList($filters: UserProgressQuestionListInput) { userProgressQuestionList(filters: $filters) { totalNum questions { frontendId title titleSlug lastSubmittedAt questionStatus lastResult } } }",
                "variables": {"filters": {"questionStatus": "SOLVED", "skip": skip, "limit": limit}},
                "operationName": "userProgressQuestionList",
            }
            data = await self._post_graphql(query, credentials=credentials)
            result = data.get("data", {}).get("userProgressQuestionList", {})
            page_questions = result.get("questions", [])

            if not page_questions:
                break

            questions.extend([LcQuestion.model_validate(q) for q in page_questions])

            if len(page_questions) < limit:
                break
            skip += limit

            # 安全护栏
            if skip > MAX_PAGES * limit:
                break

        return questions

    async def _fetch_batch_submissions(
        self,
        questions: list[LcQuestion],
        credentials: Credentials,
    ) -> dict[str, list]:
        """Batch 查询多题的提交历史，返回 {title_slug: [submissions]}。"""
        if not questions:
            return {}

        # 构造 batch query（使用 title_slug 作为别名，避免索引映射问题）
        query_parts = []
        for q in questions:
            # 使用 slug 的合法 GraphQL 别名形式（替换连字符为下划线）
            alias = q.title_slug.replace("-", "_")
            query_parts.append(
                f'{alias}: submissionList(offset: 0, limit: 50, questionSlug: "{q.title_slug}") '
                '{ submissions { id statusDisplay lang timestamp } }'
            )
        query_str = "query BatchSubmissions { " + " ".join(query_parts) + " }"

        data = await self._post_graphql(
            {"query": query_str},
            credentials=credentials,
        )

        result: dict[str, list] = {}
        for q in questions:
            alias = q.title_slug.replace("-", "_")
            batch_data = data.get("data", {}).get(alias, {})
            submissions = batch_data.get("submissions", [])
            result[q.title_slug] = submissions

        return result

    # ===== 一键登录 =====

    def browser_login_available(self) -> bool:
        """一键登录是否可用（Playwright 可选依赖已安装）。"""
        from adapters.leetcode_cn import login as login_mod

        return login_mod.playwright_available()

    async def run_browser_login(
        self, timeout: float
    ) -> tuple[Credentials, UserInfo]:
        """拉起系统浏览器登录窗口，返回抓取的凭据与验证回执。"""
        from adapters.leetcode_cn import login as login_mod

        credentials = await login_mod.capture_credentials(timeout)
        # 从 JWT payload 中解析 userSlug
        user_slug = self._extract_user_slug_from_session(
            credentials.cookies.get("LEETCODE_SESSION", "")
        )
        if not user_slug:
            raise PlatformError("无法从登录会话中解析用户信息")
        info = await self.verify(user_slug, credentials)
        return credentials, info

    # ===== 内部：GraphQL 请求 =====

    async def _post_graphql(
        self,
        payload: dict[str, Any],
        *,
        credentials: Credentials | None = None,
        anonymous: bool = False,
    ) -> dict[str, Any]:
        """发送 GraphQL POST 请求，返回解析后的 JSON。"""
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://leetcode.cn",
            "Referer": "https://leetcode.cn/",
        }
        # 如果有 csrftoken，加入请求头
        if credentials is not None:
            csrf = credentials.cookies.get("csrftoken") if hasattr(credentials, "cookies") else credentials.get("cookies", {}).get("csrftoken")
            if csrf:
                headers["x-csrftoken"] = csrf

        try:
            data = await self._fetcher.post_json(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
                credentials=credentials if isinstance(credentials, Credentials) else None,
                platform=self.platform_id,
                min_interval=self.min_interval,
            )
        except Exception as exc:
            if anonymous:
                raise PlatformError(f"LeetCode CN 请求失败: {exc}") from exc
            raise AuthExpiredError(
                f"LeetCode CN 凭据失效或请求失败，请重新授权: {exc}"
            ) from exc

        # 检查 GraphQL 错误
        if "errors" in data:
            error_msg = str(data["errors"])
            if (
                ("auth" in error_msg.lower() or "login" in error_msg.lower())
                and not anonymous
            ):
                raise AuthExpiredError("LeetCode CN 凭据已过期，请重新授权")
            raise PlatformError(f"LeetCode CN GraphQL 错误: {error_msg}")

        return data

    # ===== 内部：工具方法 =====

    @staticmethod
    def _to_submission(raw: dict, question: LcQuestion) -> PlatformSubmission:
        """单条提交归一化。"""
        return PlatformSubmission(
            submission_id=str(raw["id"]),
            problem_key=question.title_slug,
            problem_name=question.title,
            problem_url=problem_url(question.title_slug),
            verdict=map_verdict(raw.get("statusDisplay", "")),
            submitted_at=int(raw["timestamp"]),
            language=raw.get("lang", ""),
        )

    @staticmethod
    def _parse_iso(iso_str: str) -> datetime:
        """解析 ISO 8601 时间字符串（含时区）。"""
        # 处理 Python < 3.11 的兼容性
        try:
            return datetime.fromisoformat(iso_str)
        except ValueError:
            # 尝试去掉微秒部分
            if "." in iso_str:
                base, rest = iso_str.split(".", 1)
                tz_idx = rest.find("+")
                if tz_idx == -1:
                    tz_idx = rest.find("-")
                if tz_idx > 0:
                    iso_str = base + rest[tz_idx:]
                else:
                    iso_str = base
            return datetime.fromisoformat(iso_str)

    @staticmethod
    def _extract_user_slug_from_session(session_token: str) -> str | None:
        """从 LEETCODE_SESSION JWT payload 中提取 user_slug。"""
        import base64
        import json

        try:
            # JWT 格式: header.payload.signature
            parts = session_token.split(".")
            if len(parts) != 3:
                return None
            # Base64URL decode payload
            payload_b64 = parts[1]
            # 补齐 padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.b64decode(payload_b64))
            return payload.get("user_slug")
        except (ValueError, KeyError, json.JSONDecodeError):
            return None
