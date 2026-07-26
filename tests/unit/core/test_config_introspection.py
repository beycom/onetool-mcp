from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from ot.config.introspection import inspect_pack_config, redact_config

pytestmark = [pytest.mark.unit, pytest.mark.core]


class ExampleConfig(BaseModel):
    timeout: int = Field(default=30, ge=1, description="Request timeout")
    token: str = Field(default="", description="Private API token")
    headers: dict[str, str] = Field(default_factory=dict)


class NestedOptions(BaseModel):
    access_token: str = "nested-private-default"
    ordinary: str = "visible"


class NestedConfig(BaseModel):
    options: NestedOptions = Field(default_factory=NestedOptions)


def test_config_introspection_reports_schema_defaults_and_safe_errors() -> None:
    inspection = inspect_pack_config(
        ExampleConfig,
        expanded={
            "timeout": 0,
            "token": "literal-private-value",
            "headers": {"Authorization": "Bearer private-value"},
        },
        raw={
            "timeout": 0,
            "token": "${SERVICE_TOKEN}",
            "headers": {"Authorization": "${AUTH_HEADER}"},
        },
    )

    assert inspection.schema_["properties"]["timeout"]["description"] == "Request timeout"
    assert inspection.defaults["timeout"] == 30
    assert inspection.current["token"] == {
        "redacted": True,
        "set": True,
        "variable": "SERVICE_TOKEN",
    }
    assert inspection.current["headers"]["Authorization"] == {
        "redacted": True,
        "set": True,
        "variable": "AUTH_HEADER",
    }
    assert inspection.errors == (
        {
            "path": "timeout",
            "message": "Input should be greater than or equal to 1",
            "type": "greater_than_equal",
        },
    )
    assert "private-value" not in inspection.model_dump_json()


def test_nested_environment_and_credential_keys_are_redacted() -> None:
    value = {
        "transport": "stdio",
        "env": {"PUBLIC_NAME": "service", "TOKEN": "private"},
        "nested": {"client_secret": "private", "ordinary": "visible"},
    }

    redacted = redact_config(value)

    assert redacted["transport"] == "stdio"
    assert redacted["env"]["PUBLIC_NAME"] == {"redacted": True, "set": True}
    assert redacted["nested"]["client_secret"] == {
        "redacted": True,
        "set": True,
    }
    assert redacted["nested"]["ordinary"] == "visible"


def test_nested_sensitive_schema_defaults_are_redacted() -> None:
    inspection = inspect_pack_config(
        NestedConfig,
        expanded={},
    )

    nested_properties = inspection.schema_["$defs"]["NestedOptions"]["properties"]
    assert nested_properties["access_token"]["default"] == {
        "redacted": True,
        "set": True,
    }
    assert nested_properties["ordinary"]["default"] == "visible"
    assert "nested-private-default" not in inspection.model_dump_json()
