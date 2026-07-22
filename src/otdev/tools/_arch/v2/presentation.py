"""Typed theme precedence and safe offline icon resolution."""

from __future__ import annotations

import base64
import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import (
    ArchitectureWorkspace,
    ContextStatus,
    ElementStyle,
    SourceLocation,
    Theme,
    ViewGraph,
)

_APPROVED_ICON_NAMESPACES = {"aws", "azure", "bootstrap", "gcp", "tech"}
_UNSAFE_ELEMENTS = {
    "animate",
    "animateMotion",
    "animateTransform",
    "embed",
    "foreignObject",
    "iframe",
    "object",
    "script",
    "set",
    "style",
}
_REMOTE_SCHEMES = ("data:", "file:", "ftp:", "http:", "https:", "javascript:")
_THEME_KEY = re.compile(r"^(system|application|component|user|interface|relationship|tag:[^:]+|entity:.+)$")

_CLEAN_STATUS_STYLES: dict[ContextStatus, ElementStyle] = {
    "out_of_scope": ElementStyle(color="#F5F5F5", border="#666666 dashed"),
    "future": ElementStyle(color="#E1D5E7", border="#9673A6 dashed"),
    "new": ElementStyle(color="#DAE8FC", border="#6C8EBF double"),
    "change": ElementStyle(color="#FFF2CC", border="#D6B656 solid"),
    "no_change": ElementStyle(color="#D5E8D4", border="#82B366 solid"),
    "decommission": ElementStyle(color="#F8CECC", border="#B85450 double"),
}

CLEAN_THEME = Theme(
    id="clean",
    name="Clean",
    elements={
        "system": ElementStyle(shape="rectangle", padding=16),
        "application": ElementStyle(shape="rectangle", padding=12),
        "component": ElementStyle(shape="rectangle", padding=10),
        "user": ElementStyle(shape="person"),
    },
    statuses=_CLEAN_STATUS_STYLES,
)


class PresentationError(ValueError):
    """Stable presentation validation error with optional authored source."""

    def __init__(
        self, code: str, message: str, *, source: SourceLocation | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.source = source


def _inventory_path() -> Path:
    return (
        Path(__file__).parents[1]
        / "frontend"
        / "compat"
        / "fixtures"
        / "icon-inventory.json"
    )


@lru_cache(maxsize=1)
def pinned_icon_inventory() -> dict[str, frozenset[str]]:
    """Load the build-pinned LikeC4 icon names used by validation and rendering."""
    payload = json.loads(_inventory_path().read_text(encoding="utf-8"))
    namespaces = payload["namespaces"]
    if set(namespaces) != _APPROVED_ICON_NAMESPACES:
        raise PresentationError(
            "arch.invalid_icon_inventory",
            "Pinned icon inventory does not match approved namespaces",
        )
    return {key: frozenset(value) for key, value in namespaces.items()}


def _local_name(value: str) -> str:
    return value.rsplit("}", maxsplit=1)[-1]


def _sanitize_svg(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    lowered = source.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise PresentationError("arch.unsafe_icon", f"SVG declarations are not allowed: {path}")
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        raise PresentationError("arch.unsafe_icon", f"Invalid SVG '{path}': {exc}") from exc
    if _local_name(root.tag) != "svg":
        raise PresentationError("arch.unsafe_icon", f"Local icon root must be svg: {path}")
    for element in root.iter():
        if _local_name(element.tag) in _UNSAFE_ELEMENTS:
            raise PresentationError(
                "arch.unsafe_icon",
                f"Unsafe SVG element '{_local_name(element.tag)}': {path}",
            )
        for attribute, raw in element.attrib.items():
            name = _local_name(attribute).lower()
            value = raw.strip().lower()
            if name.startswith("on"):
                raise PresentationError(
                    "arch.unsafe_icon",
                    f"SVG event handlers are not allowed: {path}",
                )
            if name in {"href", "src"} and value.startswith(_REMOTE_SCHEMES):
                raise PresentationError(
                    "arch.unsafe_icon",
                    f"External SVG references are not allowed: {path}",
                )
            if "url(" in value and "url(#" not in value:
                raise PresentationError(
                    "arch.unsafe_icon",
                    f"External SVG URL references are not allowed: {path}",
                )
    encoded = base64.b64encode(ET.tostring(root, encoding="utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def resolve_icon(
    *, value: str | None, workspace_root: Path, source: SourceLocation | None = None
) -> str | None:
    """Resolve pinned namespaces or a contained sanitized local SVG."""
    if value is None:
        return None
    icon = value.strip()
    if icon == "none":
        return None
    if icon.startswith("@icons/"):
        relative = Path(icon.removeprefix("@icons/"))
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".svg":
            raise PresentationError(
                "arch.unsafe_icon_path",
                f"Unsafe local icon path '{icon}'",
                source=source,
            )
        root = (workspace_root / "assets" / "icons").resolve()
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PresentationError(
                "arch.unsafe_icon_path",
                f"Local icon escapes assets/icons: '{icon}'",
                source=source,
            ) from exc
        if not candidate.is_file():
            raise PresentationError(
                "arch.missing_icon",
                f"Local icon does not exist: '{icon}'",
                source=source,
            )
        try:
            return _sanitize_svg(candidate)
        except PresentationError as exc:
            exc.source = source
            raise
    if ":" not in icon or icon.startswith(_REMOTE_SCHEMES):
        raise PresentationError(
            "arch.unknown_icon",
            f"Unknown or remote icon reference '{icon}'",
            source=source,
        )
    namespace, name = icon.split(":", maxsplit=1)
    inventory = pinned_icon_inventory()
    if namespace not in inventory or name not in inventory[namespace]:
        raise PresentationError(
            "arch.unknown_icon",
            f"Unknown pinned icon '{icon}'",
            source=source,
        )
    return icon


def _merge_styles(*styles: ElementStyle | None) -> ElementStyle | None:
    merged: dict[str, Any] = {}
    for style in styles:
        if style is not None:
            merged.update(style.model_dump(exclude_none=True, exclude_unset=True))
    return ElementStyle.model_validate(merged) if merged else None


def resolve_theme(*, workspace: ArchitectureWorkspace, theme_id: str | None) -> Theme:
    """Resolve selected/workspace/default theme over the bundled clean fallback."""
    configured = {theme.id: theme for theme in workspace.presentation.themes}

    def resolve(selected: str, chain: tuple[str, ...]) -> Theme:
        if selected == "clean":
            return CLEAN_THEME
        if selected in chain:
            cycle = " -> ".join((*chain[chain.index(selected) :], selected))
            raise PresentationError(
                "arch.cyclic_theme",
                f"Cyclic theme inheritance: {cycle}",
            )
        theme = configured.get(selected)
        if theme is None:
            raise PresentationError("arch.unknown_theme", f"Unknown theme '{selected}'")
        for key in theme.elements:
            if _THEME_KEY.fullmatch(key) is None:
                raise PresentationError(
                    "arch.invalid_theme_selector",
                    f"Unsupported theme element selector '{key}'",
                )
        parent = resolve(theme.extends or "clean", (*chain, selected))
        return Theme(
            id=theme.id,
            name=theme.name,
            extends=theme.extends,
            elements={**parent.elements, **theme.elements},
            statuses={**parent.statuses, **theme.statuses},
        )

    return resolve(theme_id or workspace.presentation.default_theme, ())


def resolve_graph_presentation(
    *,
    graph: ViewGraph,
    workspace: ArchitectureWorkspace,
    workspace_root: Path,
    view_styles: dict[str, ElementStyle] | None = None,
) -> ViewGraph:
    """Apply kind/tag/entity/status/view precedence and resolve all graph icons."""
    theme = resolve_theme(
        workspace=workspace,
        theme_id=graph.selection.selection.theme,
    )
    overrides = view_styles or {}
    color_by = graph.selection.selection.color_by
    palettes = workspace.presentation.palettes

    def status_style(kind: str, status: ContextStatus) -> ElementStyle | None:
        if color_by != "change_status":
            return None
        if kind not in {
            "system",
            "application",
            "component",
            "interface",
        }:
            return theme.statuses.get(status)
        colors = {
            "system": palettes.change_status.system,
            "application": palettes.change_status.application,
            "component": palettes.change_status.component,
            "interface": palettes.change_status.interface,
        }[kind]
        if status == "no_change":
            return colors.no_change
        if status == "change":
            return colors.changed
        if status == "new":
            return colors.added
        if status == "decommission":
            return colors.removed
        return theme.statuses.get(status)

    def tag_style(tags: list[str]) -> ElementStyle | None:
        if color_by != "tag":
            return None
        return next((palettes.tag[tag] for tag in tags if tag in palettes.tag), None)

    nodes = []
    for node in graph.nodes:
        tag_styles = [theme.elements.get(f"tag:{tag}") for tag in node.tags]
        style = _merge_styles(
            theme.elements.get(node.entity_kind),
            *tag_styles,
            status_style(node.entity_kind, node.context_status),
            tag_style(node.tags),
            theme.elements.get(f"entity:{node.id}"),
            node.style,
            overrides.get(node.id),
        )
        icon = resolve_icon(value=node.icon, workspace_root=workspace_root, source=node.source)
        nodes.append(node.model_copy(update={"style": style, "icon": icon}))
    edges = []
    for edge in graph.edges:
        integration_style = (
            palettes.integration_type.get(edge.integration_type)
            if color_by == "integration_type" and edge.integration_type is not None
            else None
        )
        style = _merge_styles(
            theme.elements.get(edge.entity_kind),
            status_style(edge.entity_kind, edge.context_status),
            integration_style,
            tag_style(edge.tags),
            theme.elements.get(f"entity:{edge.id}"),
            edge.style,
            overrides.get(edge.id),
        )
        edges.append(edge.model_copy(update={"style": style}))
    return graph.model_copy(update={"nodes": nodes, "edges": edges})
