@echo off
rem XCPC Helper launcher: double-click to start.
rem Prefers the bundled uv.exe (portable package); falls back to uv on PATH
rem (source checkout). Keep this file pure ASCII to avoid cmd encoding issues.
cd /d "%~dp0"

if exist "%~dp0uv.exe" (set "UV=%~dp0uv.exe") else (set "UV=uv")

rem The install location may be on a different drive than uv's cache (C:),
rem where hardlinks are unsupported. Use copy mode to avoid a noisy warning.
set UV_LINK_MODE=copy

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
