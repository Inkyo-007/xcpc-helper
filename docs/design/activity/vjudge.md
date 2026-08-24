# VJudge 适配器（匿名模式，/status/data）

> 状态：已实现。
> 公共契约与同步语义见 [conventions.md](conventions.md)；本文记录 VJudge 专属实现。

## 数据源

| 用途 | 端点 | 方法 | 凭据 |
|------|------|------|------|
| 提交明细 | `GET /status/data` | 匿名 | 无需 |
| 绑定验证 · 存在性 | 试拉 `/status/data` 第 1 页 | 匿名 | 返回 data 非空即存在 |

说明：

- `/status/data` 按时间**倒序**返回（最新在前），`length` 最大 100（服务端硬限制），偏移分页（`start` = 上一页最后一条的偏移）；
- 响应为 DataTables 格式 JSON：`{data: [...], recordsTotal: N, recordsFiltered: N, draw: 1}`；
- `data` 为对象数组，每个对象包含：`runId, oj, probNum, status, language, languageCanonical, time, memory, runtime, sourceLength, userName, userId` 等字段；
- `recordsFiltered` 始终返回 `9999999`，不可靠，不做总量依据；
- **无需登录**即可查询任意用户的提交记录。

## 传输层

VJudge **无 WAF 指纹挑战**，使用共享 `HttpFetcher`（httpx）即可。

## 同步策略

### 全量同步

- 从 `start=0` 开始，逐页拉取；
- 每页 100 条，末页判定：返回条数 `< pageSize`；
- 断点：`{"start": 下一页偏移, "fetched": 累计条数}`；
- 不设绝对页数护栏：单个用户提交量实际不会过于多；
- 总量未知，不上报进度（前端显示不定态环）。

### 增量同步

- 游标：`Account.last_synced_at`（UTC 秒级时间戳）；
- 增量停止：`ts < since`（VJudge 返回的 `time` 为毫秒级，需 `/ 1000` 转秒）；
- 游标当秒提交重复拉取，由 store 按 `submission_id` 去重吸收。

## 归一化

### Verdict 映射

VJudge `status` 字段 → `Verdict`：

| 原始值 | 归一化 |
|--------|--------|
| `Accepted` / `AC` | `AC` |
| `Wrong Answer` / `WA` | `WA` |
| `Time Limit Exceeded` / `TLE` | `TLE` |
| `Memory Limit Exceeded` / `MLE` | `MLE` |
| `Runtime Error` / `RE` | `RE` |
| `Compilation Error` / `CE` | `CE` |
| `Output Limit Exceeded` / `OLE` | `OLE` |
| `Presentation Error` / `PE` | `WA` |
| `Judging` / `Pending` / `Running` / `Compiling` / `Waiting` / `In Queue` | `JG` |
| 其他 | `UKE` |

注意：`/status/data` 返回的 `status` 为完整字符串（如 `"Accepted"`），与旧 `/user/submissions` 的缩写（如 `"AC"`）不同；映射表同时兼容两种形式。

### 字段映射

- `submission_id` = `runId`
- `problem_key` = `"{oj}-{probNum}"`（如 `"Codeforces-436B"`）
- `problem_name` = `probNum`
- `problem_url` = `https://vjudge.net/problem/{oj}-{probNum}`
- `submitted_at` = `time / 1000`（毫秒转秒）
- `language` = `languageCanonical`（如 `CPP`），回退 `language`
- `difficulty` = `None`（VJudge 无难度信息）

### Handle 与 Display Name

- VJudge 用户名即 handle，无额外 display_name 字段；
- `handle` = 用户输入的 VJudge 用户名；
- `display_name` = `None`（界面回退显示 handle）。

## 陷阱备忘

- **分页大小限制**：`length` 超过 100 仍只返回 100 条；
- **recordsFiltered 不可靠**：始终返回 `9999999`，不做总量依据；
- **时间戳为毫秒级**：`time` 需 `/ 1000` 转为 UTC 秒级；
- **聚合平台特性**：题目来自不同 OJ，`problem_key` 需包含 OJ 信息以避免冲突；
- **限流保守**：`min_interval = 2.0` 为保守值。
