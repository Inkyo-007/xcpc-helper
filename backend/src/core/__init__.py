"""基础设施层：配置、数据库、异常、日志等横切能力。

【初学者导读】
core/ 目录是整个后端的"地基"，不包含任何具体业务，
而是给上层代码提供四样通用工具：

- config.py     全局配置（端口、目录、是否监听文件变化……）
- database.py   SQLite 数据库连接的创建与自动收尾
- exceptions.py 自定义业务异常 + 全局异常处理器
- logging.py    日志格式配置

上层的 routers/services/modules 都会从这里拿工具用。
"""
