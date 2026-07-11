"""Memory dump and load (YAML I/O)."""
from __future__ import annotations

import uuid
from typing import Any

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
    _use_connection,
)
from .embedding import _embed_now, _enqueue_after_commit


def dump(
    *,
    topic: str | None = None,
    output: str | None = None,
) -> str:
    """Dump memories to YAML format.

    Args:
        topic: Optional topic prefix filter
        output: Output file path (default: prints to stdout)

    Returns:
        Dumped content or file path confirmation.

    Example:
        mem.dump(output="memories.yaml")
        mem.dump(topic="projects/onetool/")
    """
    with LogSpan(span="mem.dump", topic=topic) as s:
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
                return "No memories to dump"

            s.add("memoryCount", len(rows))

            content = _export_yaml(rows)

            if output:
                validated_path, error = _validate_file_path(output, must_exist=False)
                if error:
                    return f"Error: {error}"
                assert validated_path is not None
                validated_path.parent.mkdir(parents=True, exist_ok=True)
                validated_path.write_text(content, encoding="utf-8")
                return f"Dumped {len(rows)} memories to {validated_path}"

            return content

        except Exception as e:
            s.add("error", str(e))
            return f"Error dumping memories: {e}"


def _export_yaml(rows: list[tuple[Any, ...]]) -> str:
    """Export memories to YAML via yaml.safe_dump (round-trips with load()).

    Multiline content is emitted as a literal block scalar for readability;
    everything else uses standard YAML quoting so quotes and special
    characters survive the dump/load round-trip.
    """
    try:
        import yaml
    except ImportError as e:
        raise ImportError(
            "pyyaml is required for YAML dump. Install with: pip install pyyaml"
        ) from e

    class _Dumper(yaml.SafeDumper):
        pass

    def _repr_str(dumper: Any, data: str) -> Any:
        style = "|" if "\n" in data else None
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)

    _Dumper.add_representer(str, _repr_str)

    memories = [
        {
            "id": r[0],
            "topic": r[1],
            "content": r[2],
            "category": r[3],
            "tags": _deserialize_tags(r[4]),
            "relevance": r[5],
            "access_count": r[6],
            "created_at": r[7],
            "updated_at": r[8],
            "meta": _deserialize_meta(r[9]),
        }
        for r in rows
    ]
    return yaml.dump(
        {"memories": memories},
        Dumper=_Dumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def load(
    *,
    file: str,
) -> str:
    """Import memories from a YAML file. Skips duplicates by content hash.

    Applies the same invariants as mem.write(): content is redacted and
    category/tags are validated (invalid entries are reported and skipped).
    Embeddings follow the embeddings config (sync or background); use
    mem.reindex() to backfill if embeddings were disabled during import.

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
            skipped = 0
            malformed = 0
            errors: list[str] = []
            pending: list[tuple[str, str, str, str, str, list[str], int, str]] = []

            with _use_connection() as conn:
                for mem_data in memories:
                    topic = mem_data.get("topic", "")
                    content = mem_data.get("content", "")
                    if not topic or not content:
                        malformed += 1
                        continue

                    category = mem_data.get("category", "note")
                    mem_tags = mem_data.get("tags", [])
                    try:
                        # Apply the same invariants as mem.write()
                        _validate_category(category)
                        mem_tags = _validate_tags(mem_tags)
                    except ValueError as e:
                        malformed += 1
                        errors.append(f"{topic}: {e}")
                        continue

                    content = _redact(content)
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

                    pending.append((memory_id, topic, content, content_hash,
                                    category, mem_tags, relevance, meta_str))

            # Embedding API calls happen outside the DB lock
            with_embeddings = [(entry, _embed_now(entry[2])) for entry in pending]

            with _use_connection() as conn:
                for entry, embedding in with_embeddings:
                    memory_id, topic, content, content_hash, category, mem_tags, relevance, meta_str = entry
                    conn.execute(
                        """
                        INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding, meta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [memory_id, topic, content, content_hash, category,
                         _serialize_tags(mem_tags), relevance, _serialize_embedding(embedding), meta_str],
                    )
                conn.commit()
            for entry, _embedding in with_embeddings:
                _enqueue_after_commit(entry[0])

            imported = len(with_embeddings)
            s.add("imported", imported)
            s.add("skipped", skipped)
            s.add("malformed", malformed)
            msg = f"Imported {imported} memories, skipped {skipped} duplicates"
            if malformed:
                msg += f", {malformed} malformed (missing topic/content or invalid category/tags)"
            for err in errors[:5]:
                msg += f"\n  - {err}"
            return msg

        except ImportError as e:
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error importing memories: {e}"


__all__ = ["_export_yaml", "dump", "load"]
