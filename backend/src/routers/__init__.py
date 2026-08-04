"""路由层：各功能一个子目录，薄路由，异常交由全局处理器。

【初学者导读】
routers/ 是后端最靠近前端的一层：把 HTTP 请求翻译成对 services/ 的调用。
本层的职责只有三件小事：
1. 解析 URL 和查询参数（FastAPI 自动完成大部分）
2. 调用对应的 service 方法
3. 返回响应（FastAPI 自动按 response_model 序列化成 JSON）
不在这里写业务逻辑、也不在这里捕获异常（交给 core/exceptions.py）。
"""
