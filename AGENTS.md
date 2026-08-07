# AI 开发指引入口

## 项目简介

面向 XCPC 竞赛选手的本地训练辅助 Web 软件。前后端分离：前端 Vue 3 + Vite，后端 FastAPI + uv；已上线「模板整理」大功能下的模板库与打印册，后续会持续增加新功能。功能索引见 [README.md](README.md)，运行与部署方式见 README「快速部署指南」。

## 硬约束

违反以下任意一条即视为错误，无需权衡：

1. **永远使用中文回答**。
2. **原子化提交**：增量开发遵循原子化提交规则，提交信息遵循 git-commit-zh skill（中文约定式提交）。
3. **先判断 .gitignore**：开发新内容前，若会产生不应入库的产物，先补充 `.gitignore` 再开发。
4. **提交前必须通过验证命令**（见下表），全部通过才可提交。
5. **数据落盘必须走后端写层**：对 git 管理的数据目录（`backend/content/`、`backend/books/` 等）的写操作必须经由后端对应的 writer/store（原子写入），禁止直接编辑数据文件来绕过服务层；约定细节见 [docs/design/conventions.md](docs/design/conventions.md)。
6. **前后端功能域命名对齐**：新功能的前端 `src/features/<x>/` 与后端 `modules/<x>/` 等目录使用同一域名，域名应当仅使用纯小写英文字母。
7. **新功能文档先行**：涉及新数据存储或新 API 域的功能，先在 `docs/design/` 按 [_template.md](docs/design/_template.md) 写设计文档并在[索引](docs/design/README.md)登记，再动手实现。

## 验证命令（完成定义）

当前开发环境为 Windows PowerShell：**逐行执行命令，不要使用 `&&` 连接**。

| 改动范围 | 必跑命令 |
| --- | --- |
| 后端 | `backend/` 下依次执行 `uv run pytest`、`uv run ruff check src tests` |
| 前端 | `frontend/` 下依次执行 `npm run typecheck`、`npm run test`、`npm run build` |
| 涉及 API 契约 | 起服务后 `curl http://127.0.0.1:8000/api/diagnostics` 正常返回 |

前后端都改动时两端的命令都要跑。

## 开发规范与文档

项目摘要、开发规范、文档地图与新功能流程统一维护在 [docs/rules/global.md](docs/rules/global.md)。

规则正文统一维护在 `docs/rules/`；`.cursor/rules/` 下的同名文件只是指向它们的转发壳，不要改壳文件的正文。

## 会话协议

- **会话开始**：先读 [PROGRESS.md](PROGRESS.md) 恢复上下文；
- **会话结束**：更新 PROGRESS.md（完成/进行/阻塞条目）后再做最终提交；
- PROGRESS.md 条目尽量带对应 commit hash，与 git log 互相印证。
