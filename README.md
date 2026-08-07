# XCPC Helper

面向 XCPC 竞赛的本地训练辅助工具。当前已上线「模板库」与「打印册」：以 `backend/content/` 目录为唯一事实来源管理算法模板，后端构建全文检索索引并提供 API；打印册将模板版本、章节、文字与图片编排为可打印的册子，实时预览并导出 PDF，也可打包为桌面应用运行。

## 功能特性

- **模板库**：按 `分类/模板/版本` 三级目录组织模板，支持单版本、多版本（副标签）、单子目录自动折叠三种形态
- **全文检索**：SQLite FTS5（trigram 分词），支持中文关键词、分类与标签筛选、按更新时间/优先级排序
- **变更自动重建**：watchdog 监听 `content/` 目录，增删改模板后索引自动重建，无需重启
- **说明文档渲染**：README 正文以 Markdown 渲染，支持 `$...$` 与 `$$...$$` LaTeX 数学公式（KaTeX）
- **诊断面板**：模板缺失代码文件、front matter 异常等问题在 `/api/diagnostics` 集中呈现
- **打印册**：块式编排（章节/模板版本/文字/图片/分页符），拖拽排序与指定位置插入，实时分页预览（Paged.js），一键导出 PDF；配置存于 `backend/books/`
- **桌面模式**：pywebview 一键拉起后端并打开本地窗口

## 技术栈

| 端 | 技术 |
| --- | --- |
| 前端 | Vue 3（`<script setup>`）+ Vite 6 + TypeScript + Naive UI + CodeMirror 6 + KaTeX |
| 后端 | Python 3.12+ / FastAPI + Pydantic v2 + SQLite FTS5 + uv + watchdog |
| 桌面 | pywebview |

## 目录结构

```
xcpc-helper/
├── desktop.py              # 桌面模式入口（pywebview + 自动拉起后端）
├── docs/                   # 需求与设计文档
├── frontend/               # 前端（Vue 3 + Vite）
│   └── src/
│       ├── app/            # 应用装配层（入口、路由、布局、导航、主题）
│       ├── shared/         # 跨功能复用（组件、工具、样式、API 封装、基础类型）
│       └── features/       # 功能域（与后端模块命名对齐，各自包含 api/store/types/components）
│           ├── template/   # 模板库
│           └── printbook/  # 打印册（另含 model/ 纯函数文档模型层）
└── backend/                # 后端（FastAPI + uv）
    ├── content/            # 模板内容库（唯一事实来源，纳入 git 管理）
    │   └── <分类>/<模板>/[版本/]   # 每版本：一份代码文件 + 一份 README.md
    ├── books/              # 打印册配置库（唯一事实来源，纳入 git 管理，附示例册）
    │   └── <册名>/             # 每册：book.yaml + assets/
    ├── data/               # SQLite 索引缓存（可删除重建，不入库）
    ├── src/
    │   ├── core/           # 配置、日志、全局异常处理
    │   ├── common/         # 跨功能通用工具
    │   ├── modules/        # 领域模块（扫描、解析、FTS5 仓储、监听）
    │   ├── services/       # 业务编排层
    │   └── routers/        # API 路由层（薄层）
    └── tests/              # pytest 测试
```

模板目录约定与元数据格式详见 [docs/template-manager-design.md](docs/template-manager-design.md)。

## 快速部署指南

### 环境要求

- Node.js 18+ 与 npm
- Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)
- （可选，桌面模式）`pip install pywebview`

### 方式一：本地服务（推荐）

前端构建为静态产物，由后端统一托管，单进程即可运行：

```bash
# 1. 构建前端
cd frontend
npm install
npm run build

# 2. 启动后端（自动托管 frontend/dist 并构建检索索引）
cd ../backend
uv sync
uv run uvicorn --app-dir src main:app --host 127.0.0.1 --port 8000
```

浏览器访问 <http://127.0.0.1:8000> 即可使用。`backend/content/` 下的模板变更会被自动监听并重建索引。

### 方式二：桌面应用

```bash
pip install pywebview
cd frontend && npm install && npm run build && cd ..
python desktop.py
```

`desktop.py` 会自动拉起后端服务（127.0.0.1:8000），就绪后打开桌面窗口；关闭窗口时后端随之退出。

### 方式三：前后端分离开发

```bash
# 终端 1：后端（接口变更自动重载）
cd backend
uv run uvicorn --app-dir src main:app --reload --port 8000

# 终端 2：前端（/api 已代理到 8000 端口）
cd frontend
npm install
npm run dev
```

访问 Vite 输出的地址（默认 <http://localhost:5173>）。

## 常用命令

| 目的 | 命令 |
| --- | --- |
| 后端测试 | `cd backend && uv run pytest` |
| 前端类型检查 | `cd frontend && npm run typecheck` |
| 前端生产构建 | `cd frontend && npm run build` |
| 手动重建索引 | `curl -X POST http://127.0.0.1:8000/api/templates/reload` |

## API 概览

| 接口 | 说明 |
| --- | --- |
| `GET /api/templates` | 模板列表（支持 `category` / `tags` / `keyword` / `sort` 参数） |
| `GET /api/templates/{id}` | 模板详情（含各版本代码与 README 正文） |
| `GET /api/categories` | 分类列表及模板计数 |
| `GET /api/diagnostics` | 内容库诊断信息 |
| `POST /api/templates/reload` | 手动重建索引 |

## 添加新模板

在 `backend/content/<分类>/<模板>/` 下放置代码文件与 `README.md` 即可，watcher 会自动重建索引。多版本模板为每个版本建立子目录。README 采用 YAML front matter：

```markdown
---
updated: 2026-07-05
tags: ['连通性']
source: '洛谷 P3367'        # 可选，与 page 配合展示
page: 'https://...'          # 可选
priority: 5                  # 可选，1-5，影响排序
---

正文（Markdown，支持 $O(1)$ 公式）……
```
