# 打印册（printbook）设计

> 状态：已实现（2026-08-06 定稿）。跨功能公共约定见 [../conventions.md](../conventions.md)。

## 1. 定位与总体形态

- **PDF 是一等成品**：打印册的最终产物是带页码目录的 PDF；不提供 Markdown 形式的导出与预览（Markdown 无法表达分页与页码，页码是排版后的产物，任何"先导出文本再转 PDF"的路线都拿不到页码索引）。
- **单渲染器**：屏幕实时预览与 PDF 导出共用前端同一套渲染组件（预览即所得）；后端不组装任何渲染产物，只负责册配置落盘与引用解析。
- **PDF 生成管线**：点击"导出 PDF"时，把同一份文档模型渲染到**脱离应用编辑区**的打印 DOM → Paged.js 在浏览器内分页（自动页脚页码、目录页码由 `target-counter` 回填）→ 直接唤起浏览器打印对话框"另存为 PDF"；桌面模式（pywebview）后续可免费升级为 printToPDF 一键导出。
- **册配置是唯一事实来源**：`backend/books/` 目录落盘，可手改、纳入 git、可备份迁移；不放 SQLite，不做缓存与 watcher，每次请求实时读取。

方案选型对比（为何不自建 PDF 后端）：

| 方案 | 页码目录 | 中文/高亮 | Windows 依赖 | 结论 |
| --- | --- | --- | --- | --- |
| Paged.js + 浏览器打印 | 支持（`target-counter`） | 系统字体零配置，复用 marked/KaTeX | 零新后端依赖 | **采用** |
| WeasyPrint（后端） | 支持 | 需 Pango，Windows 安装痛苦 | 重，违背轻量原则 | 备选 |
| XeLaTeX | 最专业 | 需自行配置 | 数百 MB TeX 发行版 | 过重 |
| fpdf2 / ReportLab | 需两趟渲染手写 | 高亮要另接 pygments | 纯 Python | 重复造排版轮子 |

## 2. 存储：books/ 目录

每册一个目录，目录名即册名（名称校验规则与模板名称一致，复用 `common/validation.py`）：

```plaintext
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
- **heading_level**：取值 1-6；heading 块默认 2，template 块默认 3；默认级别在"封面与选项"设置弹窗中调整，按块类型记忆，下次添加同类型块时沿用。
- **图片约束**：允许 png / jpg / jpeg / gif / webp / svg，单文件 ≤ 5MB。
- 允许同一模板（版本）在册中出现多次，不去重。

## 3. 引用解析与失效处理

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
- 损坏的 book.yaml 不阻断：册列表照常列出（名称取目录名）并附 error 信息，延续"诊断不阻断"的鲁棒哲学（见 [../conventions.md](../conventions.md)）。

## 4. 页面与交互（三栏）

页面无路由，整体替换导航中"打印册"占位页，分左中右三栏。

**左栏（资源面板）**，自上而下：

1. **打印册下拉**（NSelect）：切换当前册；下拉首项为"新建打印册"入口，点击弹窗输入册名与封面标题。下拉旁的操作菜单提供重命名、删除（确认弹窗，物理删除）、封面与选项设置（cover + options 表单弹窗）。
2. **添加块按钮组**：heading / markdown / image / page_break 四个图标按钮，点击即在当前册插入对应类型的块；image 块点击后先弹文件选择器，上传到册目录 `assets/` 后再插入。
3. **模板库紧凑列表**：带搜索、排序、分类筛选（与模板库同源数据），样式与模板库相同；模板可展开到版本粒度，**点击某个版本**即以该版本插入 template 块。

**插入位置**：块按钮组与模板选择器共用同一位置选项：-1（默认）表示追加到条目尾部，0 表示插入到头部，N 表示插入到第 N 个条目之后，避免长列表下"先加尾部再拖拽"的往返。

**中栏（当前册条目）**：

- 每行按类型渲染：拖拽手柄、类型图标与徽标、标题。
- **拖拽排序**：支持拖拽至列表顶部/底部时容器自动滚动，适配长条目场景。
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

## 5. 预览与 PDF 管线（2026-08-06 定稿）

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

## 6. 实时预览与持久化

- 详情接口返回解析后的完整内容（含代码与说明正文），前端持有本地可变副本，预览由本地副本驱动。
- 任何条目变动（增/删/排序/编辑）立即更新本地副本（预览同步变化），同时 `PUT /blocks` 全量替换持久化；**该接口返回最新完整详情**，前端以返回值刷新本地，保证与磁盘一致。
- markdown 正文等高频编辑做 500ms 防抖提交，避免每击键一次请求。

## 7. 打印质量细则

- 长代码行打印时必须换行（`white-space: pre-wrap`），不得在纸面截断；
- 长代码块允许跨页拆分，但节标题与代码首行不分离（标题 `break-after: avoid`）；
- 打印视图的代码用静态高亮（highlight.js），不使用 CodeMirror（编辑器 DOM 跨页切割易出问题）；
- 中文与公式由浏览器系统字体 + KaTeX 直接渲染；
- 行号、字号档位等打印样式自定义属 P3，预留选项位。

## 8. 边界场景

- 中文册名/块标题：URL 段 encodeURIComponent、YAML allow_unicode；PDF 文件名取封面标题（打印时设置 document.title）。
- 空册（零块）：预览空态引导，导出仍可用（仅封面 + 空目录）。
- 模板索引重建（watcher）期间读取：走 SQLite 事务读，要么旧要么新，不会读到半成品。
- 并发写同一册：store 写操作 threading.Lock 串行化（同 TemplateService 模式）。
- assets 暂不提供删除接口，未被引用的资源文件可手动清理。

## 9. 工程落地

### 后端结构

```plaintext
backend/
├── books/                       # 打印册配置（唯一事实来源，纳入 git，附示例册）
└── src/
    ├── common/
    │   └── validation.py        # 名称校验（模板/打印册共用）
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
- `config.py`：`books_dir`（默认 `backend/books`，`XCPC_BOOKS_DIR` 覆盖）。
- 依赖 `python-multipart`（图片上传 UploadFile 所需）。
- 块操作为全量替换：排序与增删是混合操作，整体提交语义最简单、无并发粒度问题，数据量不过几十块。

### API

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

### 前端落地

- `features/printbook/`：`types.ts`（PrintBook 相关类型）、`api/`（复用 shared 请求封装）、`store/`（单例 store，模式与模板库一致）、`model/`（纯函数文档模型层 `buildDocument`）、`components/`（册下拉与操作菜单、块按钮组与插入位置控件、模板列表面板、条目列表、各类型编辑弹窗、预览、打印视图）。
- 共享 `MarkdownView.vue`（marked + 自实现 KaTeX 扩展 `shared/utils/marked-katex.ts`），预览说明框与模板库说明框同源渲染。
- heading_level 按块类型的用户偏好记忆存 localStorage。
- 左栏模板列表经服务端搜索/排序（200ms 防抖），展开版本时按需拉取模板详情缓存。
- 依赖：Paged.js（分页与页码目录）、highlight.js（打印静态高亮）；拖拽排序用原生 HTML5 DnD 实现（含边缘自动滚动）。
- `.gitignore` 含 `backend/books/**/.tmp-*`（原子写崩溃残留防御）；`books/` 本身入库。

### 测试

- `tests/printbook/test_store.py`：yaml 读写回环、缺省字段省略、名称校验透传、重名 409、改名、损坏 yaml 的 error 标记、assets 上传限制；
- `tests/printbook/test_document.py`：双向转换、version 语义（null/`~`/副标签名/未命中回退）、模板缺失 resolved 为 None、assets URL 展开与还原；
- `tests/printbook/test_service.py`：服务层链路与 TestClient 端到端（临时 content/ + books/），含 404/409/400 错误结构、blocks 全量替换返回详情、assets 上传与下载；
- 前端：`npm run typecheck` + `npm run test` + `npm run build` 通过；手动走查"新建册 → 添加块/模板版本 → 指定位置插入 → 拖拽排序 → 编辑 → 实时预览 → 导出 PDF"全链路。
