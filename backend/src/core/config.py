"""应用配置。

所有配置项均可通过环境变量覆盖，前缀为 XCPC_，例如：
    XCPC_CONTENT_DIR=D:/templates
    XCPC_WATCH_ENABLED=false

【本文件在全局中的位置】
这是整个后端的"配置中心"。main.py、database.py、service.py
等文件通过 get_settings() 拿到同一份配置对象，
决定程序"在哪里读模板、把数据库放哪、监听是否开启"等。
"""

from functools import lru_cache  # 标准库：缓存函数返回值（避免重复计算）
from pathlib import Path  # 标准库：面向对象的路径类型

from pydantic_settings import BaseSettings, SettingsConfigDict  # 第三方库：从环境变量读配置

# backend/
# Path(__file__) 是当前文件（config.py）的路径；
# .resolve() 转成绝对路径；.parents[2] 表示往上走两级：
# core/config.py -> core/ -> src/ -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
# 仓库根目录（backend/ 的上一级）
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """全局配置项。

    BaseSettings 是 pydantic-settings 提供的配置基类：
    创建 Settings() 时，它会自动读取环境变量并做类型转换。
    例如环境变量 XCPC_PORT=8080 会把下面的 port 改成 8080；
    没设置的环境变量就使用等号右边的默认值。
    """

    # model_config 告诉 BaseSettings 一些读取规则
    # env_prefix="XCPC_"：只认以 XCPC_ 开头的环境变量
    # extra="ignore"：遇到不认识的环境变量时忽略，不报错
    model_config = SettingsConfigDict(env_prefix="XCPC_", extra="ignore")

    # ===== 服务相关 =====
    host: str = "127.0.0.1"  # 服务监听的地址（本机）
    port: int = 8000  # 服务监听的端口
    # 允许跨域访问本后端的前端地址（开发时前端跑在 5173 端口）
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ===== 数据相关 =====
    # 模板库内容目录（唯一事实来源）：所有模板文件都放在这里
    content_dir: Path = BACKEND_ROOT / "content"
    # SQLite 检索索引缓存目录：索引可随时删除重建
    data_dir: Path = BACKEND_ROOT / "data"
    db_name: str = "index.db"

    # ===== 文件监听相关 =====
    # 是否监听 content/ 变更并自动重建索引
    watch_enabled: bool = True
    # 文件变更后的去抖时间（秒），避免保存文件时频繁重建
    watch_debounce_seconds: float = 0.5

    # ===== 前端相关 =====
    # 前端构建产物目录（存在时由 FastAPI 直接托管，无需单独启动前端）
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"

    @property  # 装饰器：把这个方法伪装成“属性”，用法是 settings.db_path 而不是 settings.db_path()
    def db_path(self) -> Path:
        """数据库文件的完整路径 = 缓存目录 + 文件名。"""
        return self.data_dir / self.db_name  # Path 支持用 / 拼接路径


# lru_cache 装饰器：第一次调用 get_settings() 才真正创建 Settings()，
# 之后每次调用都直接返回缓存的同一份对象（全局单例），
# 避免反复读取环境变量、反复创建对象。
@lru_cache
def get_settings() -> Settings:
    return Settings()
