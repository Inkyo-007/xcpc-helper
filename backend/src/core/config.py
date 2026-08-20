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

    # 训练统计：用户数据目录（data/user/<userid>/，第一期固定 default）
    user_data_dir: Path = BACKEND_ROOT / "data" / "user"

    # 训练统计：全量同步与聚合窗口（对齐前端热力图"近一年"）。
    # 属功能域配置而非平台策略：经 service → sync 传给 adapter 的
    # fetch_submissions 参数，adapter 不内置这些值。
    activity_window_days: int = 370
    # 全量同步至少拉取的条数：窗口内不足时拉满该数（为 all-time 总量留缓冲）
    activity_full_min_rows: int = 5000
    # 应用启动时自动同步当前用户组全部账号（后台执行，失败降级为账号诊断）
    activity_sync_on_startup: bool = True

    # 是否监听 content/ 变更并自动重建索引
    watch_enabled: bool = True
    # 文件变更后的去抖时间（秒），避免频繁重建
    watch_debounce_seconds: float = 0.5

    # 导入/导出：zip 限量与上传暂存区
    transfer_max_entries: int = 5000
    transfer_max_total_mb: int = 200
    transfer_max_file_mb: int = 20
    # analyze 与 apply 之间暂存目录的保留时长（秒）
    transfer_staging_ttl_seconds: int = 3600

    # 前端构建产物目录（存在时由 FastAPI 托管）
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    @property
    def staging_dir(self) -> Path:
        return self.data_dir / ".staging"


@lru_cache
def get_settings() -> Settings:
    return Settings()
