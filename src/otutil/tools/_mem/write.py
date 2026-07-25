"""Memory write functions."""

from __future__ import annotations

import uuid
from pathlib import Path

from otpack import LogSpan

from .config import _validate_file_path
from .content import (
    _content_hash,
    _encode_sections,
    _parse_headings,
    _redact,
    _validate_category,
    _validate_tags,
)
from .db import (
    _serialize_embedding,
    _serialize_meta,
    _serialize_tags,
    _sync_vec_index,
    _use_connection,
)
from .embedding import _embed_now, _enqueue_after_commit


def write(
    *,
    topic: str,
    content: str | None = None,
    category: str = "note",
    tags: list[str] | None = None,
    relevance: int = 5,
    file: str | None = None,
    toc: bool = True,
) -> str:
    """Store a memory with topic, content, and optional metadata.

    Content is deduplicated by SHA-256 hash within the same topic.
    Secrets and PII are automatically redacted before storage.

    Provide exactly one of content or file.

    Args:
        topic: Topic path using / separator (e.g., "projects/onetool/rules")
        content: Memory content text
        category: One of: rule, context, decision, mistake, discovery, note
        tags: Optional list of tags for categorisation
        relevance: Importance score 1-10 (default: 5)
        file: Path to file to read content from (mutually exclusive with content)
        toc: Parse markdown headings and store section index in meta (default: True); pass False to skip

    Returns:
        Confirmation message with memory ID, or error message.

    Example:
        mem.write(topic="projects/onetool/rules", content="Always use keyword-only args")
        mem.write(topic="learnings/python", content="Use __future__ annotations", category="discovery")
        mem.write(topic="config", file="~/.onetool/config/onetool.yaml")
        mem.write(topic="spec", file="spec.md", toc=False)
    """
    with LogSpan(span="mem.write", topic=topic, category=category) as s:
        try:
            if content is not None and file is not None:
                return "Error: Provide content or file, not both"
            if content is None and file is None:
                return "Error: Provide content or file"

            _validate_category(category)
            if not 1 <= relevance <= 10:
                return "Error: relevance must be between 1 and 10"
            validated_tags = _validate_tags(tags)

            meta: dict[str, str] = {}
            validated_path: Path | None = None

            if file:
                validated_path, error = _validate_file_path(file, must_exist=True)
                if error:
                    s.add("error", "path_validation")
                    return f"Error: {error}"
                assert validated_path is not None
                file_stat = validated_path.stat()
                if file_stat.st_size > 1_000_000:
                    s.add("error", "file_too_large")
                    return f"Error: File too large ({file_stat.st_size / 1_000_000:.1f}MB). Max 1MB for memory content."
                content = validated_path.read_text(encoding="utf-8")

                # Auto-populate file metadata
                meta["source"] = str(validated_path.resolve())
                meta["source_mtime"] = str(file_stat.st_mtime)
                meta["content_type"] = validated_path.suffix.lstrip(".") or "txt"

            assert content is not None  # guaranteed by file read or early return
            content = _redact(content)
            content_hash = _content_hash(content)

            # Parse TOC if requested
            if toc:
                headings = _parse_headings(content)
                if headings:
                    meta["sections"] = _encode_sections(headings)
                    meta["section_count"] = str(len(headings))

            # Check for duplicate content in same topic (before paying for an embedding)
            with _use_connection() as conn:
                existing = conn.execute(
                    "SELECT id FROM memories WHERE topic = ? AND content_hash = ?",
                    [topic, content_hash],
                ).fetchone()

            if existing:
                s.add("duplicate", True)
                return f"Duplicate: Memory with same content already exists in topic '{topic}' (id: {existing[0]})"

            memory_id = str(uuid.uuid4())
            # Embedding API call happens outside the DB lock
            embedding = _embed_now(content)

            with _use_connection() as conn:
                # Re-check: another writer may have inserted while we embedded
                existing = conn.execute(
                    "SELECT id FROM memories WHERE topic = ? AND content_hash = ?",
                    [topic, content_hash],
                ).fetchone()
                if existing:
                    s.add("duplicate", True)
                    return f"Duplicate: Memory with same content already exists in topic '{topic}' (id: {existing[0]})"

                conn.execute(
                    """
                    INSERT INTO memories (id, topic, content, content_hash, category, tags, relevance, embedding, meta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        memory_id,
                        topic,
                        content,
                        content_hash,
                        category,
                        _serialize_tags(validated_tags),
                        relevance,
                        _serialize_embedding(embedding),
                        _serialize_meta(meta),
                    ],
                )
                if embedding is not None:
                    _sync_vec_index(conn, memory_id, embedding)
                conn.commit()
            _enqueue_after_commit(memory_id)

            s.add("memoryId", memory_id)
            s.add("contentLen", len(content))
            toc_msg = (
                f" (toc: {meta.get('section_count', '0')} sections)" if toc else ""
            )
            return f"Stored memory {memory_id} in topic '{topic}'{toc_msg}"

        except ValueError as e:
            s.add("error", "validation")
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error writing memory: {e}"


def write_batch(
    *,
    topic: str,
    glob_pattern: str,
    category: str = "note",
    tags: list[str] | None = None,
    relevance: int = 5,
    toc: bool = True,
) -> str:
    """Store multiple memories from files matching a glob pattern.

    Each file becomes a separate memory under the given topic,
    preserving the directory structure relative to the glob root.

    Args:
        topic: Base topic path (relative file path appended as subtopic)
        glob_pattern: Glob pattern to match files (e.g., "docs/**/*.md")
        category: Category for all memories
        tags: Tags applied to all memories
        relevance: Relevance score for all memories
        toc: Parse markdown headings and store section index per file (default: True); pass False to skip

    Returns:
        Summary of stored memories.

    Example:
        mem.write_batch(topic="docs", glob_pattern="docs/**/*.md", category="context")
        mem.write_batch(topic="specs", glob_pattern="specs/**/*.md", toc=False)
    """
    from ot.paths import get_effective_cwd

    with LogSpan(span="mem.write_batch", topic=topic, glob=glob_pattern) as s:
        try:
            _validate_category(category)

            base = get_effective_cwd()
            files = sorted(base.glob(glob_pattern))

            if not files:
                s.add("fileCount", 0)
                return f"No files matched pattern: {glob_pattern}"

            # Determine glob root: the non-wildcard prefix of the pattern
            glob_root = base
            for part in Path(glob_pattern).parts:
                if any(c in part for c in ("*", "?", "[")):
                    break
                glob_root = glob_root / part

            stored = 0
            skipped = 0
            errors = []

            for f in files:
                if not f.is_file():
                    continue

                # Preserve directory structure relative to glob root
                rel = f.relative_to(glob_root)
                subtopic = f"{topic}/{rel.as_posix()}"
                result = write(
                    topic=subtopic,
                    file=str(f),
                    category=category,
                    tags=tags,
                    relevance=relevance,
                    toc=toc,
                )
                if result.startswith("Stored"):
                    stored += 1
                elif result.startswith("Duplicate"):
                    skipped += 1
                else:
                    errors.append(f"{f.name}: {result}")

            s.add("stored", stored)
            s.add("skipped", skipped)
            s.add("errors", len(errors))

            parts = [
                f"Processed {stored + skipped + len(errors)} files: {stored} stored, {skipped} duplicates"
            ]
            if errors:
                parts.append(f", {len(errors)} errors")
                for err in errors[:5]:
                    parts.append(f"\n  - {err}")
            return "".join(parts)

        except ValueError as e:
            s.add("error", "validation")
            return f"Error: {e}"
        except Exception as e:
            s.add("error", str(e))
            return f"Error in batch write: {e}"


__all__ = ["write", "write_batch"]
