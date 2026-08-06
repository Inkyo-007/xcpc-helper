# 模板整理功能 需求分析与设计参考

> 本文档基于"算法竞赛选手的模板代码管理"这一场景，分析用户真实需求，
> 给出功能清单（含优先级）、数据模型草案与技术栈建议，作为开发参考。

## 1. 背景与痛点分析

### 现状工作流

1. 选手平时刷题时，把可复用的模板代码（线段树、网络流、FFT 等）手动建目录、手动分类保存在本地；
2. 线上赛时，翻阅本地目录，找到文件、打开、复制、粘贴到评测页面；
3. 线下赛前，把所有代码手动拼进一个 markdown 文件，导出 PDF 打印，赛场翻阅。

### 核心痛点

| 痛点 | 根因 |
| --- | --- |
| 整理成本高 | 新建/移动/重命名模板都要操作文件系统，命名和目录规范靠自觉 |
| 找模板慢 | 只能按目录层级翻，无法按关键词、标签、来源题目搜索 |
| 信息割裂 | 代码是一个文件，说明/复杂度/验证题目记在别处（或不记） |
| 打印流程繁琐 | 手动拼接 markdown，顺序、格式、分页都要人肉维护，改一处就要重拼 |
| 多语言/多变体难管理 | 同一算法的 C++/Python 版本、不同实现变体散落在不同文件 |

### 两类使用场景的差异（影响设计）

- **线上赛场景**：追求"快"。秒级检索、一键复制、界面不碍事。
- **线下赛场景**：追求"全且稳"。打印材料结构清晰、可定制、可离线生成。

## 2. 功能需求清单

### P0：基本功能

**模板库**
- 模板的显示页面：标题、分类、标签（多选）、代码、语言、说明（markdown）、复杂度、来源题目链接。
- 代码编辑器：语法高亮（C++/Python/Java 优先）、行号、只读预览模式。
- 一键复制代码到剪贴板。
- 同一模板下的多语言/多变体管理（一个模板卡片下挂多个代码版本）。

**检索与浏览**
- 左侧分类 + 标签过滤 + 关键词搜索（标题/说明/代码全文）。
- 模板列表支持按更新时间/名称/自定义优先级排序。

### P1：增量功能

**打印册**
- 从模板库中按版本勾选模板，与章节标题、自由文字、图片、显式分页符组合为有序块序列，生成单本"打印册"（Print Book），支持拖拽排序与指定位置插入。
- 导出 PDF：固定版式封面、带页码的层级目录、每模板一节（标题 + 元信息 + 代码块 + 可选说明框）、中文字体与公式支持（Paged.js 打印管线，详见第 4 节"打印册"）。
- 打印册模板化：保存多套打印册配置（如"ICPC 区域赛版"、"校内赛版"），可重复导出。

### P2：显著提升体验

- 模板库页面设置可视化增删改查页面。
- 全局快捷键唤起搜索框（类似 Spotlight 的速查面板）。
- 导出/备份整个库为单一文件（zip/json），支持在另一台机器导入。

### P3：锦上添花

- 界面主题、打印样式自定义（字体、字号、每页列数、是否显示行号）。

## 3. 非功能需求

- **本地部署**：单机运行，离线可用，无需注册登录；默认单用户。
- **轻量**：选手的笔记本环境各异，依赖越少越好；启动命令一行搞定（或绿色可执行包）。
- **响应快**：本地应用，检索和复制必须是毫秒级。
- **可移植**：Windows 优先（竞赛选手主流），兼顾 macOS/Linux。

## 4. 实现细节

### 模板库管理

所有模板内容均保存在 backend/content/ 目录下（纳入 git 管理，附带少量示例模板），具体路径样式如下：

```plaintxt
content/
├── graph/                    # 分类
│   ├── segtree/              # 主标签名称，该目录仅包含一个版本的模板（前端无副标签）
│   │   ├── segtree_lazy.cpp
│   │   └── README.md
│   ├── dsu/                  # 包含多个版本的模板
│   │   ├── path-compression/ # 副标签
│   │   │   ├── dsu.cpp
│   │   │   └── README.md
│   │   └── with-weight/
│   │       ├── dsu_weight.cpp
│   │       └── README.md
│   └── sieve/                # 这样也识别为仅包含一个版本
│       └── version1/
│           ├── euler_sieve.cpp
│           └── README.md
├── math/
... └── ...
```

content 下的每个目录名称都会作为一个分类被自动创建，该目录下的模板视作该分类。

分类下的每个目录都被视作一份模板，其目录名称为主标签的名称，主标签目录可能包含多个副标签目录。

样式中的目录、文件名均为英文，但应当适配中文名称，路径出现中文名时，应当正确识别、提取并显示，不应出现报错、乱码等情况。

对于每个版本的模板，其都应该包含一份 code 文件与一个 README.md 文件。README.md 包含了一些元数据以及模板的描述，其样式如下：

```plaintxt
---
updated: 2026-07-29
tags: ['素数', '积性函数']
source: '洛谷 P3383'
page: 'https://www.luogu.com.cn/problem/P3383'
priority: 5
---

正文说明...
```

详细说明如下：

- **updated**：非必填项。若填写，会在小标题显示更新日期；若不填写，则小标签不会显示更新日期。
- **tags**：非必填项。若填写，会在标题右侧显示胶囊式小标签，也可以使用搜索功能通过搜索该 tag 进行检索；若不填写，则不显示小标签。
- **source**：非必填项。若填写，会在小标题显示来源；若不填写，则小标签不会来源。
- **page**：非必填项。若填写，则 **source 必须填写**，会将 source 的内容转化为一个超链接，连向指定网址；若不填写，source 不会转化为超链接。若有超链接，其字体显示为主题色。
- **priority**：非必填项。若填写，则以此数字作为优先级参考数；若不填写，则参考数默认为 2。参考数越大，显示的优先级越高。
- **正文说明**：非必填项。若填写，则代码最底部会显示说明框，内容即为正文，说明框适配 Markdown；若不填写，则不显示说明框。

模板标题直接取自目录名，无需在元数据中重复声明；元数据中规范之外的字段（如历史遗留的 title）会被静默忽略，不产生诊断。

对于包含多个副标签版本的模板，列表页展示聚合后的元信息：更新日期取所有版本的最晚值，优先级取所有版本的最大值，tags 取所有版本的并集；详情页切换版本时，小标签（更新于/来源/优先级/tags）与说明框均跟随显示当前版本各自的元信息。

模板库支持两种维护方式，可混用：

1. **手动维护**：选手按上述格式直接编辑 content/ 目录，watcher 自动重建索引；格式有误时前端显示诊断提示，鲁棒性尽量强。
2. **可视化增删改**（已实现）：模板库页面提供全部交互入口——
   - 工具栏"新增模板"按钮创建空主标签（仅分类 + 模板名，分类可新）；
   - 所有主标签均可展开，展开区末尾的 + 胶囊新建版本（名称/元数据/代码/说明）；
   - 详情页右上角编辑、删除当前版本；代码与说明均支持上传本地文件或手动输入；
   - 删光所有版本后，空页面提供"删除模板"按钮移除整个主标签。

**空主标签**：完全为空的模板目录是合法状态（可视化新建的占位模板），
正常进入列表与详情（无版本字段为空、优先级取默认值 2），不产生诊断；
目录内有内容却凑不出任何版本仍属于格式错误，保留 error 诊断。

可视化写操作的约定：

- 名称统一校验：禁止 Windows 非法字符与保留名、点开头、尾部空格/点、`..`、长度 ≤ 100，中文正常放行；
- README 由表单数据全量生成：缺省字段不写入 front matter，priority 为默认值 2 时省略；规范外的历史字段在首次编辑保存后丢弃；
- 新建版本经 .tmp 暂存目录原子就位，更新走临时文件 + 原子替换；删除为物理删除（前端确认弹窗明确提示不可找回）；
- 删除非空模板被拒绝（409），需先删除其所有版本；删除/移动后空分类目录自动清理；
- 顶层单版本（代码直接在模板目录下）在写 API 的 URL 中用保留字 `~` 寻址。

### 打印册

> 本节为 2026-08-06 定稿的打印册设计，工程落地细节见 5.6。

#### 定位与总体形态

- **PDF 是一等成品**：打印册的最终产物是带页码目录的 PDF；不提供 Markdown 形式的导出与预览（Markdown 无法表达分页与页码，页码是排版后的产物，任何"先导出文本再转 PDF"的路线都拿不到页码索引）。
- **单渲染器**：屏幕实时预览与 PDF 导出共用前端同一套渲染组件（预览即所得）；后端不组装任何渲染产物，只负责册配置落盘与引用解析。
- **PDF 生成管线**：点击"导出 PDF"时，把同一份文档模型渲染到**脱离应用编辑区**的打印 DOM → Paged.js 在浏览器内分页（自动页脚页码、目录页码由 `target-counter` 回填）→ 直接唤起浏览器打印对话框"另存为 PDF"；桌面模式（pywebview）后续可免费升级为 printToPDF 一键导出。
- **册配置是唯一事实来源**：`books/` 目录落盘，可手改、纳入 git、可备份迁移；不放 SQLite，不做缓存与 watcher，每次请求实时读取。

方案选型对比（为何不自建 PDF 后端）：

| 方案 | 页码目录 | 中文/高亮 | Windows 依赖 | 结论 |
| --- | --- | --- | --- | --- |
| Paged.js + 浏览器打印 | 支持（`target-counter`） | 系统字体零配置，复用 marked/KaTeX | 零新后端依赖 | **采用** |
| WeasyPrint（后端） | 支持 | 需 Pango，Windows 安装痛苦 | 重，违背轻量原则 | 备选 |
| XeLaTeX | 最专业 | 需自行配置 | 数百 MB TeX 发行版 | 过重 |
| fpdf2 / ReportLab | 需两趟渲染手写 | 高亮要另接 pygments | 纯 Python | 重复造排版轮子 |

#### 存储：books/ 目录

每册一个目录，目录名即册名（名称校验规则与模板名称一致，复用 `common/validation.py`）：

```plaintxt
books/
└── ICPC区域赛版/
    ├── book.yaml        # 册配置
    └── assets/          # 图片等资源（封面 logo、图片块引用）
```

`book.yaml` 完整示例：

```yaml
cover:                          # 封面（册级一等配置，固定版式）
  title: 'ICPC 区域赛版'
  subtitle: '2026 赛季'          # 可选
  author: 'Ink'                  # 可选
  logo: 'assets/logo.png'        # 可选，相对册目录的路径
options:
  include_toc: true              # 生成目录（默认 true）
  include_meta: true             # 模板块显示元信息行（默认 true）
  include_body: true             # 模板块默认包含说明（默认 true；可被块级覆盖）
  h1_page_break: true            # h1 级标题前自动分页（默认 true）
blocks:
  - type: heading                # 章节标题块
    title: '数学'
    heading_level: 1
  - type: template               # 模板引用块
    template: '数学/快速幂'        # 模板 id（<分类>/<模板名>）
    version: null                 # null=主版本（第一个版本，跟随模板变化）；'~'=显式顶层单版本；其余为副标签名
    title: null                   # 册内显示名覆盖；null=用模板原名，不影响模板库本身
    heading_level: 2              # 该节标题级别（h1-h6）
    include_body: null            # 是否包含说明；null=跟随册级 options.include_body
  - type: markdown               # 自由文字 / 文章片段
    title: '赛前注意事项'          # 可选小标题
    content: |
      内联 Markdown 正文……
  - type: image                  # 图片块
    src: 'assets/complexity.png'  # 相对册目录的路径
    caption: '常用复杂度表'        # 可选
    width: '80%'                  # 打印宽度占比
  - type: page_break             # 显式分页标记，无字段
```

字段细则：

- **块存引用不存内容**：template 块只记录模板 id 与版本，预览/导出时实时从模板索引取最新代码，模板更新自动反映；已打印的 PDF 是快照，封面带生成日期，页脚为页码，放置于右下角。
- **template 块的版本在添加时确定**：用户从模板列表点击某个版本即添加该版本；不提供"换版本"编辑——需要更换时删除该块、重新从列表选择其他版本添加。
- **说明位置**：template 块包含说明时，说明框（README 正文）紧贴代码块下方。
- **分页控制**：由 `h1_page_break`（h1 标题前自动分页）+ 显式 page_break 块组合控制，不设"每节后都分页"的粗放开关。
- **heading_level**：取值 1-6；heading 块默认 2，template 块默认 3；默认级别在“封面与选项”设置弹窗中调整，按块类型记忆，下次添加同类型块时沿用。
- **图片约束**：允许 png / jpg / jpeg / gif / webp / svg，单文件 ≤ 5MB。
- 允许同一模板（版本）在册中出现多次，不去重。

#### 引用解析与失效处理

后端把每个块折算为"解析后块"（含渲染所需的全部内容），template 块逐块得出状态：

| 状态 | 条件 | 前端表现 | 导出表现 |
| --- | --- | --- | --- |
| `ok` | 模板存在且版本命中 | 正常显示 | 正常生成章节 |
| `missing_template` | 模板 id 不存在（被删/改名） | 块行标红 + 警告 | 跳过该节，输出失效清单 |
| `missing_version` | 模板在、指定版本不在 | 标黄警告，显示回退结果 | 回退主版本生成，附警告 |
| `empty_template` | 模板存在但无任何版本 | 标黄警告 | 跳过该节 |

- 图片块引用的资源文件缺失，等同失效引用处理。
- heading 块之后没有任何内容块（悬空章节）：导出时给出警告。
- 失效引用**只报告、不改写配置**：模板被误删后恢复，册自动复原。汇总为 `issues: [{block_index, level, message}]` 随详情返回。
- 损坏的 book.yaml 不阻断：册列表照常列出（名称取目录名）并附 error 信息，延续模板库"诊断不阻断"的鲁棒哲学。

#### 页面与交互（三栏）

页面无路由，整体替换导航中"打印册"占位页，分左中右三栏。

**左栏（资源面板）**，自上而下：

1. **打印册下拉**（NSelect）：切换当前册；下拉首项为"新建打印册"入口，点击弹窗输入册名与封面标题。下拉旁的操作菜单提供重命名、删除（确认弹窗，物理删除）、封面与选项设置（cover + options 表单弹窗）。
2. **添加块按钮组**：heading / markdown / image / page_break 四个图标按钮，点击即在当前册插入对应类型的块；image 块点击后先弹文件选择器，上传到册目录 `assets/` 后再插入。
3. **模板库紧凑列表**：带搜索、排序、分类筛选（与模板库同源数据），其样式于模板库相同；模板可展开到版本粒度，**点击某个版本**即以该版本插入 template 块。

**插入位置**：所有添加动作默认追加到条目尾部；同时提供位置选项，用户可选择"添加在第 N 个条目之后"，N 由用户手动填写，避免长列表下"先加尾部再拖拽"的往返。

**中栏（当前册条目）**：

- 每行按类型渲染：拖拽手柄、类型图标与徽标、标题。
- **拖拽排序**：vuedraggable（底层 Sortable.js），开启 `scroll` + `scrollSensitivity` + `scrollSpeed`，拖拽至列表顶部/底部时容器自动滚动，适配长条目场景。
- **删除**：行内删除按钮。
- **编辑**（按类型分）：
  - heading：标题、heading_level；
  - template：册内显示名（title 覆盖）、heading_level、是否包含说明（include_body）；**不可换版本**；
  - markdown：标题、正文（Markdown 编辑，先用 textarea，后续可升级编辑器）；
  - image：更换图片、caption、width；
  - page_break：不可编辑，仅能排序与删除。

**右栏（预览与导出）**：

- **实时预览**：整册滚动渲染——封面、目录、各块（标题、元信息行、说明框、代码只读高亮、图片），随"当前册条目"的任何变化实时更新。目录按 heading_level 层级缩进，不自动编号（需要编号可写进标题文字）。
- **实时预览是轻量 A4 近似页框**：预览容器按 A4 页面宽度（`mm` 单位，与打印同一套 CSS 变量）渲染封面、目录与各块；每个分页边界（封面/目录/h1/显式 page_break）开始一个新的页框，内容超长时页框自然延伸但不裁切。屏幕预览用于编辑反馈，不承诺精确分页。
- 顶部"导出 PDF"按钮：**直接**触发打印管线，不再经过独立"打印预览视图"；TOC 页码（`target-counter`）与页脚页码只在打印 DOM 中回填。目录页码不可用时的降级显示为占位符 `·`。

#### 预览与 PDF 管线（2026-08-06 定稿）

三条基线：

1. **单一文档渲染器**：块 + 选项先经 `buildDocument` 组装为纯数据结构（封面、目录、有序章节），实时预览与打印 DOM 共用同一套渲染组件与全局 CSS；
2. **精确分页只跑一次**：Paged.js 会改写 DOM，因此只在导出时作用于**脱离编辑区的打印 DOM**，运行结束（含打印失败）后销毁，编辑区预览不受影响；
3. **页面盒子统一**：A4 = 210×297mm、内容区 = 180×267mm（边距 15mm），`@page { size: A4; margin: 15mm }`，`html/body` 在打印时 `margin: 0`，所有单位用 `mm/rem`，禁止 `transform: scale` 与 `zoom`。

选项语义（`buildDocument` 的唯一输入，任意变化整体重算）：

| 选项 | 关闭时行为 |
| --- | --- |
| 生成目录 | 文档不渲染目录区块 |
| 显示元信息 | 模板节不显示分类/标签/更新/来源/优先级行 |
| 默认包含说明 | 块级 `include_body=null` 的模板不显示说明；显式 true/false 仍以块为准 |
| 一级标题前分页 | h1 不再强制另起一页；显式 page_break 块仍生效 |

渲染细则：

- **代码逐行渲染**：highlight.js 整段高亮后按换行拆成独立行容器（跨行 span 在行边界关闭并重开，保证多行注释/字符串高亮不丢），每行 `break-inside: avoid`，代码容器不设 `overflow: hidden`，长代码只在行间分页、绝不截断半行；行号用 CSS counter，打印时以 `.pagedjs_page` 为作用域每页从 1 重新计数，预览页框同构。
- **分页符去重**：相邻两个分页边界只保留一个；文档首尾不产生孤立分页符。
- **标题锚点**：目录引用稳定 ASCII 锚点（`sec-01` 等），不做中文 slug。
- **就绪顺序**：先渲染 Markdown/KaTeX/图片并等待 `document.fonts.ready` 与全部 `img.decode()`，再运行 Paged.js，否则页码与空白页都会算错；长公式超宽时降字号而非裁切。
- **空白页校验**：Paged.js 分页完成后检查页框集合，存在无内容页框即报错并拒绝打印。
- **打印颜色**：`print-color-adjust: exact`，保证 KaTeX 与代码高亮底色不丢失。
- **图片**：打印 DOM 使用绝对 URL，缺失资源显示占位框并计入已有 issues，不阻塞分页。

验收清单：超长代码跨页行数守恒；预览与打印同源同构（打印为权威成品）；四个选项每种组合下区块增删正确；页面序列无空白页；TOC 每项页码 = 标题实际所在页；公式/图片/中文/高亮屏幕与打印一致。

#### 实时预览与持久化

- 详情接口返回解析后的完整内容（含代码与说明正文），前端持有本地可变副本，预览由本地副本驱动。
- 任何条目变动（增/删/排序/编辑）立即更新本地副本（预览同步变化），同时 `PUT /blocks` 全量替换持久化；**该接口返回最新完整详情**，前端以返回值刷新本地，保证与磁盘一致。
- markdown 正文等高频编辑做 500ms 防抖提交，避免每击键一次请求。

#### 打印质量细则

- 长代码行打印时必须换行（`white-space: pre-wrap`），不得在纸面截断；
- 长代码块允许跨页拆分，但节标题与代码首行不分离（标题 `break-after: avoid`）；
- 打印视图的代码用静态高亮（highlight.js），不使用 CodeMirror（编辑器 DOM 跨页切割易出问题）；
- 中文与公式由浏览器系统字体 + KaTeX 直接渲染；
- 行号、字号档位等打印样式自定义属 P3，预留选项位。

#### 边界场景

- 中文册名/块标题：URL 段 encodeURIComponent、YAML allow_unicode；PDF 文件名取封面标题（打印时设置 document.title）。
- 空册（零块）：预览空态引导，导出仍可用（仅封面 + 空目录）。
- 模板索引重建（watcher）期间读取：走 SQLite 事务读，要么旧要么新，不会读到半成品。
- 并发写同一册：store 写操作 threading.Lock 串行化（同 TemplateService 模式）。
- assets 暂不提供删除接口，未被引用的资源文件可手动清理。

## 5. 后端设计

### 5.1 整体拓扑

- `content/` 目录是模板库的**唯一事实来源**，选手按指定格式手动维护文件；
- SQLite 不作为业务数据库，仅作为 FTS5 全文检索索引 + 元数据缓存，可随时删除重建；
- 后端通过 watchdog 监听 `content/` 变更，**自动重建索引**，改动即时生效；
- 前端通过 HTTP API 获取数据，开发环境经 Vite proxy 转发 `/api`，生产环境由 FastAPI 托管 `frontend/dist/`。

### 5.2 目录结构

```plaintxt
backend/
├── pyproject.toml              # uv 项目定义与依赖
├── .python-version
├── src/
│   ├── main.py                 # FastAPI 入口：创建 app、挂路由、全局异常处理、CORS、托管前端 dist/
│   ├── core/                   # 基础设施：config / database / exceptions / logging
│   ├── common/                 # 跨功能通用件（通用响应模型、工具函数）
│   ├── routers/
│   │   └── template/           # 模板功能的路由（薄层：参数校验 + 调 service）
│   ├── services/
│   │   └── template/           # 模板功能的业务编排（查询组装、过滤排序）
│   └── modules/
│       └── template/           # 模板功能的领域核心：scanner / parser / repository / models / schemas / watcher
├── content/                    # 模板库数据（纳入 git 管理）
└── tests/
    └── template/               # 测试按功能目录镜像组织
```

### 5.3 分层职责与约定

- `routers/`：仅做参数校验与调用 service，不写业务逻辑；不宽泛 try/except，不记录堆栈，异常统一交由全局异常处理器；
- `services/`：业务编排，组合 modules 能力对外提供用例级接口；
- `modules/<功能>/`：领域核心。SQLModel 表模型放 `models.py`，API 请求/响应的 Pydantic 模型放 `schemas.py`（对外契约与内部存储分离）；若某 schema 未来被多功能共用，再提升至 `common/`；
- 不单独设立 `api/` 目录：路由聚合由 `main.py` / `routers/__init__.py` 承担，API 公共件归属 `common/`；
- **扩展方式**：新功能（打印册、做题统计、比赛信息等）在 `routers/`、`services/`、`modules/` 下各开一个平级功能目录（如 `print_book/`），在 `main.py` 一行挂载路由，模块间零耦合。

### 5.4 API 说明

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/templates` | 模板列表（摘要），支持 `category` / `tags` / `keyword`（FTS5 搜标题/标签/说明/代码）/ `sort`（updated/name/priority） |
| GET | `/api/templates/{id}` | 模板详情，含全部副标签版本（代码 + README 正文） |
| GET | `/api/categories` | 分类列表（从 content/ 一级目录自动派生） |
| GET | `/api/diagnostics` | 扫描诊断（格式错误、缺代码文件、page 无 source 等），供前端显示报错提示 |
| POST | `/api/templates/reload` | 手动重建索引（watcher 之外的兜底） |
| POST | `/api/templates` | 新建空主标签（仅分类 + 模板名；分类可新） |
| PUT | `/api/templates/{category}/{name}` | 主标签重命名/换分类 |
| DELETE | `/api/templates/{category}/{name}` | 删除空主标签（非空 409） |
| POST | `/api/templates/{category}/{name}/versions` | 新建副标签版本 |
| PUT | `/api/templates/{category}/{name}/versions/{version}` | 更新版本（代码/元数据/正文/改名/换扩展名；`~` 表示顶层单版本） |
| DELETE | `/api/templates/{category}/{name}/versions/{version}` | 删除版本（`~` 表示顶层单版本；删光后模板留空） |

### 5.5 范围说明（2026-08-05 更新）

- 可视化增删改已落地：写操作由 `modules/template/writer.py` 统一落盘（名称校验 +
  原子写入），写接口详见 5.4；主标签重命名/换分类暂仅提供后端接口，前端入口后续补；
- 前端新增 `src/api/` 请求层，`useTemplates` 异步拉取 API，分类由后端动态返回；
- 扫描器对三种目录形态统一处理：模板目录直接含代码文件（单版本）、含多个副标签子目录（多版本）、只含一个子目录（折叠为单版本）；路径含中文名时须正确识别，不乱码不报错；完全为空的模板目录作为"空主标签"正常载入。

### 5.6 打印册功能（printbook，2026-08-06 定稿）

打印册按 5.3 的扩展约定落地为新功能目录，产品与交互设计见第 4 节"打印册"。

#### 目录结构

```plaintxt
backend/
├── books/                       # 打印册配置（唯一事实来源，纳入 git，附示例册）
└── src/
    ├── common/
    │   └── validation.py        # 名称校验（自 modules/template/writer.py 纯搬移提升，模板/打印册共用）
    ├── modules/printbook/
    │   ├── models.py            # 内部模型：BookConfig / 五种块（type 判别联合）/ BookCover / BookOptions / StoredBookInfo
    │   ├── schemas.py           # API 契约
    │   ├── store.py             # books/ 目录读写（tempfile+os.replace 原子写）与 assets 管理
    │   └── document.py          # 存储 ⇄ API 双向转换与模板引用解析（resolved 实时解析，不持久化）
    ├── services/printbook/
    │   └── service.py           # 编排：持有 TemplateService 引用，组装详情（threading.RLock 保护写操作）
    └── routers/printbook/
        └── router.py            # 薄层，asyncio.to_thread 模式同模板路由
```

- `main.py`：lifespan 中 `init_print_book_service(settings, template_service)`，一行 `include_router`；依赖方向严格单向 `printbook → template`，模板侧不感知打印册。
- `config.py`：新增 `books_dir`（默认 `backend/books`，`XCPC_BOOKS_DIR` 覆盖）。
- 后端新增依赖 `python-multipart`（图片上传 UploadFile 所需）。

#### API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/print-books` | 册列表摘要（name、title、block_count、updated、error） |
| POST | `/api/print-books` | 新建册 `{name, title?}`（201；重名 409） |
| GET | `/api/print-books/{name}` | 册详情：cover/options + 解析后 blocks（template 块内联 resolved） |
| PUT | `/api/print-books/{name}` | 更新 cover/options，支持改名 `new_name`（冲突 409） |
| DELETE | `/api/print-books/{name}` | 删除册（物理删除目录，204） |
| PUT | `/api/print-books/{name}/blocks` | 全量替换块列表，**返回最新完整详情** |
| POST | `/api/print-books/{name}/assets` | 上传图片（multipart；png/jpg/jpeg/gif/webp/svg，≤5MB） |
| GET | `/api/print-books/{name}/assets/{path}` | 资源服务，供预览/打印视图引用图片（防路径穿越） |

块操作为全量替换：排序与增删是混合操作，整体提交语义最简单、无并发粒度问题，数据量不过几十块。

#### 前端落地

- `types.ts` 追加 PrintBook 相关类型；`api/printbook.ts`（复用 `api/client.ts`）；`composables/usePrintBooks.ts`（单例 store，模式照搬 useTemplates）。
- `components/pages/PrintBook.vue` 替换 books 占位页 + `components/printbook/` 子组件目录（册下拉与操作菜单、块按钮组与插入位置控件、模板列表面板、条目列表、各类型编辑弹窗、预览、打印视图）。
- 从 `TemplateDetail.vue` 抽出共享 `MarkdownView.vue`（marked + marked-katex-extension），预览说明框与模板库说明框同源渲染。
- heading_level 按块类型的用户偏好记忆存 localStorage（`utils/storage.ts`）。
- 左栏模板列表由 `usePrintBooks` 经 `fetchTemplates` 独立拉取（服务端搜索/排序，200ms 防抖），展开版本时按需拉取模板详情缓存。
- 新依赖：Paged.js（分页与页码目录）、highlight.js（打印静态高亮）；拖拽排序用原生 HTML5 DnD 实现（含边缘自动滚动）。
- `.gitignore` 新增 `backend/books/.tmp-*`（原子写崩溃残留防御）；`books/` 本身入库。

#### 测试计划

- `tests/printbook/test_store.py`：yaml 读写回环、缺省字段省略、名称校验透传、重名 409、改名、损坏 yaml 的 error 标记、assets 上传限制；
- `tests/printbook/test_document.py`：双向转换、version 语义（null/`~`/副标签名/未命中回退）、模板缺失 resolved 为 None、assets URL 展开与还原；
- `tests/printbook/test_service.py`：服务层链路与 TestClient 端到端（临时 content/ + books/），含 404/409/400 错误结构、blocks 全量替换返回详情、assets 上传与下载；
- 前端：`npm run typecheck` + `npm run build` 通过；手动走查"新建册 → 添加块/模板版本 → 指定位置插入 → 拖拽排序 → 编辑 → 实时预览 → 导出 PDF"全链路。

#### 实施顺序（原子化提交）

1. `docs: 补充打印册功能设计`（本节）
2. `refactor(后端): 提升名称校验至 common 模块`
3. `feat(后端): 新增打印册存储与块式文档模型`（models/schemas/store/document/config/gitignore + 测试）
4. `feat(后端): 实现打印册编排、路由与资源服务`（service/router/main + 测试 + 示例册）
5. `feat(前端): 新增打印册类型、API 与数据层`
6. `feat(前端): 实现打印册三栏页面与实时预览`（含 MarkdownView 抽取、App 接线）
7. `feat(前端): 实现打印视图与 PDF 导出`（Paged.js + highlight.js）
8. `chore: 更新使用文档`（README、导航占位提示）
