"""Memory export and load (YAML I/O)."""
from __future__ import annotations

import json
import uuid
from typing import Any

from otpack import LogSpan

from .config import _validate_file_path
from .content import _content_hash, _topic_filter
from .db import (
    _deserialize_meta,
    _deserialize_tags,
    _get_connection,
    _serialize_embedding,
    _serialize_meta,
    _serialize_tags,
    _use_connection,
)
from .embedding import _maybe_embed


def export(
    *,
    topic: str | None = None,
    output: str | None = None,
) -> str:
    """Export memories to YAML format.

    Args:
        topic: Optional topic prefix filter
        output: Output file path (default: prints to stdout)

    Returns:
        Exported content or file path confirmation.

    Example:
        mem.export(output="memories.yaml")
        mem.export(topic="projects/onetool/")
    """
    with LogSpan(span="mem.export", topic=topic) as s:
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
                return "No memories to export"

            s.add("memoryCount", len(rows))

            content = _export_yaml(rows)

            if output:
                validated_path, error = _validate_file_path(output, must_exist=False)
                if error:
                    return f"Error: {error}"
                assert validated_path is not None
                validated_path.parent.mkdir(parents=True, exist_ok=True)
                validated_path.write_text(content, encoding="utf-8")
                return f"Exported {len(rows)} memories to {validated_path}"

            return content

        except Exception as e:
            s.add("error", str(e))
            return f"Error exporting memories: {e}"


def _export_yaml(rows: list[tuple]) -> str:
    """Export memories to YAML format."""
    lines = ["memories:"]
    for r in rows:
        tags_str = "[" + ", ".join(f'"{t}"' for t in _deserialize_tags(r[4])) + "]"
        # Use block scalar |- for content to safely handle newlines and special chars
        content_lines = r[2].split("\n")
        indented_content = "\n".join(f"      {line}" for line in content_lines)
        meta_dict = _deserialize_meta(r[9])
        meta_json = json.dumps(meta_dict) if meta_dict else "{}"
        lines.extend([
            f"  - id: \"{r[0]}\"",
            f"    topic: \"{r[1]}\"",
            "    content: |-",
            indented_content,
            f"    category: \"{r[3]}\"",
            f"    tags: {tags_str}",
            f"    relevance: {r[5]}",
            f"    access_count: {r[6]}",
            f"    created_at: \"{r[7]}\"",
            f"    updated_at: \"{r[8]}\"",
            f"    meta: '{meta_json}'",
            "",
        ])
    return "\n".join(lines)


def load(
    *,
    file: str,
) -> str:
    """Import memories from a YAML file. Skips duplicates by content hash.

    Does not generate embeddings. Use mem.reindex() after import if needed.

    Args:
        file: Path to YAML file to import

    Returns:
        Import summary.

    Example:
        mem.load(file="memories.yaml")
    """
    with LogSpan(span="mem.load", file=file) as s:
        try:
            try:
                import yaml
            except ImportError as e:
                raise ImportError(
                    "pyyaml is required for YAML import. Install with: pip install pyyaml"
                ) from e

            validated_path, error = _validate_file_path(file, must_exist=True)
            if error:
                return f"Error: {error}"
            assert validated_path is not None

            data = yaml.safe_load(validated_path.read_text(encoding="utf-8"))
            if not data or "memories" not in data:
                return "Error: Invalid YAML format - expected 'memories' key"

            memories = data["memories"]
            imported = 0
            skipped = 0
            malformed = 0

            with _use_connection() as conn:
                for mem_data in memories:
                    topic = mem_data.get("topic", "")
                    content = mem_data.get("content", "")
                    if not topic or not content:
                        malformed += 1
                        continue

                    content_hash = _content_hash(content)

                    # Check for existing
                    existing = conn.execute(
                        "SELECT id FROM memories WHERE topic = ? AND content_hash = ?",
                        [topic, content_hash],
                    ).fetchone()

                    if existing:
                        skipped += 1
                        continue

                    memory_id = mem_data.get("id", str(uuid.uuid4()))
                    category = mem_data.get("category", "note")
                    mem_tags = mem_data.get("tags", [])
                    relevance = max(1, min(10, int(mem_data.get("relevance", 5))))

                    # Restore meta if present
                    meta_raw = mem_data.get("meta", "{}")
                    if isinstance(meta_raw, dict):
                        meta_str = _serialize_meta(meta_raw)
                    elif isinstance(meta_raw, str):
                        # Validate it's valid JSON, normalise
                        meta_str = _serialize_meta(_deserialize_meta(meta_raw))
                    else:
                        meta_str = "{}"

                    embedding = _maybe_embed(memory_id, content)

                    conn.execute(
                        """
                        INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding, meta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [memory_id, topic, content, content_hash, category,
                         _serialize_tags(mem_tags), relevance, _serialize_embedding(embedding), meta_str],
                    )
                    imported += 1

                conn.commit()
            s.add("imported", imported)
            s.add("skipped", skipped)
            s.add("malformed", malformed)
            msg = f"Imported {imported} memories, skipped {skipped} duplicates"
            if malformed:
                msg += f", {malformed} malformed (missing topic or content)"
            return msg

        except ImportError as e:
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error importing memories: {e}"


__all__ = ["_export_yaml", "export", "load"]
