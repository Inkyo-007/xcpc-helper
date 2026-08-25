# 进度状态

> 跨会话的进度跟踪文件。会话开始时读取，会话结束前更新。
> 约定见 AGENTS.md「会话协议」。

## 进行中

- （无）

## 阻塞

- （无）

## 最近完成

### 2026-08-25 会话 5

- `5cfbb6ec` feat(activity): 新增 QOJ 平台适配器
- `37967a12` fix(前端): AccountBindModal 添加 QOJ cookie 平台注册

### 2026-08-24 会话 4

- `27caad86` feat(后端): VJudge 适配器改为匿名模式，使用 /status/data 端点
- `afd99772` fix(后端): VJudge 请求添加浏览器标识头绕过 Cloudflare 403
- `90af984a` fix(后端): VJudge 请求补充 User-Agent 头
- `088e442e` docs: 更新 VJudge 相关设计文档

### 2026-08-24 会话 3

- `7f0504dc` feat(后端): 新增 VJudge 适配器（Playwright 一键登录 + Cookie 授权）

### 2026-08-24 会话 2

- `c7f15ecb` fix(后端): LeetCode CN 提交 problem_key 改用 frontendId
- `981fcf1c` feat(前端): activity overview 网址同步增加用户组参数
- `c0dd42eb` fix(后端): 启动同步改为遍历所有用户组全部账号

### 2026-08-24 会话 1

- `e265c8fd` fix(前后端): 禁用 LeetCode CN Playwright 一键登录（滑块验证无法绕过）
- `e67d8f0a` fix(后端): LeetCode CN verify 优先使用 realName 作为显示名
- `f06e3194` style(前端): 调整 LeetCode CN 绑定 UID 输入框样式与文案
- `b5a5b595` fix(前端): 修复 LeetCode CN 手动绑定验证按钮不可用及平台名称
- `ba19f403` feat(后端): 新增 LeetCode CN 适配器（Cookie 授权 + GraphQL Batch Query）

### 2026-08-15 会话 2

- `e9738a35` feat(前端): 版本号从 package.json 动态读取
- `505e4ddd` fix(前端): 修复主题色相在 activity 页面不生效及配色不协调问题

### 2026-08-15 会话 1

- `e259f7a3` test(后端): 补充 AtCoder 适配器录制 fixture 测试
- `c5f85dc0` feat(后端): 新增 AtCoder 适配器并注册
- `efd731d7` feat(后端): net 层 4xx 错误抛带状态码的 HttpStatusError
- `7be2c424` docs: 补充 AtCoder 适配器设计与 net 层状态码错误约定
