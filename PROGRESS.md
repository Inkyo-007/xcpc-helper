# 进度状态

> 跨会话的进度跟踪文件。会话开始时读取，会话结束前更新。
> 约定见 AGENTS.md「会话协议」。

## 进行中

- （无）

## 阻塞

- （无）

## 最近完成

### 2026-08-16 会话 1

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

### 2026-08-14 会话 2

- `bde82db8` fix(前端): 头像裁剪尺寸提升至 512px 消除显示模糊

### 2026-08-14 会话 1

- `c26a2342` docs: 同步用户组（目录即组、ID 与组名分离）与信息卡 API 设计
- `cf6be31b` fix(后端): 信息卡 avatar 显式传 null 可清除头像
- `8c0e46e2` feat(前端): 用户组接入后端（新建/切换/重命名/删除真实生效）
- `127f0a9e` feat(后端): 服务层多用户组管理与信息卡 API
- `21bdbb0e` feat(后端): 用户组目录管理与同步按组隔离
- `2029f59e` feat(前端): 提交记录行底显示平台并移除行首平台标签
- `183b00f3` docs: 更新编辑用户组弹窗的平台账号列表与解绑入口说明
- `e83ebf93` feat(前端): 编辑用户组弹窗支持绑定与解绑平台账号
- `a8e61a84` docs: 更新编辑用户组弹窗与解绑入口移除的设计说明
- `fb89bde0` feat(前端): 新增编辑用户组弹窗并替换账号管理弹层
- `35975de0` refactor(前端): 移除用户组下拉菜单内的删除按钮
- `6eef1ccb` docs: 补充用户组删除与同步范围确认的设计说明
- `37e1687c` feat(前端): 汇总视图同步全部平台前弹确认框
- `696f78b1` feat(前端): 用户组菜单支持删除用户组
- `0c769713` feat(前端): 绑定与同步期间显示全屏加载遮罩
- `653fc84f` fix(前端): 收窄近期提交分页栏槽位防止溢出左栏

### 2026-08-13 会话 4

- `b9092a0f` feat(后端): 同步状态支持凭据过期标记与绑定验证能力校验
- `62e7da45` refactor(后端): net 层抽象通用 request 并支持凭据与单次重试覆盖
- `5a734845` feat(后端): 扩展平台适配契约（能力方法默认抛错、rating/contests 骨架）
- `64b1df9e` fix(后端): 强化 Codeforces 提交数据的必填校验与空值收敛
- `9fd274ef` refactor(后端): 全量同步窗口配置上移至 Settings
- `2ba52dcd` refactor(后端): Codeforces 适配器外部数据第一时间转 Pydantic 模型
- `502e5e13` fix(后端): 重试退避基准与平台限流间隔联动
- `b9c73378` fix(后端): 修正适配器边界与结构清理（游标防漏、difficulty 放宽、模块更名）
- `5f7ffeb8` fix(后端): 历史旧格式题目链接读取时幂等迁移为新格式
- `a90d59eb` feat(后端): 近期提交改为返回最后 200 次提交
- `6c94c4d3` fix(后端): Codeforces 题目外链按 contestId 区分主题库与 gym 题库

### 2026-08-13 会话 3

- `dd82e36e` docs: 标记训练统计聚合设计文档为已实现并同步第一期实现细节
- `49f232f5` feat(前端): activity 接入真实后端 API 并移除 mock 数据
- `cc0a2ca8` fix(后端): 绑定验证遇平台故障返回 502 而非 500
- `38144230` chore: 训练统计用户组运行数据不入库（保留 example 样例）
- `0a74977b` chore(后端): 同步 uv.lock（httpx 移入主依赖）
- `aa9b8557` feat(后端): 实现同步引擎与 activity API
- `2e476c69` feat(后端): 实现 activity 数据模型与 user 目录读写层（含 example 样例）
- `5578c7b3` feat(后端): 搭建 adapters 基座并实现 Codeforces 适配器
- `aee9223e` chore(后端): 提升 httpx 为主依赖并补充 activity 用户数据目录配置
- `cdcc3c76` feat(前端): 新增 JG 评测中 verdict 徽章并采用浅蓝配色
- `38352a5b` docs: 补充 JG 评测中 verdict 的模型枚举与徽章配色说明

### 2026-08-13 会话 1

- `565e46e7` docs: 更新训练统计热力图交互、近期提交分页与网址同步设计
- `3cbe2983` feat(前端): 热力图改为 DOM 网格并支持格子上浮与选中淡化动效
- `47579cb0` feat(前端): 再次点击热力图格子取消选中并移除明细返回按钮
- `f0a2cc3b` feat(前端): 近期提交每页 10 条并添加分页导航，页面改为整页滚动
- `756bf8b6` feat(前端): 页码与平台筛选同步到网址 query
- `1135047c` feat(前端): 热力图悬浮提示添加淡入淡出与位移过渡
