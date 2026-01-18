"""Index generation - capture and session index files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ot_browse.state import Annotation

from .utils import get_file_size


def generate_capture_index(
    capture_dir: Path,
    capture_data: dict[str, Any],
    has_screenshot: bool,
    has_html: bool,
) -> str:
    """Generate an LLM-optimized index markdown file summarizing the capture."""
    page_info = capture_data.get("page_info", {}) or {}
    annotations = capture_data.get("annotations", []) or []
    annotation_screenshots = capture_data.get("annotation_screenshots", []) or []
    images = capture_data.get("images", []) or []
    network = capture_data.get("network", []) or []
    console = capture_data.get("console", []) or []
    cookies = capture_data.get("cookies", []) or []
    accessibility = capture_data.get("accessibility")
    performance = capture_data.get("performance")

    title = page_info.get("title", "Untitled")
    url = page_info.get("url", "N/A")
    captured_at = datetime.now().isoformat()

    lines = [
        f"# Capture: {title}",
        "",
        f"URL: {url}",
        f"Captured: {captured_at}",
        "",
    ]

    # Navigation links
    session_dir = capture_dir.parent
    captures = sorted(
        [
            d
            for d in session_dir.iterdir()
            if d.is_dir() and d.name.startswith("capture_")
        ]
    )
    capture_idx = next(
        (i for i, c in enumerate(captures) if c.name == capture_dir.name), -1
    )

    nav_links = []
    if capture_idx > 0:
        prev_capture = captures[capture_idx - 1].name
        nav_links.append(f"[< Previous]({prev_capture}/INDEX.md)")
    nav_links.append("[Session](../INDEX.md)")
    if capture_idx < len(captures) - 1:
        next_capture = captures[capture_idx + 1].name
        nav_links.append(f"[Next >]({next_capture}/INDEX.md)")

    if nav_links:
        lines.extend(
            [
                " | ".join(nav_links),
                "",
            ]
        )

    # How to Use This Capture section
    lines.extend(
        [
            "## How to Use This Capture",
            "",
            "| Task | Recommended Approach |",
            "|------|---------------------|",
            "| Get page overview | Read this INDEX.md |",
            "| Find element selectors | Use `page.annotations` tool |",
            '| Understand page structure | Use `page.accessibility(filter_type="headings")` |',
            '| Find interactive elements | Use `page.accessibility(filter_type="interactive")` |',
            "| Search for text | Use `page.search` tool |",
            "| Compare with previous | Use `page.diff` tool |",
            "| Debug API issues | Check network.yaml |",
            "| Visual context | Read screenshots/page.webp |",
            "",
        ]
    )

    # Quick Stats
    lines.extend(
        [
            "## Quick Stats",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Annotations | {len(annotations)} |",
            f"| Images | {len(images)} |",
            f"| Network Requests | {len(network)} |",
            f"| Console Messages | {len(console)} |",
            f"| Cookies | {len(cookies)} |",
            "",
        ]
    )

    # Files with sizes and warnings
    lines.extend(
        [
            "## Files",
            "",
            "| File | Size | Description |",
            "|------|------|-------------|",
        ]
    )

    file_descriptions = [
        ("page_info.yaml", "Page, captured_at, browser info", True, False),
        (
            "annotations.yaml",
            f"{len(annotations)} annotations with details",
            bool(annotations),
            False,
        ),
        ("performance.yaml", "Performance metrics", bool(performance), False),
        (
            "accessibility.yaml",
            "Accessibility tree snapshot",
            bool(accessibility),
            True,
        ),  # Large file
        ("images.yaml", f"{len(images)} images on page", bool(images), False),
        ("network.yaml", f"{len(network)} network requests", bool(network), False),
        ("console.yaml", f"{len(console)} console messages", bool(console), False),
        ("cookies.yaml", f"{len(cookies)} cookies", bool(cookies), False),
        ("page.html", "Full HTML source", has_html, True),  # Large file
    ]

    for filename, desc, exists, is_large in file_descriptions:
        if exists:
            size = get_file_size(capture_dir / filename)
            warning = ""
            if is_large:
                # Check actual size for warning (accessibility > 100KB, HTML > 500KB per spec)
                size_kb = (
                    (capture_dir / filename).stat().st_size / 1024
                    if (capture_dir / filename).exists()
                    else 0
                )
                threshold_kb = 100 if "accessibility" in filename else 500
                if size_kb > threshold_kb:
                    warning = (
                        " **use filtering tool**"
                        if "accessibility" in filename
                        else " **use search tool**"
                    )
            lines.append(f"| [{filename}]({filename}) | {size} | {desc}{warning} |")

    # Build a set of annotation IDs that have screenshots
    ann_screenshot_ids = set(annotation_screenshots)

    # Annotations as table
    if annotations:
        lines.extend(
            [
                "",
                "## Annotations",
                "",
                "User-marked elements with CSS selectors ready for automation:",
                "",
                "| ID | Tag | Line | Selector | Screenshot |",
                "|-----|-----|------|----------|------------|",
            ]
        )

        for ann in annotations[:20]:
            ann_id = ann.get("id") or "?"
            tag_name = ann.get("tagName") or "?"
            line_num = ann.get("line_number", "-")
            selector = ann.get("selector") or ""
            # Truncate long selectors
            selector_display = selector[:50] + "..." if len(selector) > 50 else selector

            # Screenshot link
            if ann_id in ann_screenshot_ids:
                safe_id = "".join(
                    c if c.isalnum() or c in "-_" else "_" for c in ann_id
                )
                ss_link = f"[view](screenshots/{safe_id}.webp)"
            else:
                ss_link = "-"

            lines.append(
                f"| {ann_id} | `<{tag_name}>` | {line_num} | `{selector_display}` | {ss_link} |"
            )

        if len(annotations) > 20:
            lines.append("")
            lines.append(
                f"*... and {len(annotations) - 20} more (see annotations.yaml)*"
            )

        # Add Read command example
        if annotations and annotations[0].get("line_number"):
            first_line = annotations[0]["line_number"]
            lines.extend(
                [
                    "",
                    f'To read context around first annotation: `Read(file_path="page.html", offset={max(1, first_line - 10)}, limit=25)`',
                ]
            )

    # Add page screenshot at the end
    if has_screenshot:
        lines.extend(
            [
                "",
                "## Page Screenshot",
                "",
                "![Page Screenshot](screenshots/page.webp)",
            ]
        )

    lines.append("")
    return "\n".join(lines)


def generate_session_index(session_path: Path) -> str:
    """Generate a session-level INDEX.md with navigation to all captures.

    Args:
        session_path: Path to session directory.

    Returns:
        Markdown content for session INDEX.md.
    """
    session_name = session_path.name
    captures = sorted(
        [
            d
            for d in session_path.iterdir()
            if d.is_dir() and d.name.startswith("capture_")
        ]
    )

    lines = [
        f"# Session: {session_name}",
        "",
    ]

    if not captures:
        lines.extend(
            [
                "No captures yet.",
                "",
            ]
        )
        return "\n".join(lines)

    # Get first capture timestamp
    first_page_info_path = captures[0] / "page_info.yaml"
    first_captured_at = "unknown"
    if first_page_info_path.exists():
        try:
            with first_page_info_path.open() as f:
                page_info = yaml.safe_load(f)
                first_captured_at = page_info.get("captured_at", "unknown")[:19]
        except Exception:
            pass

    lines.extend(
        [
            f"Started: {first_captured_at}",
            f"Captures: {len(captures)}",
            "",
            "## Quick Links",
            "",
            f"- [First capture]({captures[0].name}/INDEX.md)",
            f"- [Latest capture]({captures[-1].name}/INDEX.md)",
            "",
            "## All Captures",
            "",
            "| # | URL | Title | Annotations | Time |",
            "|---|-----|-------|-------------|------|",
        ]
    )

    for i, capture in enumerate(captures, 1):
        page_info_path = capture / "page_info.yaml"
        annotations_path = capture / "annotations.yaml"

        url = "unknown"
        title = "untitled"
        captured_at = "-"
        ann_count = 0

        if page_info_path.exists():
            try:
                with page_info_path.open() as f:
                    page_info = yaml.safe_load(f) or {}
                    page = page_info.get("page", {})
                    url = page.get("url", "unknown")
                    title = page.get("title", "untitled")
                    captured_at = page_info.get("captured_at", "-")
                    if captured_at and len(captured_at) > 10:
                        captured_at = captured_at[11:19]  # Extract time portion
            except Exception:
                pass

        if annotations_path.exists():
            try:
                with annotations_path.open() as f:
                    annotations = yaml.safe_load(f) or []
                    ann_count = len(annotations) if isinstance(annotations, list) else 0
            except Exception:
                pass

        # Truncate for display
        url_short = url[:40] + "..." if len(url) > 40 else url
        title_short = title[:25] + "..." if len(title) > 25 else title

        lines.append(
            f"| [{i}]({capture.name}/INDEX.md) | {url_short} | {title_short} | {ann_count} | {captured_at} |"
        )

    lines.extend(
        [
            "",
            "## Usage",
            "",
            "```python",
            f'page.captures(session_id="{session_name}")',
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def generate_llm_markdown(
    url: str,
    title: str,
    annotations: list[Annotation],
) -> str:
    """Generate LLM-friendly markdown from annotations.

    Args:
        url: Current page URL.
        title: Current page title.
        annotations: List of annotations.

    Returns:
        Markdown string optimized for LLM token efficiency.
    """
    lines = [
        f"# {title}",
        f"URL: {url}",
        "",
        "## Annotated Elements",
        "",
    ]

    if not annotations:
        lines.append("_No elements annotated._")
    else:
        for ann in annotations:
            lines.append(f"### [{ann.id}] {ann.label}")
            lines.append(f"- Selector: `{ann.selector}`")
            if ann.comment:
                lines.append(f"- Note: {ann.comment}")
            lines.append("")

    return "\n".join(lines)
