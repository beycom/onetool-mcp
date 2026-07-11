"""System graph, diagram rendering, and solution-context helpers for arch pack."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError
from markupsafe import escape

from .config import ConfigResolutionError
from .models import (
    APP_REF_KEYS,
    ARROW_DIRECTIONS,
    DEFAULT_ARROW_DIRECTION,
    SHEET_INTERFACE,
    SHEET_PROJECT,
    SHEET_PROJECT_SCOPE,
    STD_APP_KEYS,
    STD_INTERFACE_KEYS,
    STD_PROJECT_KEYS,
    STD_PROJECT_SCOPE_KEYS,
    STD_SYS_KEYS,
    SYS_REF_KEYS,
    MissingDependencyError,
    first_value,
    option_as_bool,
    tags_for_row,
)
from .render_styles import (
    CHANGE_TYPE_STYLES,
    DIRECTION_STYLES,
    INTERACTION_TYPE_STYLES,
    normalize_interaction_type,
)

LEVEL_SYS = "sys"
LEVEL_APP = "app"
LEVEL_CMP = "cmp"
DETAIL_MATCH_PRIMARY = "match_primary"
CONNECT_LOWEST_VISIBLE = "lowest_visible"

# Fallback defaults for profile data options. Must match the bundled
# global_templates/arch.yaml profile values so custom profiles behave
# the same as the shipped one (guarded by a unit test).
DEFAULT_MERGE_INTERFACES = True
DEFAULT_SHOW_INTERFACE_LABELS = True
DEFAULT_SHOW_ARROWHEAD_LABELS = True
DEFAULT_INTERFACE_LABELS_TEMPLATE = "[{{ row.key }}] {{ row.name }} ({{ row.interaction_type }})"
DEFAULT_ARROWHEAD_LABELS_TEMPLATE = "{{ row.key }}"
DEFAULT_SECONDARY_SYSTEM_DETAIL = LEVEL_SYS
DEFAULT_SECONDARY_CONNECT_LEVEL = LEVEL_APP
DEFAULT_DIRECTION = "up"
PROJECT_ITEM_TYPES = {
    "sys": "system",
    "system": "system",
    "app": "application",
    "application": "application",
    "cmp": "component",
    "component": "component",
    "components": "component",
    "int": "interface",
    "interface": "interface",
}

MAX_LINE_WIDTH = 20
COMPONENT_MAX_LINE_WIDTH = 15

COMPONENT_CLASS_MAP = {
    "web": "Web",
    "db": "DB",
    "database": "DB",
    "file": "File",
    "storage": "File",
    "api": "API",
    "batch": "Batch",
    "queue": "Queue",
    "cmp": "Cmp",
    "component": "Cmp",
}
_COMPONENT_CLASSES = set(COMPONENT_CLASS_MAP.values())

_md_converter: Any | None = None


def _get_md_converter() -> Any:
    """Import markdown lazily and return a shared converter, raising
    MissingDependencyError when the optional dependency is absent."""
    global _md_converter
    if _md_converter is None:
        try:
            import markdown as md  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - import guard
            raise MissingDependencyError(
                "markdown is required for arch pack. Install with: pip install onetool-mcp[dev]"
            ) from exc
        _md_converter = md.Markdown(extensions=["nl2br"])
    return _md_converter


@dataclass(slots=True)
class EntityGraph:
    sys_rows: dict[str, dict[str, Any]]
    app_rows: dict[str, dict[str, Any]]
    cmp_rows: dict[str, dict[str, Any]]
    usr_rows: dict[str, dict[str, Any]]
    app_to_sys: dict[str, str]
    cmp_to_app: dict[str, str]
    cmp_to_sys: dict[str, str]
    usr_to_sys: dict[str, str]
    node_to_sys: dict[str, str]
    # Ordered children indexes (input row order preserved).
    sys_app_ids: dict[str, list[str]]
    app_cmp_rows: dict[str, list[dict[str, Any]]]
    sys_direct_cmp_rows: dict[str, list[dict[str, Any]]]


def title_case(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def render_markdown(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text.strip():
        return ""
    converter = _get_md_converter()
    converter.reset()
    # Escape first: python-markdown passes raw inline HTML through, and the
    # output lands in formatter:'html' table cells (XSS via workbook cells).
    rendered: str = converter.convert(str(escape(text)))
    return rendered


def first_tag_value(row: dict[str, Any]) -> str:
    tags = tags_for_row(row)
    if not tags:
        return ""
    return sorted(tags)[0]


def system_page_name(system_id: str) -> str:
    return f"{system_id}.html"


def project_page_name(project_id: str) -> str:
    return f"project-{project_id}.html"


def safe_output_fragment(value: str) -> str:
    """Sanitize a free-text value (e.g. a project stage) into a filename
    fragment. Single source of truth: the SVG writer (`arch.py`) and the page
    links built here must agree byte-for-byte or diagram links break."""
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value.strip())
    return cleaned.strip("._-") or "item"


def is_external_system(row: dict[str, Any]) -> bool:
    sys_type = first_value(row, ("system_type", "type"))
    if isinstance(sys_type, str) and sys_type.strip().lower() == "external":
        return True
    return "external" in tags_for_row(row)


def _collect_extra_keys(rows: list[dict[str, Any]], standard_keys: set[str]) -> list[str]:
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            if key.startswith("_"):
                continue
            if key in standard_keys:
                continue
            seen[key] = None
    return list(seen)


def _normalize_component_type(value: Any) -> str:
    if value is None:
        return "Cmp"
    text = str(value).strip()
    if not text:
        return "Cmp"
    mapped = COMPONENT_CLASS_MAP.get(text.lower())
    if mapped:
        return mapped
    return text


def _component_class_from_row(row: dict[str, Any]) -> str:
    value = first_value(row, ("component_type", "type", "cmp_type", "kind"))
    normalized = _normalize_component_type(value)
    return normalized if normalized in _COMPONENT_CLASSES else "Cmp"


def _component_type_label(row: dict[str, Any]) -> str:
    return _normalize_component_type(first_value(row, ("component_type", "type", "cmp_type", "kind")))


def build_entity_graph(*, entities: dict[str, list[dict[str, Any]]]) -> EntityGraph:
    sys_rows: dict[str, dict[str, Any]] = {}
    app_rows: dict[str, dict[str, Any]] = {}
    cmp_rows: dict[str, dict[str, Any]] = {}
    usr_rows: dict[str, dict[str, Any]] = {}

    for row in entities["sys"]:
        row_id = str(row.get("id", "")).strip()
        if row_id:
            sys_rows[row_id] = row

    for row in entities["app"]:
        row_id = str(row.get("id", "")).strip()
        if row_id:
            app_rows[row_id] = row

    for row in entities["cmp"]:
        row_id = str(row.get("id", "")).strip()
        if row_id:
            cmp_rows[row_id] = row

    for row in entities["usr"]:
        row_id = str(row.get("id", "")).strip()
        if row_id:
            usr_rows[row_id] = row

    app_to_sys: dict[str, str] = {}
    for app_id, row in app_rows.items():
        sys_id = str(first_value(row, SYS_REF_KEYS) or "").strip()
        if sys_id:
            app_to_sys[app_id] = sys_id

    cmp_to_app: dict[str, str] = {}
    cmp_to_sys: dict[str, str] = {}
    for cmp_id, row in cmp_rows.items():
        app_id = str(first_value(row, APP_REF_KEYS) or "").strip()
        if app_id:
            cmp_to_app[cmp_id] = app_id
            sys_id = app_to_sys.get(app_id, "")
            if sys_id:
                cmp_to_sys[cmp_id] = sys_id
        else:
            sys_id = str(first_value(row, SYS_REF_KEYS) or "").strip()
            if sys_id:
                cmp_to_sys[cmp_id] = sys_id

    usr_to_sys: dict[str, str] = {}
    for usr_id, row in usr_rows.items():
        app_id = str(first_value(row, APP_REF_KEYS) or "").strip()
        if app_id and app_id in app_to_sys:
            usr_to_sys[usr_id] = app_to_sys[app_id]

    node_to_sys: dict[str, str] = {}
    node_to_sys.update({sys_id: sys_id for sys_id in sys_rows})
    node_to_sys.update(app_to_sys)
    node_to_sys.update(cmp_to_sys)
    node_to_sys.update(usr_to_sys)

    sys_app_ids: dict[str, list[str]] = {}
    for row in entities["app"]:
        app_id = str(row.get("id", "")).strip()
        sys_id = str(first_value(row, SYS_REF_KEYS) or "").strip()
        if app_id and sys_id:
            sys_app_ids.setdefault(sys_id, []).append(app_id)

    app_cmp_rows: dict[str, list[dict[str, Any]]] = {}
    sys_direct_cmp_rows: dict[str, list[dict[str, Any]]] = {}
    for row in entities["cmp"]:
        app_id = str(first_value(row, APP_REF_KEYS) or "").strip()
        if app_id:
            app_cmp_rows.setdefault(app_id, []).append(row)
            continue
        sys_id = str(first_value(row, SYS_REF_KEYS) or "").strip()
        if sys_id:
            sys_direct_cmp_rows.setdefault(sys_id, []).append(row)

    return EntityGraph(
        sys_rows=sys_rows,
        app_rows=app_rows,
        cmp_rows=cmp_rows,
        usr_rows=usr_rows,
        app_to_sys=app_to_sys,
        cmp_to_app=cmp_to_app,
        cmp_to_sys=cmp_to_sys,
        usr_to_sys=usr_to_sys,
        node_to_sys=node_to_sys,
        sys_app_ids=sys_app_ids,
        app_cmp_rows=app_cmp_rows,
        sys_direct_cmp_rows=sys_direct_cmp_rows,
    )


def _sanitize_d2_id(name: str) -> str:
    return name.replace('"', '\\"')


def _quote_d2(label: str) -> str:
    escaped = label.replace('"', '\\"')
    return f'"{escaped}"'


def _wrap_label(name: str, max_width: int = MAX_LINE_WIDTH) -> str:
    if len(name) <= max_width:
        return _quote_d2(name)

    words: list[str] = []
    for word in name.split():
        while len(word) > max_width:
            words.append(word[:max_width])
            word = word[max_width:]
        if word:
            words.append(word)
    lines: list[str] = []
    current_line: list[str] = []
    current_len = 0

    for word in words:
        if current_len + len(word) + (1 if current_line else 0) <= max_width:
            current_line.append(word)
            current_len += len(word) + (1 if len(current_line) > 1 else 0)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_len = len(word)

    if current_line:
        lines.append(" ".join(current_line))

    return _quote_d2("\\n".join(lines))


def _interface_provider(row: dict[str, Any]) -> str:
    return str(row.get("provider") or "").strip()


def _interface_consumer(row: dict[str, Any]) -> str:
    return str(row.get("consumer") or "").strip()


def _interface_type(row: dict[str, Any]) -> str:
    return str(row.get("interaction_type") or "").strip()


def _interface_arrow_direction(row: dict[str, Any]) -> str:
    raw_value = row.get("arrow_direction")
    if raw_value is None or not str(raw_value).strip():
        return DEFAULT_ARROW_DIRECTION
    value = str(raw_value).strip().lower()
    if value not in ARROW_DIRECTIONS:
        raise ValueError(f"Invalid interface arrow_direction '{raw_value}'")
    return value


def _interface_label(row: dict[str, Any]) -> str:
    name = str(row.get("name") or row.get("id") or "interface").strip()
    interaction_type = _interface_type(row)
    if interaction_type:
        return f"{name} ({interaction_type})"
    return name


def _interface_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or "").strip()


def _interaction_class_for(interaction_type: str | None) -> str | None:
    """Map a raw `interaction_type` value to its D2 class name, or None if
    absent/unrecognized (D3 neutral fallback)."""
    normalized = normalize_interaction_type(interaction_type)
    if normalized is None:
        return None
    return INTERACTION_TYPE_STYLES[normalized]["d2_class"]


def _change_class_for(change_type: str | None) -> str | None:
    """Map a raw `change_type` value to its D2 class name, or None for
    `existing`/absent/unrecognized values (D2 neutral fallback)."""
    if not change_type:
        return None
    style = CHANGE_TYPE_STYLES.get(str(change_type).strip().lower())
    return style["d2_class"] if style else None


def _change_type_badge_html(change_type: str) -> str:
    """Render a colored badge for a scope-table `change_type` cell; `existing`
    and unrecognized values render as plain text (D5)."""
    style = CHANGE_TYPE_STYLES.get(str(change_type).strip().lower())
    if style is None:
        return str(escape(change_type))
    return f'<span class="badge" style="background:{style["color"]}">{style["label"]}</span>'


def _project_scope_item_cell_html(*, item_type: str, item_id: str, graph: EntityGraph) -> str:
    """Render a scope-table item cell: a link to the owning system's page
    when `item_id` resolves to a system, or an app/component owned by a
    system; plain text otherwise (interfaces, users, unresolved ids — D5
    'Scope table links items to system pages')."""
    owning_sys = _project_system_for_item(item_type=item_type, item_id=item_id, graph=graph)
    if owning_sys:
        return f'<a href="{escape(system_page_name(owning_sys))}">{escape(item_id)}</a>'
    return str(escape(item_id))


def _class_attr(classes: list[str | None]) -> str:
    """Render a D2 `class` attribute value from an ordered list of optional
    class names: a scalar `X` when exactly one class is present, an array
    `[A; B]` when 2+ are present (D2/D3 byte-identical-neutral-output rule).
    Registered as the `class_attr` Jinja global for system.d2.j2 and
    project.d2.j2 so templates never hardcode the scalar-vs-array choice."""
    present = [c for c in classes if c]
    if len(present) > 1:
        return "[" + "; ".join(present) + "]"
    return present[0] if present else ""


def _interaction_type_badge_html(interaction_type: str) -> str:
    """Render a badge for a recognized interfaces-table `interaction_type`
    cell; unrecognized values render as plain text (spec: interfaces table
    shows interaction type badge)."""
    normalized = normalize_interaction_type(interaction_type)
    if normalized is None:
        return str(escape(interaction_type))
    style = INTERACTION_TYPE_STYLES[normalized]
    return f'<span class="badge">{style["label"]}</span>'


# Static descriptive list mirroring COMPONENT_CLASS_MAP plus the
# Person/External/System/App node classes (D6 legend group "node classes").
# No colors here: legend swatch colors come exclusively from render_styles.py
# data (CHANGE_TYPE_STYLES/INTERACTION_TYPE_STYLES/DIRECTION_STYLES) per the
# "no hex values hardcoded in templates" rule; this list is plain text only.
_NODE_CLASS_LEGEND: tuple[dict[str, str], ...] = (
    {"label": "Person", "description": "A user/actor interacting with the solution"},
    {"label": "External System", "description": "A system outside the solution boundary"},
    {"label": "System", "description": "A system in the solution"},
    {"label": "App", "description": "An application owned by a system"},
    {"label": "Web", "description": "Web-facing component"},
    {"label": "DB", "description": "Database component"},
    {"label": "File", "description": "File/storage component"},
    {"label": "API", "description": "API component"},
    {"label": "Batch", "description": "Batch-processing component"},
    {"label": "Queue", "description": "Queue component"},
    {"label": "Cmp", "description": "Generic component"},
)


def _build_legend_context() -> dict[str, Any]:
    """Legend data shared by system and project pages (D6): node classes
    (static text), edge direction colors, interaction-type stroke patterns,
    and change-type swatches — all sourced from `render_styles.py` (plus the
    static node-class list), never hardcoded in the template. Identical for
    both page kinds; the including page's `show_change_types` flag controls
    whether the change-type group is rendered."""
    return {
        "node_classes": [dict(item) for item in _NODE_CLASS_LEGEND],
        "direction_colors": [
            {"label": style["label"], "color": style["color"]}
            for style in DIRECTION_STYLES.values()
        ],
        "interaction_types": [
            {
                "label": style["label"],
                "stroke_dash": style["stroke_dash"],
                "stroke_width": style["stroke_width"],
            }
            for style in INTERACTION_TYPE_STYLES.values()
        ],
        "change_types": [
            {"label": style["label"], "color": style["color"]}
            for style in CHANGE_TYPE_STYLES.values()
        ],
    }


def _profile_option_choice(
    *,
    profile_data: dict[str, Any],
    option_name: str,
    default: str,
    choices: set[str],
) -> str:
    value = profile_data.get(option_name, default)
    if not isinstance(value, str):
        raise ConfigResolutionError(
            f"tools.arch.profiles.<name>.data.{option_name} must be one of {sorted(choices)}, got {value!r}"
        )
    normalized = value.strip()
    if normalized not in choices:
        raise ConfigResolutionError(
            f"tools.arch.profiles.<name>.data.{option_name} must be one of {sorted(choices)}, got {value!r}"
        )
    return normalized


def _secondary_detail_for_level(*, level: str, secondary_system_detail: str) -> str:
    if secondary_system_detail == DETAIL_MATCH_PRIMARY:
        return level
    return secondary_system_detail


def _profile_option_label_template(*, profile_data: dict[str, Any], option_name: str, default: str) -> str:
    value = profile_data.get(option_name, default)
    if not isinstance(value, str):
        raise ConfigResolutionError(
            f"tools.arch.profiles.<name>.data.{option_name} must be a template string"
        )
    text = value.strip()
    if not text:
        raise ConfigResolutionError(
            f"tools.arch.profiles.<name>.data.{option_name} must be a non-empty template string"
        )
    return text


def _interface_template_row(*, row: dict[str, Any]) -> dict[str, str]:
    row_model: dict[str, str] = {}
    for key, value in row.items():
        if str(key).startswith("_"):
            continue
        if value is None:
            row_model[str(key)] = ""
            continue
        row_model[str(key)] = str(value)

    row_model.setdefault("id", _interface_id(row))
    row_model.setdefault("key", str(row.get("key") or "").strip())
    row_model.setdefault("name", str(row.get("name") or row_model["id"] or "interface").strip())
    row_model.setdefault("provider", _interface_provider(row))
    row_model.setdefault("consumer", _interface_consumer(row))
    row_model.setdefault("interaction_type", _interface_type(row))
    row_model.setdefault("arrow_direction", _interface_arrow_direction(row))
    row_model.setdefault("label", _interface_label(row))
    return row_model


def _compile_label_templates(profile_data: dict[str, Any]) -> tuple[Any, Any]:
    """Compile the profile's interface/arrowhead label templates once per view."""
    interface_labels_template = _profile_option_label_template(
        profile_data=profile_data,
        option_name="interface_labels",
        default=DEFAULT_INTERFACE_LABELS_TEMPLATE,
    )
    arrowhead_labels_template = _profile_option_label_template(
        profile_data=profile_data,
        option_name="arrowhead_labels",
        default=DEFAULT_ARROWHEAD_LABELS_TEMPLATE,
    )
    template_env = Environment(autoescape=False, undefined=StrictUndefined)
    return (
        template_env.from_string(interface_labels_template),
        template_env.from_string(arrowhead_labels_template),
    )


def _render_compiled_interface_option(*, template: Any, row: dict[str, Any], option_name: str) -> str:
    try:
        rendered = template.render(row=_interface_template_row(row=row))
    except TemplateError as exc:
        raise ConfigResolutionError(
            f"Failed rendering tools.arch.profiles.<name>.data.{option_name}: {exc}"
        ) from exc
    return str(rendered).strip()


def _endpoint_system_id(*, endpoint_id: str, graph: EntityGraph) -> str | None:
    # node_to_sys already covers every resolvable case: systems map to
    # themselves and apps/components/users appear only when they map to one.
    return graph.node_to_sys.get(endpoint_id)


def _endpoint_owner_sys(*, endpoint_id: str, graph: EntityGraph) -> str | None:
    """Owning system id for an endpoint; unknown ids count as external system ids."""
    resolved = _endpoint_system_id(endpoint_id=endpoint_id, graph=graph)
    if resolved is not None:
        return resolved
    if (
        endpoint_id not in graph.usr_rows
        and endpoint_id not in graph.app_rows
        and endpoint_id not in graph.cmp_rows
    ):
        return endpoint_id
    return None


def _system_interfaces(*, system_id: str, entities: dict[str, list[dict[str, Any]]], graph: EntityGraph) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in entities[SHEET_INTERFACE]:
        provider = _interface_provider(row)
        consumer = _interface_consumer(row)
        if not provider or not consumer:
            continue

        provider_sys = _endpoint_owner_sys(endpoint_id=provider, graph=graph)
        consumer_sys = _endpoint_owner_sys(endpoint_id=consumer, graph=graph)

        if provider_sys == system_id or consumer_sys == system_id:
            result.append(row)

    return result


def _related_user_rows(*, system_id: str, entities: dict[str, list[dict[str, Any]]], graph: EntityGraph) -> list[dict[str, Any]]:
    # Users reference apps; the system id itself is accepted as a direct reference.
    focus_ids = {system_id}
    for app_id, app_sys in graph.app_to_sys.items():
        if app_sys == system_id:
            focus_ids.add(app_id)

    related: list[dict[str, Any]] = []
    for row in entities["usr"]:
        usr_id = str(row.get("id", "")).strip()
        if not usr_id:
            continue

        app_id = str(first_value(row, APP_REF_KEYS) or "").strip()
        if app_id in focus_ids:
            related.append(row)
            continue

        if graph.usr_to_sys.get(usr_id) == system_id:
            related.append(row)

    return related


def _connect_level_rank(level: str) -> int:
    return {LEVEL_SYS: 0, LEVEL_APP: 1, LEVEL_CMP: 2}[level]


def _connect_level_allows(*, configured_level: str, target_level: str, rendered_level: str) -> bool:
    if configured_level == CONNECT_LOWEST_VISIBLE:
        return _connect_level_rank(rendered_level) >= _connect_level_rank(target_level)
    return (
        _connect_level_rank(configured_level) >= _connect_level_rank(target_level)
        and _connect_level_rank(rendered_level) >= _connect_level_rank(target_level)
    )


def _secondary_app_path(
    *,
    app_id: str,
    app_sys: str,
    rendered_level: str,
    connect_level: str,
) -> str | None:
    if _connect_level_allows(
        configured_level=connect_level,
        target_level=LEVEL_APP,
        rendered_level=rendered_level,
    ):
        return f'"{_sanitize_d2_id(app_sys)}"."{_sanitize_d2_id(app_id)}"'
    return None


def _secondary_component_path(
    *,
    cmp_id: str,
    cmp_sys: str,
    cmp_app: str | None,
    rendered_level: str,
    connect_level: str,
) -> str | None:
    if _connect_level_allows(
        configured_level=connect_level,
        target_level=LEVEL_CMP,
        rendered_level=rendered_level,
    ):
        if cmp_app:
            return (
                f'"{_sanitize_d2_id(cmp_sys)}".'
                f'"{_sanitize_d2_id(cmp_app)}".'
                f'"{_sanitize_d2_id(cmp_id)}"'
            )
        return f'"{_sanitize_d2_id(cmp_sys)}"."{_sanitize_d2_id(cmp_id)}"'

    if cmp_app and _connect_level_allows(
        configured_level=connect_level,
        target_level=LEVEL_APP,
        rendered_level=rendered_level,
    ):
        return f'"{_sanitize_d2_id(cmp_sys)}"."{_sanitize_d2_id(cmp_app)}"'

    return None


def _directed_edge_parts(
    *,
    provider_path: str,
    consumer_path: str,
    arrow_direction: str,
) -> tuple[str, str, str]:
    if arrow_direction == "provider_to_consumer":
        return provider_path, "->", consumer_path
    if arrow_direction == "none":
        return consumer_path, "--", provider_path
    if arrow_direction == "bidirectional":
        return consumer_path, "<->", provider_path
    return consumer_path, "->", provider_path


def _node_path_for_level(
    *,
    endpoint_id: str,
    level: str,
    focus_system_id: str,
    graph: EntityGraph,
    secondary_system_levels: dict[str, str] | None = None,
    secondary_connect_level: str = LEVEL_APP,
) -> str:
    if endpoint_id in graph.usr_rows:
        return f'"{_sanitize_d2_id(endpoint_id)}"'

    if endpoint_id in graph.app_rows:
        app_sys = graph.app_to_sys.get(endpoint_id)
        if app_sys == focus_system_id and level in {LEVEL_APP, LEVEL_CMP}:
            return f'"{_sanitize_d2_id(focus_system_id)}"."{_sanitize_d2_id(endpoint_id)}"'
        if app_sys:
            if app_sys != focus_system_id:
                rendered_level = (secondary_system_levels or {}).get(app_sys, LEVEL_SYS)
                app_path = _secondary_app_path(
                    app_id=endpoint_id,
                    app_sys=app_sys,
                    rendered_level=rendered_level,
                    connect_level=secondary_connect_level,
                )
                if app_path is not None:
                    return app_path
            return f'"{_sanitize_d2_id(app_sys)}"'
        return f'"{_sanitize_d2_id(endpoint_id)}"'

    if endpoint_id in graph.cmp_rows:
        cmp_sys = graph.cmp_to_sys.get(endpoint_id)
        cmp_app = graph.cmp_to_app.get(endpoint_id)
        if cmp_sys == focus_system_id:
            if level == LEVEL_CMP:
                if cmp_app:
                    return (
                        f'"{_sanitize_d2_id(focus_system_id)}".'
                        f'"{_sanitize_d2_id(cmp_app)}".'
                        f'"{_sanitize_d2_id(endpoint_id)}"'
                    )
                return f'"{_sanitize_d2_id(focus_system_id)}"."{_sanitize_d2_id(endpoint_id)}"'
            if level == LEVEL_APP and cmp_app:
                return f'"{_sanitize_d2_id(focus_system_id)}"."{_sanitize_d2_id(cmp_app)}"'
            return f'"{_sanitize_d2_id(focus_system_id)}"'
        if cmp_sys:
            rendered_level = (secondary_system_levels or {}).get(cmp_sys, LEVEL_SYS)
            cmp_path = _secondary_component_path(
                cmp_id=endpoint_id,
                cmp_sys=cmp_sys,
                cmp_app=cmp_app or None,
                rendered_level=rendered_level,
                connect_level=secondary_connect_level,
            )
            if cmp_path is not None:
                return cmp_path
            return f'"{_sanitize_d2_id(cmp_sys)}"'
        return f'"{_sanitize_d2_id(endpoint_id)}"'

    if endpoint_id in graph.sys_rows:
        return f'"{_sanitize_d2_id(endpoint_id)}"'

    resolved_sys = _endpoint_system_id(endpoint_id=endpoint_id, graph=graph)
    if resolved_sys:
        return f'"{_sanitize_d2_id(resolved_sys)}"'

    return f'"{_sanitize_d2_id(endpoint_id)}"'


def _system_node_name(system_id: str, graph: EntityGraph) -> str:
    row = graph.sys_rows.get(system_id)
    if row is not None:
        return str(row.get("name") or system_id)
    return system_id.upper()


# Matches a `content="..."` attribute anywhere inside the root `<svg>`
# opening tag. The attribute value is fully XML-escaped by `inject_content`
# (`drawio.py`, via `ElementTree`), so it never contains a raw `"` or `>` --
# the opening tag's boundary (first unescaped `>`) is therefore unambiguous
# and this regex, scoped to that substring below, cannot match past it
# (design D9).
_SVG_CONTENT_ATTR_RE = re.compile(r'\s+content="[^"]*"')


def svg_markup(svg_text: str) -> str:
    """Slice `svg_text` down to the `<svg ...>` root element and onward,
    stripping the draw.io `content` attribute (design D9) so inline page
    markup never carries the embedded model -- it exists only in the
    standalone SVG file."""
    marker = "<svg"
    idx = svg_text.find(marker)
    if idx == -1:
        return svg_text
    markup = svg_text[idx:]
    tag_close = markup.find(">")
    if tag_close == -1:
        return markup
    opening_tag = _SVG_CONTENT_ATTR_RE.sub("", markup[: tag_close + 1], count=1)
    return opening_tag + markup[tag_close + 1 :]


@dataclass(frozen=True, slots=True)
class ProjectScope:
    """Project-stage scoping for `_build_system_block` (design D3): child
    filtering by the stage's included ids plus change-class decoration."""

    explicit_system_ids: set[str]
    included_app_ids: set[str]
    included_cmp_ids: set[str]
    change_lookup: dict[tuple[str, str], str]


def _build_system_block(
    *,
    system_id: str,
    level: str,
    graph: EntityGraph,
    scope: ProjectScope | None = None,
) -> dict[str, Any]:
    row = graph.sys_rows.get(system_id)
    system_name = str((row or {}).get("name") or system_id)
    # All nodes in this block (the system itself and its apps/components)
    # belong to `system_id`, so they all link to that system's page (D4).
    system_link = f"./{system_page_name(system_id)}"
    block: dict[str, Any] = {
        "id": _sanitize_d2_id(system_id),
        "label": _quote_d2(system_name),
        "placeholder": False,
        "direct_components": [],
        "apps": [],
        "link": system_link,
    }
    if scope is not None:
        system_change_class = _resolve_change_class(scope.change_lookup, "system", system_id)
        if system_change_class:
            block["change_class"] = system_change_class

    app_ids = graph.sys_app_ids.get(system_id, [])
    cmp_rows_direct = graph.sys_direct_cmp_rows.get(system_id, [])

    # Placeholder rules differ (D3): without scope, a childless block is a
    # placeholder up front; with scope, placeholder is re-set only after
    # filtering leaves no children (bottom of this function).
    include_all = True
    if scope is None:
        if level == LEVEL_SYS or (not app_ids and not cmp_rows_direct):
            block["placeholder"] = True
            return block
    else:
        if level == LEVEL_SYS:
            block["placeholder"] = True
            return block
        include_all = system_id in scope.explicit_system_ids
        app_ids = [
            app_id for app_id in app_ids if include_all or app_id in scope.included_app_ids
        ]
        cmp_rows_direct = [
            cmp_row
            for cmp_row in cmp_rows_direct
            if include_all or str(cmp_row.get("id", "")).strip() in scope.included_cmp_ids
        ]

    if level == LEVEL_CMP:
        for cmp_row in cmp_rows_direct:
            cmp_id = str(cmp_row.get("id", "")).strip()
            if not cmp_id:
                continue
            direct_component: dict[str, Any] = {
                "id": _sanitize_d2_id(cmp_id),
                "label": _wrap_label(str(cmp_row.get("name") or cmp_id), COMPONENT_MAX_LINE_WIDTH),
                "class": _component_class_from_row(cmp_row),
                "link": system_link,
            }
            if scope is not None:
                cmp_change_class = _resolve_change_class(scope.change_lookup, "component", cmp_id)
                if cmp_change_class:
                    direct_component["change_class"] = cmp_change_class
            block["direct_components"].append(direct_component)

    for app_id in app_ids:
        app_row = graph.app_rows[app_id]
        app_block: dict[str, Any] = {
            "id": _sanitize_d2_id(app_id),
            "label": _wrap_label(str(app_row.get("name") or app_id)),
            "components": [],
            "link": system_link,
        }
        if scope is not None:
            app_change_class = _resolve_change_class(scope.change_lookup, "application", app_id)
            if app_change_class:
                app_block["change_class"] = app_change_class
        if level == LEVEL_CMP:
            for cmp_row in graph.app_cmp_rows.get(app_id, []):
                cmp_id = str(cmp_row.get("id", "")).strip()
                if not cmp_id:
                    continue
                if scope is not None and not include_all and cmp_id not in scope.included_cmp_ids:
                    continue
                app_component: dict[str, Any] = {
                    "id": _sanitize_d2_id(cmp_id),
                    "label": _wrap_label(str(cmp_row.get("name") or cmp_id), COMPONENT_MAX_LINE_WIDTH),
                    "class": _component_class_from_row(cmp_row),
                    "link": system_link,
                }
                if scope is not None:
                    cmp_change_class = _resolve_change_class(scope.change_lookup, "component", cmp_id)
                    if cmp_change_class:
                        app_component["change_class"] = cmp_change_class
                app_block["components"].append(app_component)
        block["apps"].append(app_block)

    if scope is not None and not block["apps"] and not block["direct_components"]:
        block["placeholder"] = True
    return block


def build_system_view(
    *,
    system_id: str,
    level: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    """Build the `model.system_view` render-context dict: nodes, nesting,
    and interface edges for a system-level diagram (`sys`/`app`/`cmp`).

    This is the structure `build_system_d2` templates into D2 source *and*
    the same structure the draw.io emitter's `build_mxfile`
    (`_arch/drawio.py`, design D1/D2) consumes to embed an editable model in
    the rendered SVG -- both read from this single computation so the two
    representations of the diagram never drift apart."""
    level_name = {"sys": "System", "app": "Application", "cmp": "Component"}[level]
    title_name = _system_node_name(system_id, graph)
    merge_interfaces = option_as_bool(profile_data.get("merge_interfaces"), default=DEFAULT_MERGE_INTERFACES)
    show_interface_labels = option_as_bool(
        profile_data.get("show_interface_labels"), default=DEFAULT_SHOW_INTERFACE_LABELS
    )
    show_arrowhead_labels = option_as_bool(
        profile_data.get("show_arrowhead_labels"), default=DEFAULT_SHOW_ARROWHEAD_LABELS
    )
    secondary_system_detail = _profile_option_choice(
        profile_data=profile_data,
        option_name="secondary_system_detail",
        default=DEFAULT_SECONDARY_SYSTEM_DETAIL,
        choices={LEVEL_SYS, LEVEL_APP, LEVEL_CMP, DETAIL_MATCH_PRIMARY},
    )
    secondary_connect_level = _profile_option_choice(
        profile_data=profile_data,
        option_name="secondary_system_connect_level",
        default=DEFAULT_SECONDARY_CONNECT_LEVEL,
        choices={LEVEL_SYS, LEVEL_APP, LEVEL_CMP, CONNECT_LOWEST_VISIBLE},
    )
    effective_secondary_level = _secondary_detail_for_level(
        level=level,
        secondary_system_detail=secondary_system_detail,
    )

    interface_label_tpl, arrowhead_label_tpl = _compile_label_templates(profile_data)

    interfaces = _system_interfaces(system_id=system_id, entities=entities, graph=graph)
    users = _related_user_rows(system_id=system_id, entities=entities, graph=graph)

    related_system_ids: set[str] = set()
    external_system_ids: set[str] = set()
    for row in interfaces:
        provider = _interface_provider(row)
        consumer = _interface_consumer(row)
        provider_sys = _endpoint_owner_sys(endpoint_id=provider, graph=graph)
        consumer_sys = _endpoint_owner_sys(endpoint_id=consumer, graph=graph)

        if provider_sys and provider_sys != system_id:
            if provider_sys in graph.sys_rows and not is_external_system(graph.sys_rows[provider_sys]):
                related_system_ids.add(provider_sys)
            else:
                external_system_ids.add(provider_sys)
        if consumer_sys and consumer_sys != system_id:
            if consumer_sys in graph.sys_rows and not is_external_system(graph.sys_rows[consumer_sys]):
                related_system_ids.add(consumer_sys)
            else:
                external_system_ids.add(consumer_sys)

    user_nodes: list[dict[str, str]] = []
    for user_row in users:
        user_id = str(user_row.get("id", "")).strip()
        if not user_id:
            continue
        user_name = str(user_row.get("name") or user_id)
        user_nodes.append({"id": _sanitize_d2_id(user_id), "label": _quote_d2(user_name)})

    external_nodes: list[dict[str, str]] = []
    for ext_id in sorted(external_system_ids):
        ext_name = _system_node_name(ext_id, graph)
        external_nodes.append({"id": _sanitize_d2_id(ext_id), "label": _quote_d2(ext_name)})

    system_blocks: list[dict[str, Any]] = [
        _build_system_block(system_id=system_id, level=level, graph=graph)
    ]
    secondary_system_levels: dict[str, str] = {}
    for rel_id in sorted(related_system_ids):
        secondary_system_levels[rel_id] = effective_secondary_level
        system_blocks.append(
            _build_system_block(
                system_id=rel_id,
                level=effective_secondary_level,
                graph=graph,
            )
        )

    interface_edges: list[dict[str, Any]] = []
    merged_edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in interfaces:
        provider = _interface_provider(row)
        consumer = _interface_consumer(row)
        if not provider or not consumer:
            continue

        provider_path = _node_path_for_level(
            endpoint_id=provider,
            level=level,
            focus_system_id=system_id,
            graph=graph,
            secondary_system_levels=secondary_system_levels,
            secondary_connect_level=secondary_connect_level,
        )
        consumer_path = _node_path_for_level(
            endpoint_id=consumer,
            level=level,
            focus_system_id=system_id,
            graph=graph,
            secondary_system_levels=secondary_system_levels,
            secondary_connect_level=secondary_connect_level,
        )
        arrow_direction = _interface_arrow_direction(row)
        start_path, operator, end_path = _directed_edge_parts(
            provider_path=provider_path,
            consumer_path=consumer_path,
            arrow_direction=arrow_direction,
        )

        if start_path == end_path:
            continue

        # Focus-direction styling only applies to directed edges.
        direction_class = "Interface"
        if arrow_direction in {"consumer_to_provider", "provider_to_consumer"}:
            provider_sys = _endpoint_owner_sys(endpoint_id=provider, graph=graph)
            consumer_sys = _endpoint_owner_sys(endpoint_id=consumer, graph=graph)
            start_sys, end_sys = consumer_sys, provider_sys
            if arrow_direction == "provider_to_consumer":
                start_sys, end_sys = provider_sys, consumer_sys
            if start_sys == system_id:
                direction_class = "InterfaceFromFocus"
            elif end_sys == system_id:
                direction_class = "InterfaceToFocus"

        interaction_class = _interaction_class_for(row.get("interaction_type"))

        if show_interface_labels:
            edge_label = _render_compiled_interface_option(
                template=interface_label_tpl,
                row=row,
                option_name="interface_labels",
            )
            edge_label = edge_label or _interface_label(row)
        else:
            edge_label = ""

        arrowhead_label = ""
        if show_arrowhead_labels:
            arrowhead_label = _render_compiled_interface_option(
                template=arrowhead_label_tpl,
                row=row,
                option_name="arrowhead_labels",
            )

        if merge_interfaces:
            merged_key = (start_path, operator, end_path, direction_class)
            merged_edge = merged_edges.get(merged_key)
            if merged_edge is None:
                merged_edge = {
                    "start_path": start_path,
                    "operator": operator,
                    "end_path": end_path,
                    "direction_class": direction_class,
                    "labels": [],
                    "arrowheads": [],
                }
                # First row in the merge group determines the interaction
                # stroke pattern; interaction_type is not part of the merge
                # key, so later rows in the same group cannot override it.
                if interaction_class:
                    merged_edge["interaction_class"] = interaction_class
                merged_edges[merged_key] = merged_edge
            if edge_label not in merged_edge["labels"]:
                merged_edge["labels"].append(edge_label)
            if arrowhead_label and arrowhead_label not in merged_edge["arrowheads"]:
                merged_edge["arrowheads"].append(arrowhead_label)
            continue

        edge_entry: dict[str, Any] = {
            "start_path": start_path,
            "operator": operator,
            "end_path": end_path,
            "label": edge_label.replace('"', '\\"'),
            "direction_class": direction_class,
            "source_arrowhead_id": arrowhead_label.replace('"', '\\"'),
            "target_arrowhead_id": arrowhead_label.replace('"', '\\"'),
        }
        if interaction_class:
            edge_entry["interaction_class"] = interaction_class
        interface_edges.append(edge_entry)

    if merge_interfaces:
        for merged_edge in merged_edges.values():
            arrowhead_id = "\\n".join(str(item) for item in merged_edge["arrowheads"])
            merged_entry: dict[str, Any] = {
                "start_path": str(merged_edge["start_path"]),
                "operator": str(merged_edge["operator"]),
                "end_path": str(merged_edge["end_path"]),
                "label": "\\n".join(str(item) for item in merged_edge["labels"]).replace('"', '\\"'),
                "direction_class": str(merged_edge["direction_class"]),
                "source_arrowhead_id": arrowhead_id.replace('"', '\\"'),
                "target_arrowhead_id": arrowhead_id.replace('"', '\\"'),
            }
            if merged_edge.get("interaction_class"):
                merged_entry["interaction_class"] = str(merged_edge["interaction_class"])
            interface_edges.append(merged_entry)

    return {
        "title_name": title_name,
        "level_name": level_name,
        "user_nodes": user_nodes,
        "external_nodes": external_nodes,
        "system_blocks": system_blocks,
        "interface_edges": interface_edges,
    }


def build_system_d2(
    *,
    system_id: str,
    level: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    template_path: Any,
    profile_data: dict[str, Any],
    system_view: dict[str, Any] | None = None,
) -> str:
    """Render D2 source for a system-level diagram. `system_view`, if not
    supplied, is built fresh from `entities`/`graph`/`profile_data` (via
    `build_system_view`); callers that also need the render context for the
    draw.io emitter (`_generate_solution` in `arch.py`) should build it once
    and pass it in here to avoid recomputing it."""
    if system_view is None:
        system_view = build_system_view(
            system_id=system_id,
            level=level,
            entities=entities,
            graph=graph,
            profile_data=profile_data,
        )

    env = Environment(loader=FileSystemLoader(str(template_path.parent)), autoescape=False, undefined=StrictUndefined)
    env.globals["class_attr"] = _class_attr
    env.globals["quote_d2"] = _quote_d2
    template = env.get_template(template_path.name)
    render_context = {
        "model": {"system_view": system_view},
        "profile_data": dict(profile_data),
    }
    try:
        rendered = template.render(**render_context)
    except TemplateError as exc:
        raise ConfigResolutionError(
            "Invalid tools.arch.profiles.<name>.system_diagram template "
            f"at '{template_path}': {exc}. "
            "Use only model.system_view.* and profile_data in system.d2.j2."
        ) from exc
    return rendered.strip() + "\n"


def project_stage_ids(*, project_id: str, entities: dict[str, list[dict[str, Any]]]) -> list[str]:
    seen: dict[str, None] = {}
    for row in entities.get(SHEET_PROJECT_SCOPE, []):
        if str(first_value(row, ("project", "project_id")) or "").strip() != project_id:
            continue
        stage = str(row.get("stage") or "").strip()
        if stage:
            seen[stage] = None
    return list(seen)


def _project_row(*, project_id: str, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    for row in entities.get(SHEET_PROJECT, []):
        if str(row.get("id") or "").strip() == project_id:
            return row
    return None


def _project_option_choice(*, row: dict[str, Any], field: str, default: str, choices: set[str]) -> str:
    value = row.get(field, default)
    if value is None or not str(value).strip():
        return default
    normalized = str(value).strip().lower()
    if normalized not in choices:
        raise ValueError(f"Project {field} must be one of {sorted(choices)}")
    return normalized


def _project_scope_rows(
    *,
    project_id: str,
    stage: str | None,
    entities: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in entities.get(SHEET_PROJECT_SCOPE, []):
        if str(first_value(row, ("project", "project_id")) or "").strip() != project_id:
            continue
        if stage is not None and str(row.get("stage") or "").strip() != stage:
            continue
        rows.append(row)
    return rows


def _project_scope_item_type(row: dict[str, Any]) -> str:
    return PROJECT_ITEM_TYPES.get(str(row.get("item_type") or "").strip().lower(), "")


def _project_system_for_item(*, item_type: str, item_id: str, graph: EntityGraph) -> str | None:
    if item_type == "system":
        return item_id if item_id in graph.sys_rows else None
    if item_type == "application":
        return graph.app_to_sys.get(item_id)
    if item_type == "component":
        return graph.cmp_to_sys.get(item_id)
    return None


def _project_endpoint_path(
    *,
    endpoint_id: str,
    detail_level: str,
    connect_level: str,
    graph: EntityGraph,
) -> str:
    if endpoint_id in graph.usr_rows:
        return f'"{_sanitize_d2_id(endpoint_id)}"'

    if endpoint_id in graph.sys_rows:
        return f'"{_sanitize_d2_id(endpoint_id)}"'

    if endpoint_id in graph.app_rows:
        app_sys = graph.app_to_sys.get(endpoint_id)
        if not app_sys:
            return f'"{_sanitize_d2_id(endpoint_id)}"'
        app_path = _secondary_app_path(
            app_id=endpoint_id,
            app_sys=app_sys,
            rendered_level=detail_level,
            connect_level=connect_level,
        )
        return app_path if app_path is not None else f'"{_sanitize_d2_id(app_sys)}"'

    if endpoint_id in graph.cmp_rows:
        cmp_sys = graph.cmp_to_sys.get(endpoint_id)
        cmp_app = graph.cmp_to_app.get(endpoint_id)
        if not cmp_sys:
            return f'"{_sanitize_d2_id(endpoint_id)}"'
        cmp_path = _secondary_component_path(
            cmp_id=endpoint_id,
            cmp_sys=cmp_sys,
            cmp_app=cmp_app or None,
            rendered_level=detail_level,
            connect_level=connect_level,
        )
        return cmp_path if cmp_path is not None else f'"{_sanitize_d2_id(cmp_sys)}"'

    resolved_sys = _endpoint_system_id(endpoint_id=endpoint_id, graph=graph)
    if resolved_sys:
        return f'"{_sanitize_d2_id(resolved_sys)}"'
    return f'"{_sanitize_d2_id(endpoint_id)}"'


def _add_project_endpoint_context(
    *,
    endpoint_id: str,
    detail_level: str,
    connect_level: str,
    graph: EntityGraph,
    system_ids: set[str],
    app_ids: set[str],
    cmp_ids: set[str],
    user_ids: set[str],
) -> None:
    if endpoint_id in graph.usr_rows:
        user_ids.add(endpoint_id)
        return
    if endpoint_id in graph.sys_rows:
        system_ids.add(endpoint_id)
        return
    if endpoint_id in graph.app_rows:
        app_sys = graph.app_to_sys.get(endpoint_id)
        if app_sys:
            system_ids.add(app_sys)
            if _connect_level_allows(
                configured_level=connect_level,
                target_level=LEVEL_APP,
                rendered_level=detail_level,
            ):
                app_ids.add(endpoint_id)
        return
    if endpoint_id in graph.cmp_rows:
        cmp_sys = graph.cmp_to_sys.get(endpoint_id)
        cmp_app = graph.cmp_to_app.get(endpoint_id)
        if cmp_sys:
            system_ids.add(cmp_sys)
        if cmp_app and _connect_level_allows(
            configured_level=connect_level,
            target_level=LEVEL_APP,
            rendered_level=detail_level,
        ):
            app_ids.add(cmp_app)
        if _connect_level_allows(
            configured_level=connect_level,
            target_level=LEVEL_CMP,
            rendered_level=detail_level,
        ):
            cmp_ids.add(endpoint_id)


def _project_context_sets(
    *,
    project_id: str,
    stage: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    detail_level: str,
    connect_level: str,
) -> tuple[set[str], set[str], set[str], set[str], list[dict[str, Any]]]:
    system_ids: set[str] = set()
    app_ids: set[str] = set()
    cmp_ids: set[str] = set()
    user_ids: set[str] = set()
    interfaces: list[dict[str, Any]] = []

    for row in _project_scope_rows(project_id=project_id, stage=stage, entities=entities):
        item_type = _project_scope_item_type(row)
        item_id = str(row.get("item_id") or "").strip()
        if not item_id:
            continue
        if item_type == "system":
            system_ids.add(item_id)
        elif item_type == "application":
            app_ids.add(item_id)
            item_sys = graph.app_to_sys.get(item_id)
            if item_sys:
                system_ids.add(item_sys)
        elif item_type == "component":
            cmp_ids.add(item_id)
            item_sys = graph.cmp_to_sys.get(item_id)
            item_app = graph.cmp_to_app.get(item_id)
            if item_sys:
                system_ids.add(item_sys)
            if item_app:
                app_ids.add(item_app)
        elif item_type == "interface":
            for interface_row in entities.get(SHEET_INTERFACE, []):
                if str(interface_row.get("id") or "").strip() == item_id:
                    interfaces.append(interface_row)
                    _add_project_endpoint_context(
                        endpoint_id=_interface_provider(interface_row),
                        detail_level=detail_level,
                        connect_level=connect_level,
                        graph=graph,
                        system_ids=system_ids,
                        app_ids=app_ids,
                        cmp_ids=cmp_ids,
                        user_ids=user_ids,
                    )
                    _add_project_endpoint_context(
                        endpoint_id=_interface_consumer(interface_row),
                        detail_level=detail_level,
                        connect_level=connect_level,
                        graph=graph,
                        system_ids=system_ids,
                        app_ids=app_ids,
                        cmp_ids=cmp_ids,
                        user_ids=user_ids,
                    )
                    break

    return system_ids, app_ids, cmp_ids, user_ids, interfaces


def _project_change_lookup(
    *,
    project_id: str,
    stage: str,
    entities: dict[str, list[dict[str, Any]]],
) -> dict[tuple[str, str], str]:
    """Build a `{(item_type, item_id): change_type}` lookup from this stage's
    scope rows, resolved through the same item_type/item_id extraction used
    elsewhere in this module (`_project_scope_item_type`, `_project_scope_rows`).
    `existing` rows and rows with no resolvable item_type/item_id produce no
    entry (D2 neutral-styling rule)."""
    lookup: dict[tuple[str, str], str] = {}
    for row in _project_scope_rows(project_id=project_id, stage=stage, entities=entities):
        item_type = _project_scope_item_type(row)
        item_id = str(row.get("item_id") or "").strip()
        if not item_type or not item_id:
            continue
        change_type = str(row.get("change_type") or "").strip()
        if not change_type or change_type.lower() == "existing":
            continue
        lookup[(item_type, item_id)] = change_type
    return lookup


def _resolve_change_class(
    change_lookup: dict[tuple[str, str], str],
    item_type: str,
    item_id: str,
) -> str | None:
    return _change_class_for(change_lookup.get((item_type, item_id)))


def build_project_view(
    *,
    project_id: str,
    stage: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    """Build the `model.project_view` render-context dict for a project
    stage diagram, on the same terms as `build_system_view`: `build_project_d2`
    templates it into D2 source, and the draw.io emitter's `build_mxfile`
    (`_arch/drawio.py`) consumes the same `user_nodes`/`external_nodes`/
    `system_blocks`/`interface_edges` shape to embed an editable model."""
    project = _project_row(project_id=project_id, entities=entities)
    if project is None:
        raise ValueError(f"Unknown project '{project_id}'")

    detail_level = _project_option_choice(
        row=project,
        field="detail_level",
        default=LEVEL_APP,
        choices={LEVEL_SYS, LEVEL_APP, LEVEL_CMP},
    )
    connect_level = _project_option_choice(
        row=project,
        field="connect_level",
        default=LEVEL_APP,
        choices={LEVEL_SYS, LEVEL_APP, LEVEL_CMP, CONNECT_LOWEST_VISIBLE},
    )
    system_ids, app_ids, cmp_ids, user_ids, interfaces = _project_context_sets(
        project_id=project_id,
        stage=stage,
        entities=entities,
        graph=graph,
        detail_level=detail_level,
        connect_level=connect_level,
    )
    change_lookup = _project_change_lookup(project_id=project_id, stage=stage, entities=entities)

    explicit_system_ids = {
        str(row.get("item_id") or "").strip()
        for row in _project_scope_rows(project_id=project_id, stage=stage, entities=entities)
        if _project_scope_item_type(row) == "system"
    }
    scope = ProjectScope(
        explicit_system_ids=explicit_system_ids,
        included_app_ids=app_ids,
        included_cmp_ids=cmp_ids,
        change_lookup=change_lookup,
    )
    system_blocks = [
        _build_system_block(
            system_id=system_id,
            level=detail_level,
            graph=graph,
            scope=scope,
        )
        for system_id in sorted(system_ids)
        if system_id in graph.sys_rows and not is_external_system(graph.sys_rows[system_id])
    ]
    external_nodes = [
        {"id": _sanitize_d2_id(system_id), "label": _quote_d2(_system_node_name(system_id, graph))}
        for system_id in sorted(system_ids)
        if system_id not in graph.sys_rows or is_external_system(graph.sys_rows[system_id])
    ]
    user_nodes = [
        {"id": _sanitize_d2_id(user_id), "label": _quote_d2(str(graph.usr_rows[user_id].get("name") or user_id))}
        for user_id in sorted(user_ids)
        if user_id in graph.usr_rows
    ]

    show_interface_labels = option_as_bool(
        profile_data.get("show_interface_labels"), default=DEFAULT_SHOW_INTERFACE_LABELS
    )
    show_arrowhead_labels = option_as_bool(
        profile_data.get("show_arrowhead_labels"), default=DEFAULT_SHOW_ARROWHEAD_LABELS
    )
    interface_label_tpl, arrowhead_label_tpl = _compile_label_templates(profile_data)

    interface_edges: list[dict[str, Any]] = []
    for row in interfaces:
        provider_path = _project_endpoint_path(
            endpoint_id=_interface_provider(row),
            detail_level=detail_level,
            connect_level=connect_level,
            graph=graph,
        )
        consumer_path = _project_endpoint_path(
            endpoint_id=_interface_consumer(row),
            detail_level=detail_level,
            connect_level=connect_level,
            graph=graph,
        )
        start_path, operator, end_path = _directed_edge_parts(
            provider_path=provider_path,
            consumer_path=consumer_path,
            arrow_direction=_interface_arrow_direction(row),
        )
        if start_path == end_path:
            continue
        interface_label = ""
        if show_interface_labels:
            interface_label = _render_compiled_interface_option(
                template=interface_label_tpl,
                row=row,
                option_name="interface_labels",
            )
            # Same empty-render fallback as build_system_view: a label
            # template yielding nothing falls back to the default label.
            interface_label = interface_label or _interface_label(row)
        arrowhead_label = ""
        if show_arrowhead_labels:
            arrowhead_label = _render_compiled_interface_option(
                template=arrowhead_label_tpl,
                row=row,
                option_name="arrowhead_labels",
            )
        project_edge: dict[str, Any] = {
            "start_path": start_path,
            "operator": operator,
            "end_path": end_path,
            "label": interface_label.replace('"', '\\"'),
            "direction_class": "Interface",
            "source_arrowhead_id": arrowhead_label.replace('"', '\\"'),
            "target_arrowhead_id": arrowhead_label.replace('"', '\\"'),
        }
        interaction_class = _interaction_class_for(row.get("interaction_type"))
        if interaction_class:
            project_edge["interaction_class"] = interaction_class
        edge_change_class = _resolve_change_class(change_lookup, "interface", _interface_id(row))
        if edge_change_class:
            project_edge["change_class"] = edge_change_class
        interface_edges.append(project_edge)

    return {
        "title_name": str(project.get("name") or project_id),
        "stage_name": stage,
        "detail_level": detail_level,
        "connect_level": connect_level,
        "user_nodes": user_nodes,
        "external_nodes": external_nodes,
        "system_blocks": system_blocks,
        "interface_edges": interface_edges,
    }


def build_project_d2(
    *,
    project_id: str,
    stage: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    template_path: Any,
    profile_data: dict[str, Any],
    project_view: dict[str, Any] | None = None,
) -> str:
    """Render D2 source for a project stage diagram. `project_view`, if not
    supplied, is built fresh (via `build_project_view`); callers that also
    need the render context for the draw.io emitter should build it once and
    pass it in here to avoid recomputing it."""
    if project_view is None:
        project_view = build_project_view(
            project_id=project_id,
            stage=stage,
            entities=entities,
            graph=graph,
            profile_data=profile_data,
        )

    env = Environment(loader=FileSystemLoader(str(template_path.parent)), autoescape=False, undefined=StrictUndefined)
    env.globals["class_attr"] = _class_attr
    env.globals["quote_d2"] = _quote_d2
    template = env.get_template(template_path.name)
    try:
        rendered = template.render(
            model={"project_view": project_view},
            profile_data=dict(profile_data),
        )
    except TemplateError as exc:
        raise ConfigResolutionError(
            "Invalid tools.arch.profiles.<name>.project_diagram template "
            f"at '{template_path}': {exc}. "
            "Use only model.project_view.* and profile_data in project.d2.j2."
        ) from exc
    return rendered.strip() + "\n"


def _project_item_name(*, item_type: str, item_id: str, graph: EntityGraph, entities: dict[str, list[dict[str, Any]]]) -> str:
    if item_type == "system" and item_id in graph.sys_rows:
        return str(graph.sys_rows[item_id].get("name") or item_id)
    if item_type == "application" and item_id in graph.app_rows:
        return str(graph.app_rows[item_id].get("name") or item_id)
    if item_type == "component" and item_id in graph.cmp_rows:
        return str(graph.cmp_rows[item_id].get("name") or item_id)
    if item_type == "interface":
        for row in entities.get(SHEET_INTERFACE, []):
            if str(row.get("id") or "").strip() == item_id:
                return str(row.get("name") or item_id)
    return item_id


def build_solution_project_context(
    *,
    project_id: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    svg_by_stage: dict[str, str],
    drawio_export: bool = True,
) -> dict[str, Any]:
    project = _project_row(project_id=project_id, entities=entities)
    if project is None:
        raise ValueError(f"Unknown project '{project_id}'")

    # Values land in a formatter:'html' table column; escape raw workbook text.
    metadata = [
        {"field": "ID", "value": str(escape(project_id))},
        {"field": "Status", "value": str(escape(str(project.get("status") or "")))},
        {"field": "Owner", "value": str(escape(str(project.get("owner") or "")))},
        {"field": "Sponsor", "value": str(escape(str(project.get("sponsor") or "")))},
        {"field": "Start Date", "value": str(escape(str(project.get("start_date") or "")))},
        {"field": "Target Date", "value": str(escape(str(project.get("target_date") or "")))},
        {"field": "Detail Level", "value": str(escape(str(project.get("detail_level") or LEVEL_APP)))},
        {"field": "Connect Level", "value": str(escape(str(project.get("connect_level") or LEVEL_APP)))},
    ]
    description = first_value(project, ("description",))
    if description is not None and str(description).strip():
        metadata.append({"field": "Description", "value": render_markdown(description)})
    for key in _collect_extra_keys([project], STD_PROJECT_KEYS):
        metadata.append({"field": title_case(key), "value": render_markdown(project.get(key))})

    scope_rows = _project_scope_rows(project_id=project_id, stage=None, entities=entities)
    scope_extra_keys = _collect_extra_keys(scope_rows, STD_PROJECT_SCOPE_KEYS)
    scope_data: list[dict[str, Any]] = []
    for row in scope_rows:
        item_type = _project_scope_item_type(row)
        item_id = str(row.get("item_id") or "").strip()
        entry: dict[str, Any] = {
            "stage": str(row.get("stage") or ""),
            "item_type": item_type,
            "item_id": _project_scope_item_cell_html(item_type=item_type, item_id=item_id, graph=graph),
            "name": str(row.get("name") or _project_item_name(
                item_type=item_type,
                item_id=item_id,
                graph=graph,
                entities=entities,
            )),
            "change_type": _change_type_badge_html(str(row.get("change_type") or "")),
            "owner": str(row.get("owner") or ""),
            "status": str(row.get("status") or ""),
            "description": render_markdown(first_value(row, ("description",)) or ""),
        }
        for key in scope_extra_keys:
            entry[key] = render_markdown(row.get(key))
        scope_data.append(entry)

    wide_fields = {"description", "summary", "purpose"}
    scope_columns = [
        {"title": "Stage", "field": "stage", "minWidth": 100, "sort": "asc"},
        {"title": "Item Type", "field": "item_type", "minWidth": 120},
        {"title": "Item ID", "field": "item_id", "formatter": "html", "minWidth": 140},
        {"title": "Name", "field": "name", "minWidth": 160},
        {"title": "Change Type", "field": "change_type", "formatter": "html", "minWidth": 130},
        {"title": "Owner", "field": "owner", "minWidth": 120},
        {"title": "Status", "field": "status", "minWidth": 120},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    for key in scope_extra_keys:
        is_wide = key.lower() in wide_fields
        scope_columns.append(
            {
                "title": title_case(key),
                "field": key,
                "formatter": "html",
                "flex": 4 if is_wide else 1,
                "minWidth": 200 if is_wide else 120,
            }
        )

    diagrams = []
    for stage, svg in svg_by_stage.items():
        svg_path = f"images/project-{project_id}-{safe_output_fragment(stage)}.svg"
        diagram_entry: dict[str, Any] = {
            "stage": stage,
            "level": stage,
            "label": stage,
            "svg_path": svg_path,
            "svg": svg,
            "description": "",
        }
        # `export_name` gates the "Export to draw.io" control (design D8):
        # present only when the diagram actually carries an embedded model
        # on disk, i.e. the `drawio_export` toggle is on (D10).
        if drawio_export:
            diagram_entry["export_name"] = f"{Path(svg_path).stem}.drawio.svg"
        diagrams.append(diagram_entry)

    return {
        "project": {
            "id": project_id,
            "name": str(project.get("name") or project_id),
        },
        "metadata_data": metadata,
        "metadata_columns": [
            {"title": "Field", "field": "field", "minWidth": 120},
            {"title": "Value", "field": "value", "formatter": "html", "flex": 4},
        ],
        "scope_data": scope_data,
        "scope_columns": scope_columns,
        "diagrams": diagrams,
        "legend": _build_legend_context(),
        "show_change_types": True,
        "is_index": False,
    }


def _related_projects_for_system(
    *,
    system_id: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
) -> list[dict[str, Any]]:
    """Deduped, sorted list of projects with a scope row (in any stage) that
    resolves to this system or one of its apps/components, each carrying the
    sorted set of change types affecting this system across those rows (D5
    'System page lists related projects'). Empty when no scope row
    references this system (spec 'System page with no related projects')."""
    project_rows = {
        str(row.get("id") or "").strip(): row for row in entities.get(SHEET_PROJECT, [])
    }
    change_types_by_project: dict[str, set[str]] = {}
    for row in entities.get(SHEET_PROJECT_SCOPE, []):
        project_id = str(first_value(row, ("project", "project_id")) or "").strip()
        if not project_id or project_id not in project_rows:
            continue
        item_type = _project_scope_item_type(row)
        item_id = str(row.get("item_id") or "").strip()
        if not item_type or not item_id:
            continue
        owning_sys = _project_system_for_item(item_type=item_type, item_id=item_id, graph=graph)
        if owning_sys != system_id:
            continue
        change_types = change_types_by_project.setdefault(project_id, set())
        change_type = str(row.get("change_type") or "").strip()
        if change_type:
            change_types.add(change_type)

    related: list[dict[str, Any]] = [
        {
            "id": project_id,
            "name": str(project_rows[project_id].get("name") or project_id),
            "href": project_page_name(project_id),
            "change_types": sorted(change_types),
        }
        for project_id, change_types in change_types_by_project.items()
    ]
    related.sort(key=lambda item: str(item["name"]).lower())
    return related


def build_solution_system_context(
    *,
    system_id: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    svg_by_level: dict[str, str],
    workbook_diagrams: list[dict[str, str]],
    drawio_export: bool = True,
) -> dict[str, Any]:
    sys_row = graph.sys_rows[system_id]

    # Values land in a formatter:'html' table column; escape raw workbook text.
    metadata: list[dict[str, Any]] = [{"field": "ID", "value": str(escape(system_id))}]
    sys_type = first_value(sys_row, ("system_type", "type"))
    metadata.append(
        {"field": "Type", "value": str(escape(str(sys_type))) if sys_type is not None else "internal"}
    )

    tags_value = first_value(sys_row, ("tags", "tag"))
    if tags_value is not None and str(tags_value).strip():
        metadata.append({"field": "Tags", "value": str(escape(str(tags_value)))})

    description_value = first_value(sys_row, ("description",))
    if description_value is not None and str(description_value).strip():
        metadata.append({"field": "Description", "value": render_markdown(description_value)})

    for key in _collect_extra_keys([sys_row], STD_SYS_KEYS):
        metadata.append({"field": title_case(key), "value": render_markdown(sys_row.get(key))})

    apps_in_system = [graph.app_rows[app_id] for app_id in graph.sys_app_ids.get(system_id, [])]
    app_extra_keys = _collect_extra_keys(apps_in_system, STD_APP_KEYS)

    applications_data: list[dict[str, Any]] = []
    for app_row in apps_in_system:
        app_id = str(app_row.get("id", "")).strip()
        app_name = str(app_row.get("name") or app_id)

        app_components = graph.app_cmp_rows.get(app_id, [])
        comp_parts: list[str] = []
        for cmp_row in app_components:
            cmp_name = str(cmp_row.get("name") or cmp_row.get("id") or "")
            cmp_type = _component_type_label(cmp_row)
            if cmp_type == "Cmp":
                comp_parts.append(cmp_name)
            else:
                comp_parts.append(f"{cmp_name} ({cmp_type})")

        app_data: dict[str, Any] = {
            "id": app_id,
            "name": app_name,
            "components": ", ".join(comp_parts),
            "description": render_markdown(first_value(app_row, ("description",)) or ""),
        }
        for key in app_extra_keys:
            app_data[key] = render_markdown(app_row.get(key))
        applications_data.append(app_data)

    components_data: list[dict[str, Any]] = []
    for cmp_row in graph.sys_direct_cmp_rows.get(system_id, []):
        cmp_id = str(cmp_row.get("id", "")).strip()
        if not cmp_id:
            continue
        components_data.append(
            {
                "id": cmp_id,
                "name": str(cmp_row.get("name") or cmp_id),
                "type": _component_type_label(cmp_row),
                "description": render_markdown(first_value(cmp_row, ("description",)) or ""),
            }
        )

    system_interfaces = _system_interfaces(system_id=system_id, entities=entities, graph=graph)
    interface_extra_keys = _collect_extra_keys(system_interfaces, STD_INTERFACE_KEYS)
    interfaces_data: list[dict[str, Any]] = []
    for interface_row in system_interfaces:
        entry: dict[str, Any] = {
            "key": str(interface_row.get("key") or "").strip(),
            "id": str(interface_row.get("id") or ""),
            "name": str(interface_row.get("name") or interface_row.get("id") or "interface"),
            "provider": _interface_provider(interface_row),
            "consumer": _interface_consumer(interface_row),
            "interaction_type": _interaction_type_badge_html(_interface_type(interface_row)),
            "arrow_direction": _interface_arrow_direction(interface_row),
            "description": render_markdown(first_value(interface_row, ("description",)) or ""),
        }
        for key in interface_extra_keys:
            entry[key] = render_markdown(interface_row.get(key))
        interfaces_data.append(entry)

    wide_fields = {"description", "summary", "purpose", "components"}

    metadata_columns = [
        {"title": "Field", "field": "field", "minWidth": 120},
        {"title": "Value", "field": "value", "formatter": "html", "flex": 4},
    ]

    app_columns = [
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "minWidth": 150},
        {"title": "Components", "field": "components", "flex": 4, "minWidth": 200},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    for key in app_extra_keys:
        is_wide = key.lower() in wide_fields
        app_columns.append(
            {
                "title": title_case(key),
                "field": key,
                "formatter": "html",
                "flex": 4 if is_wide else 1,
                "minWidth": 200 if is_wide else 120,
            }
        )

    cmp_columns = [
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "minWidth": 150},
        {"title": "Type", "field": "type", "minWidth": 100},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]

    interface_columns = [
        {"title": "Key", "field": "key", "minWidth": 100, "maxWidth": 120, "sort": "asc"},
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "minWidth": 150},
        {"title": "Provider", "field": "provider", "minWidth": 120},
        {"title": "Consumer", "field": "consumer", "minWidth": 120},
        {"title": "Interaction Type", "field": "interaction_type", "formatter": "html", "minWidth": 140},
        {"title": "Arrow Direction", "field": "arrow_direction", "minWidth": 160},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    for key in interface_extra_keys:
        is_wide = key.lower() in wide_fields
        interface_columns.append(
            {
                "title": title_case(key),
                "field": key,
                "formatter": "html",
                "flex": 4 if is_wide else 1,
                "minWidth": 200 if is_wide else 120,
            }
        )

    diagrams: list[dict[str, Any]] = []
    for item_level, label in (("sys", "System"), ("app", "Application"), ("cmp", "Component")):
        svg_path = f"images/{system_id}-{item_level}.svg"
        diagram_entry: dict[str, Any] = {
            "level": item_level,
            "label": label,
            "svg_path": svg_path,
            "svg": svg_by_level[item_level],
            "description": "",
        }
        # `export_name` gates the "Export to draw.io" control (design D8);
        # workbook-supplied diagrams (`additional_diagrams` below) never get
        # one (D9 "Embedding models in workbook-supplied SVGs" is a non-goal).
        if drawio_export:
            diagram_entry["export_name"] = f"{Path(svg_path).stem}.drawio.svg"
        diagrams.append(diagram_entry)

    additional_diagrams: list[dict[str, str]] = []
    for idx, diagram_row in enumerate(workbook_diagrams, start=1):
        additional_diagrams.append(
            {
                "level": f"seq-{idx}",
                "label": str(diagram_row.get("name") or f"Sequence {idx}"),
                "svg_path": str(diagram_row.get("svg_path") or ""),
                "svg": str(diagram_row.get("svg") or ""),
                "description": str(diagram_row.get("description") or ""),
            }
        )

    return {
        "system": {
            "id": system_id,
            "name": str(sys_row.get("name") or system_id),
            "applications": apps_in_system,
            "components": components_data,
        },
        "metadata_data": metadata,
        "metadata_columns": metadata_columns,
        "applications_data": applications_data,
        "applications_columns": app_columns,
        "components_data": components_data,
        "components_columns": cmp_columns,
        "interfaces_data": interfaces_data,
        "interfaces_columns": interface_columns,
        "diagrams": diagrams,
        "additional_diagrams": additional_diagrams,
        "related_projects": _related_projects_for_system(
            system_id=system_id, entities=entities, graph=graph
        ),
        "legend": _build_legend_context(),
        "show_change_types": False,
        "is_index": False,
    }


def _interaction_type_breakdown_label(raw_value: Any) -> str:
    """Group label for the index interfaces-by-type breakdown: the friendly
    label for a recognized `interaction_type`, else the literal raw text
    (D7 'unrecognized values grouped under their literal text'); empty for
    absent values so they are excluded from the breakdown entirely."""
    text = str(raw_value or "").strip()
    if not text:
        return ""
    normalized = normalize_interaction_type(text)
    if normalized:
        return str(INTERACTION_TYPE_STYLES[normalized]["label"])
    return text


def _breakdown_counts(labels: Any) -> list[dict[str, Any]]:
    """Count occurrences of each non-empty label, sorted alphabetically.
    Labels that never occur never produce an entry, so zero-count groups are
    inherently omitted (spec 'Empty groups omitted')."""
    counts: dict[str, int] = {}
    for label in labels:
        text = str(label or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(counts.items())]


def _owned_entity_name_link_html(*, item_type: str, item_id: str, name: str, graph: EntityGraph) -> str:
    """Render an app/component entity-table name cell as a link (using the
    entity's own name as link text) to its owning system's page; plain text
    when the item does not resolve to a system with a generated page (D7
    'apps/components -> owning system page')."""
    owning_sys = _project_system_for_item(item_type=item_type, item_id=item_id, graph=graph)
    if owning_sys:
        return f'<a href="{escape(system_page_name(owning_sys))}">{escape(name)}</a>'
    return str(escape(name))


def _interface_endpoint_link_html(*, endpoint_id: str, graph: EntityGraph) -> str:
    """Render an interface provider/consumer endpoint id as a link to its
    owning system's page when it resolves to a system, app, or component
    with a generated page; plain text for users and unresolved/external
    endpoints (D7 interfaces entity table: 'provider AND consumer system
    pages')."""
    if not endpoint_id:
        return ""
    if endpoint_id in graph.sys_rows:
        return _project_scope_item_cell_html(item_type="system", item_id=endpoint_id, graph=graph)
    if endpoint_id in graph.app_rows:
        return _project_scope_item_cell_html(item_type="application", item_id=endpoint_id, graph=graph)
    if endpoint_id in graph.cmp_rows:
        return _project_scope_item_cell_html(item_type="component", item_id=endpoint_id, graph=graph)
    return str(escape(endpoint_id))


def build_solution_index_context(
    *,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
) -> dict[str, Any]:
    """Solution index summary cards + global entity tables (D7).

    `summary_cards` holds totals (systems/apps/components/interfaces/
    projects) and breakdowns (systems by `system_type`, projects by
    `status`, interfaces by normalized `interaction_type`); zero-count
    totals and empty breakdowns are omitted rather than rendered as zero.

    `entity_tables` holds five `{title, columns, data}` blocks shaped like
    the existing `*_columns`/`*_data` pairs so `initAgGridTable` consumes
    them unchanged; apps/components link to their owning system page,
    interfaces link provider and consumer system pages, projects link to
    their project page. External systems (no generated page) are excluded,
    matching the systems already shown elsewhere on the index.
    """
    internal_sys_rows = [
        row
        for row in entities.get("sys", [])
        if str(row.get("id") or "").strip() and not is_external_system(row)
    ]
    app_rows = [row for row in entities.get("app", []) if str(row.get("id") or "").strip()]
    cmp_rows = [row for row in entities.get("cmp", []) if str(row.get("id") or "").strip()]
    interface_rows = [row for row in entities.get(SHEET_INTERFACE, []) if str(row.get("id") or "").strip()]
    project_rows = [row for row in entities.get(SHEET_PROJECT, []) if str(row.get("id") or "").strip()]

    totals_source = (
        ("Systems", len(internal_sys_rows)),
        ("Applications", len(app_rows)),
        ("Components", len(cmp_rows)),
        ("Interfaces", len(interface_rows)),
        ("Projects", len(project_rows)),
    )
    totals = [{"label": label, "count": count} for label, count in totals_source if count > 0]

    systems_by_type = _breakdown_counts(
        str(first_value(row, ("system_type", "type")) or "internal").strip() or "internal"
        for row in internal_sys_rows
    )
    projects_by_status = _breakdown_counts(str(row.get("status") or "") for row in project_rows)
    interfaces_by_type = _breakdown_counts(
        _interaction_type_breakdown_label(row.get("interaction_type")) for row in interface_rows
    )

    summary_cards: dict[str, Any] = {
        "totals": totals,
        "systems_by_type": systems_by_type,
        "projects_by_status": projects_by_status,
        "interfaces_by_type": interfaces_by_type,
    }

    systems_columns = [
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "formatter": "html", "minWidth": 160},
        {"title": "Type", "field": "type", "minWidth": 120},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    systems_data: list[dict[str, Any]] = []
    for row in internal_sys_rows:
        sys_id = str(row.get("id") or "").strip()
        sys_name = str(row.get("name") or sys_id)
        systems_data.append(
            {
                "id": sys_id,
                "name": f'<a href="{escape(system_page_name(sys_id))}">{escape(sys_name)}</a>',
                "type": str(first_value(row, ("system_type", "type")) or "internal"),
                "description": render_markdown(first_value(row, ("description",)) or ""),
            }
        )

    applications_columns = [
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "formatter": "html", "minWidth": 160},
        {"title": "System", "field": "system", "minWidth": 120},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    applications_data: list[dict[str, Any]] = []
    for row in app_rows:
        app_id = str(row.get("id") or "").strip()
        app_name = str(row.get("name") or app_id)
        applications_data.append(
            {
                "id": app_id,
                "name": _owned_entity_name_link_html(
                    item_type="application", item_id=app_id, name=app_name, graph=graph
                ),
                "system": graph.app_to_sys.get(app_id, ""),
                "description": render_markdown(first_value(row, ("description",)) or ""),
            }
        )

    components_columns = [
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "formatter": "html", "minWidth": 160},
        {"title": "System", "field": "system", "minWidth": 120},
        {"title": "Type", "field": "type", "minWidth": 100},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    components_data: list[dict[str, Any]] = []
    for row in cmp_rows:
        cmp_id = str(row.get("id") or "").strip()
        cmp_name = str(row.get("name") or cmp_id)
        components_data.append(
            {
                "id": cmp_id,
                "name": _owned_entity_name_link_html(
                    item_type="component", item_id=cmp_id, name=cmp_name, graph=graph
                ),
                "system": graph.cmp_to_sys.get(cmp_id, ""),
                "type": _component_type_label(row),
                "description": render_markdown(first_value(row, ("description",)) or ""),
            }
        )

    interfaces_columns = [
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "minWidth": 150},
        {"title": "Provider", "field": "provider", "formatter": "html", "minWidth": 140},
        {"title": "Consumer", "field": "consumer", "formatter": "html", "minWidth": 140},
        {"title": "Interaction Type", "field": "interaction_type", "formatter": "html", "minWidth": 140},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    interfaces_data: list[dict[str, Any]] = []
    for row in interface_rows:
        interfaces_data.append(
            {
                "id": str(row.get("id") or ""),
                "name": str(row.get("name") or row.get("id") or "interface"),
                "provider": _interface_endpoint_link_html(endpoint_id=_interface_provider(row), graph=graph),
                "consumer": _interface_endpoint_link_html(endpoint_id=_interface_consumer(row), graph=graph),
                "interaction_type": _interaction_type_badge_html(_interface_type(row)),
                "description": render_markdown(first_value(row, ("description",)) or ""),
            }
        )

    projects_columns = [
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "formatter": "html", "minWidth": 160},
        {"title": "Status", "field": "status", "minWidth": 120},
        {"title": "Owner", "field": "owner", "minWidth": 120},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    projects_data: list[dict[str, Any]] = []
    for row in project_rows:
        project_id = str(row.get("id") or "").strip()
        project_name = str(row.get("name") or project_id)
        projects_data.append(
            {
                "id": project_id,
                "name": f'<a href="{escape(project_page_name(project_id))}">{escape(project_name)}</a>',
                "status": str(row.get("status") or ""),
                "owner": str(row.get("owner") or ""),
                "description": render_markdown(first_value(row, ("description",)) or ""),
            }
        )

    entity_tables: dict[str, Any] = {
        "systems": {"title": "Systems", "columns": systems_columns, "data": systems_data},
        "applications": {"title": "Applications", "columns": applications_columns, "data": applications_data},
        "components": {"title": "Components", "columns": components_columns, "data": components_data},
        "interfaces": {"title": "Interfaces", "columns": interfaces_columns, "data": interfaces_data},
        "projects": {"title": "Projects", "columns": projects_columns, "data": projects_data},
    }

    return {
        "summary_cards": summary_cards,
        "entity_tables": entity_tables,
    }


__all__ = [
    "DEFAULT_ARROWHEAD_LABELS_TEMPLATE",
    "DEFAULT_DIRECTION",
    "DEFAULT_INTERFACE_LABELS_TEMPLATE",
    "DEFAULT_MERGE_INTERFACES",
    "DEFAULT_SECONDARY_CONNECT_LEVEL",
    "DEFAULT_SECONDARY_SYSTEM_DETAIL",
    "DEFAULT_SHOW_ARROWHEAD_LABELS",
    "DEFAULT_SHOW_INTERFACE_LABELS",
    "LEVEL_APP",
    "LEVEL_CMP",
    "LEVEL_SYS",
    "EntityGraph",
    "build_entity_graph",
    "build_project_d2",
    "build_project_view",
    "build_solution_index_context",
    "build_solution_project_context",
    "build_solution_system_context",
    "build_system_d2",
    "build_system_view",
    "first_tag_value",
    "is_external_system",
    "project_page_name",
    "project_stage_ids",
    "render_markdown",
    "safe_output_fragment",
    "svg_markup",
    "system_page_name",
]
