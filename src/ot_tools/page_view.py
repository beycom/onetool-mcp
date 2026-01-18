"""Page view tools for LLM access to ot-browse captures.

These tools help LLMs navigate and analyze page view captures stored
in the .browse/ directory by ot-browse.

Session/Capture Hierarchy:
    .browse/
    └── {session_id}/           # Session (browse session)
        ├── INDEX.md            # Session overview
        └── capture_{N}/        # Capture (page state at moment)
            ├── INDEX.md        # Capture entry point
            ├── page_info.yaml  # URL, title, viewport
            ├── annotations.yaml # User-marked elements
            ├── page.html       # Full HTML
            ├── accessibility.yaml  # ARIA tree
            ├── network.yaml    # HTTP requests
            ├── performance.yaml # Timing metrics
            └── screenshots/    # Visual captures
"""

from __future__ import annotations

# Namespace for dot notation: page.list(), page.captures(), page.summary(), etc.
namespace = "page"

__all__ = [
    "accessibility",
    "annotations",
    "captures",
    "context",
    "diff",
    "list",
    "search",
    "summary",
]

import re
from collections import deque
from pathlib import Path
from typing import Any, Literal

import yaml

from ot.config import get_config
from ot.logging import LogSpan
from ot.paths import get_effective_cwd


def _get_default_sessions_dir() -> str:
    """Get the default sessions directory from config.

    Reads from ot-serve.yaml:
        tools:
          page_view:
            sessions_dir: ".browse"  # default

    Returns:
        Directory name (typically ".browse").
    """
    return get_config().tools.page_view.sessions_dir


def _get_sessions_dir(sessions_dir: str | None = None) -> Path:
    """Get the page views directory path.

    Path resolution follows project conventions:
        - If sessions_dir provided: uses that path directly
        - Otherwise: resolves config default relative to project directory (OT_CWD)
        - Falls back to home directory if not found in project

    Resolution order when sessions_dir is None:
        1. {OT_CWD}/{config.sessions_dir} (if exists)
        2. ~/{config.sessions_dir} (if exists)
        3. {OT_CWD}/{config.sessions_dir} (default, may not exist)

    Args:
        sessions_dir: Explicit sessions directory path, or None to use config.

    Returns:
        Resolved Path to sessions directory.
    """
    if sessions_dir:
        return Path(sessions_dir)
    # Try effective cwd first, then home
    default_dir = _get_default_sessions_dir()
    cwd = get_effective_cwd()
    candidates = [
        cwd / default_dir,
        Path.home() / default_dir,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return cwd / default_dir


def _resolve_sessions_dir(sessions_dir: str | None = None) -> Path:
    """Resolve sessions directory.

    Args:
        sessions_dir: Explicit sessions directory path

    Returns:
        Path to sessions directory
    """
    return _get_sessions_dir(sessions_dir)


def _match_session(sessions_dir: Path, pattern: str) -> Path:
    """Match a session by partial pattern.

    Args:
        sessions_dir: Path to sessions directory
        pattern: Full or partial session name (e.g., "001" matches "*session_001*")

    Returns:
        Path to the matched session directory

    Raises:
        ValueError: If no match or ambiguous match
    """
    if not sessions_dir.exists():
        raise ValueError(f"Sessions directory not found: {sessions_dir}")

    # List all session directories
    sessions = sorted(
        [
            d
            for d in sessions_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ],
        key=lambda p: p.name,
    )

    if not sessions:
        raise ValueError(f"No sessions found in: {sessions_dir}")

    # Try exact match first
    exact = [s for s in sessions if s.name == pattern]
    if exact:
        return exact[0]

    # Partial match - look for pattern anywhere in name
    matches = [s for s in sessions if pattern in s.name]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        match_names = [m.name for m in matches[:5]]
        extra = f" (and {len(matches) - 5} more)" if len(matches) > 5 else ""
        raise ValueError(
            f"Multiple sessions match '{pattern}': {', '.join(match_names)}{extra}. "
            "Be more specific."
        )
    else:
        available = [s.name for s in sessions[:5]]
        extra = f" (and {len(sessions) - 5} more)" if len(sessions) > 5 else ""
        raise ValueError(
            f"No session matches '{pattern}'. Available: {', '.join(available)}{extra}"
        )


def _match_capture(session_path: Path, pattern: str) -> Path:
    """Match a capture by partial pattern.

    Args:
        session_path: Path to session directory
        pattern: Full or partial capture name (e.g., "001" matches "capture_001")

    Returns:
        Path to the matched capture directory

    Raises:
        ValueError: If no match or ambiguous match
    """
    if not session_path.exists():
        raise ValueError(f"Session not found: {session_path}")

    captures = _get_session_captures(session_path)

    if not captures:
        raise ValueError(f"No captures found in session: {session_path.name}")

    # Try exact match first
    exact = [c for c in captures if c.name == pattern]
    if exact:
        return exact[0]

    # Partial match
    matches = [c for c in captures if pattern in c.name]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        match_names = [m.name for m in matches[:5]]
        extra = f" (and {len(matches) - 5} more)" if len(matches) > 5 else ""
        raise ValueError(
            f"Multiple captures match '{pattern}': {', '.join(match_names)}{extra}. "
            "Be more specific."
        )
    else:
        available = [c.name for c in captures[:5]]
        extra = f" (and {len(captures) - 5} more)" if len(captures) > 5 else ""
        raise ValueError(
            f"No capture matches '{pattern}'. Available: {', '.join(available)}{extra}"
        )


def _load_yaml(path: Path) -> dict[str, Any] | list[Any] | None:
    """Load a YAML file, returning None if it doesn't exist."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _as_dict(data: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    """Safely convert YAML data to dict, returning empty dict if not a dict."""
    return data if isinstance(data, dict) else {}


def _get_file_size(path: Path) -> str:
    """Get human-readable file size."""
    if not path.exists():
        return "0B"
    size_bytes = path.stat().st_size
    size: float = float(size_bytes)
    for unit in ["B", "KB", "MB"]:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def _count_yaml_list_items(path: Path) -> int:
    """Count top-level list items in a YAML file by streaming.

    Much faster than loading the entire file for large YAML lists.
    Works for files where each list item starts with '- ' at column 0.
    """
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("- "):
                count += 1
    return count


def _find_line_numbers_batch(
    html_path: Path, search_terms: list[str]
) -> dict[str, int | None]:
    """Find line numbers for multiple search terms in a single pass.

    Much faster than calling _find_line_number multiple times for large files.
    """
    results: dict[str, int | None] = dict.fromkeys(search_terms, None)
    remaining = set(search_terms)

    if not html_path.exists() or not remaining:
        return results

    with html_path.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            # Check all remaining terms against this line
            found = []
            for term in remaining:
                if term in line:
                    results[term] = line_num
                    found.append(term)
            # Remove found terms from remaining
            for term in found:
                remaining.discard(term)
            # Early exit if all found
            if not remaining:
                break

    return results


def _get_session_captures(session_path: Path) -> list[Path]:
    """Get all capture directories in a session, sorted by name."""
    # glob is more efficient than iterdir + filter
    return sorted(session_path.glob("capture_*"), key=lambda p: p.name)


# === Navigation Tools ===


def list(
    *,
    sessions_dir: str | None = None,
) -> str:
    """List all page views with metadata.

    Returns a summary of all available page views including capture counts,
    first/last URLs, and timestamps.

    Args:
        sessions_dir: Optional explicit path to sessions directory.

    Returns:
        Markdown-formatted list of sessions with metadata.

    Example:
        page.list()
        page.list(sessions_dir="/path/to/.browse")
    """
    with LogSpan(span="page.list") as span:
        base_dir = _resolve_sessions_dir(sessions_dir)

        if not base_dir.exists():
            span.add("error", "no_sessions_dir")
            return f"No sessions directory found at: {base_dir}"

        sessions = []
        for item in sorted(base_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                captures = _get_session_captures(item)
                if not captures:
                    continue

                # Get first and last capture info
                first_info = _as_dict(_load_yaml(captures[0] / "page_info.yaml"))
                last_info = (
                    _as_dict(_load_yaml(captures[-1] / "page_info.yaml"))
                    if len(captures) > 1
                    else first_info
                )

                first_url = first_info.get("page", {}).get("url", "unknown")
                last_url = last_info.get("page", {}).get("url", first_url)
                captured_at = first_info.get("captured_at", "unknown")

                sessions.append(
                    {
                        "id": item.name,
                        "captures": len(captures),
                        "first_url": first_url[:60] + "..."
                        if len(first_url) > 60
                        else first_url,
                        "last_url": last_url[:60] + "..."
                        if len(last_url) > 60
                        else last_url,
                        "captured_at": captured_at,
                    }
                )

        span.add("sessionCount", len(sessions))

        if not sessions:
            return f"No sessions found in: {base_dir}"

        lines = [
            "# Page Views",
            "",
            f"Found {len(sessions)} session(s) in `{base_dir}`",
            "",
        ]
        lines.append("| Session | Captures | First URL | Started |")
        lines.append("|---------|----------|-----------|---------|")

        for s in sessions:
            lines.append(
                f"| `{s['id']}` | {s['captures']} | {s['first_url']} | {s['captured_at'][:19]} |"
            )

        lines.extend(
            [
                "",
                "## Usage",
                "",
                "To list captures in a session:",
                "```",
                f'page.captures(session_id="{sessions[0]["id"]}")',
                "```",
            ]
        )

        return "\n".join(lines)


def captures(
    *,
    session_id: str | None = None,
    sessions_dir: str | None = None,
) -> str:
    """List all captures within a page view.

    Returns details about each capture in a session including URLs, titles,
    annotation counts, and file sizes.

    Args:
        session_id: Session name or partial match (e.g., "001" matches "*session_001*")
        sessions_dir: Optional explicit path to sessions directory.

    Returns:
        Markdown-formatted list of captures with metadata.

    Example:
        page.captures(session_id="session_001")
        page.captures(session_id="001")  # partial match
    """
    with LogSpan(span="page.captures", session_id=session_id) as span:
        session_pattern = session_id
        if not session_pattern:
            span.add("error", "missing_session_id")
            return "Error: session_id parameter is required"

        base_dir = _resolve_sessions_dir(sessions_dir)

        try:
            session_path = _match_session(base_dir, session_pattern)
        except ValueError as e:
            span.add("error", str(e))
            return f"Error: {e}"

        captures = _get_session_captures(session_path)
        if not captures:
            span.add("captureCount", 0)
            return f"No captures found in session: {session_path.name}"

        span.add("captureCount", len(captures))
        session_name = session_path.name
        lines = [
            f"# Session: {session_name}",
            "",
            f"Path: `{session_path}`",
            f"Captures: {len(captures)}",
            "",
            "| # | Capture | URL | Title | Annotations |",
            "|---|---------|-----|-------|-------------|",
        ]

        for i, capture in enumerate(captures, 1):
            page_info = _as_dict(_load_yaml(capture / "page_info.yaml"))
            annotations = _load_yaml(capture / "annotations.yaml") or []

            url = page_info.get("page", {}).get("url", "unknown")
            title = page_info.get("page", {}).get("title", "untitled")
            ann_count = len(annotations) if isinstance(annotations, list) else 0

            # Truncate for display
            url_short = url[:40] + "..." if len(url) > 40 else url
            title_short = title[:30] + "..." if len(title) > 30 else title

            lines.append(
                f"| {i} | `{capture.name}` | {url_short} | {title_short} | {ann_count} |"
            )

        lines.extend(
            [
                "",
                "## Files per Capture",
                "",
            ]
        )

        # Show file sizes for first capture as example
        first_capture = captures[0]
        lines.append(f"Example from `{first_capture.name}`:")
        lines.append("")
        lines.append("| File | Size | Description |")
        lines.append("|------|------|-------------|")

        file_info = [
            ("page_info.yaml", "Page URL, title, viewport"),
            ("annotations.yaml", "User-marked elements"),
            ("page.html", "Full HTML content"),
            ("accessibility.yaml", "ARIA accessibility tree"),
            ("network.yaml", "HTTP requests"),
            ("performance.yaml", "Timing metrics"),
        ]

        for filename, desc in file_info:
            size = _get_file_size(first_capture / filename)
            warning = (
                " ⚠️ LARGE"
                if "KB" in size and float(size.replace("KB", "")) > 50
                else ""
            )
            lines.append(f"| {filename} | {size}{warning} | {desc} |")

        lines.extend(
            [
                "",
                "## Quick Actions",
                "",
                "```python",
                f'page.annotations(session_id="{session_name}", capture_id="{captures[0].name}")',
                f'page.summary(session_id="{session_name}", capture_id="{captures[0].name}")',
                "```",
            ]
        )

        return "\n".join(lines)


# === Annotation-Centric Tools ===


def annotations(
    *,
    session_id: str | None = None,
    capture_id: str | None = None,
    sessions_dir: str | None = None,
) -> str:
    """List annotations from a capture with selectors, HTML snippets, and screenshot paths.

    Annotations are user-marked elements captured during browsing. This tool
    provides quick access to what the user focused on.

    Args:
        session_id: Session name or partial match (e.g., "001" matches "*session_001*")
        capture_id: Capture name or partial match (e.g., "001" matches "capture_001")
        sessions_dir: Optional explicit path to sessions directory.

    Returns:
        Markdown-formatted list of annotations with details.

    Example:
        page.annotations(session_id="session_001", capture_id="capture_001")
        page.annotations(session_id="001", capture_id="001")  # partial match
    """
    with LogSpan(
        span="page.annotations", session_id=session_id, capture_id=capture_id
    ) as span:
        if not session_id or not capture_id:
            span.add("error", "missing_params")
            return "Error: session_id and capture_id parameters are required"

        base_dir = _resolve_sessions_dir(sessions_dir)

        try:
            session_path = _match_session(base_dir, session_id)
            capture_path = _match_capture(session_path, capture_id)
        except ValueError as e:
            span.add("error", str(e))
            return f"Error: {e}"

        annotations = _load_yaml(capture_path / "annotations.yaml")
        if not annotations:
            span.add("annotationCount", 0)
            return f"No annotations found in: {capture_path}"

        span.add("annotationCount", len(annotations))
        html_path = capture_path / "page.html"

        # Build search terms for batch lookup (single pass through HTML file)
        search_terms = []
        ann_to_search = {}  # Map annotation ID to its search terms
        for ann in annotations:
            ann_id = ann.get("id", "unknown")
            element_id = ann.get("elementId", "")
            outer_html = ann.get("outerHTML", "")
            terms = []
            if element_id:
                term = f'id="{element_id}"'
                terms.append(term)
                search_terms.append(term)
            if 'x-inspect="' in outer_html:
                term = f'x-inspect="{ann_id}"'
                terms.append(term)
                search_terms.append(term)
            ann_to_search[ann_id] = terms

        # Single pass through HTML to find all line numbers
        line_numbers = (
            _find_line_numbers_batch(html_path, search_terms) if search_terms else {}
        )

        lines = [
            f"# Annotations: {capture_id}",
            "",
            f"Found {len(annotations)} annotation(s)",
            "",
        ]

        for ann in annotations:
            ann_id = ann.get("id", "unknown")
            label = ann.get("label", "")
            tag = ann.get("tagName", "unknown")
            selector = ann.get("selector", "")
            outer_html = ann.get("outerHTML", "")
            screenshot = ann.get("screenshot", "")
            bounding_box = ann.get("bounding_box")
            computed_styles = ann.get("computed_styles")

            # Prefer line_number from annotations.yaml, fallback to batch search
            line_num = ann.get("line_number")
            if not line_num:
                for term in ann_to_search.get(ann_id, []):
                    if line_numbers.get(term):
                        line_num = line_numbers[term]
                        break

            lines.append(f"## {ann_id}" + (f" ({label})" if label else ""))
            lines.append("")
            lines.append(f"- **Tag**: `<{tag}>`")
            lines.append(f"- **Selector**: `{selector}`")
            if line_num:
                lines.append(f"- **Line**: {line_num} in page.html")
            if bounding_box:
                lines.append(
                    f"- **Position**: {bounding_box.get('x', 0)},{bounding_box.get('y', 0)} "
                    f"Size: {bounding_box.get('width', 0)}x{bounding_box.get('height', 0)}"
                )
            if computed_styles:
                # Show key styles on one line
                style_parts = []
                if computed_styles.get("display"):
                    style_parts.append(f"display:{computed_styles['display']}")
                if computed_styles.get("color"):
                    style_parts.append(f"color:{computed_styles['color']}")
                if computed_styles.get("fontSize"):
                    style_parts.append(f"font:{computed_styles['fontSize']}")
                if style_parts:
                    lines.append(f"- **Styles**: {', '.join(style_parts)}")
            if screenshot:
                screenshot_path = capture_path / screenshot
                lines.append(f"- **Screenshot**: `{screenshot_path}`")
            lines.append("")
            lines.append("**HTML:**")
            lines.append("```html")
            # Truncate long HTML
            html_display = (
                outer_html[:500] + "..." if len(outer_html) > 500 else outer_html
            )
            lines.append(html_display)
            lines.append("```")
            lines.append("")

        lines.extend(
            [
                "## Get Context Around an Annotation",
                "",
                "```python",
                f'page.context(session_id="{session_path.name}", capture_id="{capture_path.name}", annotation_id="{annotations[0].get("id", "")}")',
                "```",
            ]
        )

        return "\n".join(lines)


def context(
    *,
    session_id: str | None = None,
    capture_id: str | None = None,
    annotation_id: str,
    context_lines: int = 10,
    sessions_dir: str | None = None,
) -> str:
    """Get HTML and accessibility context around an annotation.

    Extracts the HTML lines around where an annotation appears, plus its
    position in the accessibility tree.

    Args:
        session_id: Session name or partial match (e.g., "001" matches "*session_001*")
        capture_id: Capture name or partial match (e.g., "001" matches "capture_001")
        annotation_id: The annotation ID (e.g., "h1", "p-1")
        context_lines: Number of lines before/after to include (default 10)
        sessions_dir: Optional explicit path to sessions directory.

    Returns:
        Markdown with HTML context and accessibility tree excerpt.

    Example:
        page.context(session_id="001", capture_id="001", annotation_id="h1")
        page.context(session_id="001", capture_id="001", annotation_id="btn-1", context_lines=20)
    """
    with LogSpan(
        span="page.context", annotation_id=annotation_id, context_lines=context_lines
    ) as span:
        if not session_id or not capture_id:
            span.add("error", "missing_params")
            return "Error: session_id and capture_id parameters are required"

        base_dir = _resolve_sessions_dir(sessions_dir)

        try:
            session_path = _match_session(base_dir, session_id)
            capture_path = _match_capture(session_path, capture_id)
        except ValueError as e:
            span.add("error", str(e))
            return f"Error: {e}"

        annotations = _load_yaml(capture_path / "annotations.yaml") or []
        annotation = next(
            (a for a in annotations if a.get("id") == annotation_id), None
        )

        if not annotation:
            available = [a.get("id") for a in annotations]
            span.add("error", "not_found")
            return f"Annotation '{annotation_id}' not found. Available: {available}"

        span.add("found", True)
        html_path = capture_path / "page.html"
        outer_html = annotation.get("outerHTML", "")
        element_id = annotation.get("elementId", "")
        tag = annotation.get("tagName", "unknown")

        lines = [
            f"# Context: {annotation_id}",
            "",
            f"**Tag**: `<{tag}>`",
            f"**Selector**: `{annotation.get('selector', '')}`",
            "",
        ]

        # Find line number with batch lookup (single pass for multiple terms)
        search_terms = []
        if element_id:
            search_terms.append(f'id="{element_id}"')
        if 'x-inspect="' in outer_html:
            search_terms.append(f'x-inspect="{annotation_id}"')

        line_numbers = (
            _find_line_numbers_batch(html_path, search_terms) if search_terms else {}
        )
        line_num = next(
            (line_numbers[t] for t in search_terms if line_numbers.get(t)), None
        )

        if line_num and html_path.exists():
            span.add("lineNum", line_num)
            lines.append(f"## HTML Context (line {line_num})")
            lines.append("")
            lines.append("```html")

            # Read only the lines we need, not the entire file
            start = max(1, line_num - context_lines)
            end = line_num + context_lines
            with html_path.open(encoding="utf-8") as f:
                for i, file_line in enumerate(f, 1):
                    if i < start:
                        continue
                    if i > end:
                        break
                    prefix = ">>> " if i == line_num else "    "
                    line_content = file_line.rstrip()[:200]  # Truncate long lines
                    lines.append(f"{i:6d} {prefix}{line_content}")

            lines.append("```")
            lines.append("")
            lines.append(
                "To read more context, increase `context_lines` parameter or use `page.search`."
            )
        else:
            lines.append("## HTML")
            lines.append("")
            lines.append("Could not locate element in page.html. Raw HTML:")
            lines.append("```html")
            lines.append(outer_html[:1000])
            lines.append("```")

        lines.append("")

        # Search accessibility tree for the element
        a11y_path = capture_path / "accessibility.yaml"
        if a11y_path.exists():
            lines.append("## Accessibility Tree Context")
            lines.append("")

            # Search for the annotation in accessibility tree
            label = annotation.get("label", "")
            search_terms = [t for t in [label, element_id] if t]

            found_context = []
            if search_terms:
                # Read line by line with a deque buffer for O(1) context window
                buffer: deque[str] = deque(maxlen=8)
                with a11y_path.open(encoding="utf-8") as f:
                    for line in f:
                        buffer.append(line.rstrip())

                        for term in search_terms:
                            if term.lower() in line.lower():
                                # Found - take context from buffer (last 4 lines)
                                found_context = list(buffer)[-4:]
                                # Read 4 more lines after
                                for _ in range(4):
                                    try:
                                        found_context.append(next(f).rstrip())
                                    except StopIteration:
                                        break
                                break
                        if found_context:
                            break

            if found_context:
                lines.append("```yaml")
                lines.extend(found_context)
                lines.append("```")
            else:
                lines.append(
                    f"Element not found in accessibility tree. Search for tag `{tag}` manually."
                )

        return "\n".join(lines)


def search(
    *,
    session_id: str | None = None,
    capture_id: str | None = None,
    pattern: str,
    search_in: Literal["html", "accessibility", "both"] = "both",
    max_results: int = 20,
    sessions_dir: str | None = None,
) -> str:
    """Search HTML and/or accessibility tree for a pattern.

    Performs regex search and returns matching lines with line numbers.

    Args:
        session_id: Session name or partial match (e.g., "001" matches "*session_001*")
        capture_id: Capture name or partial match (e.g., "001" matches "capture_001")
        pattern: Regex pattern to search for
        search_in: Where to search: "html", "accessibility", or "both"
        max_results: Maximum results to return (default 20)
        sessions_dir: Optional explicit path to sessions directory.

    Returns:
        Markdown-formatted search results with line numbers.

    Example:
        page.search(session_id="001", capture_id="001", pattern="button")
        page.search(session_id="001", capture_id="001", pattern="class=", search_in="html")
    """
    with LogSpan(span="page.search", pattern=pattern[:50], search_in=search_in) as span:
        if not session_id or not capture_id:
            span.add("error", "missing_params")
            return "Error: session_id and capture_id parameters are required"

        base_dir = _resolve_sessions_dir(sessions_dir)

        try:
            session_path = _match_session(base_dir, session_id)
            capture_path = _match_capture(session_path, capture_id)
        except ValueError as e:
            span.add("error", str(e))
            return f"Error: {e}"

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            span.add("error", f"invalid_regex: {e}")
            return f"Invalid regex pattern: {e}"

        results: list[dict[str, Any]] = []

        def search_file(path: Path, file_type: str) -> list[dict[str, Any]]:
            matches: list[dict[str, Any]] = []
            if not path.exists():
                return matches
            with path.open(encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        matches.append(
                            {
                                "file": file_type,
                                "line": line_num,
                                "content": line.strip()[:150],
                            }
                        )
                        if len(matches) >= max_results:
                            break
            return matches

        if search_in in ("html", "both"):
            results.extend(search_file(capture_path / "page.html", "page.html"))

        if search_in in ("accessibility", "both") and len(results) < max_results:
            remaining = max_results - len(results)
            a11y_results = search_file(
                capture_path / "accessibility.yaml", "accessibility.yaml"
            )
            results.extend(a11y_results[:remaining])

        span.add("resultCount", len(results))
        lines = [
            f"# Search: `{pattern}`",
            "",
            f"Capture: {capture_id}",
            f"Searched: {search_in}",
            f"Found: {len(results)} match(es)",
            "",
        ]

        if not results:
            lines.append("No matches found.")
            return "\n".join(lines)

        lines.append("| File | Line | Content |")
        lines.append("|------|------|---------|")

        for r in results:
            content = (
                r["content"][:80] + "..." if len(r["content"]) > 80 else r["content"]
            )
            # Escape pipes in content
            content = content.replace("|", "\\|")
            lines.append(f"| {r['file']} | {r['line']} | `{content}` |")

        lines.extend(
            [
                "",
                "## Get More Context",
                "",
                "Use `page.context` with an annotation ID, or search with a more specific pattern.",
            ]
        )

        return "\n".join(lines)


# === Filtering Tools ===


def accessibility(
    *,
    session_id: str | None = None,
    capture_id: str | None = None,
    filter_type: Literal[
        "interactive", "headings", "forms", "links", "landmarks", "all"
    ] = "interactive",
    max_lines: int = 200,
    sessions_dir: str | None = None,
) -> str:
    """Get filtered accessibility tree (258KB → <10KB).

    Filters the large accessibility tree to show only relevant elements.

    Args:
        session_id: Session name or partial match (e.g., "001" matches "*session_001*")
        capture_id: Capture name or partial match (e.g., "001" matches "capture_001")
        filter_type: What to filter for:
            - "interactive": buttons, links, inputs, checkboxes
            - "headings": heading elements
            - "forms": form controls and labels
            - "links": all links with URLs
            - "landmarks": navigation, main, banner, etc.
            - "all": no filtering (first max_lines only)
        max_lines: Maximum lines to return (default 200)
        sessions_dir: Optional explicit path to sessions directory.

    Returns:
        Filtered accessibility tree content.

    Example:
        page.accessibility(session_id="001", capture_id="001", filter_type="interactive")
        page.accessibility(session_id="001", capture_id="001", filter_type="headings")
    """
    with LogSpan(
        span="page.accessibility", filter_type=filter_type, max_lines=max_lines
    ) as span:
        if not session_id or not capture_id:
            span.add("error", "missing_params")
            return "Error: session_id and capture_id parameters are required"

        base_dir = _resolve_sessions_dir(sessions_dir)

        try:
            session_path = _match_session(base_dir, session_id)
            capture_path = _match_capture(session_path, capture_id)
        except ValueError as e:
            span.add("error", str(e))
            return f"Error: {e}"

        a11y_path = capture_path / "accessibility.yaml"

        if not a11y_path.exists():
            span.add("error", "file_not_found")
            return f"Accessibility file not found: {a11y_path}"

        # Define filter patterns for each type
        filters = {
            "interactive": r"(button|link|textbox|checkbox|radio|combobox|menu|tab|slider)",
            "headings": r"heading",
            "forms": r"(textbox|checkbox|radio|combobox|spinbutton|slider|form|group.*:)",
            "links": r"(link|/url:)",
            "landmarks": r"(banner|navigation|main|contentinfo|region|complementary|search)",
        }

        lines = [
            f"# Accessibility Tree: {capture_id}",
            "",
            f"Filter: {filter_type}",
            f"File: `{a11y_path}` ({_get_file_size(a11y_path)})",
            "",
        ]

        with a11y_path.open(encoding="utf-8") as f:
            if filter_type == "all":
                content_lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    content_lines.append(line.rstrip())
                span.add("lineCount", len(content_lines))
                lines.append("```yaml")
                lines.extend(content_lines)
                lines.append("```")
                lines.append(f"\n(Showing first {max_lines} lines)")
            else:
                pattern = re.compile(filters[filter_type], re.IGNORECASE)
                matching_lines = []

                for line in f:
                    if pattern.search(line):
                        matching_lines.append(line.rstrip())
                        if len(matching_lines) >= max_lines:
                            break

                span.add("matchCount", len(matching_lines))
                if matching_lines:
                    lines.append(f"Found {len(matching_lines)} matching elements:")
                    lines.append("")
                    lines.append("```yaml")
                    lines.extend(matching_lines)
                    lines.append("```")
                else:
                    lines.append(f"No {filter_type} elements found.")

        return "\n".join(lines)


# === Comparison Tools ===


def diff(
    *,
    session_id: str | None = None,
    capture_id_1: str | None = None,
    capture_id_2: str | None = None,
    sessions_dir: str | None = None,
) -> str:
    """Compare two captures to see what changed.

    Compares annotations, page info, and network requests between captures.

    Args:
        session_id: Session name or partial match (e.g., "001" matches "*session_001*")
        capture_id_1: First capture to compare (earlier)
        capture_id_2: Second capture to compare (later)
        sessions_dir: Optional explicit path to sessions directory.

    Returns:
        Markdown-formatted diff showing changes.

    Example:
        page.diff(session_id="001", capture_id_1="capture_001", capture_id_2="capture_002")
    """
    with LogSpan(
        span="page.diff", capture_id_1=capture_id_1, capture_id_2=capture_id_2
    ) as span:
        if not session_id or not capture_id_1 or not capture_id_2:
            span.add("error", "missing_params")
            return "Error: session_id, capture_id_1, and capture_id_2 parameters are required"

        base_dir = _resolve_sessions_dir(sessions_dir)

        try:
            session_path = _match_session(base_dir, session_id)
            capture1 = _match_capture(session_path, capture_id_1)
            capture2 = _match_capture(session_path, capture_id_2)
        except ValueError as e:
            span.add("error", str(e))
            return f"Error: {e}"

        lines = [
            f"# Diff: {capture1.name} → {capture2.name}",
            "",
        ]

        # Compare page info
        info1 = _as_dict(_load_yaml(capture1 / "page_info.yaml"))
        info2 = _as_dict(_load_yaml(capture2 / "page_info.yaml"))

        url1 = info1.get("page", {}).get("url", "")
        url2 = info2.get("page", {}).get("url", "")
        title1 = info1.get("page", {}).get("title", "")
        title2 = info2.get("page", {}).get("title", "")

        span.add("urlChanged", url1 != url2)
        lines.append("## Page Changes")
        lines.append("")

        if url1 != url2:
            lines.append(f"- **URL**: `{url1[:60]}` → `{url2[:60]}`")
        else:
            lines.append(f"- **URL**: (unchanged) `{url1[:60]}`")

        if title1 != title2:
            lines.append(f'- **Title**: "{title1}" → "{title2}"')
        else:
            lines.append(f'- **Title**: (unchanged) "{title1}"')

        lines.append("")

        # Compare annotations
        ann1 = _load_yaml(capture1 / "annotations.yaml") or []
        ann2 = _load_yaml(capture2 / "annotations.yaml") or []

        ids1 = {a.get("id") for a in ann1}
        ids2 = {a.get("id") for a in ann2}

        added = ids2 - ids1
        removed = ids1 - ids2

        span.add("annotationsAdded", len(added))
        span.add("annotationsRemoved", len(removed))
        lines.append("## Annotations")
        lines.append("")
        lines.append(f"- Before: {len(ann1)}")
        lines.append(f"- After: {len(ann2)}")
        lines.append("")

        if added:
            lines.append("### Added")
            for ann_id in sorted(added):
                ann = next(a for a in ann2 if a.get("id") == ann_id)
                lines.append(
                    f"- **{ann_id}**: `<{ann.get('tagName', '?')}>` - {ann.get('selector', '')[:50]}"
                )
            lines.append("")

        if removed:
            lines.append("### Removed")
            for ann_id in sorted(removed):
                ann = next(a for a in ann1 if a.get("id") == ann_id)
                lines.append(
                    f"- **{ann_id}**: `<{ann.get('tagName', '?')}>` - {ann.get('selector', '')[:50]}"
                )
            lines.append("")

        if not added and not removed:
            lines.append("No annotation changes.")
            lines.append("")

        # Compare network requests
        net1 = _load_yaml(capture1 / "network.yaml") or []
        net2 = _load_yaml(capture2 / "network.yaml") or []

        urls1 = {r.get("url", "") for r in net1 if isinstance(r, dict)}
        urls2 = {r.get("url", "") for r in net2 if isinstance(r, dict)}

        new_requests = urls2 - urls1

        if new_requests:
            span.add("newRequests", len(new_requests))
            lines.append("## New Network Requests")
            lines.append("")
            for url in sorted(new_requests)[:10]:
                lines.append(f"- `{url[:80]}`")
            if len(new_requests) > 10:
                lines.append(f"- ... and {len(new_requests) - 10} more")

        return "\n".join(lines)


# === Overview Tools ===


def summary(
    *,
    session_id: str | None = None,
    capture_id: str | None = None,
    sessions_dir: str | None = None,
) -> str:
    """Get a quick overview of a capture.

    Returns key metrics, file sizes, and recommendations for next steps.

    Args:
        session_id: Session name or partial match (e.g., "001" matches "*session_001*")
        capture_id: Capture name or partial match (e.g., "001" matches "capture_001")
        sessions_dir: Optional explicit path to sessions directory.

    Returns:
        Markdown-formatted summary with metrics and guidance.

    Example:
        page.summary(session_id="session_001", capture_id="capture_001")
        page.summary(session_id="001", capture_id="001")  # partial match
    """
    with LogSpan(
        span="page.summary", session_id=session_id, capture_id=capture_id
    ) as span:
        if not session_id or not capture_id:
            span.add("error", "missing_params")
            return "Error: session_id and capture_id parameters are required"

        base_dir = _resolve_sessions_dir(sessions_dir)

        try:
            session_path = _match_session(base_dir, session_id)
            capture_path = _match_capture(session_path, capture_id)
        except ValueError as e:
            span.add("error", str(e))
            return f"Error: {e}"

        # Load small files, stream-count large ones
        page_info = _as_dict(_load_yaml(capture_path / "page_info.yaml"))
        annotations = _load_yaml(capture_path / "annotations.yaml") or []
        # Stream count network requests instead of loading entire file
        network_count = _count_yaml_list_items(capture_path / "network.yaml")

        span.add("annotationCount", len(annotations))
        span.add("networkCount", network_count)
        page = page_info.get("page", {})

        lines = [
            f"# Summary: {capture_id}",
            "",
            f"**URL**: {page.get('url', 'unknown')}",
            f"**Title**: {page.get('title', 'untitled')}",
            f"**Captured**: {page_info.get('captured_at', 'unknown')[:19]}",
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Annotations | {len(annotations)} |",
            f"| Network Requests | {network_count} |",
            f"| Viewport | {page.get('viewport', {}).get('width', '?')}x{page.get('viewport', {}).get('height', '?')} |",
        ]

        lines.extend(
            [
                "",
                "## File Sizes",
                "",
                "| File | Size | Safe to Read? |",
                "|------|------|---------------|",
            ]
        )

        # (filename, threshold_kb, tool_hint) - per spec: accessibility > 100KB, HTML > 500KB
        files_to_check = [
            ("page_info.yaml", None, None),  # Always safe
            ("annotations.yaml", None, None),  # Always safe
            ("page.html", 500, "use page.search"),
            ("accessibility.yaml", 100, "use page.accessibility with filter"),
            ("network.yaml", None, None),  # Always safe
        ]

        for filename, threshold_kb, tool_hint in files_to_check:
            path = capture_path / filename
            size = _get_file_size(path)
            if threshold_kb is None:
                safe = "Yes"
            else:
                # Determine based on file-specific threshold
                size_kb = 0.0
                if "KB" in size:
                    size_kb = float(size.replace("KB", ""))
                elif "MB" in size:
                    size_kb = float(size.replace("MB", "")) * 1024

                if size_kb <= threshold_kb:
                    safe = "Yes"
                else:
                    safe = f"⚠️ Large - {tool_hint}" if tool_hint else "⚠️ Large"
            lines.append(f"| {filename} | {size} | {safe} |")

        # Screenshots
        screenshots_dir = capture_path / "screenshots"
        if screenshots_dir.exists():
            screenshots = list(screenshots_dir.glob("*.webp"))
            lines.append(f"| screenshots/ | {len(screenshots)} files | Use Read tool |")

        lines.extend(
            [
                "",
                "## Recommended Actions",
                "",
            ]
        )

        session_name = session_path.name
        capture_name = capture_path.name

        if annotations:
            lines.append(
                f'1. **View annotations**: `page.annotations(session_id="{session_name}", capture_id="{capture_name}")`'
            )
            lines.append(
                f'2. **Get context for annotation**: `page.context(session_id="{session_name}", capture_id="{capture_name}", annotation_id="{annotations[0].get("id", "")}")`'
            )

        lines.append(
            f'3. **Search page**: `page.search(session_id="{session_name}", capture_id="{capture_name}", pattern="your-search")`'
        )
        lines.append(
            f'4. **Filter accessibility tree**: `page.accessibility(session_id="{session_name}", capture_id="{capture_name}", filter_type="interactive")`'
        )

        # Check for other captures to suggest diff
        captures = _get_session_captures(session_path)
        if len(captures) > 1:
            current_idx = next(
                (i for i, c in enumerate(captures) if c.name == capture_name), 0
            )
            if current_idx > 0:
                prev_capture = captures[current_idx - 1].name
                lines.append(
                    f'5. **Compare with previous**: `page.diff(session_id="{session_name}", capture_id_1="{prev_capture}", capture_id_2="{capture_name}")`'
                )

        return "\n".join(lines)
