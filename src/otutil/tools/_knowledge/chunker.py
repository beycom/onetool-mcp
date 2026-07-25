"""Markdown file chunking for the knowledge pack.

Rules:
- If a file has ≤100 lines (after stripping frontmatter): store as a single chunk.
- If longer: split on level-1 and level-2 headings; each heading becomes a chunk.
- YAML frontmatter (---...---) is parsed via python-frontmatter and stored in meta.
- A .meta.yaml sidecar next to the .md file is also checked for url/source/crawled_at.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from otpack import parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+)$")
_EMPTY_IMG_ALT_RE = re.compile(r"!\[\]\(([^)]+)\)")


@dataclass
class Chunk:
    """A single indexable unit from a markdown file."""

    topic: str
    content: str
    content_hash: str
    source_path: str | None = (
        None  # canonical form before topic_roots stripping; None for manual writes
    )
    anchor: str = ""  # heading slug within the file; "" for page-level preamble
    meta: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    category: str = "reference"


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_sidecar(md_path: Path) -> dict[str, Any]:
    """Load .meta.yaml sidecar if it exists."""
    sidecar = md_path.with_suffix(".meta.yaml")
    if not sidecar.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
        # depth and url_base_path are ignored (computed at index time from canonical form)
        keys = (
            "url",
            "source",
            "crawled_at",
            "title",
            "description",
            "keywords",
            "category",
            "tags",
        )
        return {k: data[k] for k in keys if k in data}
    except Exception:
        return {}


def canonicalize(path: str, source_dir: str = "") -> str:
    """Convert a file path to a normalised topic form: segment/segment/segment.

    Handles three source formats:
    - Hierarchical paths (e.g. 'rhino/8mac/help/commands/move.md')
    - '::' flat files (e.g. 'rhino::8mac::help::commands::move.htm')
    - Any path with an optional source_dir prefix to strip

    Args:
        path: File path (relative or absolute).
        source_dir: Optional directory prefix to strip before canonicalising.

    Returns:
        Normalised topic string, e.g. 'commands/move'.
    """
    # Normalize path separators
    p = path.replace("\\", "/")

    # Strip source_dir prefix
    if source_dir:
        norm_source = source_dir.strip("/")
        if p.startswith(norm_source + "/"):
            p = p[len(norm_source) + 1 :]
        elif p == norm_source:
            p = ""

    # Strip leading slashes
    p = p.lstrip("/")

    # Replace '::' flat-file separator with '/'
    if "::" in p:
        p = p.replace("::", "/")

    # Split into segments and strip extension from the last segment
    parts = p.split("/") if p else []
    if parts and "." in parts[-1]:
        last = parts[-1]
        dot_idx = last.rfind(".")
        parts[-1] = last[:dot_idx]

    # Sanitise each segment: keep word chars, dots, hyphens
    segments = [re.sub(r"[^\w.\-]", "_", s) for s in parts if s]
    return "/".join(segments) or "index"


def strip_topic_roots(canonical: str, topic_roots: list[str]) -> str:
    """Strip the first matching topic_root prefix from a canonical topic.

    topic_roots entries may be full URLs or bare path prefixes.
    The root is canonicalised before matching.
    First match wins.

    Args:
        canonical: Canonical topic string.
        topic_roots: List of URL or path prefixes to strip.

    Returns:
        Stripped topic, or the original canonical if no root matches.
    """
    for root in topic_roots:
        if root.startswith(("http://", "https://")):
            from urllib.parse import urlparse

            parsed = urlparse(root)
            root_canonical = canonicalize(parsed.path)
        else:
            root_canonical = canonicalize(root)

        root_prefix = root_canonical.rstrip("/")
        if not root_prefix:
            continue
        if canonical == root_prefix:
            # Exact match — don't reduce to empty, return unchanged
            return canonical
        if canonical.startswith(root_prefix + "/"):
            return canonical[len(root_prefix) + 1 :]

    return canonical


def _make_topic(rel_path: Path, heading: str | None = None) -> str:
    """Build a topic string from relative file path and optional heading."""
    # Convert path to slash-separated string without extension
    parts = rel_path.with_suffix("").parts
    base = "/".join(parts)
    if heading:
        return f"{base}#{_slug(heading)}"
    return base


def chunk_file(
    path: Path, rel_path: Path, *, min_chunk_chars: int = 200
) -> list[Chunk]:
    """Chunk a markdown file into one or more Chunk objects.

    Args:
        path: Absolute path to the .md file.
        rel_path: Path relative to the indexed directory root (for topic naming).

    Returns:
        List of Chunk objects.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    fm_meta, body = parse_frontmatter(raw)
    body = _fill_img_alt(body)
    sidecar_meta = _load_sidecar(path)

    # Merge meta: sidecar overrides frontmatter for the shared keys
    meta: dict[str, Any] = {}
    for key in ("url", "source", "crawled_at"):
        if key in sidecar_meta:
            meta[key] = sidecar_meta[key]
        elif key in fm_meta:
            meta[key] = fm_meta[key]
    # Sidecar-only enrichment fields
    if "title" in sidecar_meta:
        meta["title"] = sidecar_meta["title"]
    # Also pick up any other frontmatter keys
    for key, val in fm_meta.items():
        if key not in meta:
            meta[key] = val

    # Sidecar category overrides the Chunk default
    category: str = sidecar_meta.get("category") or "reference"

    tags: list[str] = []
    if "tags" in fm_meta and isinstance(fm_meta["tags"], list):
        tags = [str(t) for t in fm_meta["tags"]]
    # Sidecar tags (config-level defaults written by _write_page) merged first
    if "tags" in sidecar_meta and isinstance(sidecar_meta["tags"], list):
        for t in sidecar_meta["tags"]:
            t_str = str(t)
            if t_str not in tags:
                tags.append(t_str)
    # Pre-populate tags from sidecar keywords (crawl4ai returns a comma-separated string)
    if "keywords" in sidecar_meta:
        kws = sidecar_meta["keywords"]
        if isinstance(kws, str):
            kws = [k.strip() for k in kws.split(",") if k.strip()]
        if isinstance(kws, list):
            for kw in kws:
                kw_str = str(kw)
                if kw_str not in tags:
                    tags.append(kw_str)

    # Topic derived from the file path via canonicalize
    # depth:<N> tag and chunk.meta["depth"] are set by the indexer after topic_roots stripping
    canonical = canonicalize(str(rel_path))
    base_topic = canonical
    source_path_val = canonical

    lines = body.split("\n")

    if len(lines) <= 100:
        # Single chunk
        content = body.strip()
        if not content:
            return []
        return [
            Chunk(
                topic=base_topic,
                content=content,
                content_hash=_content_hash(content),
                source_path=source_path_val,
                anchor="",
                meta=meta,
                tags=tags,
                category=category,
            )
        ]

    # Split on level-1/2 headings
    return _split_by_headings(
        body,
        base_topic,
        source_path_val,
        meta,
        tags,
        category=category,
        min_chunk_chars=min_chunk_chars,
    )


def _split_by_headings(
    body: str,
    base_topic: str,
    source_path_val: str,
    meta: dict[str, Any],
    tags: list[str],
    *,
    category: str = "reference",
    min_chunk_chars: int = 200,
) -> list[Chunk]:
    """Split content on H1/H2 headings into multiple chunks."""
    lines = body.split("\n")
    sections: list[tuple[str | None, int]] = []  # (heading_text, start_line_idx)

    in_fence = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            # `# comment` lines inside fenced code blocks are not headings
            continue
        m = _HEADING_RE.match(line)
        if m:
            sections.append((m.group(2).strip(), i))

    if not sections:
        # No headings found — treat as single chunk despite length
        content = body.strip()
        return [
            Chunk(
                topic=base_topic,
                content=content,
                content_hash=_content_hash(content),
                source_path=source_path_val,
                anchor="",
                meta=meta,
                tags=tags,
                category=category,
            )
        ]

    chunks: list[Chunk] = []
    # Preamble before first heading
    preamble_lines = lines[: sections[0][1]]
    preamble = "\n".join(preamble_lines).strip()
    if preamble:
        content = preamble
        chunks.append(
            Chunk(
                topic=base_topic,
                content=content,
                content_hash=_content_hash(content),
                source_path=source_path_val,
                anchor="",
                meta=dict(meta),
                tags=list(tags),
                category=category,
            )
        )

    for idx, (heading, start_idx) in enumerate(sections):
        end_idx = sections[idx + 1][1] if idx + 1 < len(sections) else len(lines)
        section_lines = lines[start_idx:end_idx]
        content = "\n".join(section_lines).strip()
        if not content:
            continue
        # Body is everything after the heading line
        body_text = "\n".join(section_lines[1:]).strip()
        # Skip heading-only stubs (no body content)
        if not body_text:
            continue
        # Merge short chunks into predecessor (or skip if no predecessor)
        if min_chunk_chars > 0 and len(body_text) < min_chunk_chars:
            if chunks:
                prev = chunks[-1]
                merged_content = prev.content + "\n\n" + content
                chunks[-1] = Chunk(
                    topic=prev.topic,
                    content=merged_content,
                    content_hash=_content_hash(merged_content),
                    source_path=prev.source_path,
                    anchor=prev.anchor,
                    meta=prev.meta,
                    tags=prev.tags,
                    category=prev.category,
                )
            # No predecessor → skip
            continue
        if heading is None:
            continue
        slug = _slug(heading)
        topic = f"{base_topic}#{slug}"
        chunk_meta = dict(meta)
        if heading:
            chunk_meta["heading"] = heading
        chunks.append(
            Chunk(
                topic=topic,
                content=content,
                content_hash=_content_hash(content),
                source_path=source_path_val,
                anchor=slug,
                meta=chunk_meta,
                tags=list(tags),
                category=category,
            )
        )

    if chunks:
        return chunks
    content = body.strip()
    if not content:
        return []
    return [
        Chunk(
            topic=base_topic,
            content=content,
            content_hash=_content_hash(content),
            source_path=source_path_val,
            anchor="",
            meta=meta,
            tags=tags,
            category=category,
        )
    ]


def _fill_img_alt(text: str) -> str:
    """Replace empty image alt text with the URL filename stem.

    ``![](path/to/propertiesbutton_viewport.png)``
    becomes
    ``![propertiesbutton viewport](path/to/propertiesbutton_viewport.png)``
    """
    from urllib.parse import urlparse

    def _replacer(m: re.Match[str]) -> str:
        url = m.group(1)
        try:
            path = urlparse(url).path
            stem = path.rstrip("/").rsplit("/", 1)[-1]
            # Strip extension
            if "." in stem:
                stem = stem[: stem.rfind(".")]
            alt = re.sub(r"[_\-]+", " ", stem).strip()
        except Exception:
            alt = url
        return f"![{alt}]({url})" if alt else m.group(0)

    return _EMPTY_IMG_ALT_RE.sub(_replacer, text)


def _slug(text: str) -> str:
    """Convert heading text to a URL-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return slug or "section"


__all__ = [
    "Chunk",
    "_content_hash",
    "_make_topic",
    "_slug",
    "canonicalize",
    "chunk_file",
    "strip_topic_roots",
]
