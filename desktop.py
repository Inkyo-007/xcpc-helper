"""XCPC Helper desktop entry (pywebview).

Usage:
    pip install pywebview
    cd frontend && npm install && npm run build
    python desktop.py

The frontend is the Vue 3 + Vite + TypeScript app under frontend/, served
from its build output frontend/dist/. For frontend development run
`npm run dev` in frontend/ and use the printed localhost URL instead.
When the FastAPI backend lands, point `url` at the local server.
"""

from pathlib import Path

import webview

FRONTEND = Path(__file__).parent / "frontend" / "dist" / "index.html"


def main() -> None:
    webview.create_window(
        title="XCPC Helper",
        url=str(FRONTEND),
        width=1280,
        height=800,
        min_size=(1080, 680),
    )
    webview.start()


if __name__ == "__main__":
    main()
