"""document 层测试：引用解析、版本选择语义、资源 URL 展开与还原。"""

from pathlib import Path

import pytest

from modules.printbook import document
from modules.printbook.models import (
    BookConfig,
    HeadingBlockNode,
    ImageBlockNode,
    TemplateBlockNode,
)
from modules.printbook.schemas import (
    HeadingBlock,
    ImageBlock,
    TemplateBlock,
)
from services.template.service import TemplateService


def _config_with(blocks: list) -> BookConfig:
    config = BookConfig()
    config.cover.title = "测试册"
    config.blocks = blocks
    return config


def _template_block(
    template: str, version: str | None, block_id: str = "t1"
) -> TemplateBlockNode:
    return TemplateBlockNode(
        id=block_id, template=template, version=version, heading_level=2
    )


def _resolve(template_service: TemplateService, node: TemplateBlockNode) -> TemplateBlock:
    detail = document.to_api_book(
        "测试册", _config_with([node]), template_service.get_detail
    )
    block = detail.blocks[0]
    assert isinstance(block, TemplateBlock)
    return block


def test_null_version_resolves_primary(template_service: TemplateService) -> None:
    block = _resolve(template_service, _template_block("ds/dsu", None))
    assert block.resolved is not None
    assert block.resolved.version_name == "basic"
    assert block.resolved.name == "dsu"
    assert block.resolved.cat == "ds"


def test_tilde_resolves_root_version(template_service: TemplateService) -> None:
    block = _resolve(template_service, _template_block("math/qpow", "~"))
    assert block.resolved is not None
    assert block.resolved.version_name == "qpow"
    assert block.resolved.priority == 5
    assert block.resolved.body == "快速幂。"


def test_named_version_matches_subtag(template_service: TemplateService) -> None:
    block = _resolve(template_service, _template_block("ds/dsu", "weighted"))
    assert block.resolved is not None
    assert block.resolved.version_name == "weighted"
    assert block.resolved.tags == ["连通性"]


def test_missing_version_falls_back_to_primary(
    template_service: TemplateService,
) -> None:
    block = _resolve(template_service, _template_block("ds/dsu", "被删掉的版本"))
    assert block.resolved is not None
    assert block.resolved.version_name == "basic"


def test_missing_template_resolves_none(template_service: TemplateService) -> None:
    block = _resolve(template_service, _template_block("ds/不存在", None))
    assert block.resolved is None


def test_empty_template_resolves_none(template_service: TemplateService) -> None:
    block = _resolve(template_service, _template_block("misc/empty-tpl", None))
    assert block.resolved is None


def test_heading_level_clamped(template_service: TemplateService) -> None:
    config = _config_with(
        [HeadingBlockNode(id="h1", title="章", heading_level=9)]
    )
    detail = document.to_api_book("测试册", config, template_service.get_detail)
    block = detail.blocks[0]
    assert isinstance(block, HeadingBlock)
    assert block.heading_level == 6


def test_missing_block_id_generated(template_service: TemplateService) -> None:
    config = _config_with([HeadingBlockNode(title="章", heading_level=1)])
    detail = document.to_api_book("测试册", config, template_service.get_detail)
    assert detail.blocks[0].id == "heading-1"


def test_cover_title_falls_back_to_name(template_service: TemplateService) -> None:
    config = BookConfig()
    detail = document.to_api_book("区域赛版", config, template_service.get_detail)
    assert detail.cover.title == "区域赛版"


def test_image_src_expanded(template_service: TemplateService) -> None:
    config = _config_with(
        [ImageBlockNode(id="i1", src="assets/复杂度 表.png")]
    )
    detail = document.to_api_book("测试册", config, template_service.get_detail)
    block = detail.blocks[0]
    assert isinstance(block, ImageBlock)
    assert block.src.startswith("/api/print-books/")
    assert "assets/" in block.src
    assert " " not in block.src  # 空格与中文被 URL 编码


def test_external_and_absolute_src_kept(template_service: TemplateService) -> None:
    for src in ("https://example.com/a.png", "/static/a.png", "data:image/png;base64,x"):
        config = _config_with([ImageBlockNode(id="i1", src=src)])
        detail = document.to_api_book("测试册", config, template_service.get_detail)
        block = detail.blocks[0]
        assert isinstance(block, ImageBlock)
        assert block.src == src


def test_storage_round_trip_strips_resolved_and_url(
    template_service: TemplateService,
) -> None:
    """API 块转存储：resolved 被剥离，展开的资源 URL 还原为相对路径。"""
    config = _config_with(
        [
            _template_block("ds/dsu", "weighted"),
            ImageBlockNode(id="i1", src="assets/pic.png"),
        ]
    )
    api = document.to_api_book("测试册", config, template_service.get_detail)
    nodes = document.to_storage_blocks("测试册", api.blocks)
    template_node = nodes[0]
    assert isinstance(template_node, TemplateBlockNode)
    assert not hasattr(template_node, "resolved")
    image_node = nodes[1]
    assert isinstance(image_node, ImageBlockNode)
    assert image_node.src == "assets/pic.png"


def test_storage_generates_id_for_new_blocks(
    template_service: TemplateService,
) -> None:
    nodes = document.to_storage_blocks(
        "测试册", [HeadingBlock(id="", title="新章节", heading_level=2)]
    )
    assert nodes[0].id.startswith("pb-")
