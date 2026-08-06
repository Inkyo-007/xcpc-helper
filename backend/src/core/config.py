"""应用配置。

所有配置项均可通过环境变量覆盖，前缀为 XCPC_，例如：
    XCPC_CONTENT_DIR=D:/templates
    XCPC_WATCH_ENABLED=false
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
# 仓库根目录（backend/ 的上一级）
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """全局配置项。"""

    model_config = SettingsConfigDict(env_prefix="XCPC_", extra="ignore")

    # 服务
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 模板库内容目录（唯一事实来源）
    content_dir: Path = BACKEND_ROOT / "content"
    # 打印册配置目录（唯一事实来源，每册一个子目录：book.yaml + assets/）
    books_dir: Path = BACKEND_ROOT / "books"
    # SQLite 检索索引缓存目录
    data_dir: Path = BACKEND_ROOT / "data"
    db_name: str = "index.db"

    # 是否监听 content/ 变更并自动重建索引
    watch_enabled: bool = True
    # 文件变更后的去抖时间（秒），避免频繁重建
    watch_debounce_seconds: float = 0.5

    # 前端构建产物目录（存在时由 FastAPI 托管）
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name


@lru_cache
def get_settings() -> Settings:
    return Settings()
