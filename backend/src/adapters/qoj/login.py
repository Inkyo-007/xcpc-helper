"""QOJ 一键登录（browser-login）：Playwright 拉起系统浏览器，用户自行登录。

参照 luogu/login.py 实现同形态登录采集：
- 复用系统已装浏览器（channel="chrome" 兜底 "msedge"）；
- 临时独立 profile：登录态随窗口关闭即焚；
- 用户在真实浏览器里自行完成登录；
- 轮询 cookie 罐，检测 UOJSESSID 出现后经鉴权探针确认；
- Playwright 为可选依赖，惰性导入。
"""

import asyncio
import logging
import time

from adapters.base import BrowserLoginCancelledError, Credentials, PlatformError

logger = logging.getLogger("xcpc.adapters.qoj.login")

LOGIN_URL = "http://qoj.ac/login"
COOKIE_URL = "http://qoj.ac"
# 鉴权探针端点：登录态下返回提交列表 HTML，未登录重定向到 /login
AUTH_PROBE_URL = "http://qoj.ac/submissions"
# 登录成功判定所需的 cookie 名
REQUIRED_COOKIE = "UOJSESSID"

POLL_INTERVAL = 1.0  # cookie 罐轮询间隔（秒）
DEFAULT_TIMEOUT = 180.0  # 用户登录操作超时（秒）


def playwright_available() -> bool:
    """探测可选依赖 Playwright 是否可用（不实际导入重型模块）。"""
    import importlib.util

    return importlib.util.find_spec("playwright") is not None


# 用户关窗信号（通用契约，见 base.BrowserLoginCancelledError）
LoginCancelledError = BrowserLoginCancelledError


async def _session_authed(context) -> bool:
    """鉴权探针：用浏览器上下文请求受保护接口，确认会话完整登录。

    未登录时 /submissions 会被 302 重定向到 /login（返回登录页 HTML）；
    完整登录态返回提交列表 HTML（包含表格数据）。
    探针失败按未登录处理——下一轮轮询重试，不误判成功。
    """
    try:
        resp = await context.request.get(AUTH_PROBE_URL, timeout=10_000)
        if resp.status != 200:
            return False
        text = await resp.text()
        # 登录页特征：包含 "登录" 或 "Login" 表单
        return "login" not in text.lower() or "<table" in text
    except Exception:  # noqa: BLE001 - 探针失败视同未登录，轮询继续
        return False


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
                # UOJSESSID 出现只是候选信号，必须再经鉴权探针确认完整登录态
                cookie_ready = REQUIRED_COOKIE in jar
                probe_due = time.monotonic() - last_probe >= 3.0
                if cookie_ready and probe_due:
                    last_probe = time.monotonic()
                    if await _session_authed(context):
                        return Credentials(
                            cookies={REQUIRED_COOKIE: jar[REQUIRED_COOKIE]},
                            headers={"User-Agent": ua},
                        )
                if page.is_closed():
                    raise LoginCancelledError("登录窗口已关闭")
                await asyncio.sleep(POLL_INTERVAL)
            raise TimeoutError("登录等待超时")
        except PlaywrightTimeoutError as exc:
            raise PlatformError(f"打开 QOJ 登录页失败: {exc}") from exc
        except PlaywrightError as exc:
            # 窗口被关闭等场景 Playwright 抛通用 Error
            if "closed" in str(exc).lower():
                raise LoginCancelledError("登录窗口已关闭") from exc
            raise PlatformError(f"浏览器登录窗口异常: {exc}") from exc
        finally:
            await browser.close()
