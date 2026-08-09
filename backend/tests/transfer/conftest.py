"""测试夹具：临时 content/ 样本、transfer 服务实例与最小应用客户端。"""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import Settings
from core.exceptions import register_exception_handlers
from routers.transfer.router import router as transfer_router
from services.template.service import TemplateService
from services.transfer.service import TransferService, get_transfer_service

CPP = "#include <bits/stdc++.h>\nusing namespace std;\n"

README_FULL = (
    "---\n"
    "updated: 2026-07-29\n"
    "tags: ['素数', '筛法']\n"
    "source: '洛谷 P3383'\n"
    "page: 'https://www.luogu.com.cn/problem/P3383'\n"
    "priority: 5\n"
    "---\n"
    "\n"
    "线性筛说明。\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_zip(entries: dict[str, str | bytes]) -> bytes:
    """把 {arcname: 内容} 打成 zip 字节流（测试辅助）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    """覆盖三种目录形态 + 中文路径 + 空主标签 + GBK 编码代码的 content/ 样本。"""
    root = tmp_path / "content"

    # 形态一：顶层单版本（代码直接在模板目录下）
    _write(root / "math" / "sieve" / "euler_sieve.cpp", CPP)
    _write(root / "math" / "sieve" / "README.md", README_FULL)

    # 形态二：多版本
    _write(root / "ds" / "dsu" / "basic" / "dsu.cpp", CPP)
    _write(root / "ds" / "dsu" / "basic" / "README.md", "---\npriority: 4\n---\n\n基础版。\n")
    _write(root / "ds" / "dsu" / "weighted" / "dsu_w.cpp", CPP)
    _write(root / "ds" / "dsu" / "weighted" / "README.md", "---\n---\n\n带权版。\n")

    # 形态三：单子目录折叠
    _write(root / "graph" / "tarjan" / "v1" / "tarjan.cpp", CPP)
    _write(root / "graph" / "tarjan" / "v1" / "README.md", "---\n---\n")

    # 中文路径（顶层单版本）
    _write(root / "字符串" / "哈希" / "str_hash.cpp", CPP)
    _write(root / "字符串" / "哈希" / "README.md", "---\ntags: [字符串]\n---\n\n双模哈希。\n")

    # GBK 编码的代码文件（导出应统一转为 UTF-8）
    gbk_dir = root / "misc" / "gbk-code"
    gbk_dir.mkdir(parents=True)
    (gbk_dir / "gbk.cpp").write_bytes("// 中文注释\nint main() {}\n".encode("gbk"))
    _write(gbk_dir / "README.md", "---\n---\n")

    # 空主标签
    (root / "misc" / "empty-tpl").mkdir(parents=True)

    return root


@pytest.fixture
def settings(content_dir: Path, tmp_path: Path) -> Settings:
    return Settings(
        content_dir=content_dir,
        books_dir=tmp_path / "books",
        data_dir=tmp_path / "data",
    )


@pytest.fixture
def template_service(settings: Settings) -> TemplateService:
    service = TemplateService(settings)
    service.rebuild()
    return service


@pytest.fixture
def service(settings: Settings, template_service: TemplateService) -> TransferService:
    return TransferService(settings, template_service)


@pytest.fixture
def client(service: TransferService) -> TestClient:
    """挂载 transfer 路由的最小应用，service 依赖覆盖为临时目录实例。"""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(transfer_router)
    app.dependency_overrides[get_transfer_service] = lambda: service
    return TestClient(app)
