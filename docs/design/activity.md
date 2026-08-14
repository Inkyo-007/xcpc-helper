# 训练统计聚合（activity）设计

> 状态：已实现（第一期 Codeforces + 第二期 AtCoder）；第三期洛古：进行中
> （设计已定稿：提交统计 + 绑定验证 + cookie 凭据框架 + 多用户组全链路）。
> 本文档与实际实现同步，是后续多平台适配（LeetCode / 牛客 / QOJ 等）
> 与新增功能（rating 折线、比赛信息）的规范参考；改设计必须先改本文档再改代码。
> 需求背景见 [../cache/requirement.md](../cache/requirement.md)，
> 平台接口调研见 [../cache/platform-api-research.md](../cache/platform-api-research.md)。

## 1. 背景与目标

选手的训练数据散落在 Codeforces、AtCoder、洛谷等多个平台，难以直观观察与统计。
本功能在用户绑定各平台账号后，自动拉取、整合训练数据，提供默认汇总页与单平台页，
展示解题/提交统计、activity 热力图、统计卡片与近期提交；rating 折线与比赛信息为
后续增量（契约已预留）。需求优先级归属见 [../requirements.md](../requirements.md)「做题统计」。

## 2. 总体形态

### 2.1 关键决策

- **所有对外请求经由本地后端代理**：前端直连各平台会被 CORS 拦截，且凭据（cookie）
  不能暴露给前端；FastAPI 后端天然承担采集代理角色。
- **adapter 可插拔、失败可降级**：各平台接口稳定性差异大（官方 API / 第三方 API /
  非官方接口 / cookie 授权），单平台失败只降级为该账号的诊断信息，不拖垮整个面板
  （遵循 [conventions.md](conventions.md)「诊断不阻断」）。
- **手动同步为主**：本地应用不常驻运行。提供"立即同步"按钮（汇总视图同步全部平台，
  点击前确认；平台视图只同步该平台）+ 每账号新鲜度/上次同步时间/错误状态展示；
  同步在后台异步执行，前端轮询状态接口。
- **增量同步**：每个 (用户组, 平台, 账号) 维护同步游标（UTC 秒级数据水位），
  **游标当秒的提交重复拉取、按 submission_id 去重合并**（停止条件 `ts < since`，
  避免同秒多提交被永久漏掉——见 §3.3）。
- **时区**：远端时间戳均为 UTC 秒级，按后端本地时区切"天"聚合（本地部署，
  后端时区即用户时区）。
- **用户组 = data/user/<user_id>/ 目录**：多用户组真实隔离（账号绑定、训练数据、
  信息卡），组名即目录名（支持中文），见 §3.1 与 §4.1。
- **信息卡与组名分离**：信息卡（ID / 签名 / 头像）存组内 `profile.json`，编辑互不影响。

### 2.2 平台差异适配模式：公共内核 + 平台扩展

平台知识只允许集中在两处：**后端 adapter 目录**、**前端平台组件注册表**；
router / service / modules 主干保持平台无关（不出现 `if platform == "luogu"` 分支）。

- adapter 声明 `capabilities`（提供哪些数据区块、是否需要凭据）与 `auth`；
- service / sync 按 `capabilities` 决定调用哪些能力方法，缺能力的字段省略并记诊断；
- router 用同一组端点服务所有平台，绑定/凭据差异由统一 `credentials` 载荷吸收；
- 前端按后端 `/platforms` 返回的元数据（capabilities/auth）条件渲染，平台页签、
  绑定弹窗平台下拉均由后端驱动，前端不硬编码平台清单。

### 2.3 平台优先级（分期）

1. Codeforces（官方 API，匿名可取，风险最低）——**已实现**
2. AtCoder（kenkoooo API + 官方用户主页 404 验证，匿名可取）——**已实现**
3. 洛谷（cookie 授权框架首个实例 + 反爬对抗，QOJ 等后续平台复用同一套）——**进行中**
4. LeetCode CN + 牛客（GraphQL 路径已探明 / rating 匿名接口）
5. 长尾平台（评估 ojhunt 依赖或手动导入）

## 3. 数据模型与存储

### 3.1 存储位置

统一存储在 `backend/data/user/<userid>/`，**每个用户组一个目录（目录名即组名，
支持中文）**；服务层维护当前用户组（内存态，默认 `default` 惰性初始化），
其余 API 一律作用于当前组。

```
backend/data/user/
├─ example/                     # 提交入 git 的格式样例，兼作后端测试 fixture
│  ├─ profile.json
│  └─ activity/submissions/codeforces_example.jsonl
└─ <userid>/                    # 用户组（组名 = 目录名，可新建/重命名/删除）
   ├─ profile.json              # 信息卡（ID/签名/头像）+ 账号绑定（不入库）
   ├─ activity/
   │  ├─ submissions/<platform>_<handle>.jsonl   # 每 (平台,账号) 一个文件
   │  └─ rating/<platform>_<handle>.json
   └─ secrets.json              # cookie 等凭据（gitignore，仅存本机；第三期起实现）
```

`.gitignore` 已落实：

```
backend/data/user/*/secrets.json
backend/data/user/**/.tmp-*
backend/data/user/*/   # 用户组运行数据不入库（每个组一个目录，随时变更）；
                       # 格式样例见 example/，随样例文件入 git
```

`profile.json` 结构（`modules/activity/models.py::Profile`）：

```json
{
  "id": "显示ID",            // 信息栏 ID，独立于组名（新建时初始为目录名）
  "signature": "签名",
  "avatar": "data:image/jpeg;base64,...",   // 头像 data URL 或 null
  "accounts": [
    { "platform": "codeforces", "handle": "tourist", "last_synced_at": 1755... },
    { "platform": "luogu", "handle": "1085065", "display_name": "用户名", ... }
  ]
}
```

`secrets.json` 结构（`modules/activity/models.py::Secrets`，第三期起实现）：

```json
{ "platforms": { "luogu": { "1085065": { "cookies": {"_uid": "...", "__client_id": "..."},
                                          "headers": {} } } } }
```

- 账号元数据（profile.json）与凭据（secrets.json）**分离存储**：前者可入档，
  后者 gitignore 永不入 git；解绑/换绑/删除用户组时同步清理（store 层保证）；
- `handle` 为平台内 **API 主键**（洛古为 uid 数字，用户名可改而 uid 稳定），
  `display_name` 为展示名（洛古用户名），界面一律显示 `display_name ?? handle`；
- sync 引擎按 (platform, handle) 从 secrets.json 加载凭据注入 adapter
  （匿名平台为 None）。

- 头像为前端裁剪后的 **512×512 JPEG data URL**（信息卡容器约 268px，2 倍超采样防糊；
  上限 500k 字符）。data URL 内嵌数据，**不依赖原图文件路径**，目录迁移/重命名不受影响。
- 信息栏 ID 与组名（目录名）分离：编辑 ID 只改 `profile.json`，重命名组不改变 ID。

### 3.2 统一提交模型

各平台提交归一化为 `adapters.base.PlatformSubmission`（不含 platform/handle，
由 sync 层补字段转 `modules/activity/models.py::Submission` 落盘）：

```
PlatformSubmission {
  submission_id   # 平台内唯一提交 id（去重依据）
  problem_key     # 平台内题目标识（CF "2245F" / AT "abc001_a" / LG "P1001"）
  problem_name
  problem_url     # 平台内题目外链（CF 按 contestId 位数区分：四位数主题库 /contest/，六位数 gym /gym/）
  difficulty      # 原始难度值，不做跨平台归一（int | str：CF 分数 / LC 档位 / 洛谷难度）
  verdict         # AC / WA / CE / RE / TLE / MLE / OLE / UKE / JG（评测中，CF 的 SUBMITTED / TESTING）
  submitted_at    # UTC 秒级时间戳
  language
}
```

### 3.3 游标与去重

- 每账号游标 = `profile.json` 中 `Account.last_synced_at`（数据水位，UTC 秒，null = 从未同步）；
- **增量停止条件 `ts < since`**：游标当秒的提交会重复拉取，由 store 按
  `submission_id` 去重吸收（去重是硬保证，重复拉无代价）——避免同秒多提交被漏掉；
- 游标推进取最大值防倒退；无新提交时保持原游标（空账号不落 0 游标）；
- 最近成功同步的结束时间展示在 `SyncStatus.last_synced_at`（内存态，重启后以游标近似）。

### 3.4 写入约定

沿用 [conventions.md](conventions.md)：写操作经 store 原子写入（临时文件 +
`os.replace`），同资源并发写用 `RLock` 串行化；JSONL 读入合并去重后整体原子替换；
单行损坏只跳过不阻断（返回损坏行数供日志）。用户组目录的创建/重命名/删除：
新建建目录 + 初始档案，重命名 `os.rename`（数据随目录迁移），删除 `shutil.rmtree`
（物理删除，前端明确提示不可找回）。

## 4. 页面与交互

### 4.1 信息架构与用户组

侧边栏「训练统计」组（`NavGroup.icon` 扩 `'chart'`），子页「数据总览」
`/activity/overview`：页内顶部用分段切换器切视图（汇总 / 各支持平台，
平台页签来自后端 `/platforms`，与是否绑定无关）。

**用户组**：组名 = `data/user/<user_id>/` 目录名（支持中文）。工具条右侧用户组
下拉菜单显示当前组名，菜单顶部「新建用户组」（后端建目录并自动切换），下方组列表
点击切换；重命名与删除在「编辑用户组」弹窗：重命名 = 目录改名（数据归属不变），
删除 = 物理删除该组全部数据（账号、训练数据、信息卡，不可找回），至少保留一个组，
删除当前组自动回退到剩余首个组。**信息卡（ID/签名/头像）与组名分离**：编辑信息卡
ID 不改变组名，重命名组不改变信息卡。

### 4.2 页面区块

1. **工具条**（通栏）：左侧平台分段切换器；右侧同步区——上次同步时间、
   「立即同步」（汇总视图点击先确认"同步全部平台"，平台视图只同步该平台）、
   「编辑用户组」（仅汇总视图）与账号入口（汇总视图为用户组下拉；平台视图为该平台
   绑定账号按钮，未绑定显示虚线「未绑定账号」）。
2. **左栏 · 用户信息卡**：头像（本地上传，前端裁剪 512px 方形 data URL，存后端）、
   主标签 ID、副标签签名；就地编辑，防抖提交后端。
3. **左栏 · 近期提交**：跨平台合并的最后 200 条提交（后端取历史倒序前 200，
   **不按时间窗口过滤**，近期没做题的账号也能看到最近记录），新在上；每行 verdict
   徽章 + 题号题名（点击跳平台外链）+ 平台 + 时间。每页固定 10 条分页（页码同步网址，
   见 §4.6）；点击热力图格子切当日明细（同 10 条分页，页码状态独立），再次点击取消。
4. **右栏 · 统计卡片行**：总解题数 / 总提交数 / 今日解题 / 连续活跃天数，count-up。
5. **右栏 · activity 热力图**：GitHub 式一年图（53 周 × 7 天，周日起始），
   hover 上浮 + tooltip，点击选中联动左栏明细。
6. **右栏 · 柱状图行**：近 7 天通过（日粒度）/ 近 12 个月通过（月粒度），ECharts。

verdict 徽章配色固定：AC 绿、WA 红、CE 黄、RE 紫、**JG 浅蓝**，TLE/MLE/OLE/UKE 深蓝。

### 4.3 统计口径

- 解题数 = 当天 AC 的**不同题目数**（去重键含 platform，汇总不做跨平台去重）；
- 连续天数按"当天有 AC"计；今天尚无 AC 时不算断签，统计到昨天为止；
- 热力图固定近 370 天；streak 由后端计算（可能超过窗口）；
- 柱状图由前端从日序列派生（`model/bars.ts`）。

### 4.4 空状态与绑定流程

- 未绑定任何账号：整页引导空状态「绑定第一个账号」；
- 绑定弹窗：平台下拉（后端 capabilities 驱动）→ handle 输入 →「验证」（后端
  `POST /accounts/verify`，成功回执平台内基本信息）→「确认绑定」→ 自动触发首次同步；
- 换绑：每平台每用户组只保留一个账号，绑定新账号替换旧账号并删除其本地数据；
- 解绑：确认后删除该账号本地数据（不可找回）；
- 凭据平台（洛古，第三期落地）：绑定弹窗提供「一键登录」（后端 Playwright 拉起
  系统浏览器登录窗口，见 §5.6）与「手动粘贴」两条凭据录入路径；
  `verify`/同步携带 `credentials`；绑定当下即携凭据试拉验证有效性
  （`AuthExpiredError` 在 verify 路径转 400，不放行死凭据）；
  同步中 `AuthExpiredError` → `syncErrorCode: "auth_expired"` → 账号按钮警示态
  「凭据过期」→ 点击走换绑路径重新授权 → 自动触发一次增量同步。
  过期不影响本地已有数据，游标不动，重授权后从原游标继续增量。

### 4.5 图表主题桥接

配色在 JS 侧统一生成：`model/echarts-theme.ts` 经 `getComputedStyle` 读取
`--hue` / `--text` / `--surface-2` 等 CSS 变量产出配色对象；组件用
`MutationObserver` 监听 `documentElement` 的 `data-theme` 与 `style`（`--hue`）
变化，ECharts 图触发 `setOption` 刷新，热力图格子直接以内联背景色刷新。
不反向依赖 App 的 `useTheme` 实例。

### 4.6 网址状态同步

平台筛选、热力图选中日期与列表页码写入网址 query
（`?platform=codeforces&date=2026-08-13&page=2`）：`all`、无选中日期与第 1 页
为缺省值不出现；`page` 始终表示当前列表（近期提交或当日明细）的页码。切换平台
重置日期与页码为缺省；选中/切换日期时当日明细页码回到第 1 页；翻页保留筛选与
选中日期；非法日期回退为未选中。刷新、前进/后退与复制链接均能恢复同一视图。

## 5. 平台适配层（adapters/）

> 本节是新增平台的核心规范。依赖方向严格单向：
> `routers → services → modules(activity) → adapters`，**adapters 不反向依赖任何功能域**；
> adapter 只允许被 `modules/activity/sync.py` 与 `services/activity/service.py` 触碰。

### 5.1 目录结构

```
backend/src/adapters/
├─ base.py                    # 统一契约：共享模型、枚举、异常、PlatformAdapter、显式注册表
├─ net.py                     # 外呼公共层：request/get_json/post_json、限流、退避、凭据合并
└─ <platform>/                # 每平台一个目录（简单平台单文件承载）
   ├─ __init__.py             # Adapter 类
   ├─ api_models.py           # 该平台 API 响应模型（外部数据第一时间转 Pydantic）
   └─ normalize.py            # 归一化纯函数（verdict 映射、URL/标识生成，便于单测）
```

注册表在 `adapters/__init__.py` 集中手写（静态可查，不用自动发现）：

```python
REGISTRY: dict[str, type[PlatformAdapter]] = {
    CodeforcesAdapter.platform_id: CodeforcesAdapter,
}
```

新增平台的后端成本 = 一个 adapter 目录 + 注册一行，主干零改动。

### 5.2 统一契约（base.py）

**枚举**：

```python
class Verdict(str, Enum):     # AC/WA/CE/RE/TLE/MLE/OLE/UKE/JG（平台无关，adapter 归一化）
class Capability(str, Enum):  # SUBMISSIONS / USER_INFO / RATING / CONTESTS
class AuthMode(str, Enum):    # NONE（匿名）/ COOKIE（cookie 授权）
```

**共享模型**（adapter 产出，由 sync 转领域模型）：

```python
PlatformSubmission   # 提交记录（§3.2）
UserInfo             # 绑定验证回执 { handle, avatar? }
RatingPoint          # rating 历史单点 { time, rating, contest_name }（后续增量）
ContestInfo          # 比赛信息 { contest_id, name, start_time, duration_seconds, url? }
Credentials          # 凭据 { cookies: dict, headers: dict }
```

**异常体系**：

```python
AdapterError                    # 基类
├─ UserNotFoundError            # 绑定验证用户不存在 → service 转 400
├─ PlatformError                # 平台故障（网络/限流/格式）→ sync 降级为该账号诊断
├─ AuthExpiredError             # 凭据过期 → sync 标记 error_code="auth_expired"
└─ CapabilityNotSupportedError  # 调用未声明的能力（契约违约，正常路径不触发）
```

**PlatformAdapter 能力方法**（均为**普通方法**，基类默认抛
`CapabilityNotSupportedError`；能力残缺的平台只实现 capabilities 声明的方法，
不被迫写空壳）：

| 方法 | 说明 | 能力 |
| --- | --- | --- |
| `verify(handle, credentials=None) -> UserInfo` | 绑定验证 | USER_INFO |
| `fetch_submissions(handle, *, since, credentials=None, full_window_days, full_min_rows) -> list[PlatformSubmission]` | 提交明细；`since` 为 UTC 秒游标（None 全量），增量语义平台自解释；`full_window_days`/`full_min_rows` 为上层同步策略（见 §6.3），adapter 不内置 | SUBMISSIONS |
| `fetch_rating_history(handle, credentials=None) -> list[RatingPoint]` | rating 历史（后续增量） | RATING |
| `fetch_contests() -> list[ContestInfo]` | 比赛信息（平台级，无 handle，未来 contest 功能消费） | CONTESTS |

### 5.3 外呼公共层（net.py）

所有 adapter 共用一个 `HttpFetcher`（应用级单例，随 service 生命周期，测试注入
`httpx.MockTransport`）。`request()` 承载限流/退避/信封重试核心，`get_json` /
`post_json`（GraphQL 平台用 POST）为 JSON 语法糖：

- **按平台限流**：per-platform `asyncio.Lock` + 上次请求时刻记账，请求前补齐
  `min_interval`（各 adapter 声明）；
- **重试**：传输异常 / 429 / 5xx 重试，4xx 抛 `HttpStatusError`（`PlatformError`
  子类，携带 `status_code`，供 adapter 区分 404 用户不存在等语义）；`should_retry(data)`
  钩子供 adapter 声明"业务信封重试"（CF 以 200 返回的 FAILED 信封）；响应体非 JSON 不判定；
- **退避公式**：`backoff = max(base_backoff, min_interval) × 2^n`——首次重试等满一个
  完整限流窗口，避免重试仍落在窗口内（CF 2s 间隔下固定 0.5s 起步会再撞限流）；
- **单次覆盖**：`max_retries` / `base_backoff` 可单次调用覆盖全局默认（平台专项重试，
  如洛谷 403 长延迟重试落地时按需传入）；
- **凭据统一应用**：`Credentials.cookies` 转 Cookie 头、`headers` 与调用方显式请求头
  合并（调用方优先）——adapter 不自行拼 Cookie 头；
- **传输层例外（洛古）**：洛古 WAF 按 TLS/HTTP 指纹区分客户端（实测：同 IP 同
  cookie，curl 通过、httpx 必被挑战），故洛古 adapter 不用共享 `HttpFetcher`，
  改用 `curl_cffi`（浏览器 TLS 指纹伪装）自带会话，限流/退避模式镜像本层实现，
  详见 §5.6。

### 5.4 Codeforces 适配器（范本解剖）

`adapters/codeforces/` 作为新平台的参考范本：

- **api_models.py**：`CfEnvelope[T]`（泛型信封：status/comment + 类型化 result），
  `CfUserInfo` / `CfSubmissionRow` / `CfProblem`。外部 JSON 第一时间 `model_validate`；
  可选字段默认值容错，**必填字段（id、creationTimeSeconds）缺失即校验失败**暴露
  平台格式变化（creationTimeSeconds 若给默认 0 会静默吞掉增量新提交）。
- **normalize.py**：纯函数 `map_verdict`（未列出的 verdict 归 UKE，SUBMITTED/TESTING
  归 JG）、`problem_url`（contestId 位数区分 /contest/ 与 /gym/）、`problem_key`。
- **fetch_submissions**：`user.status` 分页（单页 1000，最多 200 页护栏）；增量
  `ts < since` 停止；全量拉到覆盖 `full_window_days` 窗口为止、窗口内不足
  `full_min_rows` 条时继续拉满；信封 `_check_envelope` / `_should_retry_envelope`
  （Call limit exceeded 走重试，其余 FAILED 抛 `PlatformError`）。

### 5.5 AtCoder 适配器（kenkoooo API，第二期）

`adapters/atcoder/`，数据源与 CF 形态差异较大，要点：

- **数据源**（均为匿名可取）：
  - 提交明细：kenkoooo `GET /atcoder-api/v3/user/submissions?user=X&from_second=T`
    （社区事实标准，**升序**返回、单页上限 500、`from_second` 含边界）；
  - 题目目录：kenkoooo `/resources/problems.json`（`id → name`，`problem_name` 来源）
    与 `/resources/problem-models.json`（kenkoooo 模型分，`difficulty` 来源）；
    adapter 实例内**内存缓存 + 24h TTL，不落盘**（不新增数据目录与 gitignore）；
  - 绑定验证：官方用户主页 `https://atcoder.jp/users/{handle}` 的 **404 判定**
    （实测确认：`history/json` 对不存在用户也返回 200 `[]`，kenkoooo v2
    `user_info` 对不存在用户返回 200 全零，均无法区分；主页 404 是唯一可靠信号）。
- **失败语义分级**：`problems.json` 失败 → 抛 `PlatformError`（题名为核心展示字段，
  宁可本次同步降级重试不落库坏数据）；`problem-models.json` 失败或目录缺题 →
  `difficulty=None` 继续（非关键字段）；目录缺题时 `problem_name` 兜底 `problem_id`。
- **增量 / 全量**（kenkoooo 只能升序翻页，与 CF 倒序回扫不同）：
  - 增量：`from_second = since`（含边界，游标当秒重复拉取由 store 按
    `submission_id` 去重吸收，与 §3.3 语义一致），升序翻页至短页（<500）为止；
  - 全量：先拉 `full_window_days` 窗口；窗口内不足 `full_min_rows` 条时退到
    `from_second=0` 拉全部历史（两步策略，不逐段扩展）；
  - **页间去重与防停滞**：`from_second` 含边界 ⇒ 翻页下一页与上页末条同秒重叠，
    adapter 内按 `id` 集合去重；单页无新 id 即停（防同秒 ≥500 条死循环）；
    外加 `MAX_PAGES` 护栏；
- **verdict 映射**：`AC/WA/TLE/MLE/RE/CE/OLE` 直映射；`WJ/WR/JUDGING` → `JG`
  （评测中，对齐 CF 的 SUBMITTED/TESTING）；`IE/QLE` 与未知值 → `UKE`；
- **URL**：`problem_url = https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}`，
  `problem_key = problem_id`（如 `abc001_a`）；
- **限流**：`min_interval = 1.0`（kenkoooo 公益接口要求 ≥1s；verify 的 atcoder.jp
  请求共用同一 platform 限流桶，保守串行）；
- **net 层依赖**：verify 需区分 404（用户不存在）与其他 4xx（平台故障），
  依赖 net 层 4xx 抛出的 `HttpStatusError`（`PlatformError` 子类，携带
  `status_code`）——404 转 `UserNotFoundError`，其余维持 `PlatformError`。

### 5.6 洛古适配器（cookie 授权 + 反爬对抗范本，第三期）

`adapters/luogu/`，首个 `AuthMode.COOKIE` 平台。以下结论全部来自 2026-08-15
真实 cookie 实测：

- **数据源**：
  - 提交明细：`GET /record/list?user=<uid>&page=N&_contentOnly=1`（`_contentOnly=1`
    返回纯 JSON 信封 `{code, currentData: {records: {result, count, perPage}}}`；
    不带则返回 SPA 页 + `_feInjection` 内嵌同构数据）。时间**倒序**、perPage=20、
    倒序回扫（与 CF 同模式：增量 `ts < since` 停止，record `id` 去重）；
  - 绑定验证存在性：`GET /api/user/search?keyword=X` **匿名可用**，返回
    `{uid, name, avatar}`，取精确匹配（用户名不区分大小写或 uid 相等）；
  - 绑定验证凭据有效性：携凭据试拉 record/list 第 1 页（绑定当下拦住死凭据）；
  - **难度**：record 内嵌 `problem.difficulty`（0-7 档），无需额外请求。
- **传输层（关键）**：WAF 按 TLS 指纹区分客户端——实测 httpx（Python 指纹）
  必被 Spilopelia 挑战拦截，`curl_cffi`（`impersonate="chrome"`）通过。
  adapter 持有自己的 `curl_cffi.requests.AsyncSession`（不用共享 HttpFetcher；
  注册表构造签名不变，入参 fetcher 忽略）。凭据经 session 的 cookies 参数应用。
- **反爬挑战形态与处置**：
  - `302 + Set-Cookie: C3VK`（`Ws-Action: cc`）→ 客户端 cookie 罐跟随即可通过
    （curl_cffi 会话自动处理）；
  - Spilopelia **JS 挑战页**（请求过密时升级出现）→ 非浏览器客户端无法执行 JS，
    判平台故障：带凭据时按 `AuthExpiredError` 引导重新授权（重导 cookie 是两种
    情况的共同正确动作）；低频请求（min_interval=5s）可长期避开；
  - 信封 `code == 401/403` 且消息含「请先登录/用户不可见」→ `AuthExpiredError`；
  - `403 +「请求频繁」`（限流，非过期）→ adapter 应用层专项重试
    （4 次、30s 起步指数退避；clist 生产值为 8 次 + 50s 附加延迟，本地酌减）；
  - 其余 `code != 200` → `PlatformError`。
- **会话轮换**：服务端会 302 刷新 `__client_id`（轮换不失效，旧值仍可用），
  会话罐吸收即可；**不回写 secrets.json**（本期 YAGNI，实测旧凭据长期有效）。
- **归一化**：
  - `handle = uid`（数字）；verify 归一输入（用户名/uid 均可）并返回
    `display_name=用户名`、`avatar`；
  - `submission_id` = record `id`；`problem_key` = `pid`；`problem_name` = `title`；
  - `problem_url` = `https://www.luogu.com.cn/problem/{pid}`，`contest` 非空时
    拼 `?contestId={cid}`（clist 格式）；contest 内提交计入统计（对齐 CF gym）；
  - `difficulty` = record 内嵌 0-7 原始档（int，不归一）；
  - **verdict 映射**（数字 status 码，官方 `/_lfe/config/auth` 常量表实测校准）：
    `12→AC`、`6→WA`、`14→WA`（Unaccepted，对话确认）、`2→CE`、`7→RE`、
    `5→TLE`、`4→MLE`（**注意 4/5 与直觉相反**）、`3→OLE`、`0/1→JG`
    （等待/评测中）、`11`（UKE）/`21/22/23`（Hack 系列）/未知码 → `UKE`；
  - **language 数字码**：同一常量表的 `CodeLanguage` 内置映射（如 27=C++20、
    7=Python 3），未知码兜底空串。
- **二级密码不影响**：二级密码只保护账号安全类敏感操作，登录态读提交记录
  不触发（对话确认设计假设，架构上有 auth_expired 降级兜底）。
- **一键登录（browser-login）**：`adapters/luogu/login.py` 用 Playwright
  （可选依赖组 `browser-login`）拉起**系统 Chrome/Edge** 独立窗口（临时 profile，
  `channel="chrome"` 兜底 `msedge`，不下载浏览器二进制），用户自行完成登录
  （图形验证码/二级密码等均由用户自然处理），检测到 `__client_id` 出现即抓取
  `_uid`/`__client_id`/UA 返回；用户关窗 → canceled，超时 3 分钟 → timeout。
  凭据由 service 暂存（内存，10 分钟 TTL），bind 时消费——**凭据不经前端**。
  Playwright 未安装时 `/platforms` 的 `browserLogin=false`，前端隐藏一键登录
  按钮，降级手动粘贴（接受整串 Cookie 头，前端解析出两个字段）。

### 5.7 新平台接入清单（checklist）

1. 调研数据源（官方 API / 第三方 / 非官方 / cookie），确认每项能力可取性与限流，
   参考 [../cache/platform-api-research.md](../cache/platform-api-research.md)；
2. `backend/src/adapters/<platform>/` 目录：`__init__.py`（Adapter 类）、
   `api_models.py`（响应模型）、`normalize.py`（归一化纯函数）；
3. Adapter 声明元数据：`platform_id`（与前端 `PlatformId` 对齐）、`name`、
   `capabilities`、`auth`、`min_interval`；
4. 只实现 capabilities 声明的方法；`verify` 需要凭据时接收 `credentials`；
5. `adapters/__init__.py` 注册一行；
6. 前端 `types.ts` 的 `PlatformId` 联合类型补充平台 id（平台列表本身来自后端，
   无需硬编码清单）；绑定弹窗/平台页签自动出现；
7. 测试：`tests/adapters/test_<platform>_adapter.py`（MockTransport + 录制 JSON
   fixture：解析/分页/增量停止/信封/畸形响应/凭据）、必要时 `tests/adapters/fixtures/`
   录样数据；`test_sync` 的 FakeAdapter 模式可直接复用；
8. 跑 `uv run pytest`、`uv run ruff check src tests`；起服务 curl 全链路。

**cookie 授权平台（洛谷/QOJ）要点**：`AuthMode.COOKIE` + `Credentials` 透传；
绑定弹窗收集 cookie → `secrets.json` 存储（预留）；同步遇 `AuthExpiredError`
前端引导重新授权；低频请求 + 专项重试（min_interval 声明更长，必要时单次覆盖
`max_retries`/`base_backoff`）。

## 6. 后端工程落地

### 6.1 后端结构

```
backend/src/
├─ adapters/                   # 顶层平台适配层（跨功能复用，见 §5）
├─ routers/activity/router.py  # HTTP 边界：只做参数校验与转发，平台无关
├─ services/activity/service.py # 门面：用户组/信息卡/账号 CRUD/绑定验证、触发同步、聚合读取
└─ modules/activity/
   ├─ models.py                # Submission / Account（含 display_name）/ Profile / Secrets / SyncStatus 领域模型
   ├─ schemas.py               # API 出入参 DTO（camelCase，与前端 types.ts 对齐）
   ├─ store.py                 # data/user/<userid>/ 读写层 + 用户组目录管理 + secrets.json（原子写、锁）
   ├─ sync.py                  # 增量同步引擎：游标推进、去重合并、按组隔离、失败隔离
   └─ aggregate.py             # 纯函数：submissions → 按天聚合/总览统计（无 IO）
```

约束：

- 依赖方向严格单向 `routers → services → modules → adapters`；
- adapter 只允许被 `sync.py` 与 `service.py` 触碰；
- adapter 显式注册表（§5.1）；全量同步窗口属功能域配置（§6.3），adapter 不内置；
- `services/activity/service.py` 与 `routers/activity/router.py` 用
  `init_activity_service(settings)` / `get_activity_service()` 的 lifespan 单例模式。

### 6.2 服务层职责

- **用户组**：当前组内存态（默认 `default`，启动惰性创建）；新建自动切换、重命名
  同步目录与当前组、删除物理删除 + 清理该组同步状态、当前组被删回退（至少保留一组）；
- **信息卡**：读写当前组 `profile.json`（ID 与组名分离，avatar 显式 null 清除、
  上限 500k 字符）；
- **账号**：绑定（cookie 平台凭据必填并落 secrets.json、换绑删旧含凭据、
  展示名 display_name 随绑定持久化）、解绑、验证（能力校验 + `credentials` 透传，
  `UserNotFoundError → 400`、`AuthExpiredError → 400`、`PlatformError → 502`）；
- **凭据**：secrets.json 读写清理（store 层）；browser-login 会话编排
  （启动/状态轮询/暂存凭据 10 分钟 TTL，bind 消费，凭据不经前端）；
- **同步**：逐账号 `asyncio.create_task` 后台执行（兜底降级），前端轮询
  `/sync/status`；同步前按账号从 secrets.json 注入凭据；
- **聚合**：`overview`（totals + 370 天日序列，窗口来自配置）、`submissions`
  （当日明细 / 最后 200 条近期提交）。

### 6.3 配置项（core/config.py，XCPC_ 前缀环境变量可覆盖）

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `user_data_dir` | `backend/data/user` | 用户组根目录 |
| `activity_window_days` | 370 | 全量同步与聚合窗口（对齐热力图近一年），经 service → sync 注入 adapter |
| `activity_full_min_rows` | 5000 | 全量至少拉取的条数（窗口内不足时拉满，为 all-time 留缓冲） |

### 6.4 API（平台无关，一律作用于当前用户组）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/activity/groups` | 用户组列表 `[{name, current}]`（name 即目录名） |
| POST | `/api/activity/groups` | 新建用户组 `{name}`（建目录 + 初始信息卡，自动切换，201） |
| PATCH | `/api/activity/groups/{name}` | 重命名 `{newName}`（目录改名，数据归属不变） |
| DELETE | `/api/activity/groups/{name}` | 删除（物理删除全部数据；当前组被删回退，至少保留一个组，204） |
| POST | `/api/activity/current-group` | 切换当前用户组 `{name}` |
| GET | `/api/activity/profile` | 当前组信息卡（ID / 签名 / 头像） |
| PATCH | `/api/activity/profile` | 更新信息卡（avatar 显式 null 清除；ID 与组名分离） |
| GET | `/api/activity/platforms` | 平台元数据（id/名称/capabilities/auth/browserLogin）+ 已绑定账号（含 displayName）及同步状态 |
| POST | `/api/activity/accounts/verify` | 校验 `{platform, handle, credentials?}`；用户不存在/凭据无效 400，平台故障 502；cookie 平台凭据必填 |
| POST | `/api/activity/accounts` | 绑定 `{platform, handle, displayName?, credentials?}`（换绑删旧；cookie 平台凭据必填或消费 browser-login 暂存），自动触发首次同步（201） |
| POST | `/api/activity/platforms/{platform}/browser-login` | 启动浏览器一键登录会话（202；仅 cookie 平台且服务端具备 Playwright；单会话互斥） |
| GET | `/api/activity/platforms/{platform}/browser-login/status` | 登录会话状态（waiting/success/canceled/timeout/error + 成功后回执 handle/displayName/avatar），前端轮询 |
| DELETE | `/api/activity/accounts/{platform}/{handle}` | 解绑并删除该账号本地数据（204） |
| GET | `/api/activity/overview?platform=` | 概览：all-time 总量 + streak + 近 370 天日序列；缺省为汇总 |
| GET | `/api/activity/submissions?date=&platform=` | 带 `date` 为当日明细；不带 `date` 为最后 200 条近期提交（倒序）；平台过滤可选 |
| POST | `/api/activity/sync` | 触发同步 `{platform?}`，空为全部账号；立即返回（202） |
| GET | `/api/activity/sync/status` | 各账号同步状态（idle/running/error + 上次结果 + errorCode），前端轮询 |

错误响应统一由全局异常处理器结构化（`{error: {code, message, detail}}`）。

## 7. 前端落地

### 7.1 目录结构

```
frontend/src/features/activity/
├─ ActivityPage.vue            # 数据总览页（网址状态同步见 §4.7）
├─ api.ts / store.ts / types.ts
├─ profile.ts                  # 用户组与信息卡（后端驱动，防抖提交信息卡）
├─ model/                      # 纯函数层（vitest 覆盖）
│  ├─ heatmap.ts / heatmap-grid.ts / bars.ts / echarts-theme.ts / pagination.ts / dates.ts
├─ components/
│  ├─ UserProfileCard.vue      # 信息卡（头像 / ID / 签名就地编辑）
│  ├─ UserGroupMenu.vue        # 用户组下拉（新建 / 切换，按钮显示组名）
│  ├─ UserGroupEditModal.vue   # 编辑用户组（重命名 / 删除 / 平台账号绑定管理）
│  ├─ AccountBindModal.vue     # 绑定 / 换绑 / 凭据录入（cookie 平台：一键登录 + 整串 Cookie 粘贴）
│  ├─ SyncBar.vue / SyncOverlay.vue / PlatformTabs.vue
│  ├─ StatCards.vue / PassBarChart.vue / ActivityHeatmap.vue / SubmissionList.vue
│  └─ platforms/               # 平台专属组件注册表（后续增量，如 LuoguExtrasCard.vue）
```

### 7.2 store 与数据流

- `store.ts`：账号/平台/日序列/提交数据全部来自后端当前组 API；`watch(currentKey)`
  切组后重置视图并重拉数据；`watch([activePlatform, selectedDate])` 联动重拉
  （请求序号防竞态，丢弃过期响应）；同步用"触发 + 轮询 `/sync/status` 至 idle"；
- 平台页签（PlatformTabs）与绑定弹窗平台下拉均由后端 `/platforms` 返回驱动，
  前端不硬编码平台清单；`types.ts` 的 `PlatformId` 随新平台补充联合类型；
- **凭据平台 UI**（洛古）：绑定弹窗按 `auth === 'cookie'` 展开凭据区——
  「一键登录」（`browserLogin` 可用时，点击后轮询登录会话状态）与手动粘贴
  （整串 Cookie 头 / JSON 均可，前端解析出 `_uid` / `__client_id`）；
  账号展示一律 `displayName ?? handle`；`syncErrorCode === 'auth_expired'` 时
  账号按钮警示态「凭据过期」，点击走换绑路径重新授权，成功后自动触发一次同步；
- 网址状态同步：`?platform=&date=&page=`（缺省不写入），刷新/前进后退/复制链接可恢复。

### 7.3 用户组与信息卡（profile.ts）

- `useUserGroups()`：`groups` / `currentKey` / `createGroup` / `switchGroup` /
  `renameGroup` / `deleteGroup`，全部走后端目录 API；
- `useProfile()`：信息卡 `profile`（id/签名/头像），编辑防抖 400ms 提交
  `PATCH /profile`；头像前端裁剪 512px data URL（`fileToAvatar`，JPEG 0.9）。

### 7.4 能力条件渲染

公共区块（统计卡/热力图/柱状图/提交列表）对所有平台一致渲染；平台专属区块
（extras，如洛谷咕值）按后端 `capabilities` + 前端注册表挂载（后续增量），
`extras` 用判别联合类型保类型安全。

## 8. 验证方式

- 后端 pytest：`adapters`（net 限流/退避/信封/凭据/单次覆盖、各平台 adapter
  录制 fixture 解析）、`store`（原子写/去重合并/组目录管理/损坏容错）、
  `aggregate`（口径/时区切天/streak）、`sync`（游标推进/失败隔离/按组隔离/
  auth_expired 标记）、`service`（用户组 CRUD/组数据隔离/信息卡/绑定同步）；
  `ruff check src tests`；
- 前端 vitest：`model/` 纯函数；`typecheck`、`test`、`build`；
- API 契约：起服务后 `curl http://127.0.0.1:8000/api/diagnostics` 正常返回；
- 手动走查：新建中文组 → 切组 → 绑定 CF 账号首次同步 → 卡片/热力图/柱状图/明细
  渲染 → 组间数据隔离 → 重命名组 → 删除组回退 → 明暗主题与色相切换图表跟随 →
  断网/平台故障时诊断降级不白屏。

## 9. 实施顺序（历史）

已按序完成：设计文档 → 依赖与 gitignore → 数据模型与读写层 → adapters 基座 +
Codeforces → 同步引擎与 API → 前端接入 → 多用户组与信息卡 → 契约扩展与结构清理
→ AtCoder 适配（net 层状态码错误 + adapter + 录制测试，前端零改动）
→ 洛古适配（secrets 凭据框架 + curl_cffi 传输层 + browser-login + 前端凭据 UI）
（详见 [../../PROGRESS.md](../../PROGRESS.md)）。

## 10. 既有决策与陷阱（对话确认，勿随意回退）

- **增量游标 `ts < since`**：游标当秒提交重复拉取靠 `submission_id` 去重吸收，
  防同秒多提交漏拉；改回 `<=` 会丢数据；
- **`difficulty: int | str | None`**：保留平台原始难度值（CF 分数 / LC 档位），
  不做跨平台归一；
- **退避基准 `max(base_backoff, min_interval) × 2^n`**：首次重试错开完整限流窗口；
- **头像 512px data URL**：data URL 内嵌数据不依赖文件路径，目录迁移/重命名无损；
  512px 是信息卡 2 倍超采样防糊的决策；
- **近期提交 = 最后 200 条**（非时间窗口）：近期没做题的账号也能看到最近记录；
- **平台列表来自后端**：前端页签/绑定下拉不硬编码，新平台只加 `PlatformId` 联合类型；
- **能力方法默认抛 `CapabilityNotSupportedError`**：能力残缺平台不写空壳，
  service 按 capabilities 调用；
- **用户组删除至少保留一个组**：后端强制，前端按钮禁用联动；
- **汇总视图同步全部平台前弹确认框**（可能较慢）；平台视图只同步该平台；
- **kenkoooo `from_second` 含边界且只升序翻页**：AtCoder 增量/全量必须 adapter 内
  按 id 去重 + 单页无新 id 即停，否则同秒重叠页会死循环（§5.5）；
- **AtCoder 用户存在性只能看官方主页 404**：`history/json` 与 kenkoooo
  `user_info` 对不存在用户均返回 200，不能用于绑定验证（实测确认，§5.5）；
- **题目目录失败语义分级**：`problems.json` 失败抛错重试（题名核心）、
  `problem-models.json` 失败 difficulty 留空继续（非关键），不反向混淆（§5.5）；
- **洛古传输层必须 curl_cffi**：WAF 按 TLS 指纹封 httpx（实测同 IP 同 cookie
  curl 通过、httpx 必被挑战）；换回共享 HttpFetcher 会导致同步全灭（§5.6）；
- **洛古状态码 4=MLE / 5=TLE（与直觉相反）**：映射表以官方 `/_lfe/config/auth`
  常量为准，勿凭记忆改写；14（Unaccepted）→ WA 为对话确认口径（§5.6）；
- **洛古 handle = uid，display_name 分离**：用户名可改、uid 稳定；界面显示
  一律 `displayName ?? handle`；
- **browser-login 凭据不经前端**：service 内存暂存 + bind 消费；Playwright 为
  可选依赖组，未安装时降级手动粘贴（§5.6）；
- **`__client_id` 轮换不回写**：服务端 302 刷新会话但旧值不失效（实测），
  会话罐吸收即可；若未来失效应答频繁再考虑回写 secrets.json。
