"""Output generators for arch pack."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import yaml

from .models import first_value, tags_for_row

if TYPE_CHECKING:
    from pathlib import Path


def apply_tag_filters(
    *,
    entities: dict[str, list[dict[str, Any]]],
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
) -> dict[str, list[dict[str, Any]]]:
    """Filter entities by include/exclude tag lists."""
    include = {item.strip().lower() for item in include_tags or [] if item and item.strip()}
    exclude = {item.strip().lower() for item in exclude_tags or [] if item and item.strip()}

    if not include and not exclude:
        return {sheet: [dict(row) for row in rows] for sheet, rows in entities.items()}

    filtered: dict[str, list[dict[str, Any]]] = {sheet: [] for sheet in entities}
    for sheet, rows in entities.items():
        for row in rows:
            row_tags = tags_for_row(row)
            if include and not (row_tags & include):
                continue
            if exclude and (row_tags & exclude):
                continue
            filtered[sheet].append(dict(row))

    system_ids = {str(row.get("id", "")).strip() for row in filtered["sys"] if row.get("id")}
    app_ids = {str(row.get("id", "")).strip() for row in filtered["app"] if row.get("id")}
    cmp_ids = {str(row.get("id", "")).strip() for row in filtered["cmp"] if row.get("id")}
    usr_ids = {str(row.get("id", "")).strip() for row in filtered["usr"] if row.get("id")}
    node_ids = system_ids | app_ids | cmp_ids | usr_ids

    filtered["app"] = [
        row
        for row in filtered["app"]
        if str(first_value(row, ("sys", "system", "system_id", "sys_id")) or "").strip() in system_ids
    ]
    app_ids = {str(row.get("id", "")).strip() for row in filtered["app"] if row.get("id")}

    filtered["cmp"] = [
        row
        for row in filtered["cmp"]
        if str(first_value(row, ("app", "application", "app_id", "application_id")) or "").strip() in app_ids
    ]
    cmp_ids = {str(row.get("id", "")).strip() for row in filtered["cmp"] if row.get("id")}
    node_ids = system_ids | app_ids | cmp_ids | usr_ids

    filtered["usr"] = [
        row
        for row in filtered["usr"]
        if not first_value(row, ("app", "application", "app_id", "application_id"))
        or str(first_value(row, ("app", "application", "app_id", "application_id"))).strip() in app_ids
    ]
    usr_ids = {str(row.get("id", "")).strip() for row in filtered["usr"] if row.get("id")}
    node_ids = system_ids | app_ids | cmp_ids | usr_ids

    filtered["int"] = [
        row
        for row in filtered["int"]
        if str(first_value(row, ("src", "source", "from", "from_id", "src_id")) or "").strip() in node_ids
        and str(first_value(row, ("dst", "target", "to", "to_id", "dst_id")) or "").strip() in node_ids
    ]

    return filtered


def _node_lines(rows: list[dict[str, Any]], shape: str) -> list[str]:
    lines: list[str] = []
    for row in rows:
        node_id = str(row.get("id", "")).strip()
        if not node_id:
            continue
        name = str(row.get("name", node_id)).replace('"', "\\\"")
        lines.append(f"{node_id}: \"{name}\" {{shape: {shape}}}")
    return lines


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


def _integration_label(*, row: dict[str, Any], show_integration_ids: bool) -> str:
    name = str(row.get("name") or row.get("id") or "integration")
    int_type = str(first_value(row, ("type", "protocol", "kind")) or "").strip()
    label = f"{name} ({int_type})" if int_type else name
    if not show_integration_ids:
        return label
    integration_id = str(row.get("id") or "").strip()
    if not integration_id:
        return label
    return f"[{integration_id}] {label}"


def generate_d2(
    *,
    entities: dict[str, list[dict[str, Any]]],
    title: str,
    show_integration_ids: bool = False,
    show_arrowhead_ids: bool = False,
) -> str:
    """Generate D2 source from entities."""
    lines = [f"title: \"{title}\"", "", "# Nodes"]
    lines.extend(_node_lines(entities["sys"], "cloud"))
    lines.extend(_node_lines(entities["app"], "rectangle"))
    lines.extend(_node_lines(entities["cmp"], "cylinder"))
    lines.extend(_node_lines(entities["usr"], "person"))

    lines.append("")
    lines.append("# Ownership")

    for row in entities["app"]:
        app_id = str(row.get("id", "")).strip()
        sys_id = str(first_value(row, ("sys", "system", "system_id", "sys_id")) or "").strip()
        if app_id and sys_id:
            lines.append(f"{sys_id} -> {app_id}: \"hosts\"")

    for row in entities["cmp"]:
        cmp_id = str(row.get("id", "")).strip()
        app_id = str(first_value(row, ("app", "application", "app_id", "application_id")) or "").strip()
        if cmp_id and app_id:
            lines.append(f"{app_id} -> {cmp_id}: \"contains\"")

    lines.append("")
    lines.append("# Integrations")
    for row in entities["int"]:
        src_id = str(first_value(row, ("src", "source", "from", "from_id", "src_id")) or "").strip()
        dst_id = str(first_value(row, ("dst", "target", "to", "to_id", "dst_id")) or "").strip()
        label = _integration_label(row=row, show_integration_ids=show_integration_ids).replace('"', "\\\"")
        integration_id = str(row.get("id") or "").strip().replace('"', "\\\"")
        if src_id and dst_id:
            if show_arrowhead_ids and integration_id:
                lines.append(f"{src_id} -> {dst_id}: \"{label}\" {{")
                lines.append(f"  source-arrowhead.label: \"{integration_id}\"")
                lines.append(f"  target-arrowhead.label: \"{integration_id}\"")
                lines.append("}")
                continue
            lines.append(f"{src_id} -> {dst_id}: \"{label}\"")

    return "\n".join(lines).strip() + "\n"


def generate_markdown(*, entities: dict[str, list[dict[str, Any]]]) -> str:
    """Generate markdown summary from entities."""
    lines: list[str] = ["# Architecture Summary", ""]
    counts = {sheet: len(rows) for sheet, rows in entities.items()}
    lines.extend(
        [
            "## Counts",
            "",
            f"- Systems: {counts['sys']}",
            f"- Applications: {counts['app']}",
            f"- Components: {counts['cmp']}",
            f"- Integrations: {counts['int']}",
            f"- Users: {counts['usr']}",
            "",
        ]
    )

    for sheet, heading in (("sys", "Systems"), ("app", "Applications"), ("cmp", "Components"), ("usr", "Users")):
        lines.append(f"## {heading}")
        lines.append("")
        lines.append("| ID | Name | Tags |")
        lines.append("|---|---|---|")
        for row in entities[sheet]:
            row_id = str(row.get("id", "")).replace("|", "\\|")
            name = str(row.get("name", "")).replace("|", "\\|")
            tags = ", ".join(sorted(tags_for_row(row)))
            lines.append(f"| {row_id} | {name} | {tags} |")
        lines.append("")

    lines.append("## Integrations")
    lines.append("")
    lines.append("| ID | Source | Destination |")
    lines.append("|---|---|---|")
    for row in entities["int"]:
        row_id = str(row.get("id", "")).replace("|", "\\|")
        src = str(first_value(row, ("src", "source", "from", "from_id", "src_id")) or "").replace("|", "\\|")
        dst = str(first_value(row, ("dst", "target", "to", "to_id", "dst_id")) or "").replace("|", "\\|")
        lines.append(f"| {row_id} | {src} | {dst} |")
    lines.append("")

    return "\n".join(lines).strip() + "\n"


def serializable_entities(*, entities: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Return entities without internal bookkeeping keys."""
    cleaned: dict[str, list[dict[str, Any]]] = {}
    for sheet, rows in entities.items():
        cleaned[sheet] = []
        for row in rows:
            cleaned_row = {key: value for key, value in row.items() if not key.startswith("_")}
            cleaned[sheet].append(cleaned_row)
    return cleaned


def generate_json(
    *,
    entities: dict[str, list[dict[str, Any]]] | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    """Generate JSON output."""
    if payload is not None:
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if entities is None:
        raise ValueError("generate_json requires either entities or payload")
    return json.dumps(serializable_entities(entities=entities), indent=2, ensure_ascii=False) + "\n"


def generate_yaml(
    *,
    entities: dict[str, list[dict[str, Any]]] | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    """Generate YAML output."""
    if payload is not None:
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    if entities is None:
        raise ValueError("generate_yaml requires either entities or payload")
    return yaml.safe_dump(serializable_entities(entities=entities), sort_keys=False, allow_unicode=True)


def write_text(*, output_path: Path, content: str) -> str:
    """Write text content and return absolute path as string."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return str(output_path)


__all__ = [
    "apply_tag_filters",
    "generate_d2",
    "generate_json",
    "generate_markdown",
    "generate_yaml",
    "serializable_entities",
    "write_text",
]
