"""Memory snapshot and restore (directory-based snapshots)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from otpack import LogSpan

from .config import _validate_file_path
from .content import (
    _content_hash,
    _redact,
    _topic_filter,
    _validate_category,
    _validate_tags,
)
from .db import (
    _deserialize_meta,
    _deserialize_tags,
    _get_connection,
    _serialize_embedding,
    _serialize_meta,
    _serialize_tags,
    _sync_vec_index,
    _use_connection,
)
from .embedding import _embed_now, _enqueue_after_commit

if TYPE_CHECKING:
    from pathlib import Path


def _resolve_member_path(base: Path, rel: str) -> tuple[Path | None, str | None]:
    """Resolve a topic-derived relative path inside a snapshot directory.

    Rejects absolute paths and `..` traversal in the (untrusted) relative
    path, then validates the final joined path against allowed_file_dirs
    and exclude_file_patterns. Returns (path, error); path is None on error.
    """
    pure = PurePosixPath(rel)
    parts = [seg for seg in pure.parts if seg not in ("", ".", "/")]
    if pure.is_absolute() or not parts or ".." in parts:
        return None, f"unsafe path '{rel}' (absolute or traversal)"
    validated, error = _validate_file_path(str(base.joinpath(*parts)), must_exist=False)
    if error:
        return None, error
    return validated, None


def _strip_topic_prefix(mem_topic: str, prefix: str | None) -> str:
    """Return mem_topic relative to a topic-filter prefix.

    A topic under `prefix` keeps the remainder; a topic exactly equal to the
    prefix (without its trailing slash) keeps only its final segment.
    """
    if prefix and mem_topic.startswith(prefix):
        return mem_topic[len(prefix) :]
    if prefix and mem_topic == prefix.rstrip("/"):
        return mem_topic.rsplit("/", 1)[-1]
    return mem_topic


def snapshot(
    *,
    output: str,
    topic: str | None = None,
    ext: str = "",
    on_conflict: str = "skip",
) -> str:
    """Write memories to a directory as individual files with an index.yaml.

    Creates one file per memory record with an index.yaml containing metadata.
    Round-trips losslessly with `mem.restore()`.

    Args:
        output: Output directory path
        topic: Topic prefix filter (all memories if omitted)
        ext: File extension appended to topic for content files (default: "" — topic is the file path)
        on_conflict: "skip" (default) or "overwrite" for existing files

    Returns:
        Summary of snapshot results.

    Example:
        mem.snapshot(output="backup/consult", topic="consult/")
        mem.snapshot(output="backup/all")
        mem.snapshot(output="backup/config", topic="config/", ext=".yaml")
    """
    if on_conflict not in ("skip", "overwrite"):
        return f"Error: on_conflict must be 'skip' or 'overwrite', got '{on_conflict}'"

    with LogSpan(span="mem.snapshot", output=output, topic=topic) as s:
        try:
            conn = _get_connection()

            sql = """
                SELECT id, topic, content, category, tags, relevance, access_count,
                       created_at, updated_at, meta
                FROM memories
                WHERE 1=1
            """
            params: list[Any] = []

            topic_sql, topic_params = _topic_filter(topic)
            sql += topic_sql
            params.extend(topic_params)

            sql += " ORDER BY topic, created_at"

            rows = conn.execute(sql, params).fetchall()

            if not rows:
                return "No memories to snapshot"

            # Determine topic prefix to strip
            strip_prefix = ""
            if topic and topic.endswith("/"):
                strip_prefix = topic

            validated_path, error = _validate_file_path(output, must_exist=False)
            if error:
                return f"Error: {error}"
            assert validated_path is not None
            validated_path.mkdir(parents=True, exist_ok=True)

            written = 0
            skipped = 0
            index_entries = []
            errors: list[str] = []

            for r in rows:
                _id, mem_topic, content, category, raw_tags, relevance = (
                    r[0],
                    r[1],
                    r[2],
                    r[3],
                    r[4],
                    r[5],
                )
                tags = _deserialize_tags(raw_tags)
                raw_meta = _deserialize_meta(r[9])

                # Compute relative file path
                rel_topic = _strip_topic_prefix(mem_topic, strip_prefix)

                file_rel = rel_topic + ext
                file_path, path_error = _resolve_member_path(validated_path, file_rel)
                if file_path is None:
                    errors.append(f"{mem_topic}: {path_error}")
                    continue

                if file_path.exists() and on_conflict == "skip":
                    skipped += 1
                    index_entries.append(
                        {
                            "topic": mem_topic,
                            "file": file_rel,
                            "category": category,
                            "tags": tags,
                            "relevance": relevance,
                            "meta": raw_meta,
                        }
                    )
                    continue

                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                written += 1

                index_entries.append(
                    {
                        "topic": mem_topic,
                        "file": file_rel,
                        "category": category,
                        "tags": tags,
                        "relevance": relevance,
                        "meta": raw_meta,
                    }
                )

            # Write index.yaml
            try:
                import yaml
            except ImportError as e:
                raise ImportError(
                    "pyyaml is required for YAML snapshot. Install with: pip install pyyaml"
                ) from e

            now_str = datetime.now(UTC).isoformat()
            index_data = {
                "snapshot": {
                    "created_at": now_str,
                    "topic_filter": topic,
                    "ext": ext,
                    "count": len(index_entries),
                },
                "memories": [
                    {
                        "topic": e["topic"],
                        "file": e["file"],
                        "category": e["category"],
                        "tags": e["tags"],
                        "relevance": e["relevance"],
                        "meta": e.get("meta", {}),
                    }
                    for e in index_entries
                ],
            }

            index_path = validated_path / "index.yaml"
            index_path.write_text(
                yaml.dump(index_data, default_flow_style=False, allow_unicode=True),
                encoding="utf-8",
            )

            s.add("written", written)
            s.add("skipped", skipped)
            s.add("total", len(index_entries))
            msg = f"Snapshot {len(index_entries)} memories to {validated_path} ({written} written, {skipped} skipped)"
            if errors:
                s.add("errors", len(errors))
                msg += f", {len(errors)} errors"
                for err in errors[:5]:
                    msg += f"\n  - {err}"
            return msg

        except Exception as e:
            s.add("error", str(e))
            return f"Error creating snapshot: {e}"


def restore(
    *,
    input: str,
    topic: str | None = None,
    overwrite: bool = False,
) -> str:
    """Restore memories from a snapshot directory (created by `mem.snapshot`).

    Reads index.yaml and content files, recreating memories with full metadata.
    Applies the same invariants as mem.write(): content is redacted and
    category/tags are validated (invalid entries are reported and skipped).

    Args:
        input: Input directory path (must contain index.yaml)
        topic: Override base topic (otherwise uses topics from index)
        overwrite: If True, replace existing memories with same topic+hash
            (their history entries are removed along with the old row)

    Returns:
        Restore summary.

    Example:
        mem.restore(input="backup/consult", topic="consult")
        mem.restore(input="backup/consult", topic="consult", overwrite=True)
    """
    with LogSpan(span="mem.restore", input=input) as s:
        try:
            try:
                import yaml
            except ImportError as e:
                raise ImportError(
                    "pyyaml is required for YAML import. Install with: pip install pyyaml"
                ) from e

            validated_path, error = _validate_file_path(input, must_exist=True)
            if error:
                return f"Error: {error}"
            assert validated_path is not None

            if not validated_path.is_dir():
                return f"Error: '{input}' is not a directory"

            index_path = validated_path / "index.yaml"
            if not index_path.exists():
                return f"Error: index.yaml not found in '{input}'"

            data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
            if not data or "memories" not in data:
                return "Error: Invalid index.yaml - expected 'memories' key"

            # Determine topic remapping
            snapshot_meta = data.get("snapshot", {})
            original_filter = snapshot_meta.get("topic_filter")

            memories = data["memories"]
            skipped = 0
            errors = []
            pending: list[
                tuple[str, str, str, str, str, list[str], int, str, str | None]
            ] = []

            with _use_connection() as conn:
                for entry in memories:
                    mem_topic = entry.get("topic", "")
                    file_rel = entry.get("file", "")
                    category = entry.get("category", "note")
                    tags = entry.get("tags", [])
                    relevance = max(1, min(10, int(entry.get("relevance", 5))))

                    # Restore meta if present
                    meta_raw = entry.get("meta", {})
                    if isinstance(meta_raw, dict):
                        meta_str = _serialize_meta(meta_raw)
                    elif isinstance(meta_raw, str):
                        meta_str = _serialize_meta(_deserialize_meta(meta_raw))
                    else:
                        meta_str = "{}"

                    if not mem_topic or not file_rel:
                        errors.append("Missing topic or file in index entry")
                        continue

                    try:
                        # Apply the same invariants as mem.write()
                        _validate_category(category)
                        tags = _validate_tags(tags)
                    except ValueError as e:
                        errors.append(f"{mem_topic}: {e}")
                        continue

                    # Remap topic if override provided
                    if topic is not None:
                        # Strip original filter prefix, prepend new topic
                        rel = _strip_topic_prefix(mem_topic, original_filter)
                        mem_topic = f"{topic}/{rel}" if rel else topic

                    # Read content file (index paths are untrusted)
                    content_path, path_error = _resolve_member_path(
                        validated_path, file_rel
                    )
                    if content_path is None:
                        errors.append(f"{file_rel}: {path_error}")
                        continue
                    if not content_path.exists():
                        errors.append(f"File not found: {file_rel}")
                        continue

                    content = _redact(content_path.read_text(encoding="utf-8"))
                    content_hash = _content_hash(content)

                    # Check for existing
                    existing = conn.execute(
                        "SELECT id FROM memories WHERE topic = ? AND content_hash = ?",
                        [mem_topic, content_hash],
                    ).fetchone()

                    if existing and not overwrite:
                        skipped += 1
                        continue

                    pending.append(
                        (
                            str(uuid.uuid4()),
                            mem_topic,
                            content,
                            content_hash,
                            category,
                            tags,
                            relevance,
                            meta_str,
                            existing[0] if existing else None,
                        )
                    )

            # Embedding API calls happen outside the DB lock
            with_embeddings = [(entry, _embed_now(entry[2])) for entry in pending]

            with _use_connection() as conn:
                for entry, embedding in with_embeddings:
                    (
                        memory_id,
                        mem_topic,
                        content,
                        content_hash,
                        category,
                        tags,
                        relevance,
                        meta_str,
                        existing_id,
                    ) = entry
                    if existing_id is not None:
                        # Overwrite: remove the old row and its history entries
                        conn.execute("DELETE FROM memories WHERE id = ?", [existing_id])
                        conn.execute(
                            "DELETE FROM memory_history WHERE memory_id = ?",
                            [existing_id],
                        )

                    conn.execute(
                        """
                        INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding, meta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            memory_id,
                            mem_topic,
                            content,
                            content_hash,
                            category,
                            _serialize_tags(tags),
                            relevance,
                            _serialize_embedding(embedding),
                            meta_str,
                        ],
                    )
                    if embedding is not None:
                        _sync_vec_index(conn, memory_id, embedding)
                conn.commit()
            for entry, _embedding in with_embeddings:
                _enqueue_after_commit(entry[0])

            restored = len(with_embeddings)
            s.add("restored", restored)
            s.add("skipped", skipped)
            s.add("errors", len(errors))
            parts = [f"Restored {restored} memories, skipped {skipped}"]
            if errors:
                parts.append(f", {len(errors)} errors")
                for err in errors[:5]:
                    parts.append(f"\n  - {err}")
            return "".join(parts)

        except ImportError as e:
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error restoring snapshot: {e}"


__all__ = ["restore", "snapshot"]
