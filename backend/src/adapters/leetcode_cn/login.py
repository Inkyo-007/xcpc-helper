"""LeetCode CN 一键登录（browser-login）：Playwright 拉起系统浏览器，用户自行登录。

设计见 docs/design/activity/leetcode-cn.md：
- 复用系统已装浏览器（channel="chrome" 兜底 "msedge"），不下载浏览器二进制；
- 临时独立 profile（launch() 默认临时用户目录）：不碰用户日常浏览器数据，
  登录态随窗口关闭即焚；
- 用户在真实浏览器里自行完成登录（图形验证码/两步验证码等自然通过），
  应用轮询受控上下文的 cookie 罐：LEETCODE_SESSION 出现只是候选信号，
  再经鉴权探针（GraphQL userProgressQuestionList 返回数据）确认完整登录态才抓取；
- Playwright 为可选依赖（dependency group browser-login），惰性导入，
  未安装时由 service 层降级为手动粘贴路径。
"""

import asyncio
import logging
import time

from adapters.base import BrowserLoginCancelledError, Credentials, PlatformError

logger = logging.getLogger("xcpc.adapters.leetcode_cn.login")

LOGIN_URL = "https://leetcode.cn/accounts/login/"
COOKIE_URL = "https://leetcode.cn"
GRAPHQL_URL = "https://leetcode.cn/graphql/"
# 鉴权探针：确认会话完整登录
AUTH_PROBE_QUERY = {
    "query": "query userProgressQuestionList($filters: UserProgressQuestionListInput) { userProgressQuestionList(filters: $filters) { totalNum questions { frontendId } } }",
    "variables": {"filters": {"skip": 0, "limit": 1}},
    "operationName": "userProgressQuestionList",
}
# 登录成功判定所需的 cookie 名
REQUIRED_COOKIES = ("LEETCODE_SESSION", "csrftoken")

POLL_INTERVAL = 1.0  # cookie 罐轮询间隔（秒）
DEFAULT_TIMEOUT = 180.0  # 用户登录操作超时（秒）


def playwright_available() -> bool:
    """探测可选依赖 Playwright 是否可用（不实际导入重型模块）。"""
    import importlib.util

    return importlib.util.find_spec("playwright") is not None


# 用户关窗信号（通用契约，见 base.BrowserLoginCancelledError）
LoginCancelledError = BrowserLoginCancelledError


async def _session_authed(context) -> bool:
    """鉴权探针：用浏览器上下文请求 GraphQL，确认会话完整登录。

    探针失败（网络波动等）按未登录处理——下一轮轮询重试，不误判成功。
    """
    try:
        resp = await context.request.post(
            GRAPHQL_URL,
            data=AUTH_PROBE_QUERY,
            timeout=10_000,
        )
        if resp.status != 200:
            return False
        data = await resp.json()
    except Exception:  # noqa: BLE001 - 探针失败视同未登录，轮询继续
        return False
    return (
        isinstance(data, dict)
        and data.get("data") is not None
        and data["data"].get("userProgressQuestionList") is not None
    )


async def capture_credentials(timeout: float = DEFAULT_TIMEOUT) -> Credentials:
    """拉起系统浏览器登录窗口，返回抓取的凭据（含浏览器 UA）。

    用户关窗抛 LoginCancelledError；超时抛 asyncio.TimeoutError；
    无可用系统浏览器 / Playwright 故障抛 PlatformError。
    """
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # 复用系统浏览器：优先 Chrome，无则 Edge（Windows 预装必有）
        browser = None
        for channel in ("chrome", "msedge"):
            try:
                browser = await p.chromium.launch(channel=channel, headless=False)
                break
            except PlaywrightError:
                continue
        if browser is None:
            raise PlatformError(
                "未找到可用的系统浏览器（Chrome/Edge），请改用手动粘贴 cookie"
            )
        try:
            context = await browser.new_context()
            page = await context.new_page()
            ua = await page.evaluate("navigator.userAgent")
            await page.goto(LOGIN_URL)
            deadline = time.monotonic() + timeout
            last_probe = 0.0
            while time.monotonic() < deadline:
                cookies = await context.cookies(COOKIE_URL)
                jar = {c["name"]: c["value"] for c in cookies}
                # cookie 出现只是候选信号：匿名会话也携带 csrftoken
                # 必须再经鉴权探针确认完整登录态
                cookies_ready = all(k in jar for k in REQUIRED_COOKIES)
                probe_due = time.monotonic() - last_probe >= 3.0
                if cookies_ready and probe_due:
                    last_probe = time.monotonic()
                    if await _session_authed(context):
                        return Credentials(
                            cookies={k: jar[k] for k in REQUIRED_COOKIES},
                            headers={"User-Agent": ua},
                        )
                if page.is_closed():
                    raise LoginCancelledError("登录窗口已关闭")
                await asyncio.sleep(POLL_INTERVAL)
            raise TimeoutError("登录等待超时")
        except PlaywrightTimeoutError as exc:
            raise PlatformError(f"打开 LeetCode CN 登录页失败: {exc}") from exc
        except PlaywrightError as exc:
            # 窗口被关闭等场景 Playwright 抛通用 Error
            if "closed" in str(exc).lower():
                raise LoginCancelledError("登录窗口已关闭") from exc
            raise PlatformError(f"浏览器登录窗口异常: {exc}") from exc
        finally:
            await browser.close()
