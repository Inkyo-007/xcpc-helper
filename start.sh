#!/usr/bin/env bash
# XCPC Helper 启动脚本（Linux/macOS）：与 start.bat 等价。
# 优先使用包内自带的 uv 二进制（免安装包）；否则退回 PATH 中的 uv（源码检出）。
set -e
cd "$(dirname "$0")"

if [ -x "./uv" ]; then UV="./uv"; else UV="uv"; fi

# 安装位置可能与 uv 缓存不在同一文件系统（硬链接不可用），
# 使用 copy 模式避免告警。
export UV_LINK_MODE=copy

echo "============================================================"
echo "  XCPC Helper"
echo ""
echo "  首次运行会自动下载 Python 与依赖，需要几分钟（需联网）。"
echo "  之后启动即时完成，离线可用。"
echo ""
echo "  启动后在浏览器访问："
echo "  http://127.0.0.1:8000"
echo "============================================================"
echo ""

"$UV" run --directory backend --frozen uvicorn --app-dir src main:app --host 127.0.0.1 --port 8000
