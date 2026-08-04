"""content/ 写入操作（可视化增删改）的单元测试与路由测试。"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.config import Settings
from core.exceptions import BadRequestError, ConflictError, NotFoundError
from main import create_app
from modules.template import writer
from modules.template.parser import parse_readme_text
from modules.template.scanner import scan_content
from modules.template.schemas import VersionMetaInput, VersionUpsert
from services.template.service import TemplateService, get_template_service


def _payload(**kwargs: object) -> VersionUpsert:
    """构造一个合法的版本请求体，测试按需覆盖字段。"""
    base: dict[str, object] = {
        "name": "v1",
        "ext": "cpp",
        "code": "#include <bits/stdc++.h>\n",
        "meta": VersionMetaInput(),
        "body": "",
    }
    base.update(kwargs)
    return VersionUpsert.model_validate(base)


# ===== 名称与扩展名校验 =====


def test_validate_name_ok() -> None:
    assert writer.validate_name(" 线段树 ", "模板") == "线段树"
    assert writer.validate_name("segtree_lazy", "模板") == "segtree_lazy"


@pytest.mark.parametrize(
    "name",
    ["", "   ", "a/b", "a\\b", "a:b", "a*b", ".hidden", "dir.", "..", "a..b", "~", "CON", "com1"],
)
def test_validate_name_rejects_bad_names(name: str) -> None:
    with pytest.raises(BadRequestError):
        writer.validate_name(name, "模板")


def test_validate_name_too_long() -> None:
    with pytest.raises(BadRequestError):
        writer.validate_name("x" * 101, "模板")


def test_validate_ext() -> None:
    assert writer.validate_ext("CPP") == "cpp"
    assert writer.validate_ext(".py") == "py"
    with pytest.raises(BadRequestError):
        writer.validate_ext("rs")


def test_validate_code_filename() -> None:
    assert writer.validate_code_filename("segtree.cpp", "cpp") == "segtree.cpp"
    with pytest.raises(BadRequestError):
        writer.validate_code_filename("segtree.py", "cpp")  # 后缀与语言不符
    with pytest.raises(BadRequestError):
        writer.validate_code_filename("a/b.cpp", "cpp")


# ===== README 生成与回环 =====


def test_render_readme_roundtrip() -> None:
    """写出的 README 必须能被 parser 原样读回（回环一致）。"""
    meta = VersionMetaInput(
        updated=datetime.date(2026, 8, 5),
        tags=["素数", "数论"],
        source="洛谷 P3383",
        page="https://www.luogu.com.cn/problem/P3383",
        priority=5,
    )
    text = writer.render_readme(meta, "线性筛说明。\n\n第二段。")
    parsed, body = parse_readme_text(text, "test/README.md", [])
    assert parsed.updated == datetime.date(2026, 8, 5)
    assert parsed.tags == ["素数", "数论"]
    assert parsed.source == "洛谷 P3383"
    assert parsed.page == "https://www.luogu.com.cn/problem/P3383"
    assert parsed.priority == 5
    assert body == "线性筛说明。\n\n第二段。"


def test_render_readme_omits_defaults() -> None:
    """缺省字段不写入 front matter；全空时也产出合法的 front matter。"""
    text = writer.render_readme(VersionMetaInput(), "")
    parsed, body = parse_readme_text(text, "test/README.md", [])
    assert parsed.updated is None
    assert parsed.tags == []
    assert parsed.priority == 2
    assert body == ""
    assert "priority" not in text


# ===== 模板（主标签）操作 =====


def test_create_template_dir(content_dir: Path) -> None:
    category, name = writer.create_template_dir(content_dir, "图论", " 最短路 ")
    assert (category, name) == ("图论", "最短路")
    assert (content_dir / "图论" / "最短路").is_dir()
    # 扫描可见为空主标签
    scan = scan_content(content_dir)
    node = next(t for t in scan.templates if t.id == "图论/最短路")
    assert node.versions == []


def test_create_template_dir_conflict(content_dir: Path) -> None:
    with pytest.raises(ConflictError):
        writer.create_template_dir(content_dir, "math", "sieve")


def test_rename_template_dir(content_dir: Path) -> None:
    new_cat, new_name = writer.rename_template_dir(
        content_dir, "math", "sieve", new_category="数学", new_name="线性筛法"
    )
    assert (new_cat, new_name) == ("数学", "线性筛法")
    assert not (content_dir / "math" / "sieve").exists()
    assert (content_dir / "数学" / "线性筛法" / "euler_sieve.cpp").is_file()
    # 原分类 math 已无其他模板，被顺手清理
    assert not (content_dir / "math").exists()


def test_rename_template_dir_conflict(content_dir: Path) -> None:
    with pytest.raises(ConflictError):
        writer.rename_template_dir(content_dir, "math", "sieve", new_name="bare", new_category="misc")
    with pytest.raises(NotFoundError):
        writer.rename_template_dir(content_dir, "math", "not-exist", new_name="x")


def test_delete_template_dir(content_dir: Path) -> None:
    # 空主标签可删
    writer.delete_template_dir(content_dir, "misc", "empty-tpl")
    assert not (content_dir / "misc" / "empty-tpl").exists()
    # 非空模板拒绝删除
    with pytest.raises(ConflictError):
        writer.delete_template_dir(content_dir, "math", "sieve")
    with pytest.raises(NotFoundError):
        writer.delete_template_dir(content_dir, "math", "not-exist")


# ===== 版本操作 =====


def test_create_version_dir(content_dir: Path) -> None:
    payload = _payload(
        name="懒标记",
        meta=VersionMetaInput(updated=datetime.date(2026, 8, 5), priority=5),
        body="支持区间修改。",
    )
    slug = writer.create_version_dir(content_dir, "misc", "empty-tpl", payload)
    assert slug == "懒标记"
    version_dir = content_dir / "misc" / "empty-tpl" / "懒标记"
    assert (version_dir / "code.cpp").is_file()
    assert (version_dir / "README.md").is_file()
    # 回环：扫描读回与写入一致
    scan = scan_content(content_dir)
    node = next(t for t in scan.templates if t.id == "misc/empty-tpl")
    assert len(node.versions) == 1
    version = node.versions[0]
    assert version.name == "懒标记"
    assert version.meta.priority == 5
    assert version.meta.updated == datetime.date(2026, 8, 5)
    assert version.body == "支持区间修改。"
    assert "bits/stdc" in version.code


def test_create_version_dir_conflict_and_bad_payload(content_dir: Path) -> None:
    with pytest.raises(ConflictError):
        writer.create_version_dir(content_dir, "ds", "dsu", _payload(name="path-compression"))
    with pytest.raises(BadRequestError):
        writer.create_version_dir(content_dir, "ds", "dsu", _payload(name=None))
    with pytest.raises(BadRequestError):
        writer.create_version_dir(
            content_dir,
            "ds",
            "dsu",
            _payload(meta=VersionMetaInput(page="https://example.com")),  # page 无 source
        )
    with pytest.raises(NotFoundError):
        writer.create_version_dir(content_dir, "ds", "not-exist", _payload())


def test_update_version_dir_rename_and_ext_change(content_dir: Path) -> None:
    # 改名 + 换扩展名 + 全量重写元数据
    payload = _payload(
        name="路径压缩优化",
        ext="py",
        code="def find(x):\n    pass\n",
        meta=VersionMetaInput(tags=["连通性"]),
    )
    new_slug = writer.update_version_dir(
        content_dir, "ds", "dsu", "path-compression", "dsu.cpp", payload
    )
    assert new_slug == "路径压缩优化"
    new_dir = content_dir / "ds" / "dsu" / "路径压缩优化"
    assert new_dir.is_dir()
    assert not (content_dir / "ds" / "dsu" / "path-compression").exists()
    assert (new_dir / "code.py").is_file()
    assert not (new_dir / "dsu.cpp").exists()  # 旧代码文件被清理
    scan = scan_content(content_dir)
    node = next(t for t in scan.templates if t.id == "ds/dsu")
    slugs = [v.slug for v in node.versions]
    assert "路径压缩优化" in slugs


def test_update_version_dir_top_level(content_dir: Path) -> None:
    # 顶层单版本：只改内容，不允许改名
    payload = _payload(name=None, code="// new\n", meta=VersionMetaInput(priority=7))
    new_slug = writer.update_version_dir(
        content_dir, "math", "sieve", "", "euler_sieve.cpp", payload
    )
    assert new_slug == ""
    assert (content_dir / "math" / "sieve" / "code.cpp").is_file()
    assert not (content_dir / "math" / "sieve" / "euler_sieve.cpp").exists()
    with pytest.raises(BadRequestError):
        writer.update_version_dir(
            content_dir, "math", "sieve", "", "code.cpp", _payload(name="新名字")
        )


def test_delete_version_dir(content_dir: Path) -> None:
    # 副标签版本：整目录删除
    writer.delete_version_dir(content_dir, "ds", "dsu", "with-weight", "dsu_weight.cpp")
    assert not (content_dir / "ds" / "dsu" / "with-weight").exists()
    # 顶层单版本：只删代码与 README，目录留空成为空主标签
    writer.delete_version_dir(content_dir, "math", "sieve", "", "euler_sieve.cpp")
    template_dir = content_dir / "math" / "sieve"
    assert template_dir.is_dir()
    assert list(template_dir.iterdir()) == []
    scan = scan_content(content_dir)
    node = next(t for t in scan.templates if t.id == "math/sieve")
    assert node.versions == []


# ===== 路由测试 =====


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


def test_api_create_and_delete_template(client: TestClient) -> None:
    resp = client.post("/api/templates", json={"category": "图论", "name": "最短路"})
    assert resp.status_code == 201
    detail = resp.json()
    assert detail["id"] == "图论/最短路"
    assert detail["variant_count"] == 0
    # 冲突 → 409
    resp = client.post("/api/templates", json={"category": "图论", "name": "最短路"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"
    # 删除
    resp = client.delete("/api/templates/图论/最短路")
    assert resp.status_code == 204
    resp = client.get("/api/templates/图论/最短路")
    assert resp.status_code == 404


def test_api_delete_non_empty_template_rejected(client: TestClient) -> None:
    resp = client.delete("/api/templates/math/sieve")
    assert resp.status_code == 409


def test_api_version_crud(client: TestClient) -> None:
    # 新建版本
    resp = client.post(
        "/api/templates/misc/empty-tpl/versions",
        json={
            "name": "标准实现",
            "ext": "cpp",
            "code": "int main() {}\n",
            "meta": {"priority": 4, "updated": "2026-08-05"},
            "body": "说明。",
        },
    )
    assert resp.status_code == 201
    detail = resp.json()
    assert detail["variant_count"] == 1
    assert detail["variants"][0]["name"] == "标准实现"
    assert detail["variants"][0]["priority"] == 4
    # 更新版本（改优先级）
    resp = client.put(
        "/api/templates/misc/empty-tpl/versions/标准实现",
        json={
            "name": "标准实现",
            "ext": "cpp",
            "code": "int main() { return 0; }\n",
            "meta": {"priority": 6},
            "body": "新说明。",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["variants"][0]["priority"] == 6
    # 删除版本 → 回到空主标签
    resp = client.delete("/api/templates/misc/empty-tpl/versions/标准实现")
    assert resp.status_code == 204
    resp = client.get("/api/templates/misc/empty-tpl")
    assert resp.json()["variant_count"] == 0


def test_api_top_level_version_via_tilde(client: TestClient) -> None:
    """顶层单版本用保留字 ~ 寻址。"""
    resp = client.put(
        "/api/templates/math/sieve/versions/~",
        json={"ext": "cpp", "file": "euler_sieve.cpp", "code": "// v2\n", "meta": {}},
    )
    assert resp.status_code == 200
    assert "v2" in resp.json()["variants"][0]["code"]
    resp = client.delete("/api/templates/math/sieve/versions/~")
    assert resp.status_code == 204
    assert client.get("/api/templates/math/sieve").json()["variant_count"] == 0


def test_api_rename_template(client: TestClient) -> None:
    resp = client.put(
        "/api/templates/ds/dsu", json={"new_category": "数据结构", "new_name": "并查集"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "数据结构/并查集"
    assert client.get("/api/templates/ds/dsu").status_code == 404


def test_api_validation_error_structured(client: TestClient) -> None:
    """请求体缺字段时返回结构化 400 而非 500。"""
    resp = client.post("/api/templates", json={"category": "x"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"
