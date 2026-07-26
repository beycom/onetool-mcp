"""Safe pack-configuration schema and current-state introspection."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|authorization|bearer|cookie|credential|environment|"
    r"headers?|password|passwd|private[_-]?key|secret|token)",
    re.IGNORECASE,
)
_SENSITIVE_CONTAINERS = frozenset({"auth", "env", "environment", "headers"})
_VARIABLE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class ConfigInspection(BaseModel):
    """Redacted schema, defaults, current state, and validation errors."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_: dict[str, Any] = Field(alias="schema")
    defaults: dict[str, Any]
    current: dict[str, Any]
    errors: tuple[dict[str, str], ...] = ()


def _presence(value: Any, raw_value: Any = None) -> dict[str, Any]:
    raw_match = _VARIABLE.fullmatch(raw_value) if isinstance(raw_value, str) else None
    result: dict[str, Any] = {
        "redacted": True,
        "set": value not in (None, "", [], {}),
    }
    if raw_match:
        result["variable"] = raw_match.group(1)
    return result


def _schema_marks_sensitive(schema: dict[str, Any] | None) -> bool:
    if not schema:
        return False
    return bool(
        schema.get("writeOnly")
        or schema.get("format") in {"password", "secret"}
        or _SENSITIVE_KEY.search(str(schema.get("title", "")))
    )


def redact_config(
    value: Any,
    *,
    raw_value: Any = None,
    key: str = "",
    schema: dict[str, Any] | None = None,
    sensitive_parent: bool = False,
) -> Any:
    """Conservatively redact credential-like values while preserving structure."""

    sensitive = (
        sensitive_parent
        or key.lower() in _SENSITIVE_CONTAINERS
        or bool(_SENSITIVE_KEY.search(key))
        or _schema_marks_sensitive(schema)
    )
    if isinstance(value, dict):
        properties = schema.get("properties", {}) if schema else {}
        raw_mapping = raw_value if isinstance(raw_value, dict) else {}
        return {
            item_key: redact_config(
                item_value,
                raw_value=raw_mapping.get(item_key),
                key=item_key,
                schema=properties.get(item_key),
                sensitive_parent=sensitive,
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        item_schema = schema.get("items") if schema else None
        raw_items = raw_value if isinstance(raw_value, list) else []
        return [
            redact_config(
                item,
                raw_value=raw_items[index] if index < len(raw_items) else None,
                key=key,
                schema=item_schema,
                sensitive_parent=sensitive,
            )
            for index, item in enumerate(value)
        ]
    if sensitive:
        return _presence(value, raw_value)
    return value


def _redact_schema_defaults(
    schema: Any,
    *,
    field_name: str = "",
    sensitive_parent: bool = False,
) -> None:
    """Redact sensitive defaults in a JSON-schema subtree in place."""

    if isinstance(schema, list):
        for item in schema:
            _redact_schema_defaults(
                item,
                field_name=field_name,
                sensitive_parent=sensitive_parent,
            )
        return
    if not isinstance(schema, dict):
        return

    sensitive = (
        sensitive_parent
        or bool(_SENSITIVE_KEY.search(field_name))
        or _schema_marks_sensitive(schema)
    )
    if sensitive and "default" in schema:
        schema["default"] = _presence(schema["default"])

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, property_schema in properties.items():
            _redact_schema_defaults(
                property_schema,
                field_name=str(name),
                sensitive_parent=sensitive,
            )

    for key, child in schema.items():
        if key in {"default", "properties"}:
            continue
        _redact_schema_defaults(
            child,
            field_name=field_name,
            sensitive_parent=sensitive,
        )


def safe_model_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a model JSON schema with credential-like defaults redacted."""

    schema = model.model_json_schema()
    _redact_schema_defaults(schema)
    return schema


def _plain_config_value(value: Any) -> Any:
    """Convert nested model defaults into structures understood by redaction."""

    if isinstance(value, BaseModel):
        return {
            key: _plain_config_value(item)
            for key, item in value.model_dump(mode="python").items()
        }
    if isinstance(value, dict):
        return {
            key: _plain_config_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain_config_value(item) for item in value]
    return value


def _model_defaults(model: type[BaseModel], schema: dict[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    properties = schema.get("properties", {})
    for name, model_field in model.model_fields.items():
        if model_field.is_required():
            continue
        default = _plain_config_value(
            model_field.get_default(call_default_factory=True)
        )
        defaults[name] = redact_config(
            default,
            key=name,
            schema=properties.get(name),
        )
    return defaults


def inspect_pack_config(
    model: type[BaseModel],
    *,
    expanded: dict[str, Any],
    raw: dict[str, Any] | None = None,
) -> ConfigInspection:
    """Validate and safely inspect one pack's expanded active configuration."""

    schema = safe_model_schema(model)
    errors: tuple[dict[str, str], ...] = ()
    try:
        model.model_validate(expanded)
    except ValidationError as exc:
        errors = tuple(
            {
                "path": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors(include_input=False, include_context=False)
        )
    return ConfigInspection(
        schema=schema,
        defaults=_model_defaults(model, schema),
        current=redact_config(
            expanded,
            raw_value=raw or {},
            schema=schema,
        ),
        errors=errors,
    )
