"""SQLite 连接管理。

SQLite 在本项目中仅作为 FTS5 检索索引与元数据缓存，
可随时删除重建，因此不引入迁移工具，建表由仓储层负责。

【本文件在全局中的位置】
modules/template/repository.py 是唯一的调用方。
它每次通过 with get_connection(...) as conn: 拿到连接执行 SQL，
退出 with 时本文件自动完成 提交/回滚/关闭。
"""

import sqlite3  # Python 标准库自带的 SQLite 数据库驱动
from collections.abc import Iterator  # 类型：迭代器，用于标注生成器函数的返回类型
from contextlib import contextmanager  # 装饰器：把生成器函数变成可以用 with 的“上下文管理器”
from pathlib import Path  # 标准库：面向对象的路径类型

from core.config import get_settings  # 项目内部：拿全局配置（数据库文件放哪）


def _connect(db_path: Path) -> sqlite3.Connection:
    """创建并配置一个 SQLite 连接。

    函数名以下划线开头，是"模块私有函数"的约定：
    只在本文件内部使用，其他模块请用 get_connection()。
    """
    # 先确保数据库文件所在的目录存在：
    # parents=True 表示连父目录一起创建；exist_ok=True 表示已存在时不报错
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 打开（不存在则创建）数据库文件，得到连接对象 conn。
    # check_same_thread=False：允许连接被其他线程使用。
    # 因为路由层会用 asyncio.to_thread 把同步代码丢到线程池执行，
    # 这里放宽 SQLite "连接只能被创建它的线程使用" 的默认限制。
    conn = sqlite3.connect(db_path, check_same_thread=False)

    # 设置查询结果每行是 sqlite3.Row 对象：
    # 之后就可以写 row["id"] 这样按列名取值，而不是只能 row[0] 按下标取值
    conn.row_factory = sqlite3.Row

    # PRAGMA 是 SQLite 专有的设置命令。
    # 本地单用户场景，开启 WAL 提升并发读体验：
    # 读写互不阻塞，避免"重建索引（写）时查询（读）被卡住"
    conn.execute("PRAGMA journal_mode=WAL")
    # SQLite 默认不检查外键，必须显式开启；
    # 开启后删除模板时才能级联删除它的版本记录（见 repository.py 的建表语句）
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# @contextmanager 装饰器：把下面的"生成器函数"变成上下文管理器，
# 之后就可以用 with get_connection(...) as conn: 的方式使用。
# 规则：yield 之前的代码在"进入 with"时执行（准备资源），
#       yield 产出的值赋给 as 后面的变量，
#       yield 之后的代码在"退出 with"时执行（收尾清理）。
@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """获取数据库连接，退出时自动提交/回滚并关闭。

    参数 db_path 可传可不传（Path | None 表示"可以是 Path 也可以是 None"）：
    - 传了：用传入的数据库路径（测试时很有用）
    - 没传：用全局配置里的默认路径
    """
    # 三元表达式：条件成立取前者，否则取后者
    path = db_path if db_path is not None else get_settings().db_path
    conn = _connect(path)
    try:
        # yield 是"暂停点"：把 conn 交给 with 块使用，函数停在这里等待。
        yield conn
        # 如果 with 块里的 SQL 正常执行完，回到这里提交事务，让写入真正落库
        conn.commit()
    except BaseException:
        # 如果 with 块里抛了异常：回滚事务，不留半成品数据。
        # BaseException 范围比 Exception 更广，连 Ctrl+C 中断也会触发回滚。
        conn.rollback()
        # 不带参数的 raise 把原来的异常原样继续抛给调用方
        raise
    finally:
        # finally 无论成功还是失败都会执行：连接必须关闭，释放文件句柄
        conn.close()
