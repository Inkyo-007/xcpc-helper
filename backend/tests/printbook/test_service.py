"""打印册服务层与路由层的集成测试。"""

import pytest
from fastapi.testclient import TestClient

from core.exceptions import ConflictError, NotFoundError
from modules.printbook.schemas import BlocksReplace, PrintBookCreate, PrintBookUpdate
from services.printbook.service import PrintBookService

HEADING = {"id": "b1", "type": "heading", "title": "数学", "heading_level": 1}
TEMPLATE = {
    "id": "b2",
    "type": "template",
    "template": "math/qpow",
    "version": None,
    "heading_level": 3,
}


def test_create_list_get_rename_delete(service: PrintBookService) -> None:
    detail = service.create_book(PrintBookCreate(name="队册", title="队伍模板册"))
    assert detail.cover.title == "队伍模板册"
    assert detail.blocks == []

    summaries = service.list_books()
    assert len(summaries) == 1
    assert summaries[0].name == "队册"
    assert summaries[0].title == "队伍模板册"
    assert summaries[0].error is None

    updated = service.update_book("队册", PrintBookUpdate(new_name="正式册"))
    assert updated.name == "正式册"
    assert service.get_book("正式册").name == "正式册"
    with pytest.raises(NotFoundError):
        service.get_book("队册")

    service.delete_book("正式册")
    assert service.list_books() == []
    with pytest.raises(NotFoundError):
        service.delete_book("正式册")


def test_create_conflict(service: PrintBookService) -> None:
    service.create_book(PrintBookCreate(name="A"))
    with pytest.raises(ConflictError):
        service.create_book(PrintBookCreate(name="A"))


def test_replace_blocks_resolves_template(service: PrintBookService) -> None:
    service.create_book(PrintBookCreate(name="B"))
    detail = service.replace_blocks(
        "B", BlocksReplace.model_validate({"blocks": [HEADING, TEMPLATE]})
    )
    assert len(detail.blocks) == 2
    block = detail.blocks[1]
    assert block.type == "template"
    assert block.resolved is not None
    assert block.resolved.code.startswith("#include")
    assert block.resolved.cat == "math"

    # 缺失模板的引用解析为 None，不报错
    detail = service.replace_blocks(
        "B",
        BlocksReplace.model_validate(
            {"blocks": [{**TEMPLATE, "template": "math/missing"}]}
        ),
    )
    assert detail.blocks[0].resolved is None


def test_upload_and_read_asset(service: PrintBookService) -> None:
    service.create_book(PrintBookCreate(name="C"))
    resp = service.upload_asset("C", "图解.png", b"\x89PNG\r\n\x1a\n")
    assert resp.src == "/api/print-books/C/assets/%E5%9B%BE%E8%A7%A3.png"
    path = service.asset_file("C", "图解.png")
    assert path.read_bytes() == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(NotFoundError):
        service.asset_file("C", "不存在.png")


# ===== 路由层 =====


def test_router_book_lifecycle(client: TestClient) -> None:
    resp = client.post("/api/print-books", json={"name": "路由册", "title": "T"})
    assert resp.status_code == 201
    assert resp.json()["cover"]["title"] == "T"

    resp = client.get("/api/print-books")
    assert resp.status_code == 200
    assert [b["name"] for b in resp.json()] == ["路由册"]

    resp = client.put(
        "/api/print-books/路由册/blocks", json={"blocks": [HEADING, TEMPLATE]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["blocks"]) == 2
    assert body["blocks"][1]["resolved"]["code"].startswith("#include")

    resp = client.put("/api/print-books/路由册", json={"new_name": "改名册"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "改名册"

    resp = client.delete("/api/print-books/改名册")
    assert resp.status_code == 204
    assert client.get("/api/print-books").json() == []


def test_router_not_found(client: TestClient) -> None:
    assert client.get("/api/print-books/不存在").status_code == 404
    assert client.delete("/api/print-books/不存在").status_code == 404
    resp = client.put("/api/print-books/不存在/blocks", json={"blocks": [HEADING]})
    assert resp.status_code == 404


def test_router_assets(client: TestClient) -> None:
    client.post("/api/print-books", json={"name": "D"})
    resp = client.post(
        "/api/print-books/D/assets",
        files={"file": ("pic.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert resp.status_code == 200
    src = resp.json()["src"]
    resp = client.get(src)
    assert resp.status_code == 200
    assert resp.content == b"\x89PNG\r\n\x1a\n"

    resp = client.post(
        "/api/print-books/D/assets",
        files={"file": ("bad.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 400
