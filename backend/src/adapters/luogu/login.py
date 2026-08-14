"""洛古一键登录（browser-login）：Playwright 拉起系统浏览器，用户自行登录。

设计见 docs/design/activity.md §5.6：
- 复用系统已装浏览器（channel="chrome" 兜底 "msedge"），不下载浏览器二进制；
- 临时独立 profile（launch() 默认临时用户目录）：不碰用户日常浏览器数据，
  登录态随窗口关闭即焚；
- 用户在真实浏览器里自行完成登录（图形验证码/二级密码等自然通过），
  应用只轮询该受控上下文的 cookie 罐，检测到 __client_id 即抓取；
- Playwright 为可选依赖（dependency group browser-login），惰性导入，
  未安装时由 service 层降级为手动粘贴路径。

QOJ 等后续 cookie 平台可参照本模块实现同形态登录采集。
"""

import asyncio
import logging
import time

from adapters.base import BrowserLoginCancelledError, Credentials, PlatformError

logger = logging.getLogger("xcpc.adapters.luogu.login")

LOGIN_URL = "https://www.luogu.com.cn/auth/login"
COOKIE_URL = "https://www.luogu.com.cn"
# 登录成功判定所需的 cookie 名（_uid = 用户 id，__client_id = 会话令牌）
REQUIRED_COOKIES = ("_uid", "__client_id")

POLL_INTERVAL = 1.0  # cookie 罐轮询间隔（秒）
DEFAULT_TIMEOUT = 180.0  # 用户登录操作超时（秒）


def playwright_available() -> bool:
    """探测可选依赖 Playwright 是否可用（不实际导入重型模块）。"""
    import importlib.util

    return importlib.util.find_spec("playwright") is not None


# 用户关窗信号（通用契约，见 base.BrowserLoginCancelledError）
LoginCancelledError = BrowserLoginCancelledError


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
            while time.monotonic() < deadline:
                cookies = await context.cookies(COOKIE_URL)
                jar = {c["name"]: c["value"] for c in cookies}
                if all(k in jar for k in REQUIRED_COOKIES):
                    return Credentials(
                        cookies={k: jar[k] for k in REQUIRED_COOKIES},
                        headers={"User-Agent": ua},
                    )
                if page.is_closed():
                    raise LoginCancelledError("登录窗口已关闭")
                await asyncio.sleep(POLL_INTERVAL)
            raise TimeoutError("登录等待超时")
        except PlaywrightTimeoutError as exc:
            raise PlatformError(f"打开洛古登录页失败: {exc}") from exc
        except PlaywrightError as exc:
            # 窗口被关闭等场景 Playwright 抛通用 Error
            if "closed" in str(exc).lower():
                raise LoginCancelledError("登录窗口已关闭") from exc
            raise PlatformError(f"浏览器登录窗口异常: {exc}") from exc
        finally:
            await browser.close()
