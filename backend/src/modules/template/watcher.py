"""content/ 目录变更监听：watchdog + 去抖，变更后自动重建索引。"""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("xcpc.watcher")


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[], None], debounce_seconds: float) -> None:
        self._callback = callback
        self._debounce = debounce_seconds
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        # 写操作（writer.py）的暂存文件以 .tmp- 开头，它们随后会被原子替换/移动，
        # 属于中间态，不触发重建（最终落盘的那次 rename 会产生正常事件）
        if any(part.startswith(".tmp-") for part in Path(event.src_path).parts):
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        try:
            self._callback()
        except Exception:
            logger.exception("自动重建索引失败")


class ContentWatcher:
    """监听 content/ 目录，文件变更去抖后触发回调（重建索引）。"""

    def __init__(self, path: Path, callback: Callable[[], None], debounce_seconds: float) -> None:
        self._path = path
        self._handler = _DebouncedHandler(callback, debounce_seconds)
        self._observer = Observer()

    def start(self) -> None:
        if not self._path.is_dir():
            logger.warning("内容目录不存在，跳过监听: %s", self._path)
            return
        self._observer.schedule(self._handler, str(self._path), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        logger.info("已开始监听内容目录: %s", self._path)

    def stop(self) -> None:
        if self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=2)
