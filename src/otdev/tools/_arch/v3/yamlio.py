"""Location-aware YAML input and deterministic output for schema v3."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from weakref import ReferenceType, ref

import yaml
from pydantic import ValidationError
from yaml.events import AliasEvent, NodeEvent
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from .model import Architecture

DataPath = tuple[str | int, ...]
SourceMark = tuple[int, int]
SourceDocument = tuple[ReferenceType[Architecture], Path, dict[DataPath, SourceMark]]

_SOURCE_DOCUMENTS: dict[int, SourceDocument] = {}

_ROOT_KEYS = (
    "schema_version",
    "milestones",
    "timelines",
    "theme",
    "layout",
    "systems",
    "subsystems",
    "containers",
    "components",
    "code",
    "users",
    "interfaces",
    "relationships",
)
_ROW_KEYS = {
    "milestones": ("id", "name", "description", "tags", "properties"),
    "timelines": ("id", "milestones"),
    "systems": (
        "id",
        "name",
        "start_in",
        "end_in",
        "description",
        "tags",
        "properties",
    ),
    "subsystems": (
        "id",
        "name",
        "parent",
        "start_in",
        "end_in",
        "description",
        "tags",
        "properties",
    ),
    "containers": (
        "id",
        "name",
        "parent",
        "start_in",
        "end_in",
        "description",
        "tags",
        "properties",
    ),
    "components": (
        "id",
        "name",
        "container",
        "start_in",
        "end_in",
        "description",
        "tags",
        "properties",
    ),
    "code": (
        "id",
        "name",
        "component",
        "start_in",
        "end_in",
        "description",
        "tags",
        "properties",
    ),
    "users": ("id", "name", "start_in", "end_in", "description", "tags", "properties"),
    "interfaces": (
        "id",
        "name",
        "provider",
        "consumer",
        "call_direction",
        "data_flow_direction",
        "start_in",
        "end_in",
        "description",
        "tags",
        "properties",
    ),
    "relationships": (
        "id",
        "action",
        "source",
        "target",
        "start_in",
        "end_in",
        "description",
        "tags",
        "properties",
    ),
}


class ArchitectureLoadError(ValueError):
    """Raised when a YAML file cannot be loaded as schema v3."""


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, _data: Any) -> bool:
        return True


def _mark(node: Node) -> SourceMark:
    return node.start_mark.line + 1, node.start_mark.column + 1


def format_data_path(path: DataPath) -> str:
    rendered = ""
    for part in path:
        rendered += (
            f"[{part}]" if isinstance(part, int) else (f".{part}" if rendered else part)
        )
    return rendered or "<root>"


def _yaml_error(path: Path, mark: SourceMark, message: str) -> ArchitectureLoadError:
    return ArchitectureLoadError(f"{path}:{mark[0]}:{mark[1]}: {message}")


def _inspect_node(
    node: Node,
    *,
    file_path: Path,
    data_path: DataPath,
    marks: dict[DataPath, SourceMark],
) -> None:
    marks[data_path] = _mark(node)
    if isinstance(node, ScalarNode) and node.tag == "tag:yaml.org,2002:null":
        raise _yaml_error(file_path, _mark(node), "YAML null values are not allowed")
    if isinstance(node, SequenceNode):
        for index, child in enumerate(node.value):
            _inspect_node(
                child,
                file_path=file_path,
                data_path=(*data_path, index),
                marks=marks,
            )
    elif isinstance(node, MappingNode):
        for key_node, value_node in node.value:
            key = key_node.value if isinstance(key_node, ScalarNode) else "<key>"
            child_path = (*data_path, key)
            marks[child_path] = _mark(key_node)
            if key_node.tag == "tag:yaml.org,2002:merge" or key == "<<":
                raise _yaml_error(
                    file_path, _mark(key_node), "YAML merge keys are not allowed"
                )
            _inspect_node(
                value_node,
                file_path=file_path,
                data_path=child_path,
                marks=marks,
            )


def _parse_yaml(*, text: str, path: Path) -> tuple[Any, dict[DataPath, SourceMark]]:
    try:
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            mark = event.start_mark.line + 1, event.start_mark.column + 1
            if isinstance(event, AliasEvent):
                raise _yaml_error(path, mark, "YAML aliases are not allowed")
            if isinstance(event, NodeEvent) and event.anchor is not None:
                raise _yaml_error(path, mark, "YAML anchors are not allowed")
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if node is None:
            raise ArchitectureLoadError(f"{path}:1:1: YAML document is empty")
        marks: dict[DataPath, SourceMark] = {}
        _inspect_node(node, file_path=path, data_path=(), marks=marks)
        return yaml.safe_load(text), marks
    except ArchitectureLoadError:
        raise
    except yaml.YAMLError as exc:
        problem_mark = getattr(exc, "problem_mark", None)
        mark = (
            (problem_mark.line + 1, problem_mark.column + 1)
            if problem_mark is not None
            else (1, 1)
        )
        raise _yaml_error(path, mark, str(exc)) from exc


def _source_mark(loc: DataPath, marks: dict[DataPath, SourceMark]) -> SourceMark:
    for length in range(len(loc), -1, -1):
        if loc[:length] in marks:
            return marks[loc[:length]]
    return 1, 1


def _remember_source(
    architecture: Architecture, path: Path, marks: dict[DataPath, SourceMark]
) -> None:
    identity = id(architecture)

    def forget(dead: ReferenceType[Architecture]) -> None:
        stored = _SOURCE_DOCUMENTS.get(identity)
        if stored is not None and stored[0] is dead:
            _SOURCE_DOCUMENTS.pop(identity, None)

    reference = ref(architecture, forget)
    _SOURCE_DOCUMENTS[identity] = reference, path, marks


def source_location(
    architecture: Architecture, data_path: DataPath
) -> tuple[Path | None, SourceMark | None]:
    """Return the loaded file and nearest YAML mark for a model path."""
    source = _SOURCE_DOCUMENTS.get(id(architecture))
    if source is None or source[0]() is not architecture:
        return None, None
    return source[1], _source_mark(data_path, source[2])


def _validation_message(
    *, path: Path, error: ValidationError, marks: dict[DataPath, SourceMark]
) -> str:
    lines: list[str] = []
    for detail in error.errors(include_url=False):
        loc = tuple(part for part in detail["loc"] if isinstance(part, (str, int)))
        mark = _source_mark(loc, marks)
        lines.append(
            f"{path}:{mark[0]}:{mark[1]}: {format_data_path(loc)}: {detail['msg']}"
        )
    return "\n".join(lines)


def load_architecture(path: Path) -> Architecture:
    """Load and validate a schema-v3 YAML architecture."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ArchitectureLoadError(
            f"Unable to read architecture '{path}': {exc}"
        ) from exc
    raw, marks = _parse_yaml(text=text, path=path)
    if not isinstance(raw, dict):
        raise _yaml_error(
            path, marks.get((), (1, 1)), "YAML document must contain a mapping"
        )
    try:
        architecture = Architecture.model_validate(raw)
    except ValidationError as exc:
        raise ArchitectureLoadError(
            _validation_message(path=path, error=exc, marks=marks)
        ) from exc
    _remember_source(architecture, path, marks)
    return architecture


def _ordered_row(row: dict[str, Any], *, collection: str) -> dict[str, Any]:
    if collection == "interfaces":
        if row.get("call_direction") == "consumer_to_provider":
            row.pop("call_direction")
        if row.get("data_flow_direction") == "provider_to_consumer":
            row.pop("data_flow_direction")
    ordered = {key: row[key] for key in _ROW_KEYS[collection] if key in row}
    if "properties" in ordered:
        ordered["properties"] = dict(sorted(ordered["properties"].items()))
    return ordered


def _architecture_payload(architecture: Architecture) -> dict[str, Any]:
    raw = architecture.model_dump(
        mode="python",
        by_alias=True,
        exclude_none=True,
        exclude_unset=True,
    )
    payload: dict[str, Any] = {}
    for key in _ROOT_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if key in _ROW_KEYS:
            payload[key] = [_ordered_row(row, collection=key) for row in value]
        elif key == "layout" and isinstance(value, dict):
            spacing = value.get("spacing")
            ordered_spacing = (
                {
                    spacing_key: spacing[spacing_key]
                    for spacing_key in (
                        "node",
                        "layer",
                        "boundary",
                        *sorted(set(spacing) - {"node", "layer", "boundary"}),
                    )
                    if spacing_key in spacing
                }
                if isinstance(spacing, dict)
                else spacing
            )
            payload[key] = {
                layout_key: ordered_spacing
                if layout_key == "spacing"
                else value[layout_key]
                for layout_key in (
                    "method",
                    "direction",
                    "spacing",
                    "ranking",
                    "user_choice",
                    *sorted(
                        set(value)
                        - {
                            "method",
                            "direction",
                            "spacing",
                            "ranking",
                            "user_choice",
                        }
                    ),
                )
                if layout_key in value
            }
        else:
            payload[key] = value
    return payload


def dump_architecture(architecture: Architecture, path: Path) -> None:
    """Write an architecture as deterministic, alias-free YAML."""
    content = yaml.dump(
        _architecture_payload(architecture),
        Dumper=_NoAliasDumper,
        allow_unicode=True,
        default_flow_style=False,
        indent=2,
        sort_keys=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f".{path.name}.",
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
