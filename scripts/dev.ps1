# 一键搭建开发环境：后端依赖 + 前端依赖 + 前端生产构建。
# 用法：
#   scripts/dev.ps1            # 标准环境
#   scripts/dev.ps1 -Desktop   # 额外安装桌面模式依赖（pywebview）
param(
    [switch]$Desktop
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $root 'backend')
try {
    if ($Desktop) {
        uv sync --group desktop
    } else {
        uv sync
    }
} finally {
    Pop-Location
}

Push-Location (Join-Path $root 'frontend')
try {
    npm ci
    npm run build
} finally {
    Pop-Location
}

Write-Host "环境就绪。启动方式见 README「快速部署指南」。"
