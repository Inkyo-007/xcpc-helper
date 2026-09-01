# QOJ 适配器

> 状态：已实现。公共契约与同步语义见 [conventions.md](conventions.md)；本文只记录 QOJ 专属实现。

## 数据源

QOJ 无公开提交明细 API，经实测确认，`/submissions` 分页 HTML（服务端渲染）为唯一切实可行的数据源：

| 用途 | 端点 | 凭据 |
| --- | --- | --- |
| 提交明细 | `GET /submissions?submitter=<username>&page=N` | cookie |
| 绑定验证 · 存在性 | `GET /user/profile/<username>` | **匿名可用** |
| 绑定验证 · 凭据有效性 | 携凭据试拉 `/submissions?submitter=<handle>&page=1` | cookie |

说明：

- 响应为服务端渲染 HTML 表格，每行 9 列：提交 ID、题目、提交者、结果、运行时间、内存、语言、代码大小、提交时间。Adapter 用正则提取，非 HTML 解析库（减少依赖）；
- 倒序分页、perPage=10（固定），倒序回扫（增量 `ts < since` 停止，submission `id` 去重），流式断点为 `{"page": 页码, "fetched": 累计}`；
- 题目 URL 含 `contest_id`，格式为 `/contest/<cid>/problem/<pid>`，`problem_key` 取 `pid`；
- 无难度字段，`difficulty` 统一置 `None`；
- 无总量字段（不像洛谷有 `records.count`），不上报同步进度。

## 实现要点

**HTML 解析**。响应为服务端渲染 HTML 表格，Adapter 用正则提取每行 9 列数据，非 HTML 解析库（减少依赖）。

**分页停止条件**：
- 页数据条数 `< 10` → 最后一页；
- 或达到 `MAX_PAGES = 5000` 安全护栏（5 万条）。

**增量同步**：数据按时间倒序（最新在前），增量停止条件 `timestamp_utc_seconds < since`，游标当秒提交重复拉取由 store 按 `submission_id` 去重吸收。

**时区处理**：原始时间戳为中国时区（UTC+8），Adapter 内转换为 UTC 秒级：`datetime.strptime(..., '%Y-%m-%d %H:%M:%S').replace(tzinfo=china_tz).timestamp()`。

**Verdict 映射**（经对 544 条真实提交全面扫描）：

### A. 明确状态文本（非子任务评分）

| 原始文本 | 归一化 | 说明 |
|----------|--------|------|
| `AC ✓` | AC | 通过（Score = Full） |
| `WA` | WA | 答案错误（Score = 0） |
| `RE` | RE | 运行时错误（Score = 0） |
| `TL` | TLE | 时间限制超限（Score = 0） |
| `ML` | MLE | 内存限制超限（Score = 0） |
| `CE` | CE | 编译错误（样本中未出现，预留） |
| `OLE` | OLE | 输出限制超限（样本中未出现，预留） |
| `UKE` | UKE | 系统错误（样本中未出现，预留） |
| `JG` | JG | 评测中（样本中未出现，预留） |

### B. 子任务评分（数值分数）

QOJ 部分题目采用子任务评分制，列表页显示**实际获得分数**（如 `67`、`42`、`0`）：

| 情形 | 处理方式 |
|------|---------|
| 文本以 `✓` 结尾（如 `100 ✓`、`110 ✓`） | AC（满分通过） |
| 文本为 `AC, WA`（通常是通过后被 Hack） | WA |
| 文本为纯数字且 `data-score == data-full` | AC（满分通过） |
| 文本为纯数字且 `data-score < data-full` | UNAC（未通过，子任务部分得分） |
| 文本为纯数字且 `data-score == 0` | UNAC（零分，无法区分 WA/RE/TL） |

> 子任务评分题中，`0` 分与 `WA` 是不同的显示方式：`0` 表示子任务全错，`WA` 表示传统评测错误。列表页无法区分 `0` 分背后的具体原因，保守归 `UNAC`；非满分数字亦归 `UNAC`。

**题目外链**：`http://qoj.ac/contest/<contest_id>/problem/<problem_id>`，从表格第 2 列链接的 `href` 提取。

**难度**：QOJ 页面无难度字段，`difficulty` 统一置 `None`。

**限流**：`min_interval = 1.0`，使用共享 `HttpFetcher`（无 WAF 指纹挑战）。QOJ 无明显严格限流，偶发失败主要是 Cloudflare/网络波动导致的响应截断，非主动限流；单次调用覆盖 `max_retries = 3` 应对偶发失败。需携带浏览器标识头避免 Cloudflare 拦截（参考 VJudge）。

## 认证（Cookie 模式）

采用**洛谷同款双路径**：

### 方式一 · 一键登录（Playwright）

**UPDATE：已禁用**，几乎必然触发 cloudflare 验证，无法通过。

### 方式二 · 手动输入 cookie

绑定弹窗提供 `UOJSESSID` 输入框（仅此一项即可访问提交记录），配「如何获取 cookie？」悬浮引导。`verify`/同步携带 `credentials`；绑定当下即携凭据试拉验证有效性（`AuthExpiredError` 在 verify 路径转 400，不放行死凭据）。

### 凭据存储与过期

- `secrets.json` 中保存 `UOJSESSID`；
- 凭据失效时访问 `/submissions` 被 302 重定向到 `/login` → `AuthExpiredError`；
- 同步中 `AuthExpiredError` → `syncErrorCode: "auth_expired"` → 账号按钮警示态「凭据过期」→ 点击打开账号管理弹窗 → 选择「更新凭据」重新授权 → 验证通过后自动触发一次同步。过期不影响本地已有数据，游标不动，重授权后从原游标继续增量。

## 陷阱备忘

- **仅需 `UOJSESSID` 即可访问提交记录**：其他 cookie（`uoj_username`、`uoj_remember_token` 等）非必需；
- **时区为中国时区（UTC+8）**：直接当 UTC 会差 8 小时，必须显式转换；
- **用户验证不返回 display_name**：`/user/profile/<username>` 存在性判定通过页面内容检查（`"No Such User"`），不返回昵称；`display_name` 只能留空；
- **子任务评分非满分归 `UNAC`**：列表页无法区分 `0` 分背后的具体原因（WA/RE/TL），保守归 `UNAC`；
- **HTML 结构变更风险**：QOJ 基于 UOJ，升级可能改变表格结构，测试 fixture 可快速发现；
- **Cloudflare 偶发截断**：非浏览器请求偶发响应不完整，限流 1s + 重试 3 次可缓解；
- **Playwright 登录窗口超时**：用户可能不关闭窗口，设置 3 分钟超时；
- **CSRF Token 过期**：登录时 Token 有效期短，每次登录前先 GET 登录页提取新 Token（一键登录由 Playwright 自动处理）。
