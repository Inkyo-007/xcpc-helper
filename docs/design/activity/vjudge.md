# VJudge 适配器（Playwright 一键登录 + Cookie 授权）

> 状态：已实现。
> 公共契约与同步语义见 [conventions.md](conventions.md)；本文记录 VJudge 专属实现。

## 数据源

| 用途 | 端点 | 方法 | 凭据 |
|------|------|------|------|
| 提交明细 | `GET /user/submissions` | 需登录态 | cookie |
| 绑定验证 · 存在性 | 携凭据试拉 `/user/submissions` 第 1 页 | cookie | 返回 `data` 非空即存在 |
| 登录 | `POST /user/login` | 表单 | 用户名+密码 |

说明：

- `/user/submissions` 按时间**倒序**返回（最新在前），`pageSize` 最大 500，游标分页（`maxId` = 上一页最后一条 `runId - 1`）；
- 响应为 JSON 信封：`{data: [...], error: null}` 或 `{error: {i18nKey, trustable}}`；
- `data` 为二维数组，每行约 10+ 列：`[runId, OJId, probNum, result, language, time, memory, length, submitTime, ...]`；
- VJudge **必须登录**才能查询任何用户的提交记录，匿名请求返回 `user.error.login_required`。

## Cookie 机制

VJudge 登录后设置两个 cookie：

| Cookie 名称 | 属性 | 说明 |
|-------------|------|------|
| `JSESSIONID` | `Path=/; HttpOnly` | 会话级（浏览器关闭失效） |
| `JSESSlONID` | `Domain=vjudge.net; Max-Age=31536000` | 持久级（1 年有效期） |

**注意**：第二个 cookie 名称是 `JSESSlONID`（小写 L），非 `JSESSIONID`。

两个 cookie 必须**同时携带**才能通过认证。持久 cookie 用于跨会话识别设备，会话 cookie 用于当前登录态验证。

## 传输层

VJudge **无 WAF 指纹挑战**，使用共享 `HttpFetcher`（httpx）即可。

但 VJudge 使用 **Cloudflare Turnstile** 人机验证（从 JS bundle 源码确认）。直接程序化 POST 登录可能触发 Turnstile，故采用 **Playwright 一键登录** 为主方案：用户在真实浏览器中自然完成登录（包括可能的 Turnstile），后端从浏览器上下文抓取双 cookie。

## 一键登录（browser-login）

参照洛谷 `adapters/luogu/login.py` 实现：

1. Playwright 拉起系统 Chrome/Edge（`channel="chrome"` 兜底 `"msedge"`），临时 profile；
2. 导航到 `https://vjudge.net/status`（VJudge 登录为模态框，需先打开含登录入口的页面）；
3. 用户自行在浏览器中完成登录（处理 Turnstile/验证码等）；
4. 后端轮询浏览器上下文的 cookie 罐：双 cookie（`JSESSIONID` + `JSESSlONID`）出现为候选信号；
5. 鉴权探针：用浏览器上下文请求 `/user/submissions?username={handle}&pageSize=1`，返回含 `data` 数组（非 `error`）即确认完整登录态；
6. 抓取 cookie 与 UA，返回 `Credentials`；
7. 用户关窗 → `BrowserLoginCancelledError`；超时 3 分钟 → `TimeoutError`。

Playwright 未安装时 `/platforms` 的 `browserLogin=false`，前端隐藏一键登录按钮。

## 同步策略

### 全量同步

- 从 `maxId=null` 开始，逐页拉取；
- 每页 500 条，末页判定：返回条数 `< pageSize`；
- 断点：`{"max_id": 下一页游标, "fetched": 累计条数}`；
- 总量未知，不上报进度（前端显示不定态环）。

### 增量同步

- 游标：`Account.last_synced_at`（UTC 秒级时间戳）；
- 增量停止：`ts < since`（VJudge 返回的 `submitTime` 为毫秒级，需 `/ 1000` 转秒）；
- 游标当秒提交重复拉取，由 store 按 `submission_id` 去重吸收。

## 归一化

### Verdict 映射

VJudge `result` 字段 → `Verdict`：

| 原始值 | 归一化 |
|--------|--------|
| `AC` | `AC` |
| `WA` | `WA` |
| `TLE` | `TLE` |
| `MLE` | `MLE` |
| `RE` | `RE` |
| `CE` | `CE` |
| `OLE` | `OLE` |
| `PE` | `UKE` |
| `JUDGING` / `PENDING` | `JG` |
| 其他 | `UKE` |

### 字段映射

- `submission_id` = `runId`（第 0 列）
- `problem_key` = `"{OJId}-{probNum}"`（如 `"Codeforces-436B"`）
- `problem_name` = `probNum`（第 2 列，题号）
- `problem_url` = `https://vjudge.net/problem/{OJId}-{probNum}`
- `submitted_at` = `submitTime / 1000`（毫秒转秒）
- `language` = 第 4 列原始值
- `difficulty` = `None`（VJudge 无难度信息）

### Handle 与 Display Name

- VJudge 用户名即 handle，无额外 display_name 字段；
- `handle` = 用户输入的 VJudge 用户名；
- `display_name` = `None`（界面回退显示 handle）。

## 陷阱备忘

- **双 cookie 必须同时携带**：仅带 `JSESSIONID` 或仅带 `JSESSlONID` 均返回 `login_required`；
- **Cookie 名称大小写**：持久 cookie 为 `JSESSlONID`（小写 L），非 `JSESSIONID`；
- **时间戳为毫秒级**：`submitTime` 需 `/ 1000` 转为 UTC 秒级；
- **Turnstile 风险**：直接 POST 登录可能触发 Cloudflare Turnstile，Playwright 方案让用户自然处理；
- **登录模态框**：VJudge 登录为弹窗形式，Playwright 需打开含登录入口的页面（如 `/status`）；
- **聚合平台特性**：题目来自不同 OJ，`problem_key` 需包含 OJ 信息以避免冲突；
- **限流宽松**：VJudge 无严格限流，`min_interval = 2.0` 为保守值。
