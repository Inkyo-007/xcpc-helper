"""FTS5 检索索引与元数据缓存的读写。

SQLite 仅作缓存：每次 content/ 变更后全量重建，库文件可随时删除。
FTS5 虚拟表 SQLAlchemy/SQLModel 不支持，此处直接使用 sqlite3 原声 SQL。

中文检索策略：
- SQLite ≥ 3.34 时 FTS5 使用 trigram 分词器，支持中文子串匹配（≥3 字符）；
- 短词（如双字标签"素数"）退化为 LIKE 子串匹配；
- trigram 不可用时全部退化为 LIKE。
"""

import json
import logging
import sqlite3
from pathlib import Path

from core.database import get_connection
from modules.template.models import ScanResult, TemplateNode

logger = logging.getLogger("xcpc.repository")

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


def _try_create_fts(conn: sqlite3.Connection) -> bool:
    """创建 FTS5 表，trigram 不可用时返回 False（检索退化为 LIKE）。"""
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE templates_fts USING fts5("
            "id UNINDEXED, name, tags, body, code, tokenize='trigram')"
        )
        return True
    except sqlite3.OperationalError:
        logger.warning("当前 SQLite 不支持 trigram 分词，全文检索退化为 LIKE")
        return False


def _template_row(template: TemplateNode) -> tuple:
    """将扫描结果折算为模板级字段：主版本取第一个，标签取并集，日期取最新。"""
    primary = template.versions[0]
    tags: list[str] = []
    for version in template.versions:
        for tag in version.meta.tags:
            if tag not in tags:
                tags.append(tag)
    dates = [v.meta.updated for v in template.versions if v.meta.updated is not None]
    updated = max(dates).isoformat() if dates else None
    priority = max(v.meta.priority for v in template.versions)

    search_text = " ".join(
        [template.slug, " ".join(tags)]
        + [v.body for v in template.versions]
        + [v.code for v in template.versions]
    )
    return (
        template.id,
        template.category,
        template.slug,
        json.dumps(tags, ensure_ascii=False),
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
    """全量重建索引（事务内完成，重建期间查询不受影响）。"""
    with get_connection(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS templates_fts")
        conn.execute("DROP TABLE IF EXISTS versions")
        conn.execute("DROP TABLE IF EXISTS templates")
        conn.execute(_DDL_TEMPLATES)
        conn.execute(_DDL_VERSIONS)
        _try_create_fts(conn)

        for template in scan.templates:
            conn.execute(
                "INSERT INTO templates VALUES (" + ",".join("?" * 13) + ")",
                _template_row(template),
            )
            for order, version in enumerate(template.versions):
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
            all_tags = " ".join(
                dict.fromkeys(tag for v in template.versions for tag in v.meta.tags)
            )
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
    logger.info("索引重建完成：%d 份模板", len(scan.templates))


def _fts_available(db_path: Path) -> bool:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='templates_fts'"
        ).fetchone()
        return bool(row[0])


def search_ids(db_path: Path, keyword: str) -> set[str]:
    """按关键词过滤模板 id。多词取交集；每词优先 FTS trigram，短词退化 LIKE。"""
    terms = keyword.split()
    if not terms:
        return set()

    result: set[str] | None = None
    with get_connection(db_path) as conn:
        fts_ok = _fts_available(db_path)
        for term in terms:
            if fts_ok and len(term) >= 3:
                quoted = '"' + term.replace('"', '""') + '"'
                rows = conn.execute(
                    "SELECT id FROM templates_fts WHERE templates_fts MATCH ?",
                    (quoted,),
                ).fetchall()
                matched = {row[0] for row in rows}
            else:
                rows = conn.execute(
                    "SELECT id FROM templates WHERE search_text LIKE ? ESCAPE '\\'",
                    ("%" + _escape_like(term) + "%",),
                ).fetchall()
                matched = {row[0] for row in rows}
            result = matched if result is None else (result & matched)
    return result if result is not None else set()


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_templates(db_path: Path, category: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM templates"
    params: tuple = ()
    if category:
        sql += " WHERE category = ?"
        params = (category,)
    with get_connection(db_path) as conn:
        return conn.execute(sql, params).fetchall()


def get_template(db_path: Path, template_id: str) -> sqlite3.Row | None:
    with get_connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()


def get_versions(db_path: Path, template_id: str) -> list[sqlite3.Row]:
    with get_connection(db_path) as conn:
        return conn.execute(
            "SELECT * FROM versions WHERE template_id = ? ORDER BY ord",
            (template_id,),
        ).fetchall()


def category_counts(db_path: Path) -> list[sqlite3.Row]:
    with get_connection(db_path) as conn:
        return conn.execute(
            "SELECT category, COUNT(*) AS count FROM templates GROUP BY category "
            "ORDER BY category"
        ).fetchall()
