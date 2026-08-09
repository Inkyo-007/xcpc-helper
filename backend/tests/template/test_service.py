"""模板服务的单元测试（含 FastAPI 路由冒烟测试）。"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.config import Settings
from main import create_app
from services.template.service import TemplateService, get_template_service


@pytest.fixture
def service(tmp_path: Path, content_dir: Path) -> TemplateService:
    settings = Settings(content_dir=content_dir, data_dir=tmp_path / "data")
    svc = TemplateService(settings)
    svc.rebuild()
    return svc


@pytest.fixture
def client(service: TemplateService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_template_service] = lambda: service
    return TestClient(app)


def test_list_sorted_by_priority(service: TemplateService) -> None:
    items = service.list_templates()
    priorities = [t.priority for t in items]
    assert priorities == sorted(priorities, reverse=True)
    assert items[0].name == "sieve"


def test_list_filter_by_category_and_keyword(service: TemplateService) -> None:
    assert [t.id for t in service.list_templates(category="ds")] == ["ds/dsu"]
    hits = service.list_templates(keyword="并查集")
    assert {t.id for t in hits} == {"ds/dsu"}


def test_list_search_sorted_by_relevance(tmp_path: Path) -> None:
    """搜索时相关度恒为第一排序键：同名模板压过高优先级的间接命中。"""
    root = tmp_path / "content"

    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    _write(root / "ds" / "线段树" / "seg.cpp", "int seg[4];\n")
    _write(root / "ds" / "线段树" / "README.md", "---\npriority: 1\n---\n")
    _write(root / "ds" / "lct" / "lct.cpp", "struct LCT {};\n")
    _write(
        root / "ds" / "lct" / "README.md",
        "---\npriority: 9\n---\n\n内部用线段树维护信息。\n",
    )

    settings = Settings(content_dir=root, data_dir=tmp_path / "data")
    svc = TemplateService(settings)
    svc.rebuild()

    # 不搜索时仍按优先级：lct 在前
    assert [t.id for t in svc.list_templates()] == ["ds/lct", "ds/线段树"]
    # 搜索时按相关度：名称精确命中的“线段树”在前
    hits = svc.list_templates(keyword="线段树")
    assert [t.id for t in hits] == ["ds/线段树", "ds/lct"]


def test_list_filter_by_tags(service: TemplateService) -> None:
    hits = service.list_templates(tags=["连通性"])
    assert {t.id for t in hits} == {"ds/dsu"}


def test_detail_with_variants(service: TemplateService) -> None:
    detail = service.get_detail("ds/dsu")
    assert detail.variant_count == 2
    assert [v.id for v in detail.variants] == ["ds/dsu/path-compression", "ds/dsu/with-weight"]
    assert "带权版" in detail.variants[1].body


def test_detail_variants_carry_meta(service: TemplateService) -> None:
    """详情接口的版本携带各自元信息，前端切换版本时随动展示。"""
    detail = service.get_detail("ds/dsu")
    first, second = detail.variants
    assert first.priority == 4
    assert first.updated == datetime.date(2026, 7, 1)
    assert second.priority == 3
    assert second.updated == datetime.date(2026, 7, 10)
    assert second.tags == ["连通性"]


def test_detail_not_found(service: TemplateService) -> None:
    from core.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        service.get_detail("not/exist")


def test_detail_empty_template(service: TemplateService) -> None:
    """空主标签：详情返回空版本列表，主版本字段为 None。"""
    detail = service.get_detail("misc/empty-tpl")
    assert detail.variant_count == 0
    assert detail.variants == []
    assert detail.lang is None
    assert detail.file is None
    assert detail.priority == 2


def test_categories(service: TemplateService) -> None:
    cats = {c.id: c.count for c in service.list_categories()}
    assert cats["字符串"] == 1
    assert cats["ds"] == 1


def test_api_templates(client: TestClient) -> None:
    resp = client.get("/api/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert any(t["id"] == "math/sieve" for t in data)


def test_api_templates_query(client: TestClient) -> None:
    resp = client.get("/api/templates", params={"keyword": "素数", "category": "math"})
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()] == ["math/sieve"]


def test_api_detail_and_404(client: TestClient) -> None:
    resp = client.get("/api/templates/ds/dsu")
    assert resp.status_code == 200
    assert resp.json()["variant_count"] == 2
    resp = client.get("/api/templates/not/exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_api_categories_and_diagnostics(client: TestClient) -> None:
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    assert any(c["id"] == "math" for c in resp.json())
    resp = client.get("/api/diagnostics")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) > 0  # 测试样本含坏格式文件


def test_api_reload(client: TestClient) -> None:
    resp = client.post("/api/templates/reload")
    assert resp.status_code == 200
    assert resp.json()["templates"] > 0
