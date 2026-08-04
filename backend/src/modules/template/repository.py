"""FTS5 检索索引与元数据缓存的读写。

SQLite 仅作缓存：每次 content/ 变更后全量重建，库文件可随时删除。
FTS5 虚拟表 SQLAlchemy/SQLModel 不支持，此处直接使用 sqlite3 原生 SQL。

中文检索策略：
- SQLite >= 3.34 时 FTS5 使用 trigram 分词器，支持中文子串匹配（>=3 字符）；
- 短词（如双字标签"素数"）退化为 LIKE 子串匹配；
- trigram 不可用时全部退化为 LIKE。

【初学者导读】
数据库里共三张表：
- templates      一行一份模板（列表页需要的信息）
- versions       一行一个版本（详情页需要的代码全文）
- templates_fts  FTS5 全文检索虚拟表（专门用于关键词搜索）
重建索引（rebuild_index）时把三张表全部删掉重建；
查询（search_ids / list_templates 等）只读这三张表。
"""

import json  # 标准库：把 Python 列表转成 JSON 字符串存数据库
import logging
import sqlite3  # 标准库 SQLite 驱动（类型注解会用到 Connection / Row）
from pathlib import Path

from core.database import get_connection  # 上一讲过的连接管理器
from modules.template.models import ScanResult, TemplateNode

logger = logging.getLogger("xcpc.repository")

# ===== 建表 SQL（DDL，Data Definition Language）=====
# 三引号字符串里直接写 SQL。TEXT/INTEGER 是 SQLite 的字段类型；
# PRIMARY KEY 主键（每行唯一）；NOT NULL 不允许为空。
_DDL_TEMPLATES = """
CREATE TABLE templates (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    slug TEXT NOT NULL,
    tags TEXT NOT NULL,
    source TEXT,
    page TEXT,
    priority INTEGER NOT NULL,
    updated TEXT,
    lang TEXT NOT NULL,
    file TEXT NOT NULL,
    body TEXT NOT NULL,
    variant_count INTEGER NOT NULL,
    search_text TEXT NOT NULL
)
"""

_DDL_VERSIONS = """
CREATE TABLE versions (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    lang TEXT NOT NULL,
    file TEXT NOT NULL,
    code TEXT NOT NULL,
    body TEXT NOT NULL,
    ord INTEGER NOT NULL,
    tags TEXT NOT NULL,
    source TEXT,
    page TEXT,
    priority INTEGER NOT NULL,
    updated TEXT
)
"""
# REFERENCES templates(id) ON DELETE CASCADE：
# 外键约束——version 必须属于某个 template；删除模板时自动删掉它的所有版本
# （需要连接时开启 PRAGMA foreign_keys=ON，见 core/database.py）


def _try_create_fts(conn: sqlite3.Connection) -> bool:
    """创建 FTS5 表，trigram 不可用时返回 False（检索退化为 LIKE）。

    FTS5 是 SQLite 的全文检索扩展：把文本按词/字切开建索引，
    让"关键词搜索"比逐行 LIKE 快得多。trigram 分词器按每 3 个字符切分，
    正好适合中文（中文没有空格分词）。
    """
    try:
        conn.execute(
            # UNINDEXED 表示 id 列只存不参与检索；
            # name/tags/body/code 四列参与全文检索
            "CREATE VIRTUAL TABLE templates_fts USING fts5("
            "id UNINDEXED, name, tags, body, code, tokenize='trigram')"
        )
        return True
    except sqlite3.OperationalError:
        # 老版本 SQLite 没有 trigram 分词器：放弃 FTS，之后全部用 LIKE 搜索
        logger.warning("当前 SQLite 不支持 trigram 分词，全文检索退化为 LIKE")
        return False


def _template_row(template: TemplateNode) -> tuple:
    """将扫描结果折算为模板级字段：主版本取第一个，标签取并集，日期取最新。

    返回值是一个元组，顺序对应 INSERT 语句里的 13 个字段。
    """
    primary = template.versions[0]  # 第一个版本作为"主版本"，列表页信息取自它

    # 标签取所有版本的并集（保持出现顺序、去重）
    tags: list[str] = []
    for version in template.versions:
        for tag in version.meta.tags:
            if tag not in tags:
                tags.append(tag)

    # 日期取所有版本中最新的一天；都没有则为 None
    dates = [v.meta.updated for v in template.versions if v.meta.updated is not None]
    updated = max(dates).isoformat() if dates else None
    # 优先级取所有版本里最高的
    priority = max(v.meta.priority for v in template.versions)

    # search_text 是给 LIKE 退化检索准备的"纯文本大杂烩"：
    # 模板名 + 标签 + 所有版本的说明正文 + 所有版本的代码
    search_text = " ".join(
        [template.slug, " ".join(tags)]
        + [v.body for v in template.versions]
        + [v.code for v in template.versions]
    )
    return (
        template.id,
        template.category,
        template.slug,
        json.dumps(tags, ensure_ascii=False),  # 列表转成 JSON 字符串存一个字段
        primary.meta.source,
        primary.meta.page,
        priority,
        updated,
        primary.lang,
        primary.file,
        primary.body,
        len(template.versions),
        search_text,
    )


def rebuild_index(db_path: Path, scan: ScanResult) -> None:
    """全量重建索引（事务内完成，重建期间查询不受影响）。

    由 service.rebuild() 在启动时和文件变更时调用。
    "全量"指先删光再重新写入，简单粗暴但可靠（数据量小，成本极低）。
    """
    with get_connection(db_path) as conn:
        # 先删旧表再建新表：顺序是先删引用别人的表，再删被引用的表
        conn.execute("DROP TABLE IF EXISTS templates_fts")
        conn.execute("DROP TABLE IF EXISTS versions")
        conn.execute("DROP TABLE IF EXISTS templates")
        conn.execute(_DDL_TEMPLATES)
        conn.execute(_DDL_VERSIONS)
        _try_create_fts(conn)

        for template in scan.templates:
            # SQL 里的 ? 是占位符，真实值由第二个参数（元组）提供。
            # ",".join("?" * 13) 生成 "?,?,?,?,...,?" 共 13 个问号。
            # 用占位符而不是直接拼字符串，可以防止 SQL 注入和引号问题。
            conn.execute(
                "INSERT INTO templates VALUES (" + ",".join("?" * 13) + ")",
                _template_row(template),
            )
            # enumerate(...) 同时拿到序号和内容，用于保持版本顺序
            for order, version in enumerate(template.versions):
                # 版本 id：多版本是 "模板id/副标签"，单版本直接等于模板 id
                version_id = (
                    f"{template.id}/{version.slug}" if version.slug else template.id
                )
                conn.execute(
                    "INSERT INTO versions VALUES (" + ",".join("?" * 14) + ")",
                    (
                        version_id,
                        template.id,
                        version.name,
                        version.slug,
                        version.lang,
                        version.file,
                        version.code,
                        version.body,
                        order,
                        json.dumps(version.meta.tags, ensure_ascii=False),
                        version.meta.source,
                        version.meta.page,
                        version.meta.priority,
                        version.meta.updated.isoformat() if version.meta.updated else None,
                    ),
                )
            # dict.fromkeys(...)：把标签去重（保持顺序）后用空格拼成一个字符串
            all_tags = " ".join(
                dict.fromkeys(tag for v in template.versions for tag in v.meta.tags)
            )
            # 写入 FTS 检索表：只有 4 列参与检索（名字/标签/正文/代码）
            conn.execute(
                "INSERT INTO templates_fts (id, name, tags, body, code) VALUES (?,?,?,?,?)",
                (
                    template.id,
                    template.slug,
                    all_tags,
                    "\n".join(v.body for v in template.versions),
                    "\n".join(v.code for v in template.versions),
                ),
            )
    # 退出 with 时 get_connection 自动提交（见 core/database.py）
    logger.info("索引重建完成：%d 份模板", len(scan.templates))


def _fts_available(db_path: Path) -> bool:
    """检查数据库里是否存在 FTS 表（没有就说明当时 trigram 创建失败了）。"""
    with get_connection(db_path) as conn:
        # sqlite_master 是 SQLite 自带的"目录表"，记录库里有哪些表
        row = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='templates_fts'"
        ).fetchone()
        return bool(row[0])  # 计数大于 0 就为 True


def search_ids(db_path: Path, keyword: str) -> set[str]:
    """按关键词过滤模板 id。多词取交集；每词优先 FTS trigram，短词退化 LIKE。

    例如 keyword="线段树 懒标记"，会拆成两个词分别搜索，
    最终返回两个结果的交集（都命中的模板）。
    """
    terms = keyword.split()  # 按空白拆分关键词
    if not terms:
        return set()

    # result 用 None 表示"还没算过第一个词"；set 是集合，天然去重
    result: set[str] | None = None
    with get_connection(db_path) as conn:
        fts_ok = _fts_available(db_path)
        for term in terms:
            if fts_ok and len(term) >= 3:
                # trigram 要求词至少 3 个字符才有效。
                # 双引号包住搜索词是 FTS5 的"精确短语"语法；
                # 词里若本身有双引号，要替换成两个双引号转义
                quoted = '"' + term.replace('"', '""') + '"'
                rows = conn.execute(
                    "SELECT id FROM templates_fts WHERE templates_fts MATCH ?",
                    (quoted,),
                ).fetchall()
                # {row[0] for row in rows}：集合推导式，把所有 id 装进集合
                matched = {row[0] for row in rows}
            else:
                # 短词或没有 FTS：退化为 LIKE 子串匹配。
                # % 在 LIKE 里表示"任意字符"，所以要先转义用户输入里的 %、_、\
                rows = conn.execute(
                    "SELECT id FROM templates WHERE search_text LIKE ? ESCAPE '\\'",
                    ("%" + _escape_like(term) + "%",),
                ).fetchall()
                matched = {row[0] for row in rows}
            # 与之前的结果取交集：同时命中所有词的模板才保留
            result = matched if result is None else (result & matched)
    return result if result is not None else set()


def _escape_like(term: str) -> str:
    """转义 LIKE 查询里的特殊字符，防止用户输入的 % / _ / \\ 被当成通配符。"""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_templates(db_path: Path, category: str | None = None) -> list[sqlite3.Row]:
    """列出全部模板（可选按分类过滤），返回数据库行（Row 对象）列表。"""
    sql = "SELECT * FROM templates"
    params: tuple = ()
    if category:
        sql += " WHERE category = ?"
        params = (category,)
    with get_connection(db_path) as conn:
        # fetchall() 把查询结果全部取出成一个列表
        return conn.execute(sql, params).fetchall()


def get_template(db_path: Path, template_id: str) -> sqlite3.Row | None:
    """按 id 查单份模板，查不到返回 None。"""
    with get_connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()  # fetchone() 只取一行；没有结果时返回 None


def get_versions(db_path: Path, template_id: str) -> list[sqlite3.Row]:
    """按模板 id 查所有版本，按 ord 保持扫描时的顺序。"""
    with get_connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM versions WHERE template_id = ? ORDER BY ord",
            (template_id,),
        ).fetchall()


def category_counts(db_path: Path) -> list[sqlite3.Row]:
    """统计每个分类下有多少份模板，供前端侧边栏显示数量。"""
    with get_connection(db_path) as conn:
        return conn.execute(
            "SELECT category, COUNT(*) AS count FROM templates GROUP BY category "
            "ORDER BY category"
        ).fetchall()
