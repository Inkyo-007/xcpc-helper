# 设计文档索引

各功能的设计与实现细节按功能分目录维护，跨功能公共架构约定单独成文。

| 文档 | 功能域 | 状态 |
| --- | --- | --- |
| [conventions.md](conventions.md) | 跨功能公共约定 | 长期有效 |
| [template/template-library.md](template/template-library.md) | 模板库（template） | 已实现 |
| [template/printbook.md](template/printbook.md) | 打印册（printbook） | 已实现 |
| [template/transfer.md](template/transfer.md) | 导入 / 导出（transfer） | 已实现 |
| [activity/conventions.md](activity/conventions.md) | 训练统计聚合（activity）公共约定 | 已实现 |
| [activity/codeforces.md](activity/codeforces.md) | activity · Codeforces 适配 | 已实现 |
| [activity/atcoder.md](activity/atcoder.md) | activity · AtCoder 适配 | 已实现 |
| [activity/luogu.md](activity/luogu.md) | activity · 洛谷适配（cookie 授权 + 反爬 + UNAC 精化） | 已实现 |
| [activity/nowcoder.md](activity/nowcoder.md) | activity · 牛客竞赛适配（HTML 解析 + 时区转换） | 已实现 |
| [activity/leetcode-cn.md](activity/leetcode-cn.md) | activity · LeetCode CN 适配（Cookie + GraphQL Batch Query） | 已实现 |
| [activity/vjudge.md](activity/vjudge.md) | activity · VJudge 适配（Playwright 一键登录 + Cookie 授权） | 已实现 |

## 状态约定

- **设计中**：文档先行，实现尚未开始或进行中；
- **已实现**：功能已上线，文档描述现状，后续变更需同步更新本文档；
- **已归档**：功能废弃或文档被取代，保留备查。

## 新功能流程

1. 复制 [_template.md](_template.md) 为 `<功能目录>/<功能名>.md`，先完成"设计中"版本
   （新功能域则新建目录；现有功能域的子功能直接放进对应目录）；
2. 在本表登记条目与状态；
3. 实现过程中设计有变的，先改文档再改代码；
4. 功能上线后将状态改为"已实现"。
