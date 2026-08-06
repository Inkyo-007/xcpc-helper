"""测试夹具：临时 content/ 与 books/ 样本。"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import Settings
from core.exceptions import register_exception_handlers
from routers.printbook.router import router as printbook_router
from services.printbook.service import PrintBookService, get_print_book_service
from services.template.service import TemplateService

CPP = "#include <bits/stdc++.h>\nusing namespace std;\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    """覆盖打印册引用解析所需的三种模板形态。"""
    root = tmp_path / "content"

    # 顶层单版本（代码直接在模板目录下，URL 保留字 '~' 寻址）
    _write(root / "math" / "qpow" / "qpow.cpp", CPP)
    _write(root / "math" / "qpow" / "README.md", "---\npriority: 5\n---\n\n快速幂。\n")

    # 多版本（副标签目录 basic / weighted）
    _write(root / "ds" / "dsu" / "basic" / "dsu.cpp", CPP)
    _write(root / "ds" / "dsu" / "basic" / "README.md", "---\n---\n\n基础版。\n")
    _write(root / "ds" / "dsu" / "weighted" / "dsu_w.cpp", CPP)
    _write(
        root / "ds" / "dsu" / "weighted" / "README.md",
        "---\ntags: '连通性'\n---\n\n带权版。\n",
    )

    # 空主标签（无任何版本）
    (root / "misc" / "empty-tpl").mkdir(parents=True)

    return root


@pytest.fixture
def books_dir(tmp_path: Path) -> Path:
    return tmp_path / "books"


@pytest.fixture
def template_service(content_dir: Path, tmp_path: Path) -> TemplateService:
    service = TemplateService(
        Settings(content_dir=content_dir, data_dir=tmp_path / "data")
    )
    service.rebuild()
    return service


@pytest.fixture
def service(books_dir: Path, template_service: TemplateService) -> PrintBookService:
    return PrintBookService(Settings(books_dir=books_dir), template_service)


@pytest.fixture
def client(service: PrintBookService) -> TestClient:
    """仅挂载打印册路由的最小应用，service 依赖覆盖为临时目录实例。"""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(printbook_router)
    app.dependency_overrides[get_print_book_service] = lambda: service
    return TestClient(app)
