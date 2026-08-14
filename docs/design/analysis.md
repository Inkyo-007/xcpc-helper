# 训练分析（analysis）设计

> 状态：设计中。
> 本功能是「训练统计（activity）」的增量：在数据总览与技能树之外，新增**多维度诊断**与**可配置在线 LLM 分析报告**，
> 复用 activity 提交数据与用户组隔离，不新建功能域、不新建存储。

## 1. 背景与目标

选手已经能从「数据总览」看到热力图/统计卡片/柱状图，从「技能树」看到算法强弱。但这些都是**展示**，
缺一层**诊断**：难度分布在哪一档、错误集中在哪里（WA/TLE…）、训练节奏是否三天打鱼两天晒网、
哪些技能「投入多却过不了」。本功能把提交数据聚合成四个维度的诊断视图，并支持一键生成自然语言分析报告。

需求优先级归属见 [../requirements.md](../requirements.md)「做题统计」。

## 2. 总体形态与关键决策

- **纯派生视图，不新建存储**：训练分析是提交数据的纯函数聚合，输入即 `data/user/<user_id>/` 下提交 JSONL，
  后端只加聚合纯函数与只读端点；LLM 报告为可选增强，未配置/失败时降级为规则化报告，均不落盘。
- **薄弱点复用技能树映射**：薄弱点检测与技能树共用 `skill_tree.py` 的 `TAG_TO_DOMAIN` / `TAG_NAME` /
  `DOMAIN_ORDER` 与 `proficiency` 公式，保证「分析页的薄弱点」与「技能树的掌握度」口径一致、同源。
- **难度按原始数值分档**：难度分布沿用 `difficulty: int | str | None` 原始值，按 rating 分档（CF 直接映射；
  AtCoder kenkoooo 分与 CF rating 同桶仅作近似，跨平台尺度差异在页面副标题注明）。非数值难度归「未知」。
- **LLM = OpenAI 兼容 chat/completions**：`XCPC_LLM_*` 环境变量配置 base_url / api_key / model（默认
  DeepSeek，可换任意 OpenAI 兼容服务）；`api_key` 为空即视为未配置 → 走规则化报告（纯函数，离线零依赖）。
- **独立子页** `/activity/analysis`：「训练统计」组下，位于「数据总览」与「技能树」之间。

## 3. 数据模型与聚合口径

输入为当前用户组的全部提交（`Submission`，含 `tags` / `verdict` / `difficulty` / `submitted_at`）。
四个维度的口径如下（纯函数 `modules/activity/analysis.py`，无 IO，camelCase 输出对齐前端 types.ts）。

### 3.1 难度分布（difficulty）

按「去重后的不同题目」分档。同一题（`platform, problem_key`）多次提交合并：难度取该题提交的
最大数值难度、AC 以「该题是否存在 AC」计、提交数累加。

| 档 | 范围 |
| --- | --- |
| ≤1199 | `difficulty <= 1199` |
| 1200–1399 / 1400–1599 / … / 2600+ | 每 200 一档，最后 `>= 2600` |
| 未知 | `difficulty is None` 或非数值字符串 |

每档输出 `{ label, min, max, solvedCount, attemptCount, submissionCount, passRate }`：
`solvedCount`=去重 AC 题数、`attemptCount`=去重尝试题数（任意 verdict）、
`submissionCount`=该档提交总数、`passRate = solvedCount / attemptCount`（无尝试为 0）。

### 3.2 verdict 分布（verdicts）

按 `Verdict` 枚举声明顺序 `AC/WA/CE/RE/TLE/MLE/OLE/UKE/JG` 统计提交计数与占比。
输出 `{ verdict, count, share }`（`share = count / total`，total 为 0 时 share=0）。

### 3.3 训练节奏与活跃度（rhythm）

- `weeks`：近 12 周（含本周），每周 `{ weekStart, solved, attempts, activeDays }`——`solved`=去重 AC 题数、
  `attempts`=提交总数、`activeDays`=有提交的不同天数；升序，末尾为本周期。
- `hours`：0–23 小时提交数 `{ hour, count }`（按后端本地时区 `datetime.fromtimestamp` 切小时）。

### 3.4 薄弱点检测（weakPoints）

只统计**带标签**的提交（CF 标签；AtCoder 无标签不参与，与技能树一致）。每个 CF 标签是一个技能：

- `attemptCount` = 该标签下去重的「尝试题」（任意 verdict，标签来自题目 `tags`，每提交展开到其全部标签）；
- `solvedCount` = 该标签下去重的「AC 题」；
- `passRate = solvedCount / attemptCount`；
- `proficiency` = 复用 `skill_tree.proficiency`（对 `solvedCount` 对应的 AC 题难度权重累加套指数饱和，口径与技能树一致）；
- `maxDifficulty` = 该标签下 AC 题最高原始难度；
- `suggestion` = 规则化建议：`passRate < 0.3` →「基础薄弱，建议从该标签入门题系统刷起」；
  `0.3 ≤ passRate < 0.6` →「有一定基础，建议集中补该标签中等难度题」；否则 →「接近熟练，可上难度挑战」。

排序：弱点评分 `attemptCount × (1 - passRate)` 降序（投入多、通过少的最靠前）；仅保留 `attemptCount ≥ 2` 的技能，
取前 20 条。输出 `{ key, name, domainKey, domainName, solvedCount, attemptCount, passRate, proficiency, maxDifficulty, suggestion }`。

## 4. API 契约

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/activity/analysis?platform=` | 当前用户组四维聚合 `AnalysisOut`（platform 可选，缺省汇总） |
| POST | `/api/activity/analysis/report` | 生成分析报告 `ReportOut`（body 可选 `{ platform? }`；有 LLM 配置走 LLM，否则规则化降级） |
| GET | `/api/activity/analysis/report/config` | `ReportConfigOut`：`{ configured, model, baseUrl }`（不泄露 api_key，供前端提示「未配置」） |

`AnalysisOut`：

```jsonc
{
  "difficulty":  [ { "label", "min", "max", "solvedCount", "attemptCount", "submissionCount", "passRate" } ],
  "verdicts":    [ { "verdict", "count", "share" } ],
  "rhythm":      { "weeks": [ { "weekStart", "solved", "attempts", "activeDays" } ], "hours": [ { "hour", "count" } ] },
  "weakPoints":  [ { "key", "name", "domainKey", "domainName", "solvedCount", "attemptCount", "passRate", "proficiency", "maxDifficulty", "suggestion" } ]
}
```

`ReportOut`：`{ "content": "markdown 正文", "source": "llm" | "rule", "model": "…|null", "note": "…|null" }`。

## 5. LLM 分析报告

### 5.1 配置（core/config.py，`XCPC_` 前缀环境变量可覆盖）

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `llm_base_url` | `https://api.deepseek.com/v1` | OpenAI 兼容 base URL |
| `llm_api_key` | `""` | 空 = 未配置（走规则化降级） |
| `llm_model` | `deepseek-chat` | 模型名 |
| `llm_timeout_seconds` | `60.0` | 单次调用超时 |
| `llm_max_tokens` | `2048` | 生成上限 |

### 5.2 调用与降级

- 客户端 `services/activity/llm.py::LlmClient`：httpx POST `{base_url}/chat/completions`，
  消息含 system（竞赛教练人设 + 输出中文 markdown 要求）与 user（把 `AnalysisOut` + `overview` 总量
  序列化为紧凑 JSON 摘要）；可注入 `httpx.MockTransport` 供测试。
- `POST /report` 流程：先算 `analysis` 聚合 → 若 `api_key` 非空则调 LLM，返回 `source="llm"`；
  未配置或调用异常（网络/4xx/超时）→ `build_rule_report(analysis, overview)` 纯函数生成中文 markdown，
  `source="rule"` 并带 `note` 说明降级原因。LLM 失败**不**抛 500（降级不阻断，对齐 conventions「诊断不阻断」）。
- `build_rule_report` 至少覆盖：总体概况、难度分布解读、提交质量（verdict 占比）、训练节奏、薄弱点清单（逐条带建议）、下一步行动建议。

## 6. 前端落地

### 6.1 页面结构（AnalysisPage.vue，`/activity/analysis`）

整页滚动、卡片式布局，标题「训练分析」+ 副标题 + 「刷新」「生成 AI 报告」操作：

1. **难度分布**：横向条形图（ECharts bar，复用 `ChartHost`/`model/echarts-theme.ts` 主题桥接），
   x 轴为档位、y 轴为去重题数，叠加 solved / attempted 双序列，副标题注明跨平台尺度近似；
2. **提交质量（verdict 分布）**：环形饼图（ECharts pie），verdict 配色沿用徽章固定色（AC 绿/WA 红/…），
   中心显示总提交数；
3. **训练节奏**：近 12 周柱状图（solved / attempts）+ 活跃时段（0–23 小时）小图；
4. **薄弱点**：按域分组的卡片列表，每条显示技能名、掌握度进度条、通过率、尝试/AC 数、建议文案；
5. **AI 报告**：卡片内「生成 AI 报告」按钮 → 调 `/report` → 用 `shared/components/MarkdownView.vue` 渲染；
   `source="rule"` 时以次强调文案提示「当前为规则化报告，配置 XCPC_LLM_API_KEY 后可用在线 LLM 生成」；
   未配置（`report/config.configured=false`）时按钮旁直接给提示。

### 6.2 精修方向（数据总览 + 技能树 + 分析页，聚焦训练统计页面）

依据 frontend-design skill 原则，在不改设计令牌主体、不写死颜色的前提下：

- **层级与节奏**：统一区块卡片（`--surface` + 1px 边框 + `--radius`）的 padding 与标题字号，区块标题带
  左侧 3px 强调条（复用 `bar-pop` 思路），页头标题/副标题字号层级一致；
- **留白与对齐**：数据总览左右栏间距、统计卡片行网格间距统一为 8/12/16px 节奏，卡片内部数字与标签对齐；
- **空态与失败态**：统一「图标 + 一句话 + 动作按钮」文案（失败态给出可执行的下一步），与技能树页空态一致；
- **图表一致性**：技能树/分析页图例、tooltip 文案格式统一（`名称 · 数值 · 说明`），hover 反馈一致；
- **克制动效**：只保留入场 stagger 与 hover 微交互，避免堆砌；尊重 `prefers-reduced-motion`（main.css 已全局兜底）。

## 7. 工程落地

```
backend/src/
├─ core/config.py                    # 增 llm_* 配置项
├─ modules/activity/
│  ├─ skill_tree.py                  # _weight 提为公开 difficulty_weight（内部调用同步改）
│  ├─ analysis.py                    # 新增：四维聚合纯函数（无 IO）
│  ├─ report.py                      # 新增：build_prompt / build_rule_report 纯函数（无 IO）
│  └─ schemas.py                     # 新增 AnalysisOut / ReportOut / ReportConfigOut 等 DTO
├─ services/activity/
│  ├─ llm.py                         # 新增：LlmClient（httpx，OpenAI 兼容，可注入 MockTransport）
│  └─ service.py                     # 新增 analysis() / report() / report_config()
└─ routers/activity/router.py        # 新增 GET /analysis、POST /analysis/report、GET /analysis/report/config

backend/tests/activity/
├─ test_analysis.py                  # 四维聚合口径（去重/分桶/时区/薄弱点评分）单测
└─ test_report.py                    # 规则报告 + prompt 结构 + LlmClient(MockTransport) 单测

frontend/src/features/activity/
├─ types.ts                          # 新增 Analysis 相关类型
├─ api.ts                            # 新增 fetchAnalysis / fetchAnalysisReport / fetchReportConfig
├─ model/echarts-setup.ts            # 注册 PieChart / LegendComponent
├─ model/analysis.ts                 # 新增：聚合数据 → ECharts option 纯函数（vitest 覆盖）
├─ AnalysisPage.vue                  # 新增：训练分析页
├─ components/
│  └─ analysis/                      # 新增：DifficultyChart / VerdictChart / RhythmChart / WeakPoints / ReportCard
├─ components/SkillTree.vue          # 精修
├─ SkillTreePage.vue                 # 精修
└─ ActivityPage.vue                  # 精修
```

导航 `nav.ts` 与 `router.ts` 各加「训练分析 /activity/analysis」条目（数据总览与技能树之间）。

## 8. 验证方式

- 后端：`uv run pytest`（新增 test_analysis / test_report 全绿）、`uv run ruff check src tests`；
- 前端：`npm run typecheck`、`npm run test`（新增 analysis 纯函数用例）、`npm run build`；
- API 冒烟：起服务后 `curl /api/diagnostics`、`/api/activity/analysis`、
  `POST /api/activity/analysis/report`（未配置时返回 rule 报告）、`/api/activity/analysis/report/config` 正常；
- 手动走查：绑定 CF 账号 → 同步 → 分析页四图渲染 → 薄弱点与技能树口径一致 → 生成 AI/规则报告 → 明暗主题跟随。

## 9. 实施顺序

1. `docs: 添加训练分析（四维聚合 + LLM 报告）设计文档`
2. `feat(后端): 实现四维训练分析聚合纯函数与 API 端点`
3. `feat(前端): 新增训练分析页（难度/verdict/节奏/薄弱点）`
4. `feat(前端): 精修训练统计页面（数据总览/技能树/分析页）`
5. `feat(后端): 接入可配置在线 LLM 分析报告（规则化降级）`
6. `feat(前端): 训练分析页接入 AI 报告生成`
7. `docs: 标记训练分析设计文档为已实现`
