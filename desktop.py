"""XCPC Helper desktop entry (pywebview + FastAPI backend).

Usage:
    pip install pywebview
    cd frontend && npm install && npm run build
    python desktop.py

后端（backend/，uv 管理）负责托管 frontend/dist 并提供 /api，
桌面窗口加载本地服务地址。前端开发时仍可使用 `npm run dev`。
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import webview

PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / "backend"
HOST = "127.0.0.1"
PORT = 8000


def start_backend() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "--app-dir",
            "src",
            "main:app",
            "--host",
            HOST,
            "--port",
            str(PORT),
        ],
        cwd=BACKEND_DIR,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def wait_ready(timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"后端服务在 {timeout}s 内未就绪")


def main() -> None:
    backend = start_backend()
    try:
        wait_ready()
        webview.create_window(
            title="XCPC Helper",
            url=f"http://{HOST}:{PORT}",
            width=1280,
            height=800,
            min_size=(1080, 680),
        )
        webview.start()
    finally:
        backend.terminate()


if __name__ == "__main__":
    main()
