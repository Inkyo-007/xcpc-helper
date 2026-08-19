# Codeforces 适配器

> 状态：已实现（第一期平台，新平台的参考范本）。
> 公共契约与同步语义见 [conventions.md](conventions.md)；本文只记录 CF 专属实现。

## 数据源

CF 有官方公开 API（[apiHelp](https://codeforces.com/apiHelp)），匿名即可取数，
是三平台里最省心的：

- 提交明细：`GET /api/user.status?handle=X&from=N&count=1000`，分页倒序（最新在前）；
- 绑定验证：`GET /api/user.info?handles=X`，成功返回用户信息（含头像）即存在。

## 实现要点

**信封处理**。CF 返回 `{"status": "OK", "result": [...]}` 信封；限流时以 200 返回
`FAILED + Call limit exceeded`，靠 net 层的 `should_retry` 业务信封钩子重试，
其余 FAILED 直接抛 `PlatformError`。

**响应模型**（`api_models.py`）：外部 JSON 第一时间 `model_validate` 为
`CfEnvelope[T]`（泛型信封）+ 类型化行。可选字段给默认值容错，但必填字段
（`id`、`creationTimeSeconds`）缺失即校验失败——`creationTimeSeconds` 若给默认值 0，
增量拉取会把它当作"旧于游标"提前终止，静默吞掉后续新提交。

**归一化**（`normalize.py` 纯函数）：

- verdict：`OK→AC`、`WRONG_ANSWER→WA` 等直映射；`SUBMITTED/TESTING` → `JG`
  （评测中）；未列出的（CHALLENGED/SKIPPED/PARTIAL 等）一律归 `UKE`；
- 题目外链按 contestId 位数区分主题库与 gym：四位数 → `/contest/`，
  六位数 → `/gym/`；缺信息兜底平台主页；
- `problem_key = contestId + index`（如 `2245F`），缺失时退化为题名。

**分页**：单页 1000 条，200 页护栏（20 万条）；增量 `ts < since` 停止；
全量拉到覆盖窗口为止、窗口内不足 `full_min_rows` 条时继续拉满。
流式批次断点为 `{"from": 下一页偏移, "fetched": 累计条数}`。

**限流**：官方建议 ≥ 2 秒/请求，`min_interval = 2.0`。CF 无总量字段，
不上报同步进度（前端显示不定态环）。

## 陷阱备忘

- 限流信封是 200 + FAILED 形态，不看 HTTP 状态码——没有 `should_retry`
  钩子会把限流当成功；
- gym 与主题库 URL 形态不同，混用会 404；
- 首次同步若只拉最新一页会漏历史——全量窗口 + min_rows 双条件缺一不可。
