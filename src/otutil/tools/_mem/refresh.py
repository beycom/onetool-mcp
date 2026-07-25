"""File-backed memory refresh."""

from __future__ import annotations

import builtins
from pathlib import Path

from otpack import LogSpan

from .content import _check_staleness, _redact, _topic_filter
from .db import _deserialize_meta, _use_connection
from .embedding import _embed_now, _enqueue_after_commit
from .mutations import _apply_memory_update

_builtins_list = builtins.list


def refresh(
    *,
    topic: str | None = None,
    dry_run: bool = True,
) -> str:
    """Re-read source files for stale file-backed memories.

    Finds memories whose source files have changed since storage and updates
    their content. Preserves history (same as update). Default is dry_run=True
    for safety.

    Args:
        topic: Topic prefix to filter. If omitted, checks all memories.
        dry_run: If True (default), report what would change without modifying.

    Returns:
        Summary of refreshed, skipped, and unchanged memories.

    Example:
        mem.refresh(topic="proj/onetool-mcp/dev/")
        mem.refresh(topic="proj/onetool-mcp/dev/", dry_run=False)
    """
    mode_label = "dry run" if dry_run else "apply"
    with LogSpan(span="mem.refresh", topic=topic or "(all)", dryRun=dry_run) as s:
        try:
            with _use_connection() as conn:
                sql = (
                    "SELECT id, topic, content, content_hash, meta "
                    "FROM memories WHERE 1=1"
                )
                topic_sql, params = _topic_filter(topic)
                sql += topic_sql
                sql += " ORDER BY topic"
                rows = conn.execute(sql, params).fetchall()

            if not rows:
                s.add("found", 0)
                return "No memories found" + (f" under '{topic}'" if topic else "")

            fresh_count = 0
            stale_entries: _builtins_list[
                tuple[str, str, str, str, dict[str, str], str]
            ] = []
            missing_entries: _builtins_list[str] = []
            skipped = 0

            for mem_id, mem_topic, old_content, old_content_hash, raw_meta in rows:
                meta = _deserialize_meta(raw_meta)
                status = _check_staleness(meta)
                if status == "fresh":
                    fresh_count += 1
                elif status == "stale":
                    source_path = meta["source"]
                    stale_entries.append(
                        (
                            mem_id,
                            mem_topic,
                            old_content,
                            old_content_hash,
                            meta,
                            source_path,
                        )
                    )
                elif status == "missing":
                    missing_entries.append(mem_topic)
                else:
                    skipped += 1

            total_checked = fresh_count + len(stale_entries) + len(missing_entries)
            if total_checked == 0:
                s.add("skipped", skipped)
                return "No file-backed memories found" + (
                    f" under '{topic}'" if topic else ""
                )

            # Build report
            scope = f' for "{topic}"' if topic else ""
            parts = [f"Refresh ({mode_label}){scope}:"]

            if stale_entries:
                verb = "would update" if dry_run else "updated"
                parts.append(f"  {len(stale_entries)} stale - {verb}:")
                for (
                    mem_id,
                    mem_topic,
                    old_content,
                    old_content_hash,
                    meta,
                    source_path,
                ) in stale_entries:
                    p = Path(source_path)
                    if dry_run:
                        new_size = p.stat().st_size if p.exists() else 0
                        parts.append(
                            f"    - {mem_topic} ({len(old_content)} -> {new_size} chars)"
                        )
                    else:
                        # Actually refresh
                        try:
                            new_content = p.read_text(encoding="utf-8")
                        except OSError:
                            parts.append(
                                f"    - {mem_topic} (skipped: source file disappeared)"
                            )
                            continue
                        if len(new_content) > 1_000_000:
                            parts.append(f"    - {mem_topic} (skipped: file too large)")
                            continue

                        new_content = _redact(new_content)

                        # Update source_mtime
                        meta["source_mtime"] = str(p.stat().st_mtime)

                        # Embedding API call happens outside the DB lock
                        embedding = _embed_now(new_content)

                        with _use_connection() as conn:
                            _apply_memory_update(
                                conn,
                                memory_id=mem_id,
                                old_content=old_content,
                                old_content_hash=old_content_hash,
                                new_content=new_content,
                                meta=meta,
                                embedding=embedding,
                            )
                        _enqueue_after_commit(mem_id)

                        parts.append(
                            f"    - {mem_topic} ({len(old_content)} -> {len(new_content)} chars)"
                        )

            if missing_entries:
                parts.append(f"  {len(missing_entries)} missing - skipped:")
                for m_topic in missing_entries:
                    parts.append(f"    - {m_topic}")

            parts.append(f"  {fresh_count} fresh - no change")

            s.add("stale", len(stale_entries))
            s.add("missing", len(missing_entries))
            s.add("fresh", fresh_count)
            s.add("skipped", skipped)
            s.add("dryRun", dry_run)
            return "\n".join(parts)

        except Exception as e:
            s.add("error", str(e))
            return f"Error refreshing memories: {e}"


__all__ = ["refresh"]
