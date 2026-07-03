"""Solution bundle helpers for arch pack."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, cast

from bs4 import BeautifulSoup


class BundleError(ValueError):
    """Raised for bundle workflow errors."""


def _discover_additional_files(path_expr: str) -> list[Path]:
    """Discover files from a file, directory, or glob pattern."""
    if "*" in path_expr or "?" in path_expr or "[" in path_expr:
        raw = Path(path_expr)
        if raw.is_absolute():
            root = Path("/")
            pattern = raw.as_posix().lstrip("/")
        else:
            root = Path()
            pattern = path_expr
        return sorted(path.resolve() for path in root.glob(pattern) if path.is_file())

    path = Path(path_expr)
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.rglob("*") if item.is_file())
    return []


def _inline_html_svgs(*, html_path: Path) -> int:
    """Inline local SVG references into HTML from `data-svg-src` and `<img src=...svg>`."""
    content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "html.parser")
    replaced = 0

    for container in soup.find_all(attrs={"data-svg-src": True}):
        svg_rel_path = cast("str | None", container.get("data-svg-src"))
        if not svg_rel_path:
            continue
        svg_path = (html_path.parent / svg_rel_path).resolve()
        if not svg_path.exists():
            continue
        svg_soup = BeautifulSoup(svg_path.read_text(encoding="utf-8"), "lxml-xml")
        svg_elem = svg_soup.find("svg")
        if not svg_elem:
            continue
        container.clear()
        container.append(svg_elem)
        del container["data-svg-src"]
        replaced += 1

    for img in soup.find_all("img", src=True):
        src = str(img.get("src", ""))
        if not src.lower().endswith(".svg"):
            continue
        svg_path = (html_path.parent / src).resolve()
        if not svg_path.exists():
            continue
        svg_soup = BeautifulSoup(svg_path.read_text(encoding="utf-8"), "lxml-xml")
        svg_elem = svg_soup.find("svg")
        if not svg_elem:
            continue
        wrapper = soup.new_tag("div")
        wrapper["data-inlined-svg"] = src
        wrapper.append(svg_elem)
        img.replace_with(wrapper)
        replaced += 1

    updated = str(soup)
    if updated != content:
        html_path.write_text(updated, encoding="utf-8")
    return replaced


def bundle_solution_directory(
    *,
    directory: Path,
    output_path: Path | None = None,
    include: str | None = None,
) -> dict[str, Any]:
    """Inline SVGs and create ZIP archive for solution directory."""
    if not directory.exists() or not directory.is_dir():
        raise BundleError(f"Solution directory not found: {directory}")

    html_files = sorted(directory.rglob("*.html"))
    inlined_total = 0
    for html_file in html_files:
        inlined_total += _inline_html_svgs(html_path=html_file)

    zip_path = output_path or directory.with_suffix(".zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    archived_files: list[str] = []
    included_files: list[str] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(directory.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = file_path.relative_to(directory)
            zf.write(file_path, arcname)
            archived_files.append(str(arcname))
        if include:
            include_files = _discover_additional_files(include)
            for include_file in include_files:
                include_arcname = f"data/{include_file.name}"
                zf.write(include_file, include_arcname)
                included_files.append(str(include_file))

    return {
        "directory": str(directory),
        "bundle_path": str(zip_path),
        "html_files": [str(item) for item in html_files],
        "inlined_svgs": inlined_total,
        "archived_files": archived_files,
        "included_files": included_files,
    }


__all__ = ["BundleError", "bundle_solution_directory"]
