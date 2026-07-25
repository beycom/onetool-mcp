"""Read-only listing operations: list, grep, slice, toc, info, stats, export, dbs."""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any, cast

from otpack import LogSpan
from otutil.tools._content_util import grep_lines, parse_headings

from .config import _get_config
from .db import deserialize_meta, deserialize_tags, get_connection


def dbs() -> str:
    """List all configured knowledge databases.

    Returns:
        List of configured database names and descriptions.

    Example:
        kb.dbs()
    """
    config = _get_config()
    if not config.kb:
        return "No databases configured. Add entries under tools.knowledge.kb in onetool.yaml"
    lines = [f"Configured databases ({len(config.kb)}):"]
    for name, kb_project in config.kb.items():
        db_cfg = kb_project.db
        desc = f" — {db_cfg.description}" if db_cfg.description else ""
        lines.append(f"  {name}{desc}  ({db_cfg.path})")
    return "\n".join(lines)


def list_entries(
    *,
    db: str,
    topic: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List knowledge base entries with optional filters.

    Args:
        db: Database name
        topic: Optional topic prefix filter (e.g., 'guides/' matches all under guides)
        category: Optional category filter
        tags: Optional tag filter (matches entries with any of these tags)
        limit: Max results (default 50)
        offset: Pagination offset

    Returns:
        Formatted list of entries.

    Example:
        kb.list(db='docs')
        kb.list(db='docs', category='rule', limit=20)
    """
    with LogSpan(span="kb.list", db=db, topic=topic):
        try:
            conn = get_connection(db)
            sql = "SELECT topic, category, tags, created_at, updated_at FROM chunks WHERE 1=1"
            params: list[Any] = []
            sql, params = _apply_topic_filter(sql, params, topic)
            if category:
                sql += " AND category = ?"
                params.append(category)
            if tags:
                sql += _tags_filter(tags)
                params.extend(tags)
            sql += " ORDER BY topic LIMIT ? OFFSET ?"
            params += [limit, offset]
            rows = conn.execute(sql, params).fetchall()
            if not rows:
                return "No entries found"
            count_sql = "SELECT COUNT(*) FROM chunks WHERE 1=1"
            count_params: list[Any] = []
            count_sql, count_params = _apply_topic_filter(
                count_sql, count_params, topic
            )
            if category:
                count_sql += " AND category = ?"
                count_params.append(category)
            if tags:
                count_sql += _tags_filter(tags)
                count_params.extend(tags)
            total = conn.execute(count_sql, count_params).fetchone()[0]
            lines = [f"Entries ({len(rows)} shown, {total} total):\n"]
            for r in rows:
                tags_str = ", ".join(deserialize_tags(r[2])) if r[2] else ""
                tag_part = f"  [{tags_str}]" if tags_str else ""
                lines.append(f"  [{r[1]}] {r[0]}{tag_part}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing '{db}': {e}"


def grep(
    *,
    pattern: str,
    db: str,
    topic: str | None = None,
    category: str | None = None,
    context: int = 2,
    limit: int = 50,
    case_sensitive: bool = True,
    fixed_strings: bool = False,
) -> str:
    """Regex search across knowledge base entries.

    Args:
        pattern: Regex pattern (or literal string if fixed_strings=True)
        db: Database name
        topic: Optional topic prefix filter
        category: Optional category filter
        context: Context lines before/after each match (default 2)
        limit: Max entries to search (default 50)
        case_sensitive: Case-sensitive matching (default True)
        fixed_strings: Treat pattern as literal string

    Returns:
        Matching lines grouped by topic.

    Example:
        kb.grep(pattern='enumerate', db='docs')
    """
    with LogSpan(span="kb.grep", db=db, pattern=pattern) as s:
        try:
            if fixed_strings:
                pattern = re.escape(pattern)
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return f"Error: Invalid regex: {e}"

            conn = get_connection(db)
            sql = "SELECT topic, content FROM chunks WHERE 1=1"
            params: list[Any] = []
            sql, params = _apply_topic_filter(sql, params, topic)
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()

            output_parts = []
            total_matches = 0
            for row_topic, content in rows:
                groups = grep_lines(content, regex, context=context, max_groups=10)
                if not groups:
                    continue
                match_count = sum(1 for g in groups for _, _, is_match in g if is_match)
                total_matches += match_count
                blocks = []
                for group in groups:
                    lines = [
                        f"{'>' if is_match else ' '} {ln:4d} | {line}"
                        for ln, line, is_match in group
                    ]
                    blocks.append("\n".join(lines))
                header = f"## {row_topic} ({match_count} match{'es' if match_count != 1 else ''})"
                output_parts.append(header + "\n" + "\n  ...\n".join(blocks))

            if not output_parts:
                s.add("resultCount", 0)
                return f"No matches found for: {pattern}"
            s.add("resultCount", total_matches)
            return (
                f"Found {total_matches} matches across {len(output_parts)} entries\n\n"
                + "\n\n".join(output_parts)
            )
        except Exception as e:
            s.add("error", str(e))
            return f"Error in grep: {e}"


def slice_entry(
    *,
    topic: str,
    db: str,
    heading: str | None = None,
    start: int | None = None,
    end: int | None = None,
) -> str:
    """Extract a section from an entry by heading or line range.

    Args:
        topic: Topic identifier
        db: Database name
        heading: Section heading to extract (e.g., 'Options')
        start: Start line (1-indexed)
        end: End line (inclusive)

    Returns:
        Extracted section content.

    Example:
        kb.slice(topic='guides/move', heading='Options', db='docs')
    """
    with LogSpan(span="kb.slice", topic=topic, db=db):
        try:
            conn = get_connection(db)
            row = conn.execute(
                "SELECT content FROM chunks WHERE topic = ? ORDER BY created_at DESC LIMIT 1",
                [topic],
            ).fetchone()
            if not row:
                return f"Error: No entry found for topic '{topic}'"
            content = row[0]

            if heading:
                sections = parse_headings(content)
                for sec in sections:
                    if sec["heading"].lower() == heading.lower():
                        lines = content.split("\n")
                        section_lines = lines[sec["start"] - 1 : sec["end"]]
                        return "\n".join(section_lines)
                return f"Error: Heading '{heading}' not found in '{topic}'"

            if start is not None:
                lines = content.split("\n")
                s = max(0, start - 1)
                e = end if end is not None else len(lines)
                return "\n".join(lines[s:e])

            return cast("str", content)
        except Exception as e:
            return f"Error slicing '{topic}': {e}"


def toc(*, topic: str, db: str) -> str:
    """Return the heading structure (table of contents) of an entry.

    Args:
        topic: Topic identifier
        db: Database name

    Returns:
        Formatted table of contents.

    Example:
        kb.toc(topic='guides/move', db='docs')
    """
    with LogSpan(span="kb.toc", topic=topic, db=db):
        try:
            conn = get_connection(db)
            row = conn.execute(
                "SELECT content FROM chunks WHERE topic = ? ORDER BY created_at DESC LIMIT 1",
                [topic],
            ).fetchone()
            if not row:
                return f"Error: No entry found for topic '{topic}'"
            content = row[0]
            sections = parse_headings(content)
            lines = content.split("\n")
            if not sections:
                return f"No headings found in '{topic}' ({len(lines)} lines)"
            result = [f"TOC for '{topic}' ({len(lines)} lines):"]
            for sec in sections:
                indent = "  " * (sec["level"] - 1)
                result.append(
                    f"{indent}{'#' * sec['level']} {sec['heading']} (lines {sec['start']}-{sec['end']})"
                )
            return "\n".join(result)
        except Exception as e:
            return f"Error in toc: {e}"


def info(*, db: str) -> str:
    """Return database metadata and connection info.

    Args:
        db: Database name

    Returns:
        Database info including chunk count, embedding coverage, and file path.

    Example:
        kb.info(db='docs')
    """
    with LogSpan(span="kb.info", db=db):
        try:
            from .db import _resolve_db_path

            conn = get_connection(db)
            db_path = _resolve_db_path(db)

            # Try to read _meta chunk
            meta_row = conn.execute(
                "SELECT content, meta FROM chunks WHERE topic = '_meta'"
            ).fetchone()
            meta_content = meta_row[0] if meta_row else "(no metadata)"
            meta_extra = deserialize_meta(meta_row[1]) if meta_row else {}

            total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            vec_count = 0
            with contextlib.suppress(Exception):
                vec_count = conn.execute("SELECT COUNT(*) FROM chunks_vec").fetchone()[
                    0
                ]
            coverage = f"{100 * vec_count // total}%" if total else "N/A"

            file_size = db_path.stat().st_size if db_path.exists() else 0
            size_mb = file_size / (1024 * 1024)

            lines = [
                f"Database: {db}",
                f"Path: {db_path}",
                f"Size: {size_mb:.1f} MB",
                f"Chunks: {total}",
                f"Embedding coverage: {coverage}",
                "",
                "Metadata:",
                meta_content,
            ]
            if meta_extra:
                lines.append(f"Extra: {meta_extra}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error getting info for '{db}': {e}"


def stats(*, db: str, top: int = 5) -> str:
    """Return entry statistics broken down by category, with links, AI enrichments, and most-accessed pages.

    Args:
        db: Database name
        top: Number of most-accessed pages to show (default 5)

    Returns:
        Statistics including per-category counts, embedding coverage, file size,
        link graph summary, AI enrichment coverage, and top accessed chunks.

    Example:
        kb.stats(db='docs')
        kb.stats(db='docs', top=10)
    """
    with LogSpan(span="kb.stats", db=db):
        try:
            from .db import _resolve_db_path

            conn = get_connection(db)
            db_path = _resolve_db_path(db)

            by_cat = conn.execute(
                "SELECT category, COUNT(*) FROM chunks GROUP BY category ORDER BY COUNT(*) DESC"
            ).fetchall()
            total = sum(r[1] for r in by_cat)

            vec_count = 0
            with contextlib.suppress(Exception):
                vec_count = conn.execute("SELECT COUNT(*) FROM chunks_vec").fetchone()[
                    0
                ]

            file_size = db_path.stat().st_size if db_path.exists() else 0
            size_mb = file_size / (1024 * 1024)
            coverage = f"{100 * vec_count // total}%" if total else "N/A"

            lines = [f"Stats for '{db}' ({size_mb:.1f} MB):"]
            lines.append(f"  Total chunks: {total}")
            lines.append(f"  Embedding coverage: {coverage}")
            lines.append("  By category:")
            for cat, count in by_cat:
                lines.append(f"    {cat}: {count}")

            # Links
            edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            lines.append(f"  Links (edges): {edge_count}")
            if edge_count:
                top_linked = conn.execute(
                    """
                    SELECT c.topic, COUNT(*) AS in_degree
                    FROM edges e JOIN chunks c ON e.dst_id = c.id
                    GROUP BY e.dst_id ORDER BY in_degree DESC LIMIT 5
                    """
                ).fetchall()
                if top_linked:
                    lines.append("  Most linked pages:")
                    for topic, degree in top_linked:
                        lines.append(
                            f"    {topic} ({degree} link{'s' if degree != 1 else ''})"
                        )

            # AI enrichments
            with_summary = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE summary IS NOT NULL AND summary != ''"
            ).fetchone()[0]
            with_tags = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE tags != '[]' AND tags != ''"
            ).fetchone()[0]
            summary_pct = f"{100 * with_summary // total}%" if total else "N/A"
            tags_pct = f"{100 * with_tags // total}%" if total else "N/A"
            lines.append(
                f"  AI enrichments: summaries {with_summary}/{total} ({summary_pct}), tags {with_tags}/{total} ({tags_pct})"
            )

            # Most accessed
            top_rows = conn.execute(
                "SELECT topic, hit_count FROM chunks WHERE hit_count > 0 ORDER BY hit_count DESC LIMIT ?",
                [top],
            ).fetchall()
            if top_rows:
                lines.append(f"  Most accessed (top {len(top_rows)}):")
                for topic, hits in top_rows:
                    lines.append(f"    {topic}: {hits} hit{'s' if hits != 1 else ''}")
            else:
                lines.append("  Most accessed: none yet")

            return "\n".join(lines)
        except Exception as e:
            return f"Error getting stats for '{db}': {e}"


def export_db(
    *,
    db: str,
    path: str,
    category: str | None = None,
    topic: str | None = None,
) -> str:
    """Export the database or a subset to a JSON file.

    Args:
        db: Database name
        path: Output file path
        category: Optional category filter
        topic: Optional topic prefix filter

    Returns:
        Confirmation with export count.

    Example:
        kb.export(db='docs', path='export/docs.json')
    """
    with LogSpan(span="kb.export", db=db) as s:
        try:
            conn = get_connection(db)
            sql = "SELECT id, topic, content, category, tags, meta, created_at, updated_at FROM chunks WHERE 1=1"
            params: list[Any] = []
            sql, params = _apply_topic_filter(sql, params, topic)
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " ORDER BY topic"
            rows = conn.execute(sql, params).fetchall()

            out_path = Path(path).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            records = [
                {
                    "id": r[0],
                    "topic": r[1],
                    "content": r[2],
                    "category": r[3],
                    "tags": deserialize_tags(r[4]),
                    "meta": deserialize_meta(r[5]),
                    "created_at": r[6],
                    "updated_at": r[7],
                }
                for r in rows
            ]
            out_path.write_text(
                json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            s.add("exported", len(records))
            return f"Exported {len(records)} entries to {out_path}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error exporting '{db}': {e}"


def _apply_topic_filter(
    sql: str, params: list[Any], topic: str | None
) -> tuple[str, list[Any]]:
    if not topic:
        return sql, params
    if topic.endswith("/"):
        sql += " AND (topic = ? OR topic LIKE ?)"
        params += [topic.rstrip("/"), topic + "%"]
    elif "*" in topic:
        sql += " AND topic LIKE ?"
        params.append(topic.replace("*", "%"))
    else:
        sql += " AND topic = ?"
        params.append(topic)
    return sql, params


def _tags_filter(tags: list[str]) -> str:
    placeholders = ", ".join("?" for _ in tags)
    return f" AND EXISTS (SELECT 1 FROM json_each(tags) WHERE json_each.value IN ({placeholders}))"


__all__ = ["dbs", "grep", "info", "list_entries", "slice_entry", "stats", "toc"]
