# 构建免安装绿色压缩包：预构建前端 + 独立 uv 二进制 + 后端源码与内容库。
# Windows 产出 release/xcpc-helper-<版本>-<平台>.zip，Linux/macOS 产出 .tar.gz
# （保留可执行权限位）。用户解压后运行 start.bat（Windows）或 start.sh（Linux/macOS）。
# 用法：
#   scripts/package.ps1                                     # 本地构建 Windows 包，版本号默认为 dev
#   scripts/package.ps1 -Version v0.1.0 -Platform linux-x64 # 指定版本号与平台（CI 发版时使用）
#   scripts/package.ps1 -Platform macos-arm64 -UvVersion 0.8.0  # 固定 uv 版本（默认 latest）
param(
    [string]$Version = "dev",
    [ValidateSet("windows-x64", "linux-x64", "macos-arm64")]
    [string]$Platform = "windows-x64",
    [string]$UvVersion = "latest"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pkgName = "xcpc-helper-$Version-$Platform"
$releaseDir = Join-Path $root 'release'
$stage = Join-Path $releaseDir "stage/$pkgName"

# 平台 -> uv 发行产物名 / 包内二进制名 / 启动脚本
$platforms = @{
    'windows-x64' = @{ artifact = 'uv-x86_64-pc-windows-msvc.zip'; binary = 'uv.exe'; launcher = 'start.bat' }
    'linux-x64' = @{ artifact = 'uv-x86_64-unknown-linux-gnu.tar.gz'; binary = 'uv'; launcher = 'start.sh' }
    'macos-arm64' = @{ artifact = 'uv-aarch64-apple-darwin.tar.gz'; binary = 'uv'; launcher = 'start.sh' }
}
$target = $platforms[$Platform]

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

# ---------- 2. 下载独立 uv 二进制（已缓存则复用，CI 环境无缓存每次都会下载） ----------
$uvDir = Join-Path $releaseDir "uv/$Platform"
$uvBin = Join-Path $uvDir $target.binary
if (Test-Path $uvBin) {
    Write-Host "复用已缓存的 $($target.binary)（如需更新请删除 release/uv/$Platform/ 后重跑）"
} else {
    New-Item -ItemType Directory -Force -Path $uvDir | Out-Null
    if ($UvVersion -eq 'latest') {
        $uvUrl = "https://github.com/astral-sh/uv/releases/latest/download/$($target.artifact)"
    } else {
        $uvUrl = "https://github.com/astral-sh/uv/releases/download/$UvVersion/$($target.artifact)"
    }
    $uvPkg = Join-Path $releaseDir "uv-download.$($target.artifact)"
    Invoke-WebRequest -Uri $uvUrl -OutFile $uvPkg
    if ($target.artifact.EndsWith('.zip')) {
        Expand-Archive -Path $uvPkg -DestinationPath $uvDir -Force
    } else {
        # tar.gz：Windows 10+ 与 Linux/macOS 均自带 tar
        tar -xzf $uvPkg -C $uvDir
    }
    Remove-Item $uvPkg
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
Copy-Item $uvBin "$stage/"
Copy-Item (Join-Path $root $target.launcher) "$stage/"

# 清理可能残留的原子暂存目录
Get-ChildItem -Path $stage -Recurse -Force -Directory -Filter '.tmp-*' | Remove-Item -Recurse -Force

# ---------- 4. 压缩 ----------
if ($Platform -eq 'windows-x64') {
    $pkgPath = Join-Path $releaseDir "$pkgName.zip"
    if (Test-Path $pkgPath) {
        Remove-Item -Force $pkgPath
    }
    Compress-Archive -Path $stage -DestinationPath $pkgPath
} else {
    $pkgPath = Join-Path $releaseDir "$pkgName.tar.gz"
    if (Test-Path $pkgPath) {
        Remove-Item -Force $pkgPath
    }
    # 启动脚本与 uv 需要可执行权限位，tar 打包时保留（Windows 文件系统无此概念，
    # 跨平台构建 Linux/macOS 包请在对应系统上执行本脚本，CI 各平台原生构建）
    if (-not $IsWindows) {
        chmod +x (Join-Path $stage $target.launcher) (Join-Path $stage $target.binary)
    }
    tar -czf $pkgPath -C (Join-Path $releaseDir 'stage') $pkgName
}

Write-Host "打包完成：$pkgPath"
