"""模板库功能：content/ 目录扫描、README 解析、检索索引。

【初学者导读】
这个目录里的 6 个文件各司其职（按数据流向排序）：

- models.py     定义"扫描产物"长什么样（内存中的数据结构）
- parser.py     解析单个 README.md：开头的 YAML 元数据 + 后面的正文
- scanner.py    遍历 content/ 目录，把模板文件变成 models.py 里的对象
- repository.py 把扫描结果写入 SQLite 并建全文索引，提供查询函数
- watcher.py    监听 content/ 目录变化，自动触发重建
- schemas.py    定义 API 对前端暴露的数据格式（响应模型）
"""
