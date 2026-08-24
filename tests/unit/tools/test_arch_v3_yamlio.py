"""YAML contract tests for architecture schema v3."""

from __future__ import annotations

from pathlib import Path

import pytest

from otdev.tools._arch.v3.yamlio import (
    ArchitectureLoadError,
    dump_architecture,
    load_architecture,
)

pytestmark = [pytest.mark.unit, pytest.mark.tools]

CANONICAL_YAML = """\
schema_version: 3
milestones:
  - id: phase-1
    name: Consolidate payments
  - id: phase-2
    name: Retire legacy clearing
timelines:
  - id: preferred
    milestones: [phase-1, phase-2]
systems:
  - id: payments
    name: Payments
  - id: legacy-clearing
    name: Legacy Clearing
    end_in: phase-1
containers:
  - id: payments-api
    name: Payments API
    parent: payments
  - id: clearing-api
    name: Clearing API
    parent: legacy-clearing
    end_in: phase-1
  - id: new-clearing
    name: Clearing
    parent: payments
    start_in: phase-2
components: []
code: []
users:
  - id: customer
    name: Customer
  - id: payments-team
    name: Payments Team
interfaces:
  - id: payments-to-clearing
    name: Submit clearing request
    provider: clearing-api
    consumer: payments-api
    call_direction: consumer_to_provider
    end_in: phase-1
  - id: payments-to-new-clearing
    name: Submit clearing request
    provider: new-clearing
    consumer: payments-api
    call_direction: consumer_to_provider
    start_in: phase-2
relationships:
  - id: payments-owned-by-team
    source: payments-team
    action: owns
    target: payments
"""

MINIMAL_YAML = """\
schema_version: 3
milestones: []
systems: []
containers: []
components: []
code: []
users: []
interfaces: []
relationships: []
"""


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_canonical_example_loads(tmp_path: Path) -> None:
    architecture = load_architecture(
        _write(tmp_path / "architecture.yaml", CANONICAL_YAML)
    )

    assert architecture.schema_version == 3
    assert len(architecture.containers) == 3
    assert architecture.relationships[0].action == "owns"


def test_round_trip_is_semantic_and_idempotent(tmp_path: Path) -> None:
    source = _write(tmp_path / "source.yaml", CANONICAL_YAML)
    first_dump = tmp_path / "first.yaml"
    second_dump = tmp_path / "second.yaml"

    original = load_architecture(source)
    dump_architecture(original, first_dump)
    reloaded = load_architecture(first_dump)
    dump_architecture(reloaded, second_dump)

    assert reloaded == original
    assert second_dump.read_bytes() == first_dump.read_bytes()


def test_code_round_trips(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "source.yaml",
        MINIMAL_YAML.replace(
            "components: []\ncode: []",
            "components:\n  - id: component\n    name: Component\n    container: container\n"
            "code:\n  - id: code\n    name: Code\n    component: component",
        )
        .replace(
            "containers: []",
            "containers:\n  - id: container\n    name: Container\n    parent: system",
        )
        .replace("systems: []", "systems:\n  - id: system\n    name: System"),
    )
    output = tmp_path / "output.yaml"

    architecture = load_architecture(source)
    dump_architecture(architecture, output)

    assert load_architecture(output) == architecture
    assert architecture.code[0].component == "component"


def test_direction_defaults_are_applied_and_omitted(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "source.yaml",
        MINIMAL_YAML.replace(
            "systems: []", "systems:\n  - id: system\n    name: System"
        ).replace(
            "interfaces: []",
            "interfaces:\n  - id: interface\n    name: Interface\n"
            "    provider: system\n    consumer: system",
        ),
    )
    output = tmp_path / "output.yaml"

    architecture = load_architecture(source)
    assert architecture.interfaces[0].call_direction == "consumer_to_provider"
    assert architecture.interfaces[0].data_flow_direction == "provider_to_consumer"

    dump_architecture(architecture, output)

    dumped = output.read_text(encoding="utf-8")
    assert "call_direction" not in dumped
    assert "data_flow_direction" not in dumped


@pytest.mark.parametrize(
    "invalid_yaml",
    [
        MINIMAL_YAML + "unknown: value\n",
        MINIMAL_YAML.replace(
            "systems: []", "systems:\n  - id: 'bad id'\n    name: Bad"
        ),
        MINIMAL_YAML.replace("systems: []", "systems:\n  - id: bad\n    name: null"),
        MINIMAL_YAML.replace(
            "systems: []",
            "systems:\n  - &base\n    id: base\n    name: Base\n  - <<: *base\n    id: copy",
        ),
    ],
    ids=["unknown-field", "bad-id", "null", "anchor-merge-key"],
)
def test_rejects_invalid_yaml(tmp_path: Path, invalid_yaml: str) -> None:
    source = _write(tmp_path / "invalid.yaml", invalid_yaml)

    with pytest.raises(ArchitectureLoadError):
        load_architecture(source)
