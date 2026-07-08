"""Solution bundle helpers for arch pack."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from otpack import resolve_cwd_path


class BundleError(ValueError):
    """Raised for bundle workflow errors."""


def _discover_additional_files(path_expr: str) -> list[Path]:
    """Discover files from a file, directory, or glob pattern.

    Relative paths resolve against the effective project cwd (like the caller's
    ``directory``/``output_path``), not the process cwd, which differs under an
    MCP server.
    """
    if "*" in path_expr or "?" in path_expr or "[" in path_expr:
        raw = Path(path_expr)
        if raw.is_absolute():
            root = Path("/")
            pattern = raw.as_posix().lstrip("/")
        else:
            root = resolve_cwd_path(".")
            pattern = path_expr
        return sorted(path.resolve() for path in root.glob(pattern) if path.is_file())

    path = resolve_cwd_path(path_expr)
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.rglob("*") if item.is_file())
    return []


def _load_svg_element(*, html_path: Path, rel_src: str) -> Any | None:
    """Load a referenced SVG element ready for inlining, or None if unusable.

    Strips the draw.io embedded model (design D9): inlined SVG markup never
    carries `content`, so it exists only in the standalone file.
    """
    svg_path = (html_path.parent / rel_src).resolve()
    if not svg_path.exists():
        return None
    svg_soup = BeautifulSoup(svg_path.read_text(encoding="utf-8"), "lxml-xml")
    svg_elem = svg_soup.find("svg")
    if not svg_elem:
        return None
    if svg_elem.has_attr("content"):
        del svg_elem["content"]
    return svg_elem


def _inline_html_svgs(*, html_path: Path) -> int:
    """Inline local `<img src=...svg>` references into HTML."""
    content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(content, "html.parser")
    replaced = 0

    for img in soup.find_all("img", src=True):
        src = str(img.get("src", ""))
        if not src.lower().endswith(".svg"):
            continue
        svg_elem = _load_svg_element(html_path=html_path, rel_src=src)
        if svg_elem is None:
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
            # Skip the partially written archive itself when output_path
            # points inside the solution directory.
            if not file_path.is_file() or file_path == zip_path:
                continue
            arcname = file_path.relative_to(directory)
            zf.write(file_path, arcname)
            archived_files.append(str(arcname))
        if include:
            include_files = _discover_additional_files(include)
            used_arcnames: set[str] = set()
            for include_file in include_files:
                include_arcname = f"data/{include_file.name}"
                # Qualify colliding basenames so no include silently shadows another.
                counter = 2
                while include_arcname in used_arcnames:
                    include_arcname = f"data/{include_file.stem}_{counter}{include_file.suffix}"
                    counter += 1
                used_arcnames.add(include_arcname)
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
