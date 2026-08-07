# 模板库（template）设计

> 状态：已实现。背景与需求优先级见 [../requirements.md](../requirements.md)，
> 跨功能公共约定见 [conventions.md](conventions.md)。

## 1. 定位

- `backend/content/` 目录是模板库的**唯一事实来源**，纳入 git 管理，选手按约定格式手动维护文件；
- SQLite 不作为业务数据库，仅作为 FTS5 全文检索索引 + 元数据缓存，可随时删除重建；
- 后端通过 watchdog 监听 `content/` 变更，**自动重建索引**，改动即时生效；
- `POST /api/templates/reload` 是 watcher 之外的手动兜底。

## 2. 目录约定

```plaintext
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

- content 下的每个一级目录自动成为一个分类，该目录下的模板归属于该分类；
- 分类下的每个目录视为一份模板，目录名即主标签名称；主标签目录可包含多个副标签目录；
- 扫描器统一识别三种形态：模板目录直接含代码文件（顶层单版本）、含多个副标签子目录（多版本）、只含一个子目录（折叠为单版本）；
- 目录、文件名约定为英文，但必须适配中文名称：路径出现中文名时应正确识别、提取并显示，不出现报错、乱码。

## 3. 版本内容与元数据

每个版本包含一份代码文件与一份 `README.md`。README 采用 YAML front matter：

```plaintext
---
updated: 2026-07-29
tags: ['素数', '积性函数']
source: '洛谷 P3383'
page: 'https://www.luogu.com.cn/problem/P3383'
priority: 5
---

正文说明...
```

- **updated**：非必填。填写后在小标题显示更新日期；
- **tags**：非必填。显示为标题右侧胶囊小标签，可用于检索；
- **source**：非必填。填写后在小标题显示来源；
- **page**：非必填。填写时 **source 必须填写**，source 渲染为指向该网址的超链接（主题色）；
- **priority**：非必填，缺省为 2。数值越大显示优先级越高；
- **正文说明**：非必填。渲染为代码底部的说明框，支持 Markdown 与 KaTeX 公式。

模板标题直接取自目录名，无需在元数据中重复声明；规范之外的字段（如历史遗留的 title）静默忽略，不产生诊断。

多版本模板在列表页展示聚合元信息：更新日期取所有版本最晚值，优先级取最大值，tags 取并集；详情页切换版本时，小标签与说明框跟随当前版本各自的元信息。

## 4. 维护方式

两种维护方式可混用：

1. **手动维护**：直接编辑 content/ 目录，watcher 自动重建索引；格式有误时前端显示诊断提示，鲁棒性尽量强；
2. **可视化增删改**（已实现）：模板库页面提供全部交互入口——
   - 工具栏"新增模板"按钮创建空主标签（仅分类 + 模板名，分类可新）；
   - 所有主标签均可展开，展开区末尾的 + 胶囊新建版本（名称/元数据/代码/说明）；
   - 详情页右上角编辑、删除当前版本；代码与说明均支持上传本地文件或手动输入；
   - 删光所有版本后，空页面提供"删除模板"按钮移除整个主标签。

**空主标签**：完全为空的模板目录是合法状态（可视化新建的占位模板），
正常进入列表与详情（无版本字段为空、优先级取默认值 2），不产生诊断；
目录内有内容却凑不出任何版本仍属于格式错误，保留 error 诊断。

可视化写操作的约定：

- 名称统一校验（规则见 [conventions.md](conventions.md)），中文正常放行；
- README 由表单数据全量生成：缺省字段不写入 front matter，priority 为默认值 2 时省略；规范外的历史字段在首次编辑保存后丢弃；
- 新建版本经 .tmp 暂存目录原子就位，更新走临时文件 + 原子替换；删除为物理删除（前端确认弹窗明确提示不可找回）；
- 删除非空模板被拒绝（409），需先删除其所有版本；删除/移动后空分类目录自动清理；
- 顶层单版本（代码直接在模板目录下）在写 API 的 URL 中用保留字 `~` 寻址；
- 写操作统一由 `modules/template/writer.py` 落盘；
- 主标签重命名/换分类暂仅提供后端接口，前端入口后续补。

## 5. API

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

## 6. 验证方式

- 后端：`cd backend && uv run pytest`（`tests/template/` 覆盖 scanner/parser/repository/service/writer）；
- 涉及 API 契约变更时：起服务后 `curl http://127.0.0.1:8000/api/diagnostics` 应正常返回；
- 中文路径、三种目录形态、空主标签是重点回归场景。
