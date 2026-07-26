from __future__ import annotations

import pytest
from pydantic import ValidationError

from ot.catalog import (
    ActivationCondition,
    ConfigHook,
    InstallExtra,
    PackRequirement,
    RequirementKind,
    RuntimePackFacts,
    compose_catalog,
    parse_pack_requirements,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_composition_joins_runtime_facts_without_optional_pack_imports() -> None:
    facts = RuntimePackFacts(
        aliases=("br",),
        tools=("brave.search",),
        doc_slug="brave",
        requirements=(
            PackRequirement(
                kind=RequirementKind.SECRET,
                name="BRAVE_API_KEY",
                purpose="Authenticate Brave Search requests",
            ),
        ),
        config_hook=ConfigHook(model="otutil.tools.brave.Config"),
        active_config={"timeout": 30.0},
    )

    composed = {entry.guidance.pack: entry for entry in compose_catalog({"brave": facts})}

    assert composed["brave"].available
    assert composed["brave"].runtime == facts
    assert not composed["db"].available


def test_requirement_model_rejects_kind_specific_field_drift() -> None:
    with pytest.raises(ValidationError, match="import_name"):
        PackRequirement(
            kind=RequirementKind.LIB,
            name="openpyxl",
            purpose="Read Excel workbooks",
            install_extra=InstallExtra.UTIL,
        )

    with pytest.raises(ValidationError, match="valid only for lib"):
        PackRequirement(
            kind=RequirementKind.SECRET,
            name="TOKEN",
            purpose="Authenticate requests",
            import_name="wrong",
        )

    with pytest.raises(ValidationError, match="install_extra"):
        PackRequirement(
            kind=RequirementKind.LIB,
            name="openpyxl",
            import_name="openpyxl",
            purpose="Read Excel workbooks",
        )


def test_requirement_activation_is_typed() -> None:
    requirement = PackRequirement(
        kind=RequirementKind.CLI,
        name="d2",
        purpose="Render D2 diagrams",
        executable="d2",
        optional=True,
        activation=ActivationCondition(field="tools.diagram.backend", equals="d2"),
    )

    assert requirement.activation is not None
    assert requirement.activation.equals == "d2"


@pytest.mark.parametrize(
    ("record", "kind"),
    [
        (
            {
                "kind": "lib",
                "name": "openpyxl",
                "import_name": "openpyxl",
                "install_extra": "[util]",
                "purpose": "Read workbooks",
            },
            RequirementKind.LIB,
        ),
        (
            {
                "kind": "cli",
                "name": "Git",
                "executable": "git",
                "purpose": "Store snapshots",
            },
            RequirementKind.CLI,
        ),
        (
            {
                "kind": "secret",
                "name": "API_KEY",
                "purpose": "Authenticate requests",
            },
            RequirementKind.SECRET,
        ),
        (
            {
                "kind": "server",
                "name": "playwright",
                "purpose": "Control a browser",
            },
            RequirementKind.SERVER,
        ),
        (
            {
                "kind": "config",
                "name": "model",
                "purpose": "Select a model",
            },
            RequirementKind.CONFIG,
        ),
    ],
)
def test_normalized_requirement_parser_supports_every_kind(
    record: dict[str, object],
    kind: RequirementKind,
) -> None:
    parsed = parse_pack_requirements([record], source="fixture.py")

    assert parsed[0].kind is kind


@pytest.mark.parametrize(
    "legacy",
    [
        {"lib": [("openpyxl", "pip install openpyxl")]},
        [("openpyxl", "pip install openpyxl")],
        ["openpyxl"],
    ],
)
def test_normalized_requirement_parser_rejects_every_legacy_shape(
    legacy: object,
) -> None:
    with pytest.raises(ValueError, match=r"fixture\.py.*normalized requirement"):
        parse_pack_requirements(legacy, source="fixture.py")
