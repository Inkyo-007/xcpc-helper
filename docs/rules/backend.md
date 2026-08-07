---
description: 后端开发规范（FastAPI + Pydantic v2 + uv）
globs: backend/**
alwaysApply: false
---

# 后端开发规范

## 技术栈

- Python 3.12+ + FastAPI + Pydantic v2
- SQLModel + SQLite（FTS5，仅作索引/缓存）
- uv（依赖与虚拟环境管理）
- watchdog（文件监听）
- pytest + pytest-asyncio + httpx（测试）
- ruff（lint，配置在 pyproject.toml）

## 目录结构

```plaintext
backend/
├── content/            # 模板库数据（git 管理的事实来源）
├── books/              # 打印册配置（git 管理的事实来源）
├── data/               # SQLite 索引缓存（可删除重建，不入库）
├── src/
│   ├── main.py         # FastAPI 入口：挂路由、全局异常处理、托管前端 dist/
│   ├── core/           # 基础设施：config / database / exceptions / logging
│   ├── common/         # 跨功能通用件（通用响应模型、工具函数、名称校验）
│   ├── modules/<功能>/  # 领域核心（models / schemas / 存储与解析）
│   ├── services/<功能>/ # 业务编排层
│   └── routers/<功能>/  # API 路由层（薄层）
└── tests/<功能>/        # 测试按功能目录镜像组织
```

- `routers/`：仅做参数校验与调用 service，不写业务逻辑；不宽泛 try/except，不记录堆栈，异常统一交由全局异常处理器；
- `modules/<功能>/`：SQLModel 表模型放 `models.py`，API 请求/响应的 Pydantic 模型放 `schemas.py`（对外契约与内部存储分离）；某 schema 被多功能共用时再提升至 `common/`；
- 不单独设立 `api/` 目录：路由聚合由 `main.py` / `routers/__init__.py` 承担，API 公共件归属 `common/`；
- 测试在 `backend/tests/<功能>/` 按功能目录镜像组织；
- 功能间依赖必须单向（如 `printbook → template`），被依赖方不感知依赖方。

## 规范

- 执行完全严格的类型注解，除非必要不使用 `# type: ignore` 等方式忽略类型错误
- 任何与外部系统交互的数据第一时间转化为 Pydantic 模型，尽可能不使用 `dict[key]` 来获取数据
- 异步优先原则，禁止同步阻塞；确实需要同步调用的走 `asyncio.to_thread`
- 路由层禁止宽泛 `try/except`，仅捕获特定异常；其他异常交由全局异常处理器
- 路由层禁止 `logger.exception`，统一由全局异常处理器记录堆栈
- API 返回使用标准 HTTP 状态码，错误响应由全局处理器统一结构化
- 分层职责、功能扩展方式、文件写入与名称校验等架构约定见 [../design/conventions.md](../design/conventions.md)
- 新功能在 `routers/`、`services/`、`modules/` 下开平级功能目录，并在 `tests/<功能>/` 镜像组织测试

## 验证命令

以下命令均在 `backend/` 目录下逐行执行：

- `uv run pytest`：全部测试（改动后必跑）
- `uv run ruff check src tests`：lint
