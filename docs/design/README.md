# 设计文档索引

各功能的设计与实现细节按功能分文档维护，公共架构约定单独成文。

| 文档 | 功能域 | 状态 |
| --- | --- | --- |
| [conventions.md](conventions.md) | 跨功能公共约定 | 长期有效 |
| [template-library.md](template-library.md) | 模板库（template） | 已实现 |
| [printbook.md](printbook.md) | 打印册（printbook） | 已实现 |
| [transfer.md](transfer.md) | 导入 / 导出（transfer） | 已实现 |
| [activity.md](activity.md) | 训练统计聚合（activity） | 设计中 |

## 状态约定

- **设计中**：文档先行，实现尚未开始或进行中；
- **已实现**：功能已上线，文档描述现状，后续变更需同步更新本文档；
- **已归档**：功能废弃或文档被取代，保留备查。

## 新功能流程

1. 复制 [_template.md](_template.md) 为 `<功能名>.md`，先完成"设计中"版本；
2. 在本表登记条目与状态；
3. 实现过程中设计有变的，先改文档再改代码；
4. 功能上线后将状态改为"已实现"。
