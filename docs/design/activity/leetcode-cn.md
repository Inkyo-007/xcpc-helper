# LeetCode CN 适配器（Cookie 授权 + GraphQL Batch Query）

> 状态：已实现（第四期平台，`AuthMode.COOKIE`）。
> 公共契约与同步语义见 [conventions.md](conventions.md)；本文记录 LeetCode CN 专属实现。

## 数据源

| 用途 | 端点 | 方法 | 凭据 |
| --- | --- | --- | --- |
| 已解决题目清单 | `https://leetcode.cn/graphql/` | `userProgressQuestionList` | cookie |
| 提交明细（batch） | `https://leetcode.cn/graphql/` | `submissionList` (batch) | cookie |
| 绑定验证 · 存在性 | `https://leetcode.cn/graphql/` | `userProfilePublicProfile` | 匿名可用 |
| 绑定验证 · 凭据有效性 | `https://leetcode.cn/graphql/` | `userProgressQuestionList` | cookie |

说明：

- `userProgressQuestionList` 返回当前登录用户的已解决题目列表（`SOLVED` 状态），
  含 `frontendId`、`title`、`titleSlug`、`lastSubmittedAt`、`lastResult` 等字段；
  分页参数 `skip` + `limit`，返回 `totalNum` 总量；
- `submissionList(questionSlug, offset, limit)` 返回**单道题目**的全部提交历史
  （含 AC/WA/RE/CE/TLE/MLE 等），时间倒序；支持 `lastKey` 游标分页；
- **Batch Query**：一次 GraphQL 请求可包含多个 `submissionList` 查询（别名区分），
  实测 200 题/batch 稳定（~9 秒），1000 题/batch 可达（~35 秒）；
- `userProfilePublicProfile(userSlug)` 用于验证用户存在性（匿名可用），返回
  `username`、`siteRanking`、`profile`（含 `userSlug`、`realName`、`userAvatar`）等基本信息。

## 同步策略

### 全量同步流程

```
Step 1: userProgressQuestionList(skip=0, limit=500)
        → 获取全部已解决题目的 titleSlug 列表 + totalNum

Step 2: 按 BATCH_SIZE(=200) 分批次调 batch submissionList
        query BatchSubmissions {
          two_sum: submissionList(questionSlug: "two-sum", ...) { ... }
          add_two_numbers: submissionList(questionSlug: "add-two-numbers", ...) { ... }
          ...
        }
        → 每批返回 200 题的提交历史

Step 3: 全部提交归一化为 PlatformSubmission（含 WA/TLE/RE 等非 AC 状态）
```

### 增量同步

- 游标：`Account.last_synced_at`（UTC 秒级时间戳）
- 增量停止：只拉 `lastSubmittedAt > since` 的题目（从 `userProgressQuestionList`
  结果中过滤），再调 `submissionList` 获取这些题目的提交历史；
- 去重：store 层按 `submission_id` 去重吸收。

### 进度上报

- 总量已知：`userProgressQuestionList.totalNum` 即总题数；
- 进度计算：`progress_cb(processed_problems, total_problems)`，按**题目数**而非
  提交数上报（用户感知更直观："已同步 150/2956 题"）；
- 每完成一个 batch 更新一次进度。

## 传输层

LeetCode CN **无 WAF 指纹挑战**，使用共享 `HttpFetcher`（httpx）即可。

请求头要求：
- `Content-Type: application/json`
- `x-csrftoken: <csrftoken>`（cookie 中的 csrftoken 值）
- `Origin: https://leetcode.cn`、`Referer: https://leetcode.cn/`
- `User-Agent`（来自凭据或默认值）

限流：`min_interval = 9.0` 秒（参考 glsync 实测：60 请求/10 分钟窗口）。

Cookie 必需字段：
- `LEETCODE_SESSION`：JWT 会话令牌
- `csrftoken`：CSRF 防护令牌

## 归一化

### Verdict 映射

`submissionList.statusDisplay` → `Verdict`：

| 原始值 | 归一化 |
|--------|--------|
| `Accepted` | `AC` |
| `Wrong Answer` | `WA` |
| `Runtime Error` | `RE` |
| `Compile Error` | `CE` |
| `Time Limit Exceeded` | `TLE` |
| `Memory Limit Exceeded` | `MLE` |
| `Output Limit Exceeded` | `OLE` |
| 其他（如 `Internal Error`） | `UKE` |

### 字段映射

- `submission_id` = `submissionList.submissions[].id`
- `problem_key` = `titleSlug`（URL 标识，如 `"two-sum"`）
- `problem_name` = `userProgressQuestionList.questions[].title`（英文标题）
- `problem_url` = `https://leetcode.cn/problems/{titleSlug}/`
- `submitted_at` = `timestamp`（Unix 秒级）
- `language` = `lang`（原始值如 `"cpp"`、`"python3"`、`"java"`，不做映射）
- `difficulty` = `userProgressQuestionList.questions[].difficulty`（如有）或 `null`

### Handle 与 Display Name

- `handle` = `userSlug`（URL 标识，如 `"yawn_sean"`）
- `display_name` = `profile.realName`（优先）> `username` > `None`
  
  **注意**：`username` 字段不可靠——部分用户未设置自定义用户名时 `username` 等于
  `userSlug`（如 `kJ8bFHX3u7`），而 `realName` 始终为有效的显示名（如 `"Yx_My"`）。

## 一键登录（browser-login）

**已禁用**。LeetCode CN 在新设备/新浏览器环境登录时会强制触发滑块验证
（"按住滑块滑动到最右边"），自动化浏览器（Playwright/Selenium）因以下原因
无法通过：

1. **指纹检测**：`navigator.webdriver = true`、Chrome DevTools Protocol 暴露等
   自动化特征被识别；
2. **行为分析**：滑块拖动轨迹缺乏人类生物特征（加速/减速/微抖动）；
3. **循环失败**：刷新后仍识别为自动化环境，无法跳出验证循环。

**替代方案**：用户在日常浏览器中登录 LeetCode CN 后，通过开发者工具复制
`LEETCODE_SESSION` 与 `csrftoken` 的值，手动粘贴到绑定弹窗的输入框中。

## 绑定弹窗 UI

LeetCode CN 为无 `handleKey` 的 cookie 平台（不像洛谷 `_uid` 兼任 handle）：

- **需要手动输入 UID**：绑定弹窗显示独立的 UID 输入框（左标签"UID"、右输入框，
  样式对齐 cookie 字段），提示"输入 LeetCode CN 账号 UID"；
- **cookie 字段**：`LEETCODE_SESSION`、`csrftoken`；
- **验证按钮**：需 UID + 两个 cookie 字段全部填齐后才可用；
- **获取引导**：悬浮提示引导用户从浏览器开发者工具「应用/Application」面板
  复制 cookie 值。

## 陷阱备忘

- **Batch Query 必须带 cookie**：无 cookie 时 `submissionList` 返回空数组；
- **Batch 大小建议 200**：实测 1000 可达但响应慢（~35 秒），200 题/batch 约 9 秒
  最稳定；
- **请求体大小限制**：>100 KB 可能触发 Nginx/Cloudflare 限制；
- `userProgressQuestionList` 只返回当前登录用户数据：不能用于查其他用户；
- `recentACSubmissions` 只返回最近 ~20 条且只能查自己：不用于全量同步；
- `lastSubmittedAt` 为 ISO 8601 字符串（含时区），需解析为 Unix 秒级；
- `frontendId` 可能为字符串（如 `"面试题 17.16"`），`problem_key` 统一用
  `titleSlug`；
- **显示名优先用 realName**：`username` 可能等于 `userSlug`，不可靠；
- **一键登录不可用**：滑块验证无法通过自动化浏览器，用户必须手动输入 cookie。
