# 训练统计聚合（activity）设计

> 状态：设计中。完成后请更新 [README.md](README.md) 索引中的状态。
> 需求背景见 [../cache/requirement.md](../cache/requirement.md)，平台接口依据见 [../cache/platform-api-research.md](../cache/platform-api-research.md)。
> 当前进度：第一期范围（仅做题数据统计）已全部定稿；rating 折线与平台专属信息属后续增量，相关结构已预留。

## 1. 背景与目标

选手的训练数据散落在 Codeforces、AtCoder、洛谷等多个平台，难以直观观察与统计。本功能在用户绑定各平台账号后，自动拉取、整合训练数据，提供默认汇总页与单平台页，展示解题/提交统计、activity 热力图、rating 及其变化折线。需求优先级归属见 [../requirements.md](../requirements.md)「做题统计」。

## 2. 总体形态

### 2.1 关键决策

- **所有对外请求经由本地后端代理**：前端直连各平台会被 CORS 拦截，且凭据（cookie）不能暴露给前端；FastAPI 后端天然承担采集代理角色。
- **adapter 可插拔、失败可降级**：各平台接口稳定性差异大（官方 API / 第三方 API / 非官方接口 / cookie 授权），单平台失败只降级为该平台的诊断信息，不拖垮整个面板（遵循 [conventions.md](conventions.md)「诊断不阻断」）。
- **手动同步为主**：本地应用不常驻运行，后台定时调度收益低。第一期提供"立即同步"按钮 + 每账号新鲜度/上次同步时间/错误状态展示；同步在后台异步执行，前端轮询状态接口。
- **增量同步**：每个 (用户, 平台, 账号) 维护同步游标（CF 按时间过滤、AtCoder 用 `from_second`），重复拉取按提交 id 去重合并。
- **时区**：远端时间戳均为 UTC 秒级，按用户本地时区切"天"聚合。

### 2.2 平台差异适配模式：公共内核 + 平台扩展

平台知识只允许集中在两处：**后端 adapter 目录**、**前端平台组件注册表**；router/service/module 主干保持平台无关（不出现 `if platform == "luogu"` 分支）。

- adapter 声明 `capabilities`（提供哪些数据区块、是否需要凭据）与 `extras` 键集合（平台特有数据，如洛谷咕值、CF contribution）；
- service 按 capabilities 决定拉取与摘要组装，缺能力的字段省略并记诊断；
- router 用同一组端点服务所有平台，绑定流程差异由统一 `credentials` 载荷吸收；
- 前端按 capabilities 条件渲染公共区块，按注册表挂载平台专属组件。

### 2.3 平台优先级（分期）

1. Codeforces（官方 API，匿名可取，风险最低，打通全链路）
2. AtCoder（kenkoooo API + 官方 rating 历史接口，验证框架复用）
3. LeetCode CN + 牛客（GraphQL 路径已探明 / rating 匿名接口）
4. 洛谷（cookie 授权框架，QOJ 等后续平台复用同一套）
5. 长尾平台（评估 `ojhunt` 依赖或手动导入）

## 3. 数据模型与存储

### 3.1 存储位置

统一存储在 `backend/data/user/<userid>/`，支持多个用户组目录。存储层从第一天带 userid 维度，但服务层与 API 第一期固定走 `default`，不暴露用户组管理界面。

非敏感数据入 git（延续"git 管理数据目录"约定），敏感凭据 gitignore：

```
backend/data/user/
├─ example/                     # 提交入 git 的格式样例，兼作后端测试 fixture
│  ├─ profile.json
│  └─ activity/submissions/codeforces_example.jsonl
└─ <userid>/                    # 单用户阶段固定为 default/
   ├─ profile.json              # 用户组信息 + 各平台账号绑定（入 git）
   ├─ activity/
   │  ├─ submissions/<platform>_<handle>.jsonl   # 每 (平台,账号) 一个文件
   │  └─ rating/<platform>_<handle>.json
   └─ secrets.json              # cookie 等凭据（gitignore，仅存本机）
```

`.gitignore` 需补充（实现前先补）：

```
backend/data/user/*/secrets.json
backend/data/user/**/.tmp-*
```

### 3.2 统一提交模型

各平台提交归一化为：

```
Submission {
  platform        # codeforces / atcoder / leetcode-cn / luogu / nowcoder ...
  handle          # 该平台用户名
  submission_id   # 平台内唯一提交 id（去重依据）
  problem_key     # 平台内题目标识（CF "2245F" / AT "abc001_a" / LG "P1001"）
  problem_name
  problem_url
  difficulty      # 原始难度值，不做跨平台归一
  verdict         # AC / WA / CE / RE / TLE / MLE / OLE / UKE
  submitted_at    # UTC 秒级时间戳
  language
}
```

### 3.3 写入约定

沿用 [conventions.md](conventions.md)：写操作经后端 store 层原子写入（临时文件 + `os.replace`），同资源并发写用锁串行化。JSONL 读入合并去重后整体原子替换。

## 4. 页面与交互

### 4.1 信息架构

侧边栏新增「训练统计」组（`NavGroup.icon` 联合类型扩 `'chart'`），子页「数据总览」，路由 `/activity/overview`。第一期**只做一个页面**：页内顶部用分段切换器切视图（汇总 / 各支持平台，页签与绑定状态无关——未绑定平台的视图用于引导绑定与换绑），后续 rating 折线与平台专属卡片直接长在单平台视图内，不再动信息架构。

**用户组**：存储层第一天带 userid 维度（见 §3.1），前端原型阶段即暴露用户组管理：工具条右侧的用户组下拉菜单展示当前用户 ID（与左侧用户信息卡的主标签一致），菜单顶部为「新建用户组」，下方为用户组列表，点击切换。各用户组的档案（ID / 签名 / 头像）、账号绑定与训练数据互相隔离；用户信息卡编辑 ID 即重命名当前组（数据归属不变，靠内部稳定 key 区分）。

### 4.2 页面区块

页面主体为左右双栏（不出现分界线，仅以间距区分）：左栏较窄，右栏较宽；顶部工具条通栏。

1. **工具条**（通栏）：左侧平台分段切换器（汇总 + 全部支持平台）；右侧同步区——上次同步时间（等宽字体 muted）、「立即同步」按钮（lucide `RefreshCw`，同步中旋转禁用）、账号管理弹层（解绑）、以及随视图切换形态的账号入口：
   - **汇总视图**：用户组下拉菜单，按钮显示当前用户 ID（见 §4.1「用户组」）；
   - **平台视图**：显示当前平台绑定账号的 ID（soft 主按钮，lucide `Link2`），未绑定则显示虚线「未绑定账号」；点击进入绑定 / 换绑弹窗（锁定该平台）。同步失败出 warning 徽章，点开看诊断，已有数据照常展示。
2. **左栏 · 用户信息卡**：头像（用户本地上传，前端裁剪缩放为方形后持久化；mock 阶段存 localStorage，后端 `profile.json` 就绪后迁移）、主标签（ID）、副标签（签名）；ID 与签名点击就地编辑。
3. **左栏 · 近期提交**：跨平台合并的最近提交，较新在上。每行：verdict 徽章、题目基本信息（平台 + 题号 + 题名，点击跳平台原站外链）、语言与提交时间。**每页固定 10 条**，底部放分页导航（页码同步到网址，见 §4.7）。点击热力图格子后切换为当日明细（标题变为该日期），**当日明细同样每页 10 条分页**，两种模式的页码状态各自独立；不提供返回按钮——**再次点击同一格子取消选中**，即回到近期提交。
4. **右栏 · 统计卡片行**（四张一排）：总解题数、总提交数、今日解题、连续活跃天数。数字 count-up 滚动，卡片入场 stagger。
5. **右栏 · activity 热力图**：GitHub 式一年图（53 周 × 7 天，周日起始）。hover 时格子上浮（放大 + 投影 + 置顶，不被相邻格遮挡）并出 tooltip（日期 + 提交/通过数）；**点击选中某天**：选中格维持上浮态并加 accent 描边，其余格子淡化且不再响应悬停动效，联动左栏提交列表；再次点击该格取消选中。
6. **右栏 · 柱状图行**（洛谷主页风格，两张并排，窄屏堆叠）：左「近 7 天通过」日粒度、右「近 12 个月通过」月粒度，均为 AC 数；accent 色圆角柱，hover tooltip。

verdict 徽章配色固定、不随主题色相变化：AC 绿、WA 红、CE 黄、RE 紫，TLE / MLE / OLE / UKE 深蓝。

### 4.3 热力图着色规则

按用户拍板：提交与 AC 分层——

| 档位 | 条件 | 色阶 |
| --- | --- | --- |
| 0 | 无提交 | 空格（`var(--surface-2)`） |
| 1 | 有提交、0 AC | 最低透明度档 |
| 2–5 | AC ≥ 1，按 AC 数分桶（1–2 / 3–5 / 6–9 / ≥10） | 透明度逐级升高 |

颜色不写死：全部用 `hsl(var(--hue) …)` 分档透明度，随主题色相与明暗联动。档位映射在 `model/heatmap.ts` 纯函数完成。

### 4.4 统计口径

- 解题数 = 当天 AC 的**不同题目数**（重复提交不重复计）；汇总页不做跨平台去重；
- 连续天数按"当天有 AC"计；今天尚无 AC 时不算断签，统计到昨天为止的连续段；
- 热力图固定近一年，不做范围切换。

### 4.5 空状态与绑定流程

- **未绑定任何账号**：整页引导空状态（PlaceholderPage 风格：图标 + hint +「绑定第一个账号」按钮，平台自由选择）；平台视图未绑定时由工具条的「未绑定账号」按钮引导绑定；
- **绑定弹窗**：平台下拉（capabilities 驱动，第一期仅 Codeforces）→ handle 输入 →「验证」（调后端确认用户存在，成功回执一行平台内基本信息）→「确认绑定」→ 自动触发首次同步；从平台视图打开时锁定该平台；
- **换绑**：**每个平台在每个用户组下只保留一个绑定账号**。平台视图点击已绑定的账号 ID 打开换绑弹窗（标题与确认按钮变为「换绑」），绑定新账号即替换旧账号并删除其本地数据；
- **解绑**：账号管理弹层内操作，DeleteConfirmModal 同款确认；解绑删除该账号本地数据，明确提示不可找回。

### 4.6 图表主题桥接

配色在 JS 侧统一生成：`model/echarts-theme.ts` 经 `getComputedStyle` 读取 `--hue`/`--text`/`--surface-2` 等 CSS 变量产出配色对象；组件用 MutationObserver 监听 `documentElement` 的 `data-theme` 与 `style`（`--hue`）变化，ECharts 图触发 `setOption` 刷新，热力图格子直接以内联背景色刷新。不反向依赖 App 的 `useTheme` 实例。

### 4.7 网址状态同步

平台筛选、热力图选中日期与列表页码写入网址 query（`?platform=codeforces&date=2026-08-13&page=2`）：`all`、无选中日期与第 1 页为缺省值，不出现在网址中；`page` 始终表示当前列表（近期提交或当日明细）的页码。切换平台重置日期与页码为缺省；选中/切换日期时当日明细页码回到第 1 页；翻页保留筛选与选中日期；非法日期回退为未选中。刷新、浏览器前进/后退与复制链接均能恢复同一视图。

## 5. 工程落地

### 5.1 后端结构

```
backend/src/
├─ adapters/                    # 顶层平台适配层，跨功能复用（未来比赛功能共用）
│  ├─ base.py                   # PlatformAdapter 协议、capabilities 声明、显式注册表、共享模型
│  ├─ net.py                    # 外呼公共层：httpx 封装、限流间隔、退避重试
│  ├─ codeforces/__init__.py    # 简单平台单文件承载
│  ├─ atcoder/__init__.py
│  └─ luogu/                    # 复杂平台按能力拆文件（auth.py / records.py / parser.py）
├─ routers/activity/router.py   # HTTP 边界，只做参数校验与转发，平台无关
├─ services/activity/service.py # 门面：账号 CRUD/绑定验证、触发同步、聚合读取、诊断
│                                # 沿用 init_activity_service(settings) 的 lifespan 单例模式
└─ modules/activity/
   ├─ models.py                 # Submission / RatingPoint / Account / SyncCursor 等领域模型
   ├─ schemas.py                # API 出入参 DTO（与 models 分离）
   ├─ store.py                  # data/user/<userid>/ 读写层（原子写、锁）
   ├─ credentials.py            # secrets.json 存取
   ├─ sync.py                   # 增量同步引擎：游标推进、去重合并、单账号锁、失败隔离
   └─ aggregate.py              # 纯函数：submissions → 按天聚合/总览统计（无 IO）
```

约束：

- 依赖方向严格单向：`routers → services → modules → adapters`，adapters 不反向依赖任何功能域；
- adapter 只允许被 `sync.py` 与 `service.py` 触碰，router 不直接 import adapter；
- adapter 注册采用**显式注册表**（`base.py` 手写注册，静态可查），不用自动发现；
- 新增平台的后端成本 = 一个 adapter 目录 + 注册一行，主干零改动。

新依赖：`httpx` 从 dev 组提升到主依赖；重试退避手写，不引新库。

### 5.2 API

端点平台无关；概览响应预留 `capabilities` 与 `extras` 字段（第一期为空）；绑定用统一端点 + 可选 `credentials` 载荷。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/activity/platforms` | 平台元数据（id/名称/capabilities）+ 已绑定账号及各账号同步状态 |
| POST | `/api/activity/accounts/verify` | 校验 `{platform, handle}` 存在性，回执平台内用户基本信息 |
| POST | `/api/activity/accounts` | 绑定账号 `{platform, handle, credentials?}`，成功后自动触发首次同步 |
| DELETE | `/api/activity/accounts/{platform}/{handle}` | 解绑并删除该账号本地数据（204） |
| GET | `/api/activity/overview?platform=` | 概览：all-time 总量 + streak + 近 370 天日序列 `[{date, submissions, solved}]`；缺省为汇总 |
| GET | `/api/activity/submissions?date=&platform=` | 某日提交明细（平台过滤可选） |
| POST | `/api/activity/sync` | 触发同步 `{platform?}`，空为全部账号；立即返回 |
| GET | `/api/activity/sync/status` | 各账号同步状态（idle/running/上次结果/错误诊断），前端 1.5s 轮询 |

柱状图（近 7 天 / 近 12 月 AC 数）由前端 `model/bars.ts` 从日序列派生，不单独出 API。streak 由后端计算（可能超过日序列窗口）。

### 5.3 前端落地

```
frontend/src/features/activity/
├─ ActivityPage.vue             # 汇总页（默认落地页）
├─ PlatformPage.vue             # 单平台独立页（后续增量；第一期为页内分段切换，见 §4.1）
├─ api.ts / store.ts / types.ts
├─ model/                       # 纯函数层（vitest 覆盖）
│  ├─ heatmap.ts                # 日序列 → 档位映射（着色规则见 §4.3）
│  ├─ bars.ts                   # 日序列 → 近 7 天 / 近 12 月 AC 柱状数据
│  ├─ echarts-theme.ts          # CSS 变量 → ECharts 配色对象（主题桥接，见 §4.6）
│  ├─ rating-tiers.ts           # 各平台 rating 分档/配色表（后续增量）
│  └─ ...
└─ components/
   ├─ UserProfileCard.vue       # 用户信息卡（头像上传 / ID / 签名就地编辑）
   ├─ UserGroupMenu.vue         # 用户组下拉菜单（汇总视图；新建/切换用户组）
   ├─ AccountBindModal.vue      # 绑定/解绑/凭据录入
   ├─ SyncStatusBar.vue         # 新鲜度 + 手动同步 + 错误诊断
   ├─ OverviewCards.vue         # 跨平台总数据
   ├─ PassBarChart.vue          # 通过数柱状图（日/月两种粒度复用）
   ├─ ActivityHeatmap.vue       # GitHub 式热力图（DOM 网格，上浮/选中动效）
   ├─ RatingChart.vue           # rating 折线 + 分档底色（后续增量）
   └─ platforms/                # 平台专属组件注册表（如 LuoguExtrasCard.vue）
```

约束：

- extras 在 `types.ts` 用判别联合类型（`LuoguExtras | CodeforcesExtras | ...`）保类型安全；
- `PlatformPage.vue` 按 capabilities 条件渲染公共区块 + 查表挂载专属区块；
- 柱状图自第一期起引入 **ECharts**：按需引入（`echarts/core` + Bar/Grid/Tooltip，SVGRenderer）；主题桥接见 §4.6；rating 折线期追加 LineChart 与分档底色；
- 热力图用 DOM 网格实现（悬停上浮、选中淡化等逐格动效在 ECharts calendar 上难以做到），格子配色复用 §4.6 的配色对象；
- `app/nav.ts`、`app/router.ts` 各加一条，替换占位页。

## 6. 验证方式

- 后端：`aggregate`（口径/时区切天）、`store`（原子写/去重合并）、`sync`（游标推进/失败隔离）、CF adapter（录制 JSON fixture 解析）的 pytest；`ruff check`；
- 前端：`model/` 纯函数 vitest（heatmap 档位、bars 派生、echarts-theme）；`typecheck`、`test`、`build`；
- API 契约：起服务后 `curl http://127.0.0.1:8000/api/diagnostics` 正常返回；
- 手动走查：绑定 CF 账号 → 首次同步 → 卡片/柱状/热力图/明细渲染 → 点击格子联动明细 → 明暗主题与色相切换下图表跟随 → 断网/平台故障时诊断降级不白屏。

## 7. 实施顺序（原子化提交计划）

1. `docs: 添加训练统计聚合设计文档`
2. `chore: 补充 activity 数据目录 gitignore 与 httpx/echarts 依赖`
3. `feat(后端): 实现 activity 数据模型与 user 目录读写层（含 example 样例）`
4. `feat(后端): 搭建 adapters 基座并实现 Codeforces 适配器`
5. `feat(后端): 实现同步引擎与 activity API`
6. `feat(前端): 搭建数据总览页骨架与绑定/同步交互`
7. `feat(前端): 实现统计卡片、柱状图、热力图与明细列表`
8. `docs: 标记训练统计聚合设计文档为已实现`
