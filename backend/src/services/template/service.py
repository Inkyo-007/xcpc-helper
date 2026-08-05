"""模板库业务编排：索引重建、列表查询、详情组装、过滤排序、可视化增删改。

【初学者导读】
TemplateService 是后端的"业务总管"，routers/ 只跟它打交道：
- 启动时 init_template_service() 创建全局唯一实例并完成首次重建
- rebuild()：扫描 content/ -> 重建 SQLite 索引
- list_templates()：给列表页（支持分类/标签/关键词过滤 + 排序）
- get_detail()：给详情页（模板概要 + 全部版本的代码）
- create/rename/delete：对模板和版本做可视化增删改（落盘到 content/）
数据流向：content/ 目录 --扫描--> SQLite --查询--> 本服务 --组装--> 前端
"""

import datetime
import json  # 数据库里 tags 存的是 JSON 字符串，读出后要解析回列表
import logging
import sqlite3  # 类型注解会用到 sqlite3.Row
import threading

from core.config import Settings, get_settings
from core.exceptions import NotFoundError  # 查不到模板时抛这个异常（变成 404）
from modules.template import repository, writer  # 数据库读写 + 文件系统写操作
from modules.template.models import Diagnostic, TemplateNode, VersionNode
from modules.template.scanner import scan_content
from modules.template.schemas import (
    ROOT_VERSION_TOKEN,
    CategoryInfo,
    SortMode,
    TemplateCreate,
    TemplateDetail,
    TemplateRename,
    TemplateSummary,
    TemplateVersion,
    VersionUpsert,
)

logger = logging.getLogger("xcpc.service.template")


class TemplateService:
    """模板库服务。读写均作用于 SQLite 缓存，rebuild 由扫描结果驱动。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings  # 全局配置（content 目录、数据库路径等）
        self._diagnostics: list[Diagnostic] = []  # 最近一次扫描产生的诊断列表
        # RLock 是可重入锁：同一个线程可以反复拿锁。
        # 写操作需要在持锁状态下调用 rebuild()，而 rebuild() 内部又会再拿一次锁，
        # 所以这里必须用 RLock 而不是普通 Lock，否则会自己锁死自己。
        self._lock = threading.RLock()

    # ===== 索引生命周期 =====

    def rebuild(self) -> tuple[int, int]:
        """扫描 content/ 并全量重建索引，返回 (模板数, 诊断数)。

        启动时调用一次；之后文件变更（watcher）或手动请求 reload 接口时调用。
        """
        # 第一步：扫描目录，得到内存中的模板对象列表 + 诊断列表
        scan = scan_content(self._settings.content_dir)
        # with self._lock: 拿到锁再修改共享数据，避免与读取方竞争
        with self._lock:
            # 第二步：把扫描结果全量写入 SQLite（见 repository.rebuild_index）
            repository.rebuild_index(self._settings.db_path, scan)
            self._diagnostics = scan.diagnostics
        return len(scan.templates), len(scan.diagnostics)

    def diagnostics(self) -> list[Diagnostic]:
        """返回最近一次扫描的诊断（list(...) 复制一份，避免外部改到内部状态）。"""
        return list(self._diagnostics)

    # ===== 查询 =====

    def list_templates(
        self,
        *,
        category: str | None = None,
        tags: list[str] | None = None,
        keyword: str | None = None,
        sort: SortMode = "priority",
    ) -> list[TemplateSummary]:
        """列出模板摘要。

        过滤顺序：关键词（数据库检索）-> 分类（SQL）-> 标签（内存过滤），
        最后按 sort 排序。参数前的 * 表示都必须用关键字传入。
        """
        db = self._settings.db_path
        # matched_ids 为 None 表示"没有关键词，不过滤"
        matched_ids: set[str] | None = None
        if keyword and keyword.strip():
            # 关键词搜索交给数据库层（FTS 或 LIKE），返回命中的模板 id 集合
            matched_ids = repository.search_ids(db, keyword.strip())

        # 先从数据库取出（可选按分类过滤的）全部模板行
        rows = repository.list_templates(db, category)
        summaries: list[TemplateSummary] = []
        for row in rows:
            # 关键词过滤：不在命中集合里的直接跳过
            if matched_ids is not None and row["id"] not in matched_ids:
                continue
            # 数据库里 tags 是 JSON 字符串，解析回列表再判断
            row_tags: list[str] = json.loads(row["tags"])
            # 标签过滤：要求传入的每个标签都在模板的标签里（交集语义）
            if tags and not all(tag in row_tags for tag in tags):
                continue
            # all(...)：括号里每个条件都为 True 才返回 True
            summaries.append(_row_to_summary(row))

        return _sort_summaries(summaries, sort)

    def get_detail(self, template_id: str) -> TemplateDetail:
        """查单份模板的详情（概要 + 所有版本的代码）。"""
        db = self._settings.db_path
        row = repository.get_template(db, template_id)
        if row is None:
            # 抛业务异常：最终由全局处理器变成 404 JSON 响应
            raise NotFoundError(f"模板不存在: {template_id}")
        # 列表推导式：把每个数据库行转成 TemplateVersion 对象
        versions = [
            TemplateVersion(
                id=v["id"],
                name=v["name"],
                lang=v["lang"],
                file=v["file"],
                code=v["code"],
                body=v["body"],
                tags=json.loads(v["tags"]),
                src=v["source"],
                page=v["page"],
                updated=(
                    datetime.date.fromisoformat(v["updated"]) if v["updated"] else None
                ),
                priority=v["priority"],
            )
            for v in repository.get_versions(db, template_id)
        ]
        return TemplateDetail(
            # **_row_to_summary(row).model_dump()：
            # 先把行转成摘要对象，model_dump() 转回字典，
            # ** 把字典"摊开"成关键字参数（等价于逐个写 id=..., name=..., ...）
            **_row_to_summary(row).model_dump(),
            desc=row["body"],
            variants=versions,
        )

    def list_categories(self) -> list[CategoryInfo]:
        """列出所有分类及其模板数量（前端侧边栏用）。"""
        rows = repository.category_counts(self._settings.db_path)
        return [
            CategoryInfo(id=row["category"], name=row["category"], count=row["count"])
            for row in rows
        ]

    # ===== 可视化增删改（写操作） =====

    def _scan_for_write(self) -> list[TemplateNode]:
        """写操作前的现场扫描：拿最新的目录结构做存在性校验。"""
        return scan_content(self._settings.content_dir).templates

    @staticmethod
    def _find_node(
        templates: list[TemplateNode], category: str, name: str
    ) -> TemplateNode:
        """在扫描结果里按分类+模板名找节点，找不到抛 404。"""
        for node in templates:
            if node.category == category and node.slug == name:
                return node
        raise NotFoundError(f"模板不存在: {category}/{name}")

    @staticmethod
    def _find_version(node: TemplateNode, slug: str) -> VersionNode:
        """在模板节点里按副标签 slug 找版本，找不到抛 404。"""
        for version in node.versions:
            if version.slug == slug:
                return version
        # slug 为空字符串是"顶层单版本"，显示名用 ROOT_VERSION_TOKEN（~）
        label = slug or ROOT_VERSION_TOKEN
        raise NotFoundError(f"版本不存在: {node.id}/{label}")

    def create_template(self, payload: TemplateCreate) -> TemplateDetail:
        """新建空主标签目录并重建索引，返回新建模板的详情。"""
        with self._lock:
            # writer 负责在 content/ 下真正创建目录
            category, name = writer.create_template_dir(
                self._settings.content_dir, payload.category, payload.name
            )
            self.rebuild()  # 目录落盘后重建索引，让新模板立刻可见
        return self.get_detail(f"{category}/{name}")

    def rename_template(
        self, category: str, name: str, payload: TemplateRename
    ) -> TemplateDetail:
        """主标签重命名/换分类，返回新位置上的模板详情。"""
        with self._lock:
            new_category, new_name = writer.rename_template_dir(
                self._settings.content_dir,
                category,
                name,
                new_category=payload.new_category,
                new_name=payload.new_name,
            )
            self.rebuild()
        return self.get_detail(f"{new_category}/{new_name}")

    def delete_template(self, category: str, name: str) -> None:
        """删除空主标签目录（非空目录由 writer 拒绝，防误删整棵树）。"""
        with self._lock:
            writer.delete_template_dir(self._settings.content_dir, category, name)
            self.rebuild()

    def create_version(
        self, category: str, name: str, payload: VersionUpsert
    ) -> TemplateDetail:
        """在模板下新建副标签版本，返回整个模板的最新详情。"""
        with self._lock:
            writer.create_version_dir(
                self._settings.content_dir, category, name, payload
            )
            self.rebuild()
        return self.get_detail(f"{category}/{name}")

    def update_version(
        self, category: str, name: str, version_token: str, payload: VersionUpsert
    ) -> TemplateDetail:
        """更新版本内容（代码/元数据/正文/改名/换扩展名），返回模板最新详情。"""
        # URL 里的 "~" 翻译成空字符串，表示"顶层单版本"
        slug = "" if version_token == ROOT_VERSION_TOKEN else version_token
        with self._lock:
            node = self._find_node(self._scan_for_write(), category, name)
            current = self._find_version(node, slug)
            writer.update_version_dir(
                self._settings.content_dir,
                category,
                name,
                current.slug,
                current.file,
                payload,
            )
            self.rebuild()
        return self.get_detail(f"{category}/{name}")

    def delete_version(
        self, category: str, name: str, version_token: str
    ) -> TemplateDetail:
        """删除一个版本。删光后模板成为空主标签，返回模板最新详情。"""
        slug = "" if version_token == ROOT_VERSION_TOKEN else version_token
        with self._lock:
            node = self._find_node(self._scan_for_write(), category, name)
            current = self._find_version(node, slug)
            writer.delete_version_dir(
                self._settings.content_dir, category, name, current.slug, current.file
            )
            self.rebuild()
        return self.get_detail(f"{category}/{name}")


def _row_to_summary(row: sqlite3.Row) -> TemplateSummary:
    """把一行数据库记录转成对外的 TemplateSummary 对象。"""
    # 数据库里日期存的是字符串，解析回 date 对象；为空则保持 None
    updated: datetime.date | None = (
        datetime.date.fromisoformat(row["updated"]) if row["updated"] else None
    )
    return TemplateSummary(
        id=row["id"],
        name=row["slug"],  # 显示名就是模板目录名（slug 列）
        cat=row["category"],
        lang=row["lang"],
        file=row["file"],
        tags=json.loads(row["tags"]),
        src=row["source"],
        page=row["page"],
        updated=updated,
        priority=row["priority"],
        variant_count=row["variant_count"],
    )


def _sort_summaries(items: list[TemplateSummary], sort: SortMode) -> list[TemplateSummary]:
    """按指定方式排序摘要列表。"""
    if sort == "name":
        # 按名称排序（忽略大小写）
        return sorted(items, key=lambda t: t.name.lower())
    if sort == "updated":
        # 按更新日期倒序；没填日期的排最后
        # key 返回一个元组：第一个元素把"有无日期"分开，第二个是日期本身
        return sorted(
            items,
            key=lambda t: (t.updated is not None, t.updated or datetime.date.min),
            reverse=True,
        )
    # priority：优先级降序，其次按更新日期
    return sorted(
        items,
        key=lambda t: (t.priority, t.updated or datetime.date.min),
        reverse=True,
    )


# ===== 依赖注入（FastAPI 风格的"全局服务实例"管理）=====

_service: TemplateService | None = None  # 模块级变量：全局唯一的服务实例


def init_template_service(settings: Settings | None = None) -> TemplateService:
    """应用启动时调用：创建服务并完成首次索引构建。

    由 main.py 的 lifespan 调用一次；之后的 HTTP 请求都复用同一个实例。
    """
    global _service  # global 声明：下面要修改模块级变量 _service
    _service = TemplateService(settings or get_settings())
    _service.rebuild()  # 启动即完成首次扫描 + 建索引，第一个请求不用等
    return _service


def get_template_service() -> TemplateService:
    """FastAPI 依赖：获取全局服务实例。

    路由函数通过 Depends(get_template_service) 拿到这个服务，
    这样所有请求共享同一个实例（共享同一份诊断与锁）。
    """
    if _service is None:
        raise RuntimeError("TemplateService 尚未初始化")
    return _service