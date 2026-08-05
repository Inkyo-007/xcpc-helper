"""content/ 目录变更监听：watchdog + 去抖，变更后自动重建索引。

【初学者导读】
启动后端后，如果你往 content/ 目录里加了一个模板文件，
本模块会"看到"这次文件变化，等 0.5 秒（去抖）没有新动静后，
自动调用重建索引的回调函数，让新模板立刻能被搜到。
两个类的分工：
- _DebouncedHandler：收到文件事件，负责"去抖"后调用回调
- ContentWatcher：对外提供 start()/stop()，封装 watchdog 的 Observer
"""

import logging
import threading  # 标准库：线程与定时器
from collections.abc import Callable  # Callable[[], None] 表示"无参数无返回值的函数"类型
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler  # 第三方库 watchdog：监听文件系统事件
from watchdog.observers import Observer  # watchdog 的核心：观察者，后台线程持续监听目录

logger = logging.getLogger("xcpc.watcher")


class _DebouncedHandler(FileSystemEventHandler):
    """文件事件处理器（模块私有，类名下划线开头）。

    继承 FileSystemEventHandler，重写 on_any_event，
    之后任何文件的新增/修改/删除都会调用这个方法。
    """

    def __init__(self, callback: Callable[[], None], debounce_seconds: float) -> None:
        self._callback = callback  # 去抖结束后要调用的函数（重建索引）
        self._debounce = debounce_seconds  # 去抖等待秒数
        self._timer: threading.Timer | None = None  # 当前等待中的定时器（没有则为 None）
        self._lock = threading.Lock()  # 锁：文件事件线程与定时器线程会同时改 _timer，需要保护

    def on_any_event(self, event: FileSystemEvent) -> None:
        """watchdog 每次检测到文件变化时调用本方法。"""
        if event.is_directory:
            return  # 目录本身的变化不触发重建，只关心文件
        # 写操作（writer.py）的暂存文件以 .tmp- 开头，它们随后会被原子替换/移动，
        # 属于中间态，不触发重建（最终落盘的那次 rename 会产生正常事件）
        if any(part.startswith(".tmp-") for part in Path(event.src_path).parts):
            return
        # with self._lock: 拿到锁，保证同一时间只有一个线程修改 _timer
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()  # 取消上一次的等待（这就是"去抖"的核心）
            # 新建定时器：_debounce 秒后在线程里调用 self._fire
            self._timer = threading.Timer(self._debounce, self._fire)
            # daemon=True：守护线程，主程序退出时它也跟着退出，不会卡住
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        """去抖时间到，真正执行回调（重建索引）。"""
        try:
            self._callback()
        except Exception:
            # 重建失败不能让监听线程崩溃，只记录堆栈日志
            logger.exception("自动重建索引失败")


class ContentWatcher:
    """监听 content/ 目录，文件变更去抖后触发回调（重建索引）。

    由 main.py 的 lifespan 在启动时创建并 start()，关闭时 stop()。
    """

    def __init__(self, path: Path, callback: Callable[[], None], debounce_seconds: float) -> None:
        self._path = path
        self._handler = _DebouncedHandler(callback, debounce_seconds)
        self._observer = Observer()  # watchdog 的观察者对象，内部跑一个后台线程

    def start(self) -> None:
        if not self._path.is_dir():
            logger.warning("内容目录不存在，跳过监听: %s", self._path)
            return
        # schedule(处理器, 目录, recursive=True)：递归监听整个目录树
        self._observer.schedule(self._handler, str(self._path), recursive=True)
        self._observer.daemon = True  # 守护线程：主程序退出时监听线程一起退出
        self._observer.start()
        logger.info("已开始监听内容目录: %s", self._path)

    def stop(self) -> None:
        if self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=2)  # 等监听线程结束，最多等 2 秒