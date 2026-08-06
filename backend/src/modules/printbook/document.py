"""引用解析与协议转换：存储模型与 API 契约互转。

读取方向（to_api_book）：填充 template 块的 resolved（实时向模板服务
取最新内容，存引用不存内容）、展开图片资源为可渲染 URL、补全缺失的
块 id、收敛 heading_level 到 1-6（手改 yaml 容错）。

写入方向（to_storage_blocks）：剥离 resolved、把本服务展开的资源 URL
还原为相对路径、为缺省块 id 生成新值。
"""

from collections.abc import Callable
from urllib.parse import quote, unquote
from uuid import uuid4

from core.exceptions import NotFoundError
from modules.printbook.models import (
    BookBlockNode,
    BookConfig,
    HeadingBlockNode,
    ImageBlockNode,
    MarkdownBlockNode,
    PageBreakBlockNode,
    TemplateBlockNode,
)
from modules.printbook.schemas import (
    BookBlock,
    CoverPayload,
    HeadingBlock,
    ImageBlock,
    MarkdownBlock,
    OptionsPayload,
    PageBreakBlock,
    PrintBookDetail,
    ResolvedTemplateInfo,
    TemplateBlock,
)
from modules.template.schemas import TemplateDetail, TemplateVersion

MIN_HEADING_LEVEL = 1
MAX_HEADING_LEVEL = 6

# 取模板详情的回调（TemplateService.get_detail）；未命中抛 NotFoundError
GetDetail = Callable[[str], TemplateDetail]


def _clamp_level(level: int) -> int:
    return max(MIN_HEADING_LEVEL, min(MAX_HEADING_LEVEL, level))


def _api_base(name: str) -> str:
    return f"/api/print-books/{quote(name, safe='')}"


def expand_asset_url(name: str, src: str) -> str:
    """相对资源路径展开为可渲染 URL；外部/绝对地址原样保留。"""
    if src.startswith(("/", "http://", "https://", "data:", "blob:")):
        return src
    return f"{_api_base(name)}/{quote(src, safe='/')}"


def normalize_asset_src(name: str, src: str) -> str:
    """把本服务展开的 URL 还原为相对路径（写回 yaml 前调用）。"""
    prefix = f"{_api_base(name)}/"
    if src.startswith(prefix):
        return unquote(src[len(prefix) :])
    return src


def _pick_variant(
    template_id: str, version: str | None, variants: list[TemplateVersion]
) -> TemplateVersion:
    """null 取主版本；'~' 取顶层单版本；其余按副标签名匹配。

    指定版本未命中（被删/改名）时回退主版本，保证册内容可用。
    """
    if version is None:
        return variants[0]
    if version == "~":
        for variant in variants:
            if variant.id == template_id:
                return variant
        return variants[0]
    for variant in variants:
        if variant.name == version or variant.id == f"{template_id}/{version}":
            return variant
    return variants[0]


def _resolve_template(
    node: TemplateBlockNode, get_detail: GetDetail
) -> ResolvedTemplateInfo | None:
    """解析模板引用；模板缺失或无版本时返回 None（前端按未知模板展示）。"""
    try:
        detail = get_detail(node.template)
    except NotFoundError:
        return None
    if not detail.variants:
        return None
    target = _pick_variant(node.template, node.version, detail.variants)
    return ResolvedTemplateInfo(
        name=detail.name,
        cat=detail.cat,
        version_name=target.name,
        lang=target.lang,
        file=target.file,
        code=target.code,
        body=target.body,
        tags=target.tags,
        src=target.src,
        page=target.page,
        updated=target.updated,
        priority=target.priority,
    )


def to_api_book(
    name: str, config: BookConfig, get_detail: GetDetail
) -> PrintBookDetail:
    """存储配置到 API 详情：解析引用、展开资源 URL、补全块 id。"""
    blocks: list[BookBlock] = []
    for index, node in enumerate(config.blocks):
        block_id = node.id or f"{node.type}-{index + 1}"
        if isinstance(node, HeadingBlockNode):
            blocks.append(
                HeadingBlock(
                    id=block_id,
                    title=node.title,
                    heading_level=_clamp_level(node.heading_level),
                )
            )
        elif isinstance(node, TemplateBlockNode):
            blocks.append(
                TemplateBlock(
                    id=block_id,
                    template=node.template,
                    version=node.version,
                    title=node.title,
                    heading_level=_clamp_level(node.heading_level),
                    include_body=node.include_body,
                    resolved=_resolve_template(node, get_detail),
                )
            )
        elif isinstance(node, MarkdownBlockNode):
            blocks.append(
                MarkdownBlock(id=block_id, title=node.title, content=node.content)
            )
        elif isinstance(node, ImageBlockNode):
            blocks.append(
                ImageBlock(
                    id=block_id,
                    src=expand_asset_url(name, node.src),
                    caption=node.caption,
                    width=node.width,
                )
            )
        else:
            blocks.append(PageBreakBlock(id=block_id))
    cover = CoverPayload(
        title=config.cover.title or name,
        subtitle=config.cover.subtitle,
        author=config.cover.author,
        logo=expand_asset_url(name, config.cover.logo) if config.cover.logo else None,
    )
    return PrintBookDetail(
        name=name,
        cover=cover,
        options=OptionsPayload(**config.options.model_dump()),
        blocks=blocks,
    )


def to_storage_blocks(name: str, blocks: list[BookBlock]) -> list[BookBlockNode]:
    """API 块列表到存储块列表：剥离 resolved、还原资源 URL、补全新 id。"""
    nodes: list[BookBlockNode] = []
    for block in blocks:
        block_id = block.id or f"pb-{uuid4().hex[:8]}"
        if isinstance(block, HeadingBlock):
            nodes.append(
                HeadingBlockNode(
                    id=block_id,
                    title=block.title,
                    heading_level=_clamp_level(block.heading_level),
                )
            )
        elif isinstance(block, TemplateBlock):
            nodes.append(
                TemplateBlockNode(
                    id=block_id,
                    template=block.template,
                    version=block.version,
                    title=block.title,
                    heading_level=_clamp_level(block.heading_level),
                    include_body=block.include_body,
                )
            )
        elif isinstance(block, MarkdownBlock):
            nodes.append(
                MarkdownBlockNode(id=block_id, title=block.title, content=block.content)
            )
        elif isinstance(block, ImageBlock):
            nodes.append(
                ImageBlockNode(
                    id=block_id,
                    src=normalize_asset_src(name, block.src),
                    caption=block.caption,
                    width=block.width,
                )
            )
        else:
            nodes.append(PageBreakBlockNode(id=block_id))
    return nodes
