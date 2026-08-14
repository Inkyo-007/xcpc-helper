# 技能树可视化（skill-tree）设计

> 状态：设计中。完成后请更新 [README.md](README.md) 索引中的状态。
> 本功能是「训练统计（activity）」的增量，复用其提交数据与用户组隔离，不新建功能域。

## 1. 背景与目标

选手的训练数据已由 activity 功能自动导入（Codeforces / AtCoder），但现有「数据总览」页只呈现
热力图、统计卡片与提交列表，无法直观回答「我哪些算法强、哪些还薄弱」。本功能把 AC 过的题目
按算法标签聚合成一棵**技能树**：以放射状 SVG 呈现「根 → 技能域 → 技能」两级结构，节点颜色深浅、
大小按掌握度（0~1）缩放，hover 显示做题数、最高难度与掌握度百分比，帮助选手快速定位训练短板。

需求优先级归属见 [../requirements.md](../requirements.md)「做题统计」。

## 2. 总体形态

### 2.1 关键决策

- **复用 activity 数据，不新建存储**：技能树是提交数据的纯派生视图，输入即 `data/user/<user_id>/`
  下的提交 JSONL；后端只加一个聚合纯函数与一个只读端点，不引入新落盘文件。
- **技能来源 = Codeforces 标签（第一期）**：CF `user.status` 每道题自带 `problem.tags`，是最细粒度、
  无需额外请求的技能信号。AtCoder 无标签，其提交不参与技能映射（保留后续按难度分档扩展的空间）。
  因此第一期技能树只反映 Codeforces 数据，页面空状态文案说明这一点。
- **自定义 SVG 放射状布局，不引 D3 / cytoscape**：节点数少（数十个），手写径向布局即可做到
  「炫酷」的入场上浮、掌握度着色与 hover 动效，避免为一次性图表引入重型依赖（对齐 global.md 第 6 条）。
- **掌握度 = AC 难度加权累加的指数饱和**：单题按难度给权重，累加后经 `1 - e^(-score/3)` 压到 0~1，
  早期增长快、后期放缓，避免一两道水题刷满、也避免高难度题被淹没（公式见 §3.3）。
- **只统计「AC 过的不同题目」**：同一题多次提交按 `(platform, problem_key)` 去重，只有 verdict=AC 计入，
  与 activity 的「解题数」口径一致。

### 2.2 方案选型（含否决项）

| 方案 | 结论 | 理由 |
| --- | --- | --- |
| ECharts graph / tree | 否决 | 树节点动效（逐个上浮、按掌握度渐变、hover 置顶）在 ECharts 上受制于其渲染器，且 activity 已为柱状图引入 ECharts，技能树更依赖精细 SVG 动画 |
| D3 / cytoscape | 否决 | 节点数量级小，收益不足以抵消新增依赖 |
| 力导向图（force） | 否决 | 布局不确定、每次抖动，不利于「稳定对比强弱」的阅读体验 |
| 自定义 SVG 径向树 | **采用** | 布局纯函数可单测，颜色直接读 CSS 变量随主题联动，动效可控 |

## 3. 数据模型与存储

### 3.1 提交模型补字段

技能树依赖题目标签，需在归一化提交模型上补一个可选字段（向后兼容：旧 JSONL 无该字段时按空列表
解析，`merge_submissions` 的 `model_validate_json` 不报错）：

```python
# adapters.base.PlatformSubmission / modules.activity.models.Submission 各加一行
tags: list[str] = Field(default_factory=list)  # 题目标签（CF problem.tags；AtCoder 无）
```

CF 适配器在 `_to_submission` 里透传 `problem.tags`（`CfProblem` 补 `tags` 字段）；AtCoder 恒为空。
标签只在**新同步**的提交上落盘：已存在的历史提交（旧格式无标签）不会被增量游标重新拉取，故
需要用户「解绑后重新绑定」或等待后续提交才逐步补齐标签——这是增量同步的自然代价，文档明示。

### 3.2 技能域与标签映射（后端常量表）

两级结构：**技能域**（domain，12 个固定类别）→ **技能**（skill，即 CF 标签，中文名）。

| 技能域 key | 中文名 | 覆盖的 CF 标签 |
| --- | --- | --- |
| data_structures | 数据结构 | data structures / dsu / trees / hashing |
| graphs | 图论 | graphs / dfs and similar / shortest paths / flows / graph matchings / 2-sat |
| dynamic_programming | 动态规划 | dp |
| math | 数学 | math / number theory / combinatorics / chinese remainder theorem / fft / matrices / probabilities |
| geometry | 计算几何 | geometry |
| strings | 字符串 | strings / string suffix structures |
| greedy | 贪心 | greedy |
| search | 搜索 | brute force / meet-in-the-middle / divide and conquer |
| implementation | 构造与实现 | implementation / constructive algorithms / expression parsing / interactive / schedules |
| basics | 基础算法 | binary search / ternary search / two pointers / sortings |
| bitmasks | 位运算 | bitmasks |
| games | 博弈 | games |

未命中上表的标签归入 `other`（其他）域，保证不漏数。技能中文名由 `TAG_NAME` 表逐标签给出，
未命中直接用原英文标签。

### 3.3 掌握度公式

```python
def _weight(difficulty: int | str | None) -> float:
    if difficulty is None or isinstance(difficulty, str):
        return 0.5                          # 未知 / 非数值难度给基础权重
    return max(0.5, float(difficulty) / 1000.0)   # CF rating：800→0.8，2000→2.0

def proficiency(weights: list[float]) -> float:
    if not weights:
        return 0.0
    return round(min(1.0, 1.0 - math.exp(-sum(weights) / 3.0)), 4)
```

- 每个「AC 过的不同题目」贡献一个 `_weight(difficulty)` 权重到其每个标签；
- 技能节点掌握度 = 该技能全部 AC 题权重累加后套 `proficiency`；
- 技能域掌握度 = 其下属技能权重的并集累加后套 `proficiency`（域与技能口径一致，取并集而非平均）；
- `maxDifficulty` = 该节点下 AC 题的最高原始难度；`acCount` = 去重后的 AC 题数。

### 3.4 输出契约

```
SkillTreeOut {
  domains: [ SkillDomainOut ]      # 按 DOMAIN_ORDER 固定顺序
  totals:  { acCount, proficiency, maxDifficulty }
}
SkillDomainOut { key, name, proficiency, acCount, maxDifficulty, skills: [SkillOut] }
SkillOut       { key, name, tag, proficiency, acCount, maxDifficulty }
```

域内技能按 `acCount` 降序（并列按 tag 字典序），让「练得最多」的技能排在前面。

## 4. 页面与交互

### 4.1 信息架构

「训练统计」组下新增子页「技能树」，路由 `/activity/skill-tree`（独立于「数据总览」页，
给放射状树留出整页空间）。侧边栏 `nav.ts` 与 `router.ts` 各加一条。

### 4.2 页面结构

整页居中布局，标题「技能树」+ 副标题（说明基于 Codeforces 标签、掌握度口径）。主体为响应式 SVG：

- **根节点**：中心圆，显示「技能树」与全站总掌握度百分比；
- **第一环 · 技能域**：12 个域节点按固定角度均布（顶端正上方起始、顺时针），节点大小随域掌握度缩放，
  颜色 = accent 色相按掌握度取透明度/饱和度；
- **第二环 · 技能**：每个域下的技能节点围绕其父域扇形排布，叶子节点更小，同样按掌握度着色；
- **连线**：根 → 域为直线，域 → 技能为二次贝塞尔曲线（`path` 的 `Q` 指令），线宽/透明度随子节点掌握度渐变；
- **动效**：入场时节点按深度顺序 stagger 上浮 + 淡入；hover 某节点时其子树连线高亮、该节点放大并出
  tooltip（`名称 · AC 数 · 最高难度 · 掌握度%`），其余节点轻度降饱和（呼应热力图的选中淡化）。

### 4.3 着色与主题桥接

颜色不写死：沿用 `model/echarts-theme.ts` 的思路，组件层 `getComputedStyle` 读取 `--hue` / `--text` /
`--surface-2` 等 CSS 变量，节点填充 `hsla(var(--hue), 68%, L%, α)`，α 随掌握度线性映射（0→0.15，1→1），
明暗主题与色相切换自动跟随（MutationObserver 监听，与热力图一致）。

### 4.4 空状态

- 未绑定 Codeforces / 无 AC 提交：居中空态（图标 + hint +「去绑定 Codeforces 账号」按钮，跳转
  `/activity/overview` 引导绑定）；
- 有 AC 但无标签（如历史旧数据）：提示「历史数据缺少标签，重新同步后可生成技能树」。

## 5. 工程落地

### 5.1 后端结构

```
backend/src/
├─ adapters/
│  ├─ base.py                        # PlatformSubmission 补 tags
│  └─ codeforces/
│     ├─ api_models.py               # CfProblem 补 tags
│     └─ __init__.py                 # _to_submission 透传 tags
├─ modules/activity/
│  ├─ models.py                      # Submission 补 tags
│  ├─ skill_tree.py                  # 新增：DOMAIN_ORDER / TAG_TO_DOMAIN / TAG_NAME / build_skill_tree（纯函数，无 IO）
│  └─ schemas.py                     # 新增 SkillOut / SkillDomainOut / SkillTreeOut
├─ services/activity/service.py      # 新增 skill_tree(platform=None)
└─ routers/activity/router.py        # 新增 GET /api/activity/skill-tree
```

依赖方向不变：`routers → services → modules`；`skill_tree.py` 只 import `models.Submission` 与
`adapters.base.Verdict`，与 `aggregate.py` 同级、无 IO。

### 5.2 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/activity/skill-tree?platform=` | 当前用户组全部账号（可按平台过滤）AC 题聚合的技能树；缺省汇总 |

### 5.3 前端落地

```
frontend/src/features/activity/
├─ types.ts                          # 新增 SkillNode / SkillDomain / SkillTree 类型
├─ api.ts                            # 新增 fetchSkillTree(scope) 与响应类型
├─ model/skill-tree.ts               # 新增：径向布局纯函数（角度/半径/坐标 → 节点渲染模型）
├─ model/skill-tree.test.ts          # 新增：布局与掌握度映射单测
├─ components/SkillTree.vue          # 新增：SVG 放射状技能树（连线/节点/动效/tooltip）
└─ SkillTreePage.vue                 # 新增：整页（加载/空态/主题桥接/切组刷新）
```

无新增依赖；复用 `shared/api/client` 与 lucide 图标。纯函数覆盖角度分配、半径计算与
「数据 → 渲染节点」映射，供 vitest 覆盖。

## 6. 验证方式

- 后端：`skill_tree` 纯函数 pytest（去重口径、标签→域映射、掌握度公式边界：空集=0、满集=1、
  难度 None 兜底、未命中标签归 other）；CF adapter 的 `tags` 透传用现有 fixture 补断言；`ruff check`。
- 前端：`model/skill-tree.test.ts` 覆盖布局纯函数；`npm run typecheck` / `npm run test` / `npm run build`。
- API 契约：起服务后 `curl http://127.0.0.1:8000/api/diagnostics` 与
  `curl http://127.0.0.1:8000/api/activity/skill-tree` 正常返回。
- 手动走查：绑定 CF 账号 → 同步 → 技能树渲染各域/技能 → hover tooltip → 明暗主题与色相切换跟随 →
  无数据时空态引导。

## 7. 实施顺序（原子化提交计划）

1. `docs: 添加技能树可视化设计文档`
2. `feat(后端): 提交模型与 CF 适配器补充题目标签字段`
3. `feat(后端): 实现技能树聚合纯函数与 API 端点`
4. `feat(前端): 新增技能树 SVG 可视化页面与布局模型`
5. `docs: 标记技能树设计文档为已实现`
