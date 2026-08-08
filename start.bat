@echo off
rem XCPC Helper 启动脚本：双击即用。
rem 免安装包内自带 uv.exe 则优先使用；源码目录下则使用 PATH 中的 uv。
rem 内容保持纯 ASCII，避免 cmd 中文编码问题。
cd /d "%~dp0"

if exist "%~dp0uv.exe" (set "UV=%~dp0uv.exe") else (set "UV=uv")

echo ============================================================
echo   XCPC Helper
echo.
echo   First run will download Python and dependencies
echo   automatically, which takes a few minutes (needs network).
echo   Subsequent starts are instant and work offline.
echo.
echo   After startup, open this address in your browser:
echo   http://127.0.0.1:8000
echo ============================================================
echo.

"%UV%" run --directory backend --frozen uvicorn --app-dir src main:app --host 127.0.0.1 --port 8000
pause
