.DEFAULT_GOAL := help

# 可在调用时覆盖服务地址，例如：make start HOST=0.0.0.0 PORT=9000
UV ?= uv
NPM ?= npm
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help setup start setup-desktop desktop

help:
	@echo XCPC Helper Makefile
	@echo make setup          - 安装依赖并构建前端
	@echo make start          - 启动浏览器模式
	@echo make setup-desktop  - 安装桌面模式依赖并构建前端
	@echo make desktop        - 启动桌面模式

# 对应 README「源码部署」中的环境准备步骤
setup:
	$(UV) sync --directory backend
	$(NPM) --prefix frontend ci
	$(NPM) --prefix frontend run build

# 对应 README「源码部署」中的浏览器启动方式
start:
	$(UV) run --directory backend uvicorn --app-dir src main:app --host $(HOST) --port $(PORT)

# 对应 README「桌面模式」中的环境准备步骤
setup-desktop:
	$(UV) sync --directory backend --group desktop
	$(NPM) --prefix frontend ci
	$(NPM) --prefix frontend run build

# 启动 pywebview；--directory 会把工作目录切换到 backend/
desktop:
	$(UV) run --directory backend --group desktop python ../desktop.py
