# 进度状态

> 跨会话的进度跟踪文件。会话开始时读取，会话结束前更新。
> 约定见 AGENTS.md「会话协议」。

## 进行中

- （无）

## 阻塞

- （无）

## 待办（已知但未排期）

- [模板库] 主标签重命名/换分类的前端入口（后端接口已就绪）
- [打印册] assets 资源删除接口（当前只能手动清理未引用文件）

## 最近完成

- 2026-08-08 chore: 环境子系统补缺（.nvmrc + engines 锁定 Node、desktop 依赖组纳管 pywebview、scripts/dev.ps1 一键搭建）
- 2026-08-08 docs: 精简 AGENTS.md（删项目简介、开发类硬约束下沉 global.md、指引节置顶）
- 2026-08-08 docs: 新增全局开发规范 global.md（项目摘要/开发规范/开发指南），文档地图自 AGENTS.md 下沉；backend.md 补目录结构
- 2026-08-08 docs: 命令改为逐行写法以兼容 Windows PowerShell；规则文件改用 .md 扩展名并同步引用
- 2026-08-07 docs: 重组文档体系（AGENTS.md 薄入口、docs/rules、docs/design、PROGRESS.md）
- 2026-08-07 `b9df9746` fix(前端): 修复深链接下静态资源 404 的问题
- 2026-08-07 `05561cf8` feat(前端): 引入 vue-router 统一导航
- 2026-08-07 `74a74fd3` feat(后端): 添加前端路由的 SPA 回退
- 2026-08-07 `f0124ca6` refactor(前端): 按功能域重组目录结构
