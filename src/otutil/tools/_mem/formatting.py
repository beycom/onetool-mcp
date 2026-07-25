"""Tree formatting, list entry metadata, and staleness display."""

from __future__ import annotations

import builtins
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from otpack import LogSpan

from .content import _check_staleness, _topic_filter
from .db import _deserialize_meta, _deserialize_tags, _use_connection

_builtins_list = builtins.list


def stale(
    *,
    topic: str | None = None,
) -> str:
    """Check which file-backed memories have outdated content relative to their source files.

    Scans memories for staleness by comparing stored source_mtime against the
    current file modification time. Only checks memories that have source
    metadata (written via file= parameter).

    Args:
        topic: Topic prefix to filter (e.g., "docs/"). If omitted, checks all memories.

    Returns:
        Summary of fresh, stale, missing, and skipped memories.

    Example:
        mem.stale()
        mem.stale(topic="proj/onetool-mcp/dev/")
    """
    with LogSpan(span="mem.stale", topic=topic or "(all)") as s:
        try:
            with _use_connection() as conn:
                sql = "SELECT topic, meta FROM memories WHERE 1=1"
                topic_sql, params = _topic_filter(topic)
                sql += topic_sql
                sql += " ORDER BY topic"
                rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("found", 0)
                return "No memories found" + (f" under '{topic}'" if topic else "")

            fresh: _builtins_list[str] = []
            stale_list: _builtins_list[tuple[str, str, str]] = []
            missing_list: _builtins_list[str] = []
            skipped = 0

            for row_topic, raw_meta in rows:
                meta = _deserialize_meta(raw_meta)
                status = _check_staleness(meta)
                if status == "fresh":
                    fresh.append(row_topic)
                elif status == "stale":
                    stored = meta.get("source_mtime", "")
                    source_path = Path(meta["source"])
                    try:
                        current = str(source_path.stat().st_mtime)
                    except OSError:
                        missing_list.append(row_topic)
                        continue
                    stale_list.append((row_topic, stored, current))
                elif status == "missing":
                    missing_list.append(row_topic)
                else:
                    skipped += 1

            total_checked = len(fresh) + len(stale_list) + len(missing_list)
            if total_checked == 0:
                s.add("skipped", skipped)
                return "No file-backed memories found" + (
                    f" under '{topic}'" if topic else ""
                )

            scope = f' under "{topic}"' if topic else ""
            parts = [f"Checked {total_checked} file-backed memories{scope}:"]
            parts.append(f"  {len(fresh)} fresh")

            if stale_list:
                parts.append(f"  {len(stale_list)} stale:")
                for st_topic, stored_mt, current_mt in stale_list:
                    stored_dt = datetime.fromtimestamp(
                        float(stored_mt), tz=UTC
                    ).strftime("%Y-%m-%d")
                    current_dt = datetime.fromtimestamp(
                        float(current_mt), tz=UTC
                    ).strftime("%Y-%m-%d")
                    parts.append(
                        f"    - {st_topic} (stored: {stored_dt}, file: {current_dt})"
                    )

            if missing_list:
                parts.append(f"  {len(missing_list)} missing:")
                for m_topic in missing_list:
                    parts.append(f"    - {m_topic} (source file deleted)")

            if skipped:
                parts.append(f"  ({skipped} memories without source metadata skipped)")

            s.add("fresh", len(fresh))
            s.add("stale", len(stale_list))
            s.add("missing", len(missing_list))
            s.add("skipped", skipped)
            return "\n".join(parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error checking staleness: {e}"


def _format_as_tree(
    rows: _builtins_list[Any],
    *,
    topic: str | None,
    depth: int,
) -> str:
    """Format list rows as a tree hierarchy.

    Row schema: (id, topic, category, tags, relevance, access_count,
                 created_at, content_len, meta).
    """
    # Strip common prefix if topic filter provided with trailing /
    prefix = ""
    if topic and topic.endswith("/"):
        prefix = topic

    # Build nested tree dict; leaf nodes store metadata tuple
    tree_dict: dict[str, Any] = {}
    for r in rows:
        mem_id, mem_topic, category, tags_raw, relevance = r[0], r[1], r[2], r[3], r[4]
        content_len, meta_json = r[7], r[8]
        rel_topic = (
            mem_topic[len(prefix) :]
            if prefix and mem_topic.startswith(prefix)
            else mem_topic
        )
        parts = rel_topic.split("/")
        node = tree_dict
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            elif not isinstance(node[part], dict):
                # Existing leaf becomes a dict; preserve leaf data under ""
                leaf_data = node[part]
                node[part] = {"": leaf_data}
            node = node[part]
        # Store leaf with metadata tuple
        leaf_name = parts[-1]
        tags_list = _deserialize_tags(tags_raw)
        row_meta = json.loads(meta_json) if meta_json else {}
        section_count = int(row_meta.get("section_count", 0))
        node[leaf_name] = (
            "_leaf_",
            mem_id,
            category,
            tags_list,
            content_len,
            relevance,
            section_count,
        )

    # Render tree
    lines: _builtins_list[str] = []
    total = len(rows)
    header = f"{prefix}" if prefix else "(all)"
    lines.append(f"{header}  (mem_count={total})")
    _render_tree(tree_dict, lines, prefix="", max_depth=depth)

    return "\n".join(lines)


def _format_entry_meta(
    *,
    mem_id: str,
    content_len: int,
    section_count: int,
    relevance: int,
    category: str,
    tags_list: _builtins_list[str],
) -> str:
    """Format parenthesised metadata for list and tree entries.

    Attribute order: id, len, sec, rel, category, tags.
    Hide-if-default: sec hidden when 0, rel hidden when 5, tags hidden when empty.
    """
    meta_parts = [f"id={mem_id[:8]}", f"len={content_len}"]
    if section_count > 0:
        meta_parts.append(f"sec={section_count}")
    if relevance != 5:
        meta_parts.append(f"rel={relevance}")
    meta_parts.append(f"category={category}")
    if tags_list:
        meta_parts.append(f"tags={'|'.join(tags_list)}")
    return f"({' '.join(meta_parts)})"


def _render_tree(
    node: dict[str, Any],
    lines: _builtins_list[str],
    prefix: str,
    max_depth: int,
    current_depth: int = 1,
) -> None:
    """Recursively render a tree dict into indented lines with box-drawing connectors."""
    entries = sorted(node)
    for idx, name in enumerate(entries):
        is_last = idx == len(entries) - 1
        connector = "└── " if is_last else "├── "
        extension = "    " if is_last else "│   "
        value = node[name]
        if isinstance(value, tuple) and value and value[0] == "_leaf_":
            # Leaf node with metadata
            _, mem_id, category, tags_list, content_len, relevance, section_count = (
                value
            )
            meta = _format_entry_meta(
                mem_id=mem_id,
                content_len=content_len,
                section_count=section_count,
                relevance=relevance,
                category=category,
                tags_list=tags_list,
            )
            lines.append(f"{prefix}{connector}{name}  {meta}")
        elif isinstance(value, dict):
            # Directory node - count leaves
            leaf_count = _count_leaves(value)
            lines.append(f"{prefix}{connector}{name}/  (mem_count={leaf_count})")
            if not (max_depth > 0 and current_depth >= max_depth):
                _render_tree(
                    value,
                    lines,
                    prefix=prefix + extension,
                    max_depth=max_depth,
                    current_depth=current_depth + 1,
                )


def _count_leaves(node: dict[str, Any] | tuple[Any, ...]) -> int:
    """Count leaf nodes (memories) in a tree dict or tuple leaf."""
    if isinstance(node, tuple):
        return 1
    if not node:
        return 0
    return sum(_count_leaves(v) for v in node.values())


__all__ = [
    "_count_leaves",
    "_format_as_tree",
    "_format_entry_meta",
    "_render_tree",
    "stale",
]
