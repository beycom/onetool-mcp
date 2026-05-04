"""System graph, diagram rendering, and solution-context helpers for arch pack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import markdown as md  # type: ignore[import-untyped]
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from .config import ConfigResolutionError
from .models import first_value, tags_for_row

STD_SYS_KEYS = {"id", "name", "type", "system_type", "tag", "tags", "description"}
STD_APP_KEYS = {"id", "name", "sys", "system", "system_id", "sys_id", "tag", "tags", "description"}
STD_CMP_KEYS = {
    "id",
    "name",
    "app",
    "application",
    "app_id",
    "application_id",
    "sys",
    "system",
    "system_id",
    "sys_id",
    "type",
    "component_type",
    "cmp_type",
    "tag",
    "tags",
    "description",
}
STD_INT_KEYS = {
    "id",
    "key",
    "name",
    "src",
    "source",
    "from",
    "from_id",
    "src_id",
    "dst",
    "target",
    "to",
    "to_id",
    "dst_id",
    "type",
    "integration_type",
    "tag",
    "tags",
    "description",
}

LEVEL_SYS = "sys"
LEVEL_APP = "app"
LEVEL_CMP = "cmp"

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

_md_converter = md.Markdown(extensions=["nl2br"])


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


def title_case(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def render_markdown(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text.strip():
        return ""
    _md_converter.reset()
    rendered: str = _md_converter.convert(text)
    return rendered


def first_tag_value(row: dict[str, Any]) -> str:
    tags = tags_for_row(row)
    if not tags:
        return ""
    return sorted(tags)[0]


def system_page_name(system_id: str) -> str:
    return f"{system_id}.html"


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
    return normalized if normalized in {"Web", "DB", "File", "API", "Batch", "Queue", "Cmp"} else "Cmp"


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
        sys_id = str(first_value(row, ("sys", "system", "system_id", "sys_id")) or "").strip()
        if sys_id:
            app_to_sys[app_id] = sys_id

    cmp_to_app: dict[str, str] = {}
    cmp_to_sys: dict[str, str] = {}
    for cmp_id, row in cmp_rows.items():
        app_id = str(first_value(row, ("app", "application", "app_id", "application_id")) or "").strip()
        if app_id:
            cmp_to_app[cmp_id] = app_id
            sys_id = app_to_sys.get(app_id, "")
            if sys_id:
                cmp_to_sys[cmp_id] = sys_id
        else:
            sys_id = str(first_value(row, ("sys", "system", "system_id", "sys_id")) or "").strip()
            if sys_id:
                cmp_to_sys[cmp_id] = sys_id

    usr_to_sys: dict[str, str] = {}
    for usr_id, row in usr_rows.items():
        app_id = str(first_value(row, ("app", "application", "app_id", "application_id")) or "").strip()
        if app_id and app_id in app_to_sys:
            usr_to_sys[usr_id] = app_to_sys[app_id]

    node_to_sys: dict[str, str] = {}
    node_to_sys.update({sys_id: sys_id for sys_id in sys_rows})
    node_to_sys.update(app_to_sys)
    node_to_sys.update(cmp_to_sys)
    node_to_sys.update(usr_to_sys)

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
    )


def _sanitize_d2_id(name: str) -> str:
    return name.replace('"', '\\"')


def _quote_d2(label: str) -> str:
    escaped = label.replace('"', '\\"')
    return f'"{escaped}"'


def _wrap_label(name: str, max_width: int = MAX_LINE_WIDTH) -> str:
    if len(name) <= max_width:
        return _quote_d2(name)

    words = name.split()
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


def _integration_src(row: dict[str, Any]) -> str:
    return str(first_value(row, ("src", "source", "from", "from_id", "src_id")) or "").strip()


def _integration_dst(row: dict[str, Any]) -> str:
    return str(first_value(row, ("dst", "target", "to", "to_id", "dst_id")) or "").strip()


def _integration_type(row: dict[str, Any]) -> str:
    return str(first_value(row, ("integration_type", "type")) or "").strip()


def _integration_label(row: dict[str, Any]) -> str:
    name = str(row.get("name") or row.get("id") or "integration").strip()
    int_type = _integration_type(row)
    if int_type:
        return f"{name} ({int_type})"
    return name


def _integration_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or "").strip()


def _option_as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    return bool(value)


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


def _integration_template_row(*, row: dict[str, Any]) -> dict[str, str]:
    row_model: dict[str, str] = {}
    for key, value in row.items():
        if str(key).startswith("_"):
            continue
        if value is None:
            row_model[str(key)] = ""
            continue
        row_model[str(key)] = str(value)

    row_model.setdefault("id", _integration_id(row))
    row_model.setdefault("key", str(row.get("key") or "").strip())
    row_model.setdefault("name", str(row.get("name") or row_model["id"] or "integration").strip())
    row_model.setdefault("src", _integration_src(row))
    row_model.setdefault("dst", _integration_dst(row))
    row_model.setdefault("type", _integration_type(row))
    row_model.setdefault("label", _integration_label(row))
    return row_model


def _render_compiled_integration_option(*, template: Any, row: dict[str, Any], option_name: str) -> str:
    try:
        rendered = template.render(row=_integration_template_row(row=row))
    except TemplateError as exc:
        raise ConfigResolutionError(
            f"Failed rendering tools.arch.profiles.<name>.data.{option_name}: {exc}"
        ) from exc
    return str(rendered).strip()


def _endpoint_system_id(*, endpoint_id: str, graph: EntityGraph) -> str | None:
    if endpoint_id in graph.node_to_sys:
        return graph.node_to_sys[endpoint_id]
    if endpoint_id in graph.sys_rows:
        return endpoint_id
    if endpoint_id in graph.app_rows:
        return graph.app_to_sys.get(endpoint_id)
    if endpoint_id in graph.cmp_rows:
        return graph.cmp_to_sys.get(endpoint_id)
    if endpoint_id in graph.usr_rows:
        return graph.usr_to_sys.get(endpoint_id)
    return None


def _system_integrations(*, system_id: str, entities: dict[str, list[dict[str, Any]]], graph: EntityGraph) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in entities["int"]:
        src = _integration_src(row)
        dst = _integration_dst(row)
        if not src or not dst:
            continue

        src_sys = _endpoint_system_id(endpoint_id=src, graph=graph)
        dst_sys = _endpoint_system_id(endpoint_id=dst, graph=graph)

        if src_sys is None and src not in graph.usr_rows and src not in graph.app_rows and src not in graph.cmp_rows:
            src_sys = src
        if dst_sys is None and dst not in graph.usr_rows and dst not in graph.app_rows and dst not in graph.cmp_rows:
            dst_sys = dst

        if src_sys == system_id or dst_sys == system_id:
            result.append(row)

    return result


def _related_user_rows(*, system_id: str, entities: dict[str, list[dict[str, Any]]], graph: EntityGraph) -> list[dict[str, Any]]:
    focus_ids = {system_id}
    for app_id, app_sys in graph.app_to_sys.items():
        if app_sys == system_id:
            focus_ids.add(app_id)
    for cmp_id, cmp_sys in graph.cmp_to_sys.items():
        if cmp_sys == system_id:
            focus_ids.add(cmp_id)

    related: list[dict[str, Any]] = []
    for row in entities["usr"]:
        usr_id = str(row.get("id", "")).strip()
        if not usr_id:
            continue

        app_id = str(first_value(row, ("app", "application", "app_id", "application_id")) or "").strip()
        if app_id in focus_ids:
            related.append(row)
            continue

        if graph.usr_to_sys.get(usr_id) == system_id:
            related.append(row)

    return related


def _node_path_for_level(*, endpoint_id: str, level: str, focus_system_id: str, graph: EntityGraph) -> str:
    if endpoint_id in graph.usr_rows:
        return f'"{_sanitize_d2_id(endpoint_id)}"'

    if endpoint_id in graph.app_rows:
        app_sys = graph.app_to_sys.get(endpoint_id)
        if app_sys == focus_system_id and level in {LEVEL_APP, LEVEL_CMP}:
            return f'"{_sanitize_d2_id(focus_system_id)}"."{_sanitize_d2_id(endpoint_id)}"'
        if app_sys:
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


def svg_markup(svg_text: str) -> str:
    marker = "<svg"
    idx = svg_text.find(marker)
    if idx == -1:
        return svg_text
    return svg_text[idx:]


def _build_system_block(*, system_id: str, level: str, graph: EntityGraph, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    row = graph.sys_rows.get(system_id)
    system_name = str((row or {}).get("name") or system_id)
    sys_id = _sanitize_d2_id(system_id)
    block: dict[str, Any] = {
        "id": sys_id,
        "label": _quote_d2(system_name),
        "placeholder": False,
        "direct_components": [],
        "apps": [],
    }

    app_ids = [
        str(app_row.get("id", "")).strip()
        for app_row in entities["app"]
        if str(first_value(app_row, ("sys", "system", "system_id", "sys_id")) or "").strip() == system_id
        and str(app_row.get("id", "")).strip()
    ]
    cmp_rows_direct = [
        cmp_row
        for cmp_row in entities["cmp"]
        if str(first_value(cmp_row, ("app", "application", "app_id", "application_id")) or "").strip() == ""
        and str(first_value(cmp_row, ("sys", "system", "system_id", "sys_id")) or "").strip() == system_id
    ]

    if level == LEVEL_SYS or (not app_ids and not cmp_rows_direct):
        block["placeholder"] = True
        return block

    if level == LEVEL_CMP:
        for cmp_row in cmp_rows_direct:
            cmp_id = str(cmp_row.get("id", "")).strip()
            if not cmp_id:
                continue
            cmp_name = str(cmp_row.get("name") or cmp_id)
            cmp_class = _component_class_from_row(cmp_row)
            block["direct_components"].append(
                {
                    "id": _sanitize_d2_id(cmp_id),
                    "label": _wrap_label(cmp_name, COMPONENT_MAX_LINE_WIDTH),
                    "class": cmp_class,
                }
            )

    for app_id in app_ids:
        app_row = graph.app_rows[app_id]
        app_name = str(app_row.get("name") or app_id)
        app_cmp_rows = [
            cmp_row
            for cmp_row in entities["cmp"]
            if str(first_value(cmp_row, ("app", "application", "app_id", "application_id")) or "").strip() == app_id
        ]

        app_block: dict[str, Any] = {
            "id": _sanitize_d2_id(app_id),
            "label": _wrap_label(app_name),
            "components": [],
        }
        if level == LEVEL_CMP and app_cmp_rows:
            for cmp_row in app_cmp_rows:
                cmp_id = str(cmp_row.get("id", "")).strip()
                if not cmp_id:
                    continue
                cmp_name = str(cmp_row.get("name") or cmp_id)
                cmp_class = _component_class_from_row(cmp_row)
                app_block["components"].append(
                    {
                        "id": _sanitize_d2_id(cmp_id),
                        "label": _wrap_label(cmp_name, COMPONENT_MAX_LINE_WIDTH),
                        "class": cmp_class,
                    }
                )
        block["apps"].append(app_block)
    return block


def build_system_d2(
    *,
    system_id: str,
    level: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    template_path: Any,
    profile_data: dict[str, Any],
) -> str:
    level_name = {"sys": "System", "app": "Application", "cmp": "Component"}[level]
    title_name = _system_node_name(system_id, graph)
    merge_integrations = _option_as_bool(profile_data.get("merge_integrations"), default=False)
    show_integration_labels = _option_as_bool(profile_data.get("show_integration_labels"), default=True)
    show_arrowhead_labels = _option_as_bool(profile_data.get("show_arrowhead_labels"), default=False)

    integration_labels_template = _profile_option_label_template(
        profile_data=profile_data,
        option_name="integration_labels",
        default="[{{ row.key }}] {{ row.name }}",
    )
    arrowhead_labels_template = _profile_option_label_template(
        profile_data=profile_data,
        option_name="arrowhead_labels",
        default="{{ row.key }}",
    )

    template_env = Environment(autoescape=False, undefined=StrictUndefined)
    integration_label_tpl = template_env.from_string(integration_labels_template)
    arrowhead_label_tpl = template_env.from_string(arrowhead_labels_template)

    integrations = _system_integrations(system_id=system_id, entities=entities, graph=graph)
    users = _related_user_rows(system_id=system_id, entities=entities, graph=graph)

    related_system_ids: set[str] = set()
    external_system_ids: set[str] = set()
    for row in integrations:
        src = _integration_src(row)
        dst = _integration_dst(row)
        src_sys = _endpoint_system_id(endpoint_id=src, graph=graph)
        dst_sys = _endpoint_system_id(endpoint_id=dst, graph=graph)

        if src_sys is None and src not in graph.usr_rows and src not in graph.app_rows and src not in graph.cmp_rows:
            src_sys = src
        if dst_sys is None and dst not in graph.usr_rows and dst not in graph.app_rows and dst not in graph.cmp_rows:
            dst_sys = dst

        if src_sys and src_sys != system_id:
            if src_sys in graph.sys_rows and not is_external_system(graph.sys_rows[src_sys]):
                related_system_ids.add(src_sys)
            else:
                external_system_ids.add(src_sys)
        if dst_sys and dst_sys != system_id:
            if dst_sys in graph.sys_rows and not is_external_system(graph.sys_rows[dst_sys]):
                related_system_ids.add(dst_sys)
            else:
                external_system_ids.add(dst_sys)

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
        _build_system_block(system_id=system_id, level=level, graph=graph, entities=entities)
    ]
    for rel_id in sorted(related_system_ids):
        system_blocks.append(_build_system_block(system_id=rel_id, level=LEVEL_SYS, graph=graph, entities=entities))

    integration_edges: list[dict[str, str]] = []
    merged_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in integrations:
        src = _integration_src(row)
        dst = _integration_dst(row)
        if not src or not dst:
            continue

        src_path = _node_path_for_level(endpoint_id=src, level=level, focus_system_id=system_id, graph=graph)
        dst_path = _node_path_for_level(endpoint_id=dst, level=level, focus_system_id=system_id, graph=graph)

        if src_path == dst_path:
            continue

        src_sys = _endpoint_system_id(endpoint_id=src, graph=graph)
        dst_sys = _endpoint_system_id(endpoint_id=dst, graph=graph)
        if src_sys is None and src not in graph.usr_rows and src not in graph.app_rows and src not in graph.cmp_rows:
            src_sys = src
        if dst_sys is None and dst not in graph.usr_rows and dst not in graph.app_rows and dst not in graph.cmp_rows:
            dst_sys = dst

        direction_class = "Integration"
        if src_sys == system_id:
            direction_class = "IntegrationFromFocus"
        elif dst_sys == system_id:
            direction_class = "IntegrationToFocus"

        if show_integration_labels:
            edge_label = _render_compiled_integration_option(
                template=integration_label_tpl,
                row=row,
                option_name="integration_labels",
            )
            edge_label = edge_label or _integration_label(row)
        else:
            edge_label = ""

        arrowhead_label = ""
        if show_arrowhead_labels:
            arrowhead_label = _render_compiled_integration_option(
                template=arrowhead_label_tpl,
                row=row,
                option_name="arrowhead_labels",
            )

        if merge_integrations:
            merged_key = (src_path, dst_path, direction_class)
            merged_edge = merged_edges.get(merged_key)
            if merged_edge is None:
                merged_edge = {
                    "src_path": src_path,
                    "dst_path": dst_path,
                    "direction_class": direction_class,
                    "labels": [],
                    "arrowheads": [],
                }
                merged_edges[merged_key] = merged_edge
            if edge_label not in merged_edge["labels"]:
                merged_edge["labels"].append(edge_label)
            if arrowhead_label and arrowhead_label not in merged_edge["arrowheads"]:
                merged_edge["arrowheads"].append(arrowhead_label)
            continue

        integration_edges.append(
            {
                "src_path": src_path,
                "dst_path": dst_path,
                "label": edge_label.replace('"', '\\"'),
                "direction_class": direction_class,
                "source_arrowhead_id": arrowhead_label.replace('"', '\\"'),
                "target_arrowhead_id": arrowhead_label.replace('"', '\\"'),
            }
        )

    if merge_integrations:
        for merged_edge in merged_edges.values():
            arrowhead_id = "\\n".join(str(item) for item in merged_edge["arrowheads"])
            integration_edges.append(
                {
                    "src_path": str(merged_edge["src_path"]),
                    "dst_path": str(merged_edge["dst_path"]),
                    "label": "\\n".join(str(item) for item in merged_edge["labels"]).replace('"', '\\"'),
                    "direction_class": str(merged_edge["direction_class"]),
                    "source_arrowhead_id": arrowhead_id.replace('"', '\\"'),
                    "target_arrowhead_id": arrowhead_id.replace('"', '\\"'),
                }
            )

    env = Environment(loader=FileSystemLoader(str(template_path.parent)), autoescape=False, undefined=StrictUndefined)
    template = env.get_template(template_path.name)
    system_view: dict[str, Any] = {
        "title_name": title_name,
        "level_name": level_name,
        "user_nodes": user_nodes,
        "external_nodes": external_nodes,
        "system_blocks": system_blocks,
        "integration_edges": integration_edges,
    }
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


def build_solution_system_context(
    *,
    system_id: str,
    entities: dict[str, list[dict[str, Any]]],
    graph: EntityGraph,
    svg_by_level: dict[str, str],
    workbook_diagrams: list[dict[str, str]],
) -> dict[str, Any]:
    sys_row = graph.sys_rows[system_id]

    metadata: list[dict[str, Any]] = [{"field": "ID", "value": system_id}]
    sys_type = first_value(sys_row, ("system_type", "type"))
    metadata.append({"field": "Type", "value": str(sys_type) if sys_type is not None else "internal"})

    tags_value = first_value(sys_row, ("tags", "tag"))
    if tags_value is not None and str(tags_value).strip():
        metadata.append({"field": "Tags", "value": str(tags_value)})

    description_value = first_value(sys_row, ("description",))
    if description_value is not None and str(description_value).strip():
        metadata.append({"field": "Description", "value": render_markdown(description_value)})

    for key in _collect_extra_keys([sys_row], STD_SYS_KEYS):
        metadata.append({"field": title_case(key), "value": render_markdown(sys_row.get(key))})

    apps_in_system = [
        row
        for row in entities["app"]
        if str(first_value(row, ("sys", "system", "system_id", "sys_id")) or "").strip() == system_id
    ]
    app_extra_keys = _collect_extra_keys(apps_in_system, STD_APP_KEYS)

    applications_data: list[dict[str, Any]] = []
    for app_row in apps_in_system:
        app_id = str(app_row.get("id", "")).strip()
        app_name = str(app_row.get("name") or app_id)

        app_components = [
            cmp_row
            for cmp_row in entities["cmp"]
            if str(first_value(cmp_row, ("app", "application", "app_id", "application_id")) or "").strip() == app_id
        ]
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
    for cmp_row in entities["cmp"]:
        cmp_sys = str(first_value(cmp_row, ("sys", "system", "system_id", "sys_id")) or "").strip()
        cmp_app = str(first_value(cmp_row, ("app", "application", "app_id", "application_id")) or "").strip()
        if cmp_app:
            continue
        if cmp_sys != system_id:
            continue
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

    system_integrations = _system_integrations(system_id=system_id, entities=entities, graph=graph)
    int_extra_keys = _collect_extra_keys(system_integrations, STD_INT_KEYS)
    integrations_data: list[dict[str, Any]] = []
    for int_row in system_integrations:
        entry: dict[str, Any] = {
            "seq": str(int_row.get("key") or "").strip(),
            "id": str(int_row.get("id") or ""),
            "name": str(int_row.get("name") or int_row.get("id") or "integration"),
            "consumer": _integration_src(int_row),
            "provider": _integration_dst(int_row),
            "type": _integration_type(int_row),
            "description": render_markdown(first_value(int_row, ("description",)) or ""),
        }
        for key in int_extra_keys:
            entry[key] = render_markdown(int_row.get(key))
        integrations_data.append(entry)

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

    int_columns = [
        {"title": "#", "field": "seq", "minWidth": 60, "maxWidth": 80, "sort": "asc"},
        {"title": "ID", "field": "id", "minWidth": 120},
        {"title": "Name", "field": "name", "minWidth": 150},
        {"title": "Consumer", "field": "consumer", "minWidth": 120},
        {"title": "Provider", "field": "provider", "minWidth": 120},
        {"title": "Type", "field": "type", "minWidth": 100},
        {"title": "Description", "field": "description", "formatter": "html", "flex": 4, "minWidth": 200},
    ]
    for key in int_extra_keys:
        is_wide = key.lower() in wide_fields
        int_columns.append(
            {
                "title": title_case(key),
                "field": key,
                "formatter": "html",
                "flex": 4 if is_wide else 1,
                "minWidth": 200 if is_wide else 120,
            }
        )

    diagrams: list[dict[str, str]] = []
    for item_level, label in (("sys", "System"), ("app", "Application"), ("cmp", "Component")):
        diagrams.append(
            {
                "level": item_level,
                "label": label,
                "svg_path": f"images/{system_id}-{item_level}.svg",
                "svg": svg_by_level[item_level],
                "description": "",
            }
        )

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
        "integrations_data": integrations_data,
        "integrations_columns": int_columns,
        "integrations": integrations_data,
        "diagrams": diagrams,
        "additional_diagrams": additional_diagrams,
    }


__all__ = [
    "LEVEL_APP",
    "LEVEL_CMP",
    "LEVEL_SYS",
    "EntityGraph",
    "build_entity_graph",
    "build_solution_system_context",
    "build_system_d2",
    "first_tag_value",
    "is_external_system",
    "render_markdown",
    "svg_markup",
    "system_page_name",
]
