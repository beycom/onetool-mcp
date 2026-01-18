"""Session storage - session management and capture saving."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ot_browse.config import get_config
from ot_browse.state import Annotation

from .index import generate_capture_index, generate_session_index
from .utils import (
    _get_sessions_dir,
    clean_text,
    find_line_numbers,
    set_max_text_length,
    yaml_dump,
)


def list_sessions() -> list[dict[str, Any]]:
    """List all existing sessions.

    Returns:
        List of session info dicts with 'name' and 'path' keys.
    """
    sessions_dir = _get_sessions_dir()
    if not sessions_dir.exists():
        return []

    sessions = []
    for session_path in sorted(sessions_dir.iterdir(), reverse=True):
        if not session_path.is_dir():
            continue
        sessions.append(
            {
                "name": session_path.name,
                "path": str(session_path),
            }
        )

    return sessions


def create_session(name: str | None = None) -> tuple[str, Path]:
    """Create a new session directory.

    Args:
        name: Optional session name. Auto-generated if not provided.

    Returns:
        Tuple of (session_name, session_path).
    """
    sessions_dir = _get_sessions_dir()
    sessions_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    if name:
        session_name = f"{timestamp}_session_{name}"
    else:
        # Find next available number
        existing = list(sessions_dir.glob(f"{timestamp}_session_*"))
        num = len(existing) + 1
        session_name = f"{timestamp}_session_{num:03d}"

    session_path = sessions_dir / session_name
    session_path.mkdir(parents=True, exist_ok=True)

    return session_name, session_path


def save_capture(
    session_path: Path,
    capture_num: int,
    url: str,
    title: str,
    annotations: list[Annotation],
    full_page: bool = False,
    screenshot_data: bytes | None = None,
) -> Path:
    """Save a capture to the session.

    Args:
        session_path: Path to the session directory.
        capture_num: Capture number for naming.
        url: Current page URL.
        title: Current page title.
        annotations: List of annotations to save.
        full_page: Whether this is a full-page capture.
        screenshot_data: Optional screenshot bytes.

    Returns:
        Path to the saved capture YAML file.
    """
    # Create capture filename
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
    safe_title = safe_title[:50].strip().replace(" ", "-").lower() or "untitled"
    filename = f"{capture_num:03d}_{safe_title}"

    # Build capture data
    capture_data: dict[str, Any] = {
        "captured_at": datetime.now().isoformat(),
        "url": url,
        "title": title,
        "full_page": full_page,
        "annotations": [asdict(a) for a in annotations],
    }

    # Save screenshot if provided
    if screenshot_data:
        screenshot_path = session_path / "screenshots" / f"{filename}.webp"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(screenshot_data)
        capture_data["screenshot"] = f"screenshots/{filename}.webp"

    # Write capture YAML
    capture_path = session_path / "captures" / f"{filename}.yaml"
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    capture_path.write_text(yaml_dump(capture_data))

    return capture_path


def save_comprehensive_capture(
    session_path: Path,
    capture_num: int,
    capture_data: dict[str, Any],
) -> Path:
    """Save a comprehensive capture to the session.

    Args:
        session_path: Path to the session directory.
        capture_num: Capture number for naming.
        capture_data: Dict from browser.capture_comprehensive().

    Returns:
        Path to the saved capture directory.
    """
    # Initialize text length from config
    config = get_config()
    set_max_text_length(config.max_text_length)

    page_info = capture_data.get("page_info", {}) or {}

    # Create capture directory directly under session
    capture_name = f"capture_{capture_num:03d}"
    capture_dir = session_path / capture_name
    capture_dir.mkdir(parents=True, exist_ok=True)

    # Extract screenshot
    screenshot_data = capture_data.pop("screenshot", None)
    html_data = capture_data.pop("html", None)

    # Create screenshots directory
    screenshots_dir = capture_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    # Save main screenshot
    if screenshot_data:
        screenshot_path = screenshots_dir / "page.webp"
        screenshot_path.write_bytes(screenshot_data)

    # Save HTML
    if html_data:
        html_path = capture_dir / "page.html"
        html_path.write_text(html_data, encoding="utf-8")

    # Build page_info with core metadata
    raw_annotations = capture_data.get("annotations", [])
    browser_info = capture_data.get("browser_info", {})
    performance = capture_data.get("performance")

    # Compute line numbers for annotations (requires HTML content)
    line_numbers = find_line_numbers(html_data or "", raw_annotations)

    # Clean annotations - keep essential fields + enhanced data
    annotations = []
    for ann in raw_annotations:
        clean_ann = {
            "id": ann.get("id", ""),
            "label": ann.get("label", ""),
            "selector": ann.get("selector", ""),
            "tagName": ann.get("tagName", ""),
        }
        if ann.get("elementId"):
            clean_ann["elementId"] = ann["elementId"]
        if ann.get("outerHTML"):
            clean_ann["outerHTML"] = clean_text(ann["outerHTML"])

        # Enhanced annotation data
        ann_id = ann.get("id", "")
        if ann_id in line_numbers:
            clean_ann["line_number"] = line_numbers[ann_id]
        if ann.get("bounding_box"):
            clean_ann["bounding_box"] = ann["bounding_box"]
        if ann.get("computed_styles"):
            clean_ann["computed_styles"] = ann["computed_styles"]

        annotations.append(clean_ann)

    # Save annotation screenshots and add screenshot paths to annotations
    annotation_screenshots = capture_data.get("annotation_screenshots", {})
    if annotation_screenshots:
        for ann_id, screenshot_bytes in annotation_screenshots.items():
            safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in ann_id)
            screenshot_filename = f"{safe_id}.webp"
            (screenshots_dir / screenshot_filename).write_bytes(screenshot_bytes)

            # Add screenshot path to matching annotation
            for ann in annotations:
                if ann.get("id") == ann_id:
                    ann["screenshot"] = f"screenshots/{screenshot_filename}"
                    break

    # Save page_info.yaml (page, captured_at, browser only)
    page_info_data: dict[str, Any] = {
        "page": page_info or {},
        "captured_at": datetime.now().isoformat(),
        "browser": browser_info or {},
    }
    (capture_dir / "page_info.yaml").write_text(yaml_dump(page_info_data))

    # Save annotations to separate file
    if annotations:
        (capture_dir / "annotations.yaml").write_text(yaml_dump(annotations))

    # Save performance to separate file
    if performance:
        (capture_dir / "performance.yaml").write_text(yaml_dump(performance))

    # Save images
    images = capture_data.get("images", [])
    if images:
        (capture_dir / "images.yaml").write_text(yaml_dump(images))

    # Save network
    network = capture_data.get("network", [])
    if network:
        (capture_dir / "network.yaml").write_text(yaml_dump(network))

    # Save cookies
    cookies = capture_data.get("cookies", [])
    if cookies:
        (capture_dir / "cookies.yaml").write_text(yaml_dump(cookies))

    # Save accessibility snapshot (aria_tree is already YAML-formatted)
    accessibility = capture_data.get("accessibility")
    if accessibility:
        aria_tree = accessibility.get("aria_tree", "")
        if aria_tree:
            (capture_dir / "accessibility.yaml").write_text(aria_tree, encoding="utf-8")

    # Save console messages
    console = capture_data.get("console", [])
    if console:
        (capture_dir / "console.yaml").write_text(yaml_dump(console))

    # Generate index file
    index_content = generate_capture_index(
        capture_dir=capture_dir,
        capture_data={
            "page_info": page_info,
            "browser_info": browser_info,
            "annotations": annotations,
            "annotation_screenshots": list(annotation_screenshots.keys())
            if annotation_screenshots
            else [],
            "accessibility": accessibility,
            "images": images,
            "performance": capture_data.get("performance"),
            "network": capture_data.get("network", []),
            "console": console,
            "cookies": cookies,
        },
        has_screenshot=screenshot_data is not None,
        has_html=html_data is not None,
    )
    (capture_dir / "INDEX.md").write_text(index_content, encoding="utf-8")

    # Generate/update session-level INDEX.md
    session_index_content = generate_session_index(session_path)
    (session_path / "INDEX.md").write_text(session_index_content, encoding="utf-8")

    return capture_dir
