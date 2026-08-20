# AI 开发指引入口

## 开发规范与文档

项目摘要、开发规范、文档地图与新功能流程统一维护在 [docs/rules/global.md](docs/rules/global.md)，开始任何开发前必须先读。

规则正文统一维护在 `docs/rules/`；`.cursor/rules/` 下的同名文件只是指向它们的转发壳，不要改壳文件的正文。

## 硬约束

违反以下任意一条即视为错误，无需权衡：

1. **永远使用中文回答**。
2. **原子化提交**：增量开发遵循原子化提交规则，提交信息遵循 git-commit-zh skill（中文约定式提交）。
3. **提交前必须通过验证命令**（见下表），全部通过才可提交。

## 验证命令（完成定义）

以下命令在 Windows / Linux / macOS 下一致；在 Windows PowerShell 中请**逐行执行命令，不要使用 `&&` 连接**。

| 改动范围 | 必跑命令 |
| --- | --- |
| 后端 | `backend/` 下依次执行 `uv run pytest`、`uv run ruff check src tests` |
| 前端 | `frontend/` 下依次执行 `npm run typecheck`、`npm run test`、`npm run build` |
| 涉及 API 契约 | 起服务后 `curl http://127.0.0.1:8000/api/diagnostics` 正常返回 |

前后端都改动时两端的命令都要跑。

## 会话协议

- **会话开始**：先读 [PROGRESS.md](PROGRESS.md) 恢复上下文；
- **会话结束**：当用户明确会话将结束或指示更新 PROGRESS.md 时，更新 PROGRESS.md（完成/进行/阻塞条目）后再做最终提交；除此之外不得随意编写 PROGRESS.md 的内容。
- `PROGRESS.md` 条目必须带上对应的 commit hash，与 git log 互相印证。