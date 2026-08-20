# 牛客竞赛（NowCoder）适配器

> 状态：已实现。公共契约与同步语义见 [conventions.md](conventions.md)；本文只记录牛客专属实现。

## 数据源

牛客无公开提交明细 API，经 ojhunt-lite 源码交叉验证与实测确认，`practice-coding` 分页 HTML（服务端渲染）为唯一切实可行的数据源：

- **提交明细**：`GET /acm/contest/profile/{uid}/practice-coding?pageSize=50&statusTypeFilter=-1&languageCategoryFilter=-1&orderType=DESC&page=N`——倒序分页、perPage=50（经实测，pageSize=200 时第 3 页起返回重复数据，50 稳定可靠）；
- **绑定验证**：`GET /acm/contest/rating-history?uid={uid}`——对合法 UID 返回 `code=0,data=[...]`，对非法 UID 返回 `code=0,data=[]`，是唯一轻量可靠的存在性判定方式。

## 实现要点

**HTML 解析**。响应为服务端渲染 HTML 表格，每行 9 列：提交 ID、题目、状态、得分、运行时间、内存、代码长度、语言、提交时间。Adapter 用正则提取，非 HTML 解析库（减少依赖）。

**分页停止条件**：
- 页数据条数 `< pageSize` → 最后一页；
- 或达到 `MAX_PAGES = 100` 安全护栏。

**增量同步**：数据按时间倒序（最新在前），增量停止条件 `timestamp_utc_seconds < since`，游标当秒提交重复拉取由 store 按 `submission_id` 去重吸收。

**时区处理**：原始时间戳为中国时区（UTC+8），Adapter 内转换为 UTC 秒级：`datetime.strptime(..., '%Y-%m-%d %H:%M:%S').replace(tzinfo=china_tz).timestamp()`。

**Verdict 映射**（经对 330 条真实提交全面扫描）：

| 原始文本 | CSS 类 | 归一化 |
|----------|--------|--------|
| 答案正确 | `font-green` | AC |
| 答案错误 | `font-red` | WA |
| 运行超时 | 无 | TLE |
| 段错误 | `font-red` | RE |
| 内存超限 | 无 | MLE |
| 编译错误 | `font-red` | CE |
| 执行出错 | 无 | RE |
| 浮点错误 | `font-red` | RE |

> 牛客无 `UNAC` 概念，所有非 AC 均有明确细分。`执行出错`为通用运行时错误，粒度粗于 `段错误`/`浮点错误`，统一归 RE。

**题目外链**：`https://ac.nowcoder.com/acm/problem/{problem_id}`，problem_id 从表格第 2 列提取。

**难度**：牛客页面无难度字段，`difficulty` 统一置 `None`。

**限流**：`min_interval = 1.0`，使用共享 `HttpFetcher`（无 WAF 指纹挑战）。

## 陷阱备忘

- **pageSize=200 有服务器 bug**：第 3 页起返回与第 2 页相同数据，必须用 pageSize=50；
- **时间戳为中国时区**：直接当 UTC 会差 8 小时，必须显式转换；
- **rating-history 验证不返回用户名**：`display_name` 只能留空；
- **HTML 结构变更风险**：牛客为商业平台，页面结构可能调整，测试 fixture 可快速发现。
