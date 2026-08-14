---
description: 全局开发规范（项目摘要、开发规范、开发指南）
alwaysApply: true
---

# 全局开发规范

## 项目摘要

面向 XCPC 竞赛选手的本地训练辅助 Web 软件。前后端分离：前端 Vue 3 + Vite，后端 FastAPI + uv；本地部署、离线可用、Windows 优先。已上线部分功能（具体内容见设计文档索引 [../design/README.md](../design/README.md)），后续会持续增加新功能。

## 开发规范

1. 先主动审查所有依赖与相关文件，再规划实现方案。
2. 禁止假定、猜测任何实现；行为以代码与设计文档为准。
3. 除非用户要求，否则保持最小化修改，不顺手重构无关代码。
4. 对参考信息有困惑时主动提问，不要带着歧义开工。
5. 永远保持项目工程化、整洁性、可维护性，合理拆分功能模块。
6. 优先复用仓库现有的模式、组件与工具函数，不重复造轮子；引入新依赖、新抽象前必须有明确收益。
7. 开发新内容前先判断是否需要补充 `.gitignore`，需要则先补充再开发。
8. 数据落盘必须走后端写层：对 git 管理的数据目录（`backend/content/`、`backend/books/` 等）的写操作必须经由后端对应的 writer/store（原子写入），禁止直接编辑数据文件绕过服务层；约定细节见 [../design/conventions.md](../design/conventions.md)。
9. 修改 API 契约或数据格式时，同步更新 `docs/design/` 对应设计文档。
10. 交付前跑通改动范围对应的验证命令（见根目录 AGENTS.md「验证命令」）。
11. 当新功能开发完成，且所有验证通过时，同步更新文档内容，使文档维持时效性。

## 开发指南

### 文档地图

| 位置 | 内容 |
| --- | --- |
| [frontend.md](frontend.md) | 前端开发规范（技术栈、目录结构、组件与测试要求） |
| [backend.md](backend.md) | 后端开发规范（技术栈、目录结构、类型注解、异步、异常处理） |
| [../design/README.md](../design/README.md) | 设计文档索引（按功能分文档，含状态与新功能流程） |
| [../design/conventions.md](../design/conventions.md) | 跨功能公共架构约定（分层、扩展方式、写入约定、鲁棒哲学） |
| [../requirements.md](../requirements.md) | 功能清单（含优先级）与非功能需求 |
| [../../PROGRESS.md](../../PROGRESS.md) | 跨会话进度状态（会话开始读取、结束更新） |
| [../../README.md](../../README.md) | 项目介绍（面向用户：功能说明、快速上手、反馈入口） |
| [../development.md](../development.md) | 开发者文档（技术栈、目录结构、部署方式、API 概览） |

### 新功能开发流程

1. 涉及新数据存储或新 API 域时，先在 `docs/design/` 按 [_template.md](../design/_template.md) 写设计文档，并在[索引](../design/README.md)登记状态；
2. 前端 `src/features/<x>/` 与后端 `modules/<x>/` 使用同一域名（纯小写英文字母）；
3. 按原子化提交推进，提交信息遵循 git-commit-zh skill（中文约定式提交）；
4. 功能上线后更新设计文档状态。
