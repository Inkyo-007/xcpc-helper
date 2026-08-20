# 导入 / 导出（transfer）设计

> 状态：已实现。背景与需求优先级见 [../../requirements.md](../../requirements.md)（"导入 / 导出"），
> 跨功能公共约定见 [../conventions.md](../conventions.md)。

## 1. 背景与目标

- 模板库（`backend/content/`）与打印册（`backend/books/`）都是 git 管理的文件目录，天然可打包迁移；本功能把它做成一键导入/导出（zip 压缩包）；
- **导出即规范化**：无论当前 `content/` 是哪种目录形态（顶层单版本、单子目录折叠、多版本），导出统一为 `content/<分类>/<模板>/<版本>/code.ext + README.md` 三层标准结构，代码统一 UTF-8；
- **最大程度适配外来模板库**：选手自收集的模板几乎都不是标准形态。本期只适配最常见的一种——`某文件夹/<分类>/<代码文件>.<ext>`（每个分类目录下直接平铺若干代码文件，**每份代码文件即一份模板**，模板名取文件名主名）；其余形态识别为"格式错误"列入警告，由用户选择是否继续导入可识别的部分；
- 模板库与打印册**分开导入/导出**：打印册块存引用不存内容，单独导入的册在缺少模板时走既有的 `missing_template` 失效引用机制（只报告不阻断），后续导入模板库后自动复原，无需任何补偿逻辑。

明确不做（本期）：category 下再嵌套细分类目录的递归识别（进警告清单）；导出时的按分类/按模板勾选；.txt 当代码导入（进警告清单）。

## 2. 总体形态

- 压缩包布局（导出入口统一产物）：

```plaintext
xcpc-templates-20260809.zip        # 或 xcpc-books-*.zip
├── manifest.json                  # 归档标识：app / kind / format 版本 / 导出时间 / 统计
├── content/<分类>/<模板>/<版本>/  # kind=templates 时存在
└── books/<册名>/book.yaml+assets/ # kind=books 时存在
```

- `manifest.json`：`{"app": "xcpc-helper", "kind": "templates"|"books", "format": 1, "exported_at": "...", "counts": {...}}`。导入端据此识别"本软件导出的标准归档"并校验 kind 与入口匹配（在模板库入口传了册包时给出明确报错）；
- **导入两阶段**：`analyze`（上传 zip → 解压至暂存区 → 返回识别结果 + 警告清单 + 冲突清单）与 `apply`（携带暂存 id 与冲突策略 → 落盘 → 返回导入报告）。"格式错误是否继续导入"的裁决落在 analyze 结果的确认按钮上；
- **导入策略**（三种策略在 analyze 结果页始终可选，apply 统一执行）：
  - `skip`：合并导入，跳过与现有库同名的项，保留现有；
  - `overwrite`：整体替代——先清空整个 content/（或 books/）目录的全部内容（含目录本身，不留空目录触发告警），再把归档内容写入空库；选中时前端给出不可撤销警示；
  - `rename`：合并导入，同名项自动改名（`名称-2`、`名称-3`……递增），两边都保留；
- 所有落盘写操作经由既有 writer/store（模板走 `modules/template/writer.py`，册走 `modules/printbook/store.py`），保持"数据落盘必须走写层"的硬约定；导入完成后由服务端显式触发一次索引 rebuild 收尾（不等 watcher 去抖）。

被否决方案：

| 方案 | 否决理由 |
| --- | --- |
| 导出直接打包磁盘目录 | 原样输出非标准形态，违背"导出即规范化"；也拿不到 UTF-8 统一编码 |
| 外来结构靠启发式一路猜到底（含嵌套细分） | "目录里既有代码又有子目录"等形态存在真实歧义，猜错代价高；本期只覆盖无歧义的平铺形态，其余显式警告 |
| 分析结果做成可编辑映射表 | 平铺形态规则完全确定，无需用户裁决；警告 + 确认即可，交互更轻 |
| 导入/导出做独立页面 | 操作型功能，弹窗足够；导航占位项 `/template/io` 移除 |

## 3. 识别与规范化细则

### 3.1 标准归档（含 manifest.json 且 kind 匹配）

- `content/` 子树按三层结构直接映射导入（含多版本与空主标签目录）；
- `books/` 子树每册一个目录（book.yaml + assets/），book.yaml 损坏的册列入警告并跳过，不阻断其余册。
- 本软件归档被连文件夹整体打包（压缩包根仅含一个目录且其内含 manifest/content/books）时，同样先静默下钻一层再识别。

### 3.2 外来模板库（无 manifest 或结构不符）

- 先剥离**单层包裹目录**：用户常把整个模板文件夹直接打成 zip，导致归档多一层外壳。压缩包根仅含一个目录且其内目录数多于文件数时，静默下钻一层再识别（单分类外来库形态相同但子项以代码文件为主，不受影响）；
- 顶层每个一级目录视为**分类**；分类目录下每个代码文件（扩展名命中 `CODE_EXTENSIONS`）视为一份**单版本模板**，模板名取文件名主名；
- 以下条目一律列入警告并跳过（analyze 返回警告清单，用户确认后继续导入可识别部分）：
  - 分类目录下的**子目录**（不递归识别）；
  - 压缩包**根部散落的文件**（无分类归属）；
  - 扩展名不在白名单内的文件（含 .txt、.md 等）；
- **同主名不同扩展名**（如 `dsu.cpp` 与 `dsu.py` 同分类）：拆成两份模板，后者自动改名 `dsu-py`（仍冲突则递增后缀），列入警告说明；选手几乎不会同模板存两种语言，保持"一文件一模板"的后端一贯性；
- **名称清洗**：外来名称可能违反 `common/validation.py` 规则（非法字符、尾部点/空格、点开头、保留名等）。analyze 阶段给出清洗后的建议名（非法字符替换为 `_`、修剪首尾点与空格、空名/保留名兜底为 `未命名-N`），每次清洗都在警告清单中明示；
- 导入落盘一律写为三层标准结构：单版本模板的版本目录名取**模板名自身**（扫描器对单子目录折叠展示，前端无副标签页签，体验与顶层单版本一致）。

### 3.3 导出规范化细则（模板库）

- 以 `scan_content()` 结果为唯一事实来源重新序列化，不直接打包磁盘；
- 顶层单版本（代码直接在模板目录下）升格为三层结构，版本目录名取模板名自身（与该模板已有子目录冲突时 `-2` 递增）；已知取舍：册中对顶层单版本的显式引用（version=`~`）在导入新库后按 `missing_version` 回退主版本，行为可接受；
- 每个版本目录写 `code.<ext>`（沿用原文件名，非法时回退 `code.<ext>`）与 `README.md`（由 `writer.render_readme` 按元数据全量生成，缺失元数据时生成空 front matter 占位）；
- 代码统一以 UTF-8 写出（scanner 已做 GBK 兜底读取，导出即完成转码）；
- 空主标签（空目录占位模板）以显式目录条目写入 zip，保证往返不丢。

### 3.4 zip 安全（必踩坑清单）

- **中文文件名**：Windows 压的 zip 中文名常为 GBK 且无 UTF-8 标志，`zipfile` 按 cp437 解出乱码——对非 UTF-8 标志条目取原始字节按 GBK 重解码兜底；
- **zip slip**：条目规范化路径必须留在归档根内，拒绝绝对路径、`..` 穿越、盘符；
- **限量**：条目数、总解压大小、单文件大小均设上限，超限整体拒绝（400）。

## 4. 页面与交互

不开独立页面，入口收进两个功能页（侧边导航 `/template/io` 占位项随之移除）。

**模板库页**：工具栏新增一个"导入 / 导出"图标按钮（lucide `FolderSync` + NTooltip），弹出 `TemplateTransferModal`：

1. **模式选择**：两个选项——"导入模板" / "导出模板库"；
2. 导入：NUpload 拖拽区（仅 .zip）→ 自动 analyze → 结果页（成功摘要"识别出 N 个分类 / M 个模板" + 按分类分组的只读清单；警告区 NAlert + 明细；有冲突时 NRadioGroup 选策略）→ 主按钮确认（有警告时文案"仍要导入"）→ apply → 导入报告（新建/跳过/覆盖/重命名/失败计数 + 明细）→ 关闭后刷新模板列表。零可识别项时显示错误并禁止继续；
3. 导出：确认框（说明导出范围与规范化行为）→ 确认后浏览器下载 zip。

**打印册页**：册切换器最左侧的 `BookOpen` 图标移除，原位放"导入 / 导出"图标按钮，弹出 `BookTransferModal`：

1. 模式选择："导入打印册" / "导出打印册"；
2. 导入：选包 → analyze（校验 kind=books、列出册、检出重名）→ 冲突策略 → apply → 报告 → 刷新册列表并切换到首个新导入的册；
3. 导出：NRadioGroup 选"导出当前册 / 导出所有册"→ 确认 → 下载。

## 5. 工程落地

### 后端结构

```plaintext
backend/src/
├── modules/transfer/
│   ├── archive.py       # zip 安全读写：GBK 文件名兜底、zip slip 校验、限量、manifest 读写
│   ├── schemas.py       # API 契约：AnalyzeResult / ImportReport / 冲突策略等
│   ├── templates_io.py  # 模板库导出（扫描结果 → 标准三层 zip）与导入（analyze/apply 的识别与映射）
│   └── books_io.py      # 打印册导出（当前册/所有册）与导入识别
├── services/transfer/
│   └── service.py       # 编排：暂存区管理、调 writer/store 落盘、RLock 串行、导入后 rebuild
└── routers/transfer/
    └── router.py        # 薄层，asyncio.to_thread；下载为 zip 字节响应（RFC 5987 文件名）
```

- 依赖方向严格单向 `transfer → template / printbook`；模板、打印册两侧不感知 transfer；
- `modules/printbook/store.py` 增补整册目录的原子就位/替换函数（暂存目录 + rename），供册导入调用；
- `modules/template/writer.py` 增补整棵模板树的物理删除函数（仅供导入 overwrite 策略使用）；
- 暂存区：`backend/data/.staging/transfer-<uuid>/`（data 目录本就不入库，`.gitignore` 补 `.staging/`）；analyze 时清理超期暂存（TTL 1 小时），apply 后立即删除；
- `config.py` 增补 zip 限量配置（条目数/总大小/单文件），默认值保守。

### API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/transfer/export/templates` | 导出模板库 zip（标准化三层结构） |
| GET | `/api/transfer/export/books` | 导出所有册 zip |
| GET | `/api/transfer/export/books/{name}` | 导出单册 zip |
| POST | `/api/transfer/import/templates/analyze` | 上传 zip（multipart），返回识别结果 + 警告 + 冲突清单与暂存 id |
| POST | `/api/transfer/import/templates/apply` | `{staging_id, strategy}` 执行导入，返回导入报告 |
| POST | `/api/transfer/import/books/analyze` | 同上，册包专用（校验 kind=books） |
| POST | `/api/transfer/import/books/apply` | 同上，册包导入执行 |

### 前端落地

- `features/transfer/`：`types.ts`（AnalyzeResult / ImportReport / 策略枚举）、`api.ts`（复用 shared `request`，上传走 FormData；下载先 fetch 校验响应、失败时抛出可读错误，成功再经 blob + 隐藏 `<a>` 落地）、`components/`（`TemplateTransferModal.vue`、`BookTransferModal.vue`、共用 `TransferUpload.vue` 拖拽区与 `TransferReport.vue` 结果展示）；
- 宿主页面改动：`TemplateLibraryPage.vue` 工具栏加入口按钮；`BookSidePanel.vue` 移除 `BookOpen` 图标、加入口按钮；`nav.ts` / `router.ts` 移除 `/template/io` 占位（`PlaceholderMeta` 的 `import` 图标若不再使用一并清理）；
- 导入完成后：模板库页走 store 既有刷新；打印册页刷新册列表并选中新册；
- 不新增依赖；展示组装若有纯函数逻辑放 `features/transfer/model/` 并配 vitest。

## 6. 验证方式

- 后端：`tests/transfer/` 覆盖——archive（GBK 名、zip slip、限量、包裹目录剥离）、导出规范化（三种形态 → 三层结构、UTF-8、空主标签目录条目、manifest）、analyze（外来平铺映射、包裹层下钻、子目录/根文件/.txt 警告、名称清洗、同主名拆分）、apply 三种冲突策略、导出→导入 round-trip 扫描结果等价、册导入导出（单册/全册、冲突策略、损坏 book.yaml 跳过、包裹层下钻）、TestClient 端到端；
- 验证命令：`backend/` 下 `uv run pytest`、`uv run ruff check src tests`；起服务后 `curl http://127.0.0.1:8000/api/diagnostics` 正常返回；
- 前端：`npm run typecheck`、`npm run test`、`npm run build`；
- 手动走查：模板库导出 → 解压核对三层结构 → 重新导入（冲突策略各试一次）；构造外来平铺 zip（含中文名、子目录、.txt、同主名多扩展名）走完整导入；册导出当前/所有 → 删册 → 导入恢复。

## 7. 实施顺序（原子化提交计划）

1. `docs: 添加导入/导出功能设计文档`
2. `feat(后端): 实现模板库导出与导入`
3. `feat(后端): 实现打印册导出与导入`
4. `feat(前端): 添加导入/导出弹窗组件`
5. `feat(前端): 接入模板库与打印册入口并移除 io 占位页`
6. `fix(后端): 导入识别时剥离单层包裹目录`
7. `docs: 更新导入/导出设计文档状态与进度`
