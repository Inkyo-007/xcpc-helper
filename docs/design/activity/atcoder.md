# AtCoder 适配器

> 状态：已实现（第二期平台，匿名可取）。
> 公共契约与同步语义见 [conventions.md](conventions.md)；本文只记录 AT 专属实现。

## 数据源

AtCoder 官方没有公开提交记录 API，明细走社区事实标准的
[kenkoooo API](https://kenkoooo.com/atcoder/resources/about-api)（长期稳定维护的
公益接口）：

- 提交明细：`GET /atcoder-api/v3/user/submissions?user=X&from_second=T`——
  **升序**返回、单页上限 500、`from_second` 含边界；
- 题目目录：`/resources/problems.json`（`id → name`，题名来源）与
  `/resources/problem-models.json`（kenkoooo 模型分，难度来源）——adapter 实例内
  内存缓存 + 24h TTL，不落盘；
- 绑定验证：官方用户主页 `https://atcoder.jp/users/{handle}` 的 **404 判定**。

## 实现要点

**绑定验证为什么不能用现成接口**：实测确认 `history/json` 对不存在用户也返回
200 `[]`，kenkoooo v2 `user_info` 对不存在用户返回 200 全零——都分不出"不存在"。
用户主页 404 是唯一可靠信号；区分 404 与其他 4xx 依赖 net 层的
`HttpStatusError`（携带 `status_code`）。

**升序翻页的坑**（与 CF 倒序回扫完全不同）：

- 增量：`from_second = since`（含边界），游标当秒重复拉取由 store 去重吸收；
- 全量两步策略：先拉 `full_window_days` 窗口；窗口内不足 `full_min_rows` 条时
  退到 `from_second=0` 拉全部历史（不逐段扩展）；
- **页间去重与防停滞**：`from_second` 含边界 ⇒ 翻页时下一页与上页末条同秒重叠，
  adapter 内按 `id` 集合去重；单页无新 id 即停（否则同秒 ≥500 条会死循环）；
  外加 `MAX_PAGES` 护栏；
- 流式批次断点为 `{"from_second": 续拉位置, "fetched": 累计, "from_zero": 是否已
  进入全历史阶段}`。

**失败语义分级**：`problems.json` 失败 → 抛 `PlatformError`（题名是核心展示字段，
宁可本次同步降级重试不落库坏数据）；`problem-models.json` 失败或目录缺题 →
`difficulty=None` 继续（非关键字段）；目录缺题时 `problem_name` 兜底 `problem_id`。

**归一化**：

- verdict：`AC/WA/TLE/MLE/RE/CE/OLE` 直映射；`WJ/WR/JUDGING` → `JG`（评测中）；
  `IE/QLE` 与未知值 → `UKE`；
- URL：`https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}`，
  `problem_key = problem_id`（如 `abc001_a`）；
- 必填字段 `id` 与 `epoch_second` 缺失即校验失败（防增量静默漏数据，同 CF 的
  `creationTimeSeconds` 教训）。

**限流**：kenkoooo 要求 ≥ 1 秒/请求（公益接口，请尊重），`min_interval = 1.0`；
verify 的 atcoder.jp 请求共用同一 platform 限流桶，保守串行。

## 陷阱备忘

- **`from_second` 含边界且只升序翻页**：不去做重 + 停滞检测就是死循环；
- **用户存在性只能看官方主页 404**，kenkoooo 侧所有接口都分不出不存在用户；
- 题目目录两个文件的失败语义不同（题名抛错 / 难度留空），不要混淆；
- kenkoooo 响应是裸 JSON 无信封——网关异常可能返回 HTML 错误页，adapter 的
  `_get_json` 包装把非 JSON 收敛为 `PlatformError`，否则 sync 的降级路径接不住。
