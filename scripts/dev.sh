#!/usr/bin/env bash
# 一键搭建开发环境：后端依赖 + 前端依赖 + 前端生产构建（Linux/macOS 版，与 scripts/dev.ps1 等价）。
# 用法：
#   scripts/dev.sh             # 标准环境
#   scripts/dev.sh --desktop   # 额外安装桌面模式依赖（pywebview）
set -e
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$root/backend"
if [ "${1:-}" = "--desktop" ]; then
    uv sync --group desktop
else
    uv sync
fi

cd "$root/frontend"
npm ci
npm run build

echo "环境就绪。启动方式见 README「快速部署指南」。"
