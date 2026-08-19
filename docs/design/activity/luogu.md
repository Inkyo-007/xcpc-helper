# 洛谷适配器（cookie 授权 + 反爬对抗 + UNAC 精化）

> 状态：已实现（第三期平台，首个 `AuthMode.COOKIE`；结论全部来自真实 cookie 实测）。
> 公共契约与同步语义见 [conventions.md](conventions.md)；本文记录洛谷专属实现。

## 数据源

| 用途 | 端点 | 凭据 |
| --- | --- | --- |
| 提交明细 | `GET /record/list?user=<uid>&page=N&_contentOnly=1` | cookie |
| 单条精化 | `GET /record/{id}?_contentOnly=1` | cookie |
| 绑定验证 · 存在性 | `GET /api/user/search?keyword=X` | **匿名可用** |
| 绑定验证 · 凭据有效性 | 携凭据试拉 record/list 第 1 页 | cookie |

说明：

- `_contentOnly=1` 让页面接口返回纯 JSON 信封 `{code, currentData}`；不带则返回
  SPA 页 + `_feInjection` 内嵌同构数据。record/list 时间**倒序**、perPage=20，
  倒序回扫（增量 `ts < since` 停止，record `id` 去重），流式断点为
  `{"page": 页码, "fetched": 累计}`；
- 难度直接内嵌在 record 的 `problem.difficulty`（0-7 档），无需额外请求；
- search 是模糊匹配，verify 取精确命中（uid 相等或用户名不区分大小写相等）；
  归一后 `handle = uid`（API 主键稳定）、`display_name = 用户名`（界面展示）。

## 传输层：WAF 指纹对抗（关键）

洛谷 WAF 按 TLS/HTTP 指纹区分客户端——实测同 IP 同 cookie 下 curl 通过、
httpx 必被 Spilopelia 挑战拦截。所以洛谷 adapter **不用共享 HttpFetcher**，
改用 `curl_cffi`（`impersonate="chrome"` 浏览器指纹伪装）自带会话；注册表构造
签名不变（入参 fetcher 忽略），会话按次创建（cookie 罐吸收挑战与轮换），
限流记账留在实例上跨次生效。

反爬挑战的三种形态与处置：

- `302 + Set-Cookie: C3VK`（`Ws-Action: cc`）→ 会话罐跟随自动通过；
- Spilopelia **JS 挑战页**（请求过密时升级出现）→ 非浏览器客户端无法执行 JS，
  带凭据时按 `AuthExpiredError` 引导重新授权（重导 cookie 是两种情况的共同
  正确动作），匿名判 `PlatformError`；低频请求（`min_interval = 5.0`）可长期避开；
- 信封 `code == 401/403` 且消息含「请先登录/用户不可见」→ `AuthExpiredError`；
  `403 +「请求频繁」`（限流，非过期）→ 应用层专项重试（4 次、30s 起步指数退避；
  clist 生产值 8 次 + 50s 附加延迟，本地酌减）；其余 `code != 200` → `PlatformError`。

会话轮换：服务端会 302 刷新 `__client_id`（轮换不失效，旧值仍可用），会话罐
吸收即可；**不回写 secrets.json**（实测旧凭据长期有效）。

## 归一化

- `submission_id` = record `id`；`problem_key` = `pid`；`problem_name` = `title`；
  `problem_url = https://www.luogu.com.cn/problem/{pid}`，`contest` 非空时拼
  `?contestId={cid}`（clist 格式）；比赛内提交计入统计（对齐 CF gym）；
- **verdict 映射**（数字 status 码，以官方 `/_lfe/config/auth` 常量表实测校准）：
  `12→AC`、`6→WA`、`14→UNAC`、`2→CE`、`7→RE`、`5→TLE`、`4→MLE`、
  `3→OLE`、`0/1→JG`、`11/21/22/23`（UKE/Hack 系列）与未知码 → `UKE`。
  **注意 4/5 与直觉相反（4 是 MLE、5 是 TLE）**；
- **language 数字码**：同一常量表的 `CodeLanguage` 内置映射（27=C++20、
  7=Python 3 等），未知码兜底空串；
- **进度上报**：全量时首页信封 `records.count` 即全站总条数，
  `progress_cb(fetched, total)` 逐页上报真实百分比；增量总量不可知，不上报。

**为什么 14 归一为 UNAC**：洛谷记录列表口径只有 AC/CE/Unaccepted（官方常量
`filterable` 佐证：仅 2/12/14 可筛选），WA/TLE/MLE/RE 细分只存在于记录详情的
测试点信息里。为不误导（把 TLE 显示成 WA），14 归一为 UNAC；存量历史 WA
（旧口径落盘）不做迁移，重新同步即被新口径覆盖。细分可经精细化同步还原（见下）。

## 一键登录（browser-login）

`adapters/luogu/login.py` 用 Playwright（可选依赖组 `browser-login`）拉起**系统
Chrome/Edge** 独立窗口（临时 profile，`channel="chrome"` 兜底 `msedge`，不下载
浏览器二进制），用户自行完成登录——图形验证码/**两步验证码**/二级密码等由用户
自然处理（二级密码只保护账号安全类操作，登录态读记录不触发）。

登录完成判定为**双重确认**：cookie 罐出现 `_uid`/`__client_id` 只是候选信号
（匿名与两步验证中间态也携带 `__client_id`），再经鉴权探针（浏览器上下文请求
`record/list?_contentOnly=1` 返回 `code==200` 的 JSON，节流到至多 3s 一次）
确认完整登录态才抓取 cookie 与 UA 返回。用户关窗 → canceled，超时 3 分钟 →
timeout。凭据由 service 暂存（内存，10 分钟 TTL），bind 时消费——**凭据不经
前端**。Playwright 未安装时 `/platforms` 的 `browserLogin=false`，前端隐藏一键
登录按钮，仅保留方式二手动输入。

## 精细化同步（UNAC refine）

把存量 UNAC 逐条拉详情改写为细分结果——只影响提交列表徽章的细分，统计口径
（AC vs 非 AC）不受影响。

**判定规则**：

- 详情 `record/:id` → 全部 subtask 的全部测试点中，**按严重度取最重**
  （对话确认）：`RE > TLE > MLE > OLE > WA`；
- 保守规则与 UKE 层级：JG 测试点不参选（评测中/未定态）；无可参选测试点但
  存在 UKE 测点 → 判 **UKE**（记录确实遭遇评测方故障；实测确认存在纯 UKE /
  UKE+AC 混合 / AC 多数+个别 UKE 的形态）；全 AC 或无测试点信息 → 保持 UNAC
  不乱猜；
- CE 不经精化（列表口径本就区分）；
- **终止保证（防重试循环）**：`Submission.refine_attempted` 标记——详情拉取
  成功但无法判定时打标，不再重试；待办口径为
  `verdict == UNAC and not refine_attempted`（曾出现仅 UKE 测点的记录被保守
  规则无限重试的事故，勿回退）。

**引擎**（`modules/activity/refine.py`，service 持有）：

- 启动时快照存量 UNAC（按 `submitted_at` **升序**，从旧往新），`total` 固定为
  本轮快照条数（精化途中新增的 UNAC 留下轮，进度不倒退）；
- **剩余 UNAC 即待办**：中止/中断后无需额外游标，下次启动重扫自动续传；
  中止为**状态即时翻转**（stop 立即置 stopped，前端即时反馈；在飞的一条最多
  多完成一次写入，无害；陈旧任务经 current_task 防护不覆写新轮次）；
  stopped/idle 态的 `total` 按存量剩余实时计算（快照分母中止后即过时）；
- **与普通同步协同**：每条记录处理前获取该账号的同步锁（SyncEngine 单账号
  `asyncio.Lock`）——普通同步全程持锁，精化自然暂停，结束后自动继续
  （移交延迟 ≤ 一条记录）；
- 与同步共用 adapter 的 5s 限流节奏（`_get_json` 实例级 pacing），不加速
  WAF 风险；单条详情复用同一传输层与信封判定；
- store 的 `update_verdicts`（按 submission_id 就地改写 verdict，原子写 +
  同锁串行）是"磁盘优先、合并不覆盖旧行"规则的**唯一受控例外**；
- `Account.refine_auto`（默认关）：普通同步完成后自动启动精化（增量带来的
  几条新 UNAC 秒级完成）；「已完成」按存量待办清零计算，不持久化状态。

**前端**：平台视图工具条「同步」按钮右侧的「精细化同步」按钮（能力驱动：平台
声明 REFINE_VERDICT 且已绑定时挂载），精化进行中按钮右上角显示黄色圆点角标
（与页签同步角标同视觉语言，store 全局轮询精化状态驱动）；弹窗三态——未开始
（功能说明 + 按存量×5s 的耗时预估 + 确认）/ 进行中（百分比 + 中止）/ 已完成
（「随同步自动精化」开关）。

## 陷阱备忘

- **传输层必须 curl_cffi**：换回共享 HttpFetcher 会被 WAF 指纹挑战全灭；
- **状态码 4=MLE / 5=TLE（与直觉相反）**：映射表以官方常量为准，勿凭记忆改写；
- **handle = uid，display_name 分离**：用户名可改、uid 稳定；界面显示一律
  `displayName ?? handle`；
- **匿名/两步验证中间态也携带 `__client_id`**：一键登录的完成判定必须
  cookie 出现 + 鉴权探针双重确认，只看 cookie 会在两步验证码账号上提前关窗
  抓走半成品会话；
- **一键登录成功不回填 handle 输入框**：绑定弹窗的 watcher 会把程序化赋值
  误判为用户改动而清空回执（曾致"登录成功却无反馈、无法绑定"）；
- **精化是 store 合并规则的唯一受控例外**：其余路径维持"磁盘优先、合并不
  覆盖旧行"；
- **精化与普通同步共用账号锁**：绕开锁会导致并发写与限流失控。
