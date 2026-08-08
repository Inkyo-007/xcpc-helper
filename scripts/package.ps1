# 构建免安装绿色压缩包：预构建前端 + 独立 uv.exe + 后端源码与内容库。
# 产出 release/xcpc-helper-<版本>-windows-x64.zip，用户解压后双击「启动.bat」即可使用。
# 用法：
#   scripts/package.ps1                      # 本地构建，版本号默认为 dev
#   scripts/package.ps1 -Version v0.1.0      # 指定版本号（CI 发版时使用）
#   scripts/package.ps1 -UvVersion 0.8.0     # 固定 uv 版本（默认 latest）
param(
    [string]$Version = "dev",
    [string]$UvVersion = "latest"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pkgName = "xcpc-helper-$Version-windows-x64"
$releaseDir = Join-Path $root 'release'
$stage = Join-Path $releaseDir "stage/$pkgName"

# 全新环境（如 CI）下 release/ 可能不存在，Invoke-WebRequest 不会自动创建父目录
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

# ---------- 1. 构建前端静态产物 ----------
Push-Location (Join-Path $root 'frontend')
try {
    npm ci
    npm run build
} finally {
    Pop-Location
}

# ---------- 2. 下载独立 uv.exe（已缓存则复用，CI 环境无缓存每次都会下载） ----------
$uvDir = Join-Path $releaseDir 'uv'
$uvExe = Join-Path $uvDir 'uv.exe'
if (Test-Path $uvExe) {
    Write-Host "复用已缓存的 uv.exe（如需更新请删除 release/uv/ 后重跑）"
} else {
    if ($UvVersion -eq 'latest') {
        $uvUrl = 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip'
    } else {
        $uvUrl = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
    }
    $uvZip = Join-Path $releaseDir 'uv-download.zip'
    Invoke-WebRequest -Uri $uvUrl -OutFile $uvZip
    Expand-Archive -Path $uvZip -DestinationPath $uvDir -Force
}

# ---------- 3. 组装目录（保持 backend/ 与 frontend/dist 同级，与源码布局一致） ----------
if (Test-Path $stage) {
    Remove-Item -Recurse -Force $stage
}
New-Item -ItemType Directory -Force -Path "$stage/backend", "$stage/frontend" | Out-Null

Copy-Item (Join-Path $root 'backend/pyproject.toml') "$stage/backend/"
Copy-Item (Join-Path $root 'backend/uv.lock') "$stage/backend/"
Copy-Item -Recurse (Join-Path $root 'backend/src') "$stage/backend/"
Copy-Item -Recurse (Join-Path $root 'backend/content') "$stage/backend/"
Copy-Item -Recurse (Join-Path $root 'backend/books') "$stage/backend/"
Copy-Item -Recurse (Join-Path $root 'frontend/dist') "$stage/frontend/"
Copy-Item $uvExe "$stage/"

# 清理可能残留的原子暂存目录
Get-ChildItem -Path $stage -Recurse -Force -Directory -Filter '.tmp-*' | Remove-Item -Recurse -Force

# 启动脚本：内容保持纯 ASCII，避免 cmd 编码问题
$bat = @'
@echo off
cd /d "%~dp0"
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
uv.exe run --directory backend --frozen uvicorn --app-dir src main:app --host 127.0.0.1 --port 8000
pause
'@
[System.IO.File]::WriteAllText((Join-Path $stage '启动.bat'), $bat, [System.Text.Encoding]::ASCII)

# ---------- 4. 压缩 ----------
$zipPath = Join-Path $releaseDir "$pkgName.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path $stage -DestinationPath $zipPath

Write-Host "打包完成：$zipPath"
