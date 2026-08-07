---
description: 前端开发规范（Vue 3 + Naive UI + TypeScript）
globs: frontend/**
alwaysApply: false
---

# 前端开发规范

## 技术栈

**框架**

- Vue 3（3.5，`<script setup>` + Composition API）
- Vite 6（构建与开发服务器）
- TypeScript 5.7 + vue-tsc（类型检查）
- vue-router 4（导航）

**UI 与代码展示**

- Naive UI 2.41：组件库（按钮、输入框、下拉、弹层等），配合 NConfigProvider 做主题定制
- CodeMirror 6：代码展示（C++ 语法高亮、只读、自动换行、自定义主题）
- KaTeX + marked：Markdown 与数学公式渲染
- Paged.js + highlight.js：打印分页与打印视图静态高亮
- lucide-vue-next：图标库
- vitest：单元测试

## 目录结构

```plaintext
frontend/src/
├── app/            # 应用装配层（入口、路由、布局、导航、主题）
├── shared/         # 跨功能复用（组件、工具、样式、API 封装、基础类型）
└── features/       # 功能域（与后端模块命名对齐）
    └── <功能>/     # 各自包含 api / store / types / components，需要时加 model/ 纯函数层
```

## 规范

1. **组件规范性**：前端页面必须尽可能使用 Naive UI 组件进行原子化样式开发
2. **统一性**：必须使用和当前样式统一的样式和行为；图标统一使用 lucide-vue-next
3. **主题集成**：样式必须随主题变化而变化，不写死颜色
4. **可扩展性**：可根据需要扩展新的类型或样式
5. **简单易用**：提供简洁的 API，降低使用门槛
6. **功能域对齐**：新功能在 `features/` 下开与后端同名的目录；跨功能复用的组件/工具提升至 `shared/`
7. **纯函数可测**：`model/` 等纯函数模块必须配 vitest 单元测试（`*.test.ts` 与源码同目录）

## 验证命令

以下命令均在 `frontend/` 目录下逐行执行：

- `npm run typecheck`：类型检查（改动后必跑）
- `npm run test`：vitest 单元测试
- `npm run build`：生产构建（含 vue-tsc）
