"""SQLite 连接管理。

SQLite 在本项目中仅作为 FTS5 检索索引与元数据缓存，
可随时删除重建，因此不引入迁移工具，建表由仓储层负责。
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from core.config import get_settings


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # 本地单用户场景，开启 WAL 提升并发读体验
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """获取数据库连接，退出时自动提交/回滚并关闭。"""
    path = db_path if db_path is not None else get_settings().db_path
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
