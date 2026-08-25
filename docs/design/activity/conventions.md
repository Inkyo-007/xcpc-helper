# 训练统计聚合（activity）：公共约定

> 状态：已实现（Codeforces / AtCoder / 洛谷 / 牛客 / LeetCode CN / VJudge 六平台全链路）。
> 本文档承载 activity 域的平台无关约定；各平台的适配细节见同目录
> [codeforces.md](codeforces.md) / [atcoder.md](atcoder.md) / [luogu.md](luogu.md) / [nowcoder.md](nowcoder.md) / [leetcode-cn.md](leetcode-cn.md) / [vjudge.md](vjudge.md)。
> 需求背景见 [../../cache/requirement.md](../../cache/requirement.md)，
> 平台接口调研见 [../../cache/platform-api-research.md](../../cache/platform-api-research.md)。
> 改设计必须先改本文档（或对应平台文档）再改代码。

## 1. 这个功能做什么

选手的训练数据散落在 Codeforces、AtCoder、洛谷等多个平台，难以直观观察与统计。
本功能在用户绑定各平台账号后，自动拉取并整合训练数据，提供汇总页与单平台页，
展示解题/提交统计、activity 热力图、统计卡片与近期提交；rating 折线与比赛信息
为后续增量（契约已预留）。需求优先级归属见 [../../requirements.md](../../requirements.md)「做题统计」。

## 2. 总体形态

### 2.1 关键决策

- **所有对外请求经由本地后端代理**。前端直连各平台会被 CORS 拦截，且凭据
  （cookie）不能暴露给前端；FastAPI 后端天然承担采集代理角色。
- **adapter 可插拔、失败可降级**。各平台接口稳定性差异大（官方 API / 第三方
  API / 非官方接口 / cookie 授权），单平台失败只降级为该账号的诊断信息，不拖垮
  整个面板（遵循 [../conventions.md](../conventions.md)「诊断不阻断」）。
- **启动自动同步 + 手动同步**。本地应用不常驻运行，所以每次启动（后端 lifespan
  就绪后）自动对当前用户组全部账号触发一次同步（后台异步，等价于"立即同步
  全部"；可用 `activity_sync_on_startup=false` 关闭）。界面上另有"立即同步"
  按钮：汇总视图同步全部平台（点击前先确认），平台视图只同步该平台。每个账号
  都有新鲜度/上次同步时间/错误状态展示；同步在后台异步执行，前端轮询状态接口。
- **增量同步**。每个（用户组, 平台, 账号）维护同步游标（UTC 秒级数据水位），
  游标当秒的提交重复拉取、按 submission_id 去重合并（停止条件 `ts < since`，
  避免同秒多提交被永久漏掉——见 §3.3）。
- **时区**。远端时间戳均为 UTC 秒级，按后端本地时区切"天"聚合（本地部署，
  后端时区即用户时区）。
- **用户组 = data/user/<user_id>/ 目录**。多用户组真实隔离（账号绑定、训练
  数据、信息卡），组名即目录名（支持中文），见 §3.1 与 §4.1。
- **信息卡与组名分离**。信息卡（ID / 签名 / 头像）存组内 `profile.json`，
  编辑互不影响。

### 2.2 平台差异适配模式：公共内核 + 平台扩展

平台知识只允许集中在两处：**后端 adapter 目录**、**前端平台组件注册表**；
router / service / modules 主干保持平台无关（不出现 `if platform == "luogu"` 分支）。

- adapter 声明 `capabilities`（提供哪些数据区块、是否需要凭据）与 `auth`；
- service / sync 按 `capabilities` 决定调用哪些能力方法，缺能力的字段省略并记诊断；
- router 用同一组端点服务所有平台，绑定/凭据差异由统一 `credentials` 载荷吸收；
- 前端按后端 `/platforms` 返回的元数据（capabilities/auth/browserLogin）条件渲染，
  平台页签与绑定弹窗形态（匿名 / cookie 两种方式）均由后端驱动，前端不硬编码平台清单。

### 2.3 平台优先级（分期）

1. Codeforces（官方 API，匿名可取，风险最低）——**已实现**
2. AtCoder（kenkoooo API + 官方用户主页 404 验证，匿名可取）——**已实现**
3. 洛谷（cookie 授权框架首个实例 + 反爬对抗，QOJ 等后续平台复用同一套）——**已实现**
4. LeetCode CN + 牛客（GraphQL 路径已探明 / rating 匿名接口）——**已实现**
5. VJudge（/status/data 匿名端点，Cloudflare 需浏览器标识头）——**已实现**
6. 长尾平台（评估 ojhunt 依赖或手动导入）

## 3. 数据模型与存储

### 3.1 存储位置

统一存储在 `backend/data/user/<userid>/`，**每个用户组一个目录（目录名即组名，
支持中文）**；服务层维护当前用户组（内存态，默认 `default`——仅在不存在任何
用户组的首次运行时创建；default 被删除/重命名后重启不再重建，回落到现存首个组），
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
   └─ secrets.json              # cookie 等凭据（gitignore，仅存本机）
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

`secrets.json` 结构（`modules/activity/models.py::Secrets`）：

```json
{ "platforms": { "luogu": { "1085065": { "cookies": {"_uid": "...", "__client_id": "..."},
                                          "headers": {} } } } }
```

- 账号元数据（profile.json）与凭据（secrets.json）**分离存储**：前者可入档，
  后者 gitignore 永不入 git；解绑/换绑/删除用户组时同步清理（store 层保证）；
- `handle` 为平台内 **API 主键**（洛谷为 uid 数字，用户名可改而 uid 稳定），
  `display_name` 为展示名（洛谷用户名），界面一律显示 `display_name ?? handle`；
- sync 引擎按 (platform, handle) 从 secrets.json 加载凭据注入 adapter
  （匿名平台为 None）；
- 头像为前端裁剪后的 **512×512 JPEG data URL**（信息卡容器约 268px，2 倍超采样
  防糊；上限 500k 字符）。data URL 内嵌数据，**不依赖原图文件路径**，目录迁移/
  重命名不受影响；
- 信息栏 ID 与组名（目录名）分离：编辑 ID 只改 `profile.json`，重命名组不改变 ID。

### 3.2 统一提交模型

各平台提交归一化为 `adapters.base.PlatformSubmission`（不含 platform/handle，
由 sync 层补字段转 `modules/activity/models.py::Submission` 落盘）：

```
PlatformSubmission {
  submission_id   # 平台内唯一提交 id（去重依据）
  problem_key     # 平台内题目标识（CF "2245F" / AT "abc001_a" / LG "P1001"）
  problem_name
  problem_url     # 平台内题目外链
  difficulty      # 原始难度值，不做跨平台归一（int | str：CF 分数 / LC 档位 / 洛谷难度档）
  verdict         # AC / WA / CE / RE / TLE / MLE / OLE / UKE / JG（评测中）/ UNAC（未通过但细分未知）
  submitted_at    # UTC 秒级时间戳
  language
}
```

- **UNAC 语义**：洛谷记录列表只区分 AC / CE / Unaccepted（官方常量 `filterable`
  佐证：仅 2/12/14 可筛选），WA/TLE/MLE/RE 细分只在记录详情的测试点信息里。
  为不误导（把 TLE 显示成 WA），14 归一为 UNAC（未通过、细分未知），可经
  精细化同步还原细分（见 [luogu.md](luogu.md)）；**存量历史 WA（旧口径落盘）
  不做迁移**，重新同步即被新口径覆盖（对话确认）。

### 3.3 游标、断点与去重

这是同步正确性的核心约定，三个概念各司其职：

- **游标**（`Account.last_synced_at`）= 数据水位：回答"数据完整到哪个时间点"。
  只进不退、**绝不在一次同步的中途推进**（否则未拉取的较旧区段会被永久漏掉）；
  无新提交时保持原游标（空账号不落 0 游标）。
- **增量停止条件 `ts < since`**：游标当秒的提交会重复拉取，由 store 按
  `submission_id` 去重吸收（去重是硬保证，重复拉无代价）——避免同秒多提交被漏掉。
- **断点**（`Account.sync_checkpoint`，可选字段，仅全量回填期存在）= 平台自解释
  的续传位置（洛谷=页码 / CF=偏移 / AT=from_second 秒，附累计条数 fetched），
  回答"回填进行到哪了"。**每批落盘后推进、全量完成即清除**；中断后下次同步
  识别断点续跑，换绑/解绑/删组随账号自动清理。
- 「xx 前同步」展示用 `Account.last_sync_ok_at`（每次同步成功落盘的真实时刻，
  **与数据水位游标分离**——游标是"数据新到哪"，拿它展示会在重启后/同步中
  显示成数据水龄，如 71 天前最后提交被显示为"71 天前同步"）；内存态
  `SyncStatus.last_synced_at` 为本次会话的同步结束时间，缺失时回退 last_sync_ok_at。

### 3.4 写入约定

沿用 [../conventions.md](../conventions.md)：写操作经 store 原子写入（临时文件 +
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

1. **工具条**（通栏）：左侧平台分段切换器（**平台同步中时其页签文本右上角显示
   黄色圆点角标**，不进入该平台页也可知悉）；右侧同步区——上次同步时间
   （**按视图区分**：平台视图取该平台账号的最近同步时间，汇总视图取全部账号的
   最近同步时间；未绑定/未同步显示「尚未同步」）、「立即同步」（汇总视图点击
   先确认"同步全部平台"，平台视图只同步该平台；点击即转圈进入进行态，完成后
   弹出「同步完成」/失败警告提示——快速或无新增同步也有明确反馈）、
   「编辑用户组」（仅汇总视图）与账号入口（汇总视图为用户组下拉；平台视图为
   该平台绑定账号按钮，点击打开**账号管理弹窗**——列表行式：换绑 / 解绑
   （确认后删除本地数据，不可找回）；未绑定显示虚线「未绑定账号」直接进绑定弹窗）。
   **同步为纯后台属性，无全局遮罩**：平台视图下该平台同步中时，右栏替换为
   同步进行态面板（进度环 + 百分比，总量未知的平台仅显示不定态环），
   其他平台视图与模板库等其他功能互不干扰；
   **平台视图未绑定账号时**，右栏不显示全零统计，替换为未绑定引导面板
   （「还未绑定 <平台> 账号」+ 绑定按钮）。
2. **左栏 · 用户信息卡**：头像（本地上传，前端裁剪 512px 方形 data URL，存后端）、
   主标签 ID、副标签签名；就地编辑，防抖提交后端。
3. **左栏 · 近期提交**：跨平台合并的最后 200 条提交（后端取历史倒序前 200，
   **不按时间窗口过滤**，近期没做题的账号也能看到最近记录），新在上；每行 verdict
   徽章 + 题号题名（点击跳平台外链）+ 平台 + 时间（时间规则：当天只显示时刻，
   当年更早的带 `MM-DD`，往年带完整 `YYYY-MM-DD`）。每页固定 10 条分页（页码同步网址，
   见 §4.6）；点击热力图格子切当日明细（同 10 条分页，页码状态独立），再次点击取消。
4. **右栏 · 统计卡片行**：总解题数 / 总提交数 / 今日解题 / 连续活跃天数，count-up。
5. **右栏 · activity 热力图**：GitHub 式一年图（53 周 × 7 天，周日起始），
   hover 上浮 + tooltip，点击选中联动左栏明细。
6. **右栏 · 柱状图行**：近 7 天通过（日粒度）/ 近 12 个月通过（月粒度），ECharts。

verdict 徽章配色固定：AC 绿、WA 红、CE 黄、RE 紫、**JG 浅蓝**、**UNAC 同 WA 红**
（未通过但细分未知），TLE/MLE/OLE/UKE 深蓝。

### 4.3 统计口径

- 解题数 = 当天 AC 的**不同题目数**（去重键含 platform，汇总不做跨平台去重）；
- 连续天数按"当天有 AC"计；今天尚无 AC 时不算断签，统计到昨天为止；
- 热力图固定近 370 天；streak 由后端计算（可能超过窗口）；
- 柱状图由前端从日序列派生（`model/bars.ts`）。

### 4.4 空状态与绑定流程

- 未绑定任何账号：整页引导空状态「绑定第一个账号」；
- 绑定弹窗：顶部提示「你正在绑定 <平台> 账号」（平台由入口锁定，弹窗内不再
  提供平台切换；空状态入口回落为平台列表首个，换平台可先点平台页签）→
  handle 输入 →「验证」（后端 `POST /accounts/verify`，成功回执平台内基本信息）
  →「确认绑定」→ 自动触发首次同步；
- 换绑：每平台每用户组只保留一个账号，绑定新账号替换旧账号并删除其本地数据；
- 解绑：确认后删除该账号本地数据（不可找回）；
- **更新凭据**（仅 cookie 平台）：凭据过期时，用户可通过「更新凭据」重新录入
  cookie（验证回执 handle 必须与当前绑定一致），仅覆盖 secrets.json 中的凭据，
  **保留 submissions 与同步游标**，更新成功后自动触发一次同步；
- 凭据平台（洛谷）：绑定弹窗提供两条路径——「方式一 · 一键登录」（后端
  Playwright 拉起系统浏览器登录窗口，见 [luogu.md](luogu.md)）与
  「方式二 · 手动输入 cookie」（逐字段输入框：`_uid`（即平台 UID，兼作 handle）
  与 `__client_id`，配「如何获取 cookie？」悬浮引导）；
  `verify`/同步携带 `credentials`；绑定当下即携凭据试拉验证有效性
  （`AuthExpiredError` 在 verify 路径转 400，不放行死凭据）；
  同步中 `AuthExpiredError` → `syncErrorCode: "auth_expired"` → 账号按钮警示态
  「凭据过期」→ 点击打开账号管理弹窗 → 选择「更新凭据」重新授权 → 验证通过
  后自动触发一次同步。过期不影响本地已有数据，游标不动，重授权后从原游标继续增量。

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
    AtCoderAdapter.platform_id: AtCoderAdapter,
    LuoguAdapter.platform_id: LuoguAdapter,
}
```

新增平台的后端成本 = 一个 adapter 目录 + 注册一行，主干零改动。

### 5.2 统一契约（base.py）

**枚举**：

```python
class Verdict(str, Enum):     # AC/WA/CE/RE/TLE/MLE/OLE/UKE/JG/UNAC（平台无关，adapter 归一化）
class Capability(str, Enum):  # SUBMISSIONS / USER_INFO / RATING / CONTESTS / REFINE_VERDICT
class AuthMode(str, Enum):    # NONE（匿名）/ COOKIE（cookie 授权）
```

**共享模型**（adapter 产出，由 sync 转领域模型）：

```python
PlatformSubmission   # 提交记录（§3.2）
UserInfo             # 绑定验证回执 { handle, display_name?, avatar? }
RatingPoint          # rating 历史单点 { time, rating, contest_name }（后续增量）
ContestInfo          # 比赛信息 { contest_id, name, start_time, duration_seconds, url? }
Credentials          # 凭据 { cookies: dict, headers: dict }
SyncBatch            # 流式拉取批次 { items, checkpoint, done }
```

**异常体系**：

```python
AdapterError                    # 基类
├─ UserNotFoundError            # 绑定验证用户不存在 → service 转 400
├─ PlatformError                # 平台故障（网络/限流/格式）→ sync 降级为该账号诊断
│   └─ HttpStatusError          # 4xx 等不可重试状态码，携带 status_code（如 404 → 用户不存在）
├─ AuthExpiredError             # 凭据过期 → sync 标记 error_code="auth_expired"
├─ CapabilityNotSupportedError  # 调用未声明的能力（契约违约，正常路径不触发）
└─ BrowserLoginCancelledError   # 浏览器一键登录被用户取消
```

**PlatformAdapter 能力方法**（基类默认抛 `CapabilityNotSupportedError`；能力残缺的
平台只实现 capabilities 声明的方法，不被迫写空壳）：

| 方法 | 说明 | 能力 |
| --- | --- | --- |
| `verify(handle, credentials=None) -> UserInfo` | 绑定验证 | USER_INFO |
| `fetch_submissions(handle, *, since, credentials=None, full_window_days, full_min_rows, progress_cb=None, resume_checkpoint=None) -> AsyncIterator[SyncBatch]` | 提交明细，**流式逐批产出**（见下） | SUBMISSIONS |
| `fetch_rating_history(handle, credentials=None) -> list[RatingPoint]` | rating 历史（后续增量） | RATING |
| `fetch_contests() -> list[ContestInfo]` | 比赛信息（平台级，无 handle，未来 contest 功能消费） | CONTESTS |
| `fetch_submission_verdict(record_id, credentials=None) -> Verdict \| None` | 单条提交的细分结果精化（列表只有 UNAC 的平台拉详情判定）；返回 None = 无法判定保持原样 | REFINE_VERDICT |

**流式契约（SyncBatch）**：`{items, checkpoint, done}`——`items` 为本批提交
（通常一页）；`checkpoint` 为全量回填断点（增量模式恒为 None），平台自解释
并附累计条数（如 `{"page": 12, "fetched": 240}`），断点页码/偏移会随新提交
漂移，靠 store 按 `submission_id` 去重吸收（多拉无代价、不漏）；`done=True`
表示拉取完成（游标此时才可推进）。**方向差异的约定**：降序平台（CF/洛谷）
先产最新批次，升序平台（AT kenkoooo）先产最旧批次——中断时降序缺最旧、
升序缺最新，正确性不受影响；同步开始后出现的新提交一律不追，由下次增量
兜底（游标语义保证）。

**数据迁移钩子**：`normalize_url(url)`（5f7ffeb8 先例）——历史数据读取时经钩子
幂等转换为当前口径（默认恒等），平台规则演进无需重新同步。

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
- **传输层例外（洛谷）**：洛谷 WAF 按 TLS/HTTP 指纹区分客户端（实测：同 IP 同
  cookie，curl 通过、httpx 必被挑战），故洛谷 adapter 不用共享 `HttpFetcher`，
  改用 `curl_cffi`（浏览器 TLS 指纹伪装）自带会话，限流/退避模式镜像本层实现，
  详见 [luogu.md](luogu.md)。

### 5.4 新平台接入清单（checklist）

1. 调研数据源（官方 API / 第三方 / 非官方 / cookie），确认每项能力可取性与限流，
   参考 [../../cache/platform-api-research.md](../../cache/platform-api-research.md)；
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
绑定弹窗收集 cookie → `secrets.json` 存储；同步遇 `AuthExpiredError`
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
   ├─ models.py                # Submission / Account / Profile / Secrets / SyncStatus 领域模型
   ├─ schemas.py               # API 出入参 DTO（camelCase，与前端 types.ts 对齐）
   ├─ store.py                 # data/user/<userid>/ 读写层 + 用户组目录管理 + secrets.json（原子写、锁）
   ├─ sync.py                  # 同步引擎：流式双模式、游标/断点、去重合并、失败隔离
   ├─ refine.py                # 精细化同步引擎（UNAC → 细分结果，见 luogu.md）
   └─ aggregate.py             # 纯函数：submissions → 按天聚合/总览统计（无 IO）
```

约束：

- 依赖方向严格单向 `routers → services → modules → adapters`；
- adapter 只允许被 `sync.py` 与 `service.py` 触碰；
- adapter 显式注册表（§5.1）；全量同步窗口属功能域配置（§6.3），adapter 不内置；
- `services/activity/service.py` 与 `routers/activity/router.py` 用
  `init_activity_service(settings)` / `get_activity_service()` 的 lifespan 单例模式。

### 6.2 服务层职责

- **用户组**：当前组内存态（默认 `default`，仅在无任何组的首次运行时创建；
  default 被删除/重命名后重启不再重建，回落到现存首个组）；新建自动切换、重命名
  同步目录与当前组、删除物理删除 + 清理该组同步状态、当前组被删回退（至少保留一组）；
- **信息卡**：读写当前组 `profile.json`（ID 与组名分离，avatar 显式 null 清除、
  上限 500k 字符）；
- **账号**：绑定（cookie 平台凭据必填并落 secrets.json、换绑删旧含凭据、
  展示名 display_name 随绑定持久化）、解绑、**更新凭据**（仅覆盖 secrets.json，
  保留 submissions 与游标；验证新凭据有效性；校验回执 handle 与当前绑定一致）、
  验证（能力校验 + `credentials` 透传，
  `UserNotFoundError → 400`、`AuthExpiredError → 400`、`PlatformError → 502`）；
- **凭据**：secrets.json 读写清理（store 层）；browser-login 会话编排
  （启动/状态轮询/暂存凭据 10 分钟 TTL，bind 消费，凭据不经前端）；
- **同步**：逐账号 `asyncio.create_task` 后台执行（兜底降级），前端轮询
  `/sync/status`；**应用启动时自动触发一次全部账号同步**（lifespan 内
  `sync(None)`，`activity_sync_on_startup` 可关）；同步前按账号从
  secrets.json 注入凭据；**流式双模式**——
  账号有断点或游标为空为全量/回填模式（**每批落盘 + 每批存断点**，`done`
  时推进游标并清除断点；中断后下次同步从断点续跑），否则增量模式
  （攒齐批次一次落盘，游标语义不变）；
- **聚合**：`overview`（totals + 370 天日序列，窗口来自配置）、`submissions`
  （当日明细 / 最后 200 条近期提交）。

### 6.3 配置项（core/config.py，XCPC_ 前缀环境变量可覆盖）

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `user_data_dir` | `backend/data/user` | 用户组根目录 |
| `activity_window_days` | 370 | 全量同步与聚合窗口（对齐热力图近一年），经 service → sync 注入 adapter |
| `activity_full_min_rows` | 5000 | 全量至少拉取的条数（窗口内不足时拉满，为 all-time 留缓冲） |
| `activity_sync_on_startup` | true | 应用启动时自动同步当前组全部账号（false 关闭） |

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
| PUT | `/api/activity/accounts/{platform}/{handle}/credentials` | 更新已绑定账号的凭据（仅 cookie 平台）：验证新凭据有效性后仅覆盖 secrets.json，保留 submissions 与游标，成功后清除错误状态并返回账号信息 |
| POST | `/api/activity/platforms/{platform}/browser-login` | 启动浏览器一键登录会话（202；仅 cookie 平台且服务端具备 Playwright；单会话互斥） |
| GET | `/api/activity/platforms/{platform}/browser-login/status` | 登录会话状态（waiting/success/canceled/timeout/error + 成功后回执 handle/displayName/avatar），前端轮询 |
| DELETE | `/api/activity/accounts/{platform}/{handle}` | 解绑并删除该账号本地数据（204） |
| GET | `/api/activity/overview?platform=` | 概览：all-time 总量 + streak + 近 370 天日序列；缺省为汇总 |
| GET | `/api/activity/submissions?date=&platform=` | 带 `date` 为当日明细；不带 `date` 为最后 200 条近期提交（倒序）；平台过滤可选 |
| POST | `/api/activity/sync` | 触发同步 `{platform?}`，空为全部账号；立即返回（202） |
| GET | `/api/activity/sync/status` | 各账号同步状态（idle/running/error + 上次结果 + errorCode + syncProgress 0~1 可空），前端轮询 |
| POST | `/api/activity/accounts/{platform}/{handle}/refine` | 启动精细化同步（202；能力缺失 400、进行中 409；仅 REFINE_VERDICT 平台） |
| DELETE | `/api/activity/accounts/{platform}/{handle}/refine` | 中止精细化同步（204，幂等） |
| GET | `/api/activity/accounts/{platform}/{handle}/refine` | 精化状态 `{state, done, total, auto}`（state: idle/running/stopped/done；idle 时 total = 当前待精化数，供前端预估耗时） |
| PATCH | `/api/activity/accounts/{platform}/{handle}` | 更新账号配置 `{refineAuto}`（普通同步完成后自动启动精化） |

错误响应统一由全局异常处理器结构化（`{error: {code, message, detail}}`）。

## 7. 前端落地

### 7.1 目录结构

```
frontend/src/features/activity/
├─ ActivityPage.vue            # 数据总览页（网址状态同步见 §4.6）
├─ api.ts / store.ts / types.ts
├─ profile.ts                  # 用户组与信息卡（后端驱动，防抖提交信息卡）
├─ model/                      # 纯函数层（vitest 覆盖）
│  ├─ heatmap.ts / heatmap-grid.ts / bars.ts / echarts-theme.ts / pagination.ts / dates.ts / refine.ts
├─ components/
│  ├─ UserProfileCard.vue      # 信息卡（头像 / ID / 签名就地编辑）
│  ├─ UserGroupMenu.vue        # 用户组下拉（新建 / 切换，按钮显示组名）
│  ├─ UserGroupEditModal.vue   # 编辑用户组（重命名 / 删除 / 平台账号绑定管理）
│  ├─ AccountBindModal.vue     # 绑定 / 换绑（cookie 平台：一键登录 + cookie 逐字段输入）
│  ├─ AccountManageModal.vue   # 账号管理（更新凭据 / 换绑 / 解绑）
│  ├─ CredentialsUpdateModal.vue # 更新凭据弹窗（cookie 平台：验证回执 handle 必须与当前绑定一致）
│  ├─ RefineModal.vue          # 精细化同步弹窗（三态，见 luogu.md）
│  ├─ SyncBar.vue / PlatformTabs.vue（同步中平台黄点角标）
│  ├─ SyncProgressPanel.vue    # 平台视图右栏同步进行态（进度环 + 百分比 / 不定态）
│  ├─ StatCards.vue / PassBarChart.vue / ActivityHeatmap.vue / SubmissionList.vue
│  └─ platforms/               # 平台专属组件注册表（后续增量，如 LuoguExtrasCard.vue）
```

### 7.2 store 与数据流

- `store.ts`：账号/平台/日序列/提交数据全部来自后端当前组 API；`watch(currentKey)`
  切组后重置视图并重拉数据；`watch([activePlatform, selectedDate])` 联动重拉
  （请求序号防竞态，丢弃过期响应）；**同步为纯后台属性，无全局遮罩**：触发后
  立即转后台低频轮询 `/sync/status`（2s 间隔，状态含 syncProgress 实时合并到
  accounts——账号按钮与平台页签角标即时反映），全部完成后刷新数据；
  页面初始化时若发现账号仍在同步（刷新/重开页面），自动接入后台轮询；
  洛谷首次全量需数分钟（20 条/页 × 5s 反爬间隔），平台视图右栏显示
  SyncProgressPanel（有总量显示百分比进度环，否则不定态环），期间可自由
  切换平台页签与使用模板库等其他功能；
- 平台页签（PlatformTabs）由后端 `/platforms` 返回驱动，前端不硬编码平台清单；
  `types.ts` 的 `PlatformId` 随新平台补充联合类型；
- **凭据平台 UI**（洛谷 / LeetCode CN）：绑定弹窗按 `auth === 'cookie'` 展开——
  洛谷提供「方式一 · 一键登录」（`browserLogin` 可用时）与「方式二 · 手动输入 cookie」；
  **LeetCode CN 仅支持手动输入 cookie**（滑块验证无法通过自动化浏览器，
  `browserLogin` 恒为 `false`），需输入 UID + `LEETCODE_SESSION` + `csrftoken`；
  账号展示一律 `displayName ?? handle`；`syncErrorCode === 'auth_expired'` 时
  账号按钮警示态「凭据过期」，点击打开账号管理弹窗，选择「更新凭据」重新授权
  （验证回执 handle 必须与当前绑定一致），成功后自动触发一次同步；
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
  `aggregate`（口径/时区切天/streak）、`sync`（游标推进/断点续传/失败隔离/
  按组隔离/auth_expired 标记）、`refine`（精化规则/暂停/中止续扫）、
  `service`（用户组 CRUD/组数据隔离/信息卡/绑定同步）；
  `ruff check src tests`；
- 前端 vitest：`model/` 纯函数；`typecheck`、`test`、`build`；
- API 契约：起服务后 `curl http://127.0.0.1:8000/api/diagnostics` 正常返回；
- 手动走查：新建中文组 → 切组 → 绑定 CF 账号首次同步 → 卡片/热力图/柱状图/明细
  渲染 → 组间数据隔离 → 重命名组 → 删除组回退 → 明暗主题与色相切换图表跟随 →
  断网/平台故障时诊断降级不白屏。

## 9. 实施顺序（历史）

已按序完成：设计文档 → 依赖与 gitignore → 数据模型与读写层 → adapters 基座 +
Codeforces → 同步引擎与 API → 前端接入 → 多用户组与信息卡 → 契约扩展与结构清理
→ AtCoder 适配 → 洛谷适配（secrets 凭据框架 + curl_cffi 传输层 + browser-login +
前端凭据 UI）→ 流式拉取与断点续传 → 启动时自动同步 → UNAC 精细化同步
→ LeetCode CN 适配（Cookie + GraphQL Batch Query，无 browser-login）
（详见 [../../../PROGRESS.md](../../../PROGRESS.md)）。

## 10. 既有决策与陷阱（对话确认，勿随意回退）

平台专属的陷阱记录在各平台文档末尾；以下为跨平台约定：

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
- **流式落盘 + 断点续传**：全量回填按批落盘（每页即存），中断后从
  `Account.sync_checkpoint` 续跑；**游标绝不在中途推进**（增量段中途推进
  游标会把未拉取的较旧区段永久漏掉）；断点页码/偏移随新提交漂移由
  `submission_id` 去重吸收（多拉无代价、不漏）；增量同步保持整批完成后
  一次落盘（增量段短，无断点需求）；
- **同步进度为可选契约**：`progress_cb(fetched, total)` 只有总量可知的平台
  （洛谷 records.count）上报；总量未知的平台不报，前端必须兼容不定态；
- **同步无全局遮罩**：同步是后台属性，进行态只落在账号按钮 / 平台页签
  黄点角标 / 平台视图右栏进度面板，不得阻塞其他功能（对话确认）；
- **账号展示名与 API 主键分离**：`handle` 是平台内主键（洛谷为 uid），
  界面显示一律 `displayName ?? handle`；
- **凭据与账号元数据分离存储**：secrets.json 永不入 git；browser-login 抓取的
  凭据由 service 内存暂存 + bind 消费，不经前端。
