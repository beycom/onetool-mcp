"""Schema-v2 YAML/Excel loading and sparse normalization tests."""

from __future__ import annotations

from typing import Any

import pytest

from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.models import Change, CompleteState
from otdev.tools._arch.v2.normalize import normalize_change
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

pytestmark = [pytest.mark.unit, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES


def _without_sources(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_sources(item)
            for key, item in value.items()
            if key not in {"source", "source_location"}
        }
    if isinstance(value, list):
        return [_without_sources(item) for item in value]
    return value


@pytest.fixture
def base_state() -> CompleteState:
    """Return a compact complete state with a removable D subtree."""
    return CompleteState.model_validate(
        {
            "id": "base",
            "systems": [
                {"id": "A", "name": "System A", "description": "Original"},
                {"id": "B", "name": "System B"},
                {"id": "D", "name": "System D"},
            ],
            "applications": [
                {"id": "app-a", "name": "App A", "system": "A"},
                {"id": "app-d", "name": "App D", "system": "D"},
            ],
            "components": [
                {"id": "cmp-d", "name": "Component D", "application": "app-d"}
            ],
            "interfaces": [
                {
                    "id": "A-to-D",
                    "name": "A to D",
                    "provider": "app-a",
                    "consumer": "app-d",
                }
            ],
        }
    )


def _change(*, change_id: str = "change", patches: dict[str, Any]) -> Change:
    return Change.model_validate(
        {"id": change_id, "name": change_id, "patches": patches}
    )


def test_canonical_yaml_excel_load_identically() -> None:
    """Canonical paired YAML/Excel fixtures preserve the same schema-v2 semantics."""
    yaml_document = load_workspace(FIXTURES / "arch-v2-canonical.yaml")
    excel_document = load_workspace(FIXTURES / "arch-v2-canonical.xlsx")

    yaml_payload = _without_sources(yaml_document.workspace.model_dump(mode="json"))
    excel_payload = _without_sources(excel_document.workspace.model_dump(mode="json"))
    assert excel_payload == yaml_payload
    assert "states[0].interfaces[0].provider" in yaml_document.sources
    assert any(
        location.sheet == "interface" for location in excel_document.sources.values()
    )


def test_sparse_change_a_b_c_d() -> None:
    """sparse-change-a-b-c-d: sparse intent derives modify/add/remove operations."""
    workspace = load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace
    result = normalize_change(state=workspace.states[0], change=workspace.changes[0])
    operations = {
        (item.kind, item.entity_kind, item.entity_id)
        for item in result.change.operations
    }

    assert result.issues.errors == []
    assert ("modify", "system", "A") in operations
    assert ("add", "system", "B") in operations
    assert ("add", "system", "C") in operations
    assert ("remove", "system", "D") in operations
    assert all(item.source is not None for item in result.change.operations)


def test_blank_versus_unset(base_state: CompleteState) -> None:
    """blank-versus-unset: blank is a no-op while unset explicitly clears."""
    blank = _change(patches={"systems": [{"id": "A", "description": None}]})
    unset = _change(patches={"systems": [{"id": "A", "unset": ["description"]}]})

    assert normalize_change(state=base_state, change=blank).change.operations == []
    unset_operations = normalize_change(
        state=base_state, change=unset
    ).change.operations
    assert len(unset_operations) == 1
    assert unset_operations[0].kind == "modify"
    assert unset_operations[0].unset == ["description"]


def test_asserted_change_reorder(base_state: CompleteState) -> None:
    """asserted-change-reorder: asserted modify-before-add is an error."""
    change = _change(
        patches={
            "systems": [
                {"id": "future", "change_type": "changed", "description": "Too early"}
            ]
        }
    )
    result = normalize_change(state=base_state, change=change)
    assert [issue.code for issue in result.issues.errors] == ["arch.modify_before_add"]


def test_move_normalization(base_state: CompleteState) -> None:
    """move-normalization: containment changes become explicit move operations."""
    change = _change(patches={"applications": [{"id": "app-a", "parent": "B"}]})
    result = normalize_change(state=base_state, change=change)

    assert result.issues.errors == []
    assert len(result.change.operations) == 1
    operation = result.change.operations[0]
    assert operation.kind == "move"
    assert operation.from_parent == "A"
    assert operation.to_parent == "B"


@pytest.mark.parametrize(
    "patch,missing",
    [
        ({"id": "new-system"}, ["name"]),
        ({"id": "new-app", "name": "New App"}, ["system"]),
        ({"id": "new-component", "name": "New Component"}, ["application"]),
    ],
)
def test_incomplete_add_property(
    base_state: CompleteState, patch: dict[str, Any], missing: list[str]
) -> None:
    """incomplete-add property: every entity kind retains required-add fields."""
    field = {
        "new-system": "systems",
        "new-app": "applications",
        "new-component": "components",
    }[patch["id"]]
    result = normalize_change(
        state=base_state, change=_change(patches={field: [patch]})
    )
    assert result.issues.errors[0].code == "arch.incomplete_add"
    assert result.issues.errors[0].details["missing_fields"] == missing


def test_missing_interface_endpoint(base_state: CompleteState) -> None:
    """missing-interface-endpoint: additions require both existing endpoints."""
    change = _change(
        patches={
            "interfaces": [
                {
                    "id": "missing-edge",
                    "name": "Missing edge",
                    "provider": "app-a",
                    "consumer": "not-present",
                }
            ]
        }
    )
    result = normalize_change(state=base_state, change=change)
    assert [issue.code for issue in result.issues.errors] == [
        "arch.missing_interface_endpoint"
    ]


def test_added_parent_must_have_the_correct_entity_kind(
    base_state: CompleteState,
) -> None:
    """A planned interface ID cannot satisfy an application's system parent."""
    change = _change(
        patches={
            "applications": [{"id": "new-app", "name": "New", "parent": "future"}],
            "interfaces": [
                {
                    "id": "future",
                    "name": "Future interface",
                    "provider": "app-a",
                    "consumer": "B",
                }
            ],
        }
    )

    result = normalize_change(state=base_state, change=change)

    assert "arch.missing_parent" in {issue.code for issue in result.issues.errors}
    assert not any(
        operation.entity_kind == "application" and operation.entity_id == "new-app"
        for operation in result.change.operations
    )


def test_interface_endpoint_cannot_use_a_planned_non_endpoint(
    base_state: CompleteState,
) -> None:
    """A planned relationship ID cannot satisfy an interface endpoint."""
    change = _change(
        patches={
            "interfaces": [
                {
                    "id": "new-interface",
                    "name": "New interface",
                    "provider": "app-a",
                    "consumer": "future-relationship",
                }
            ],
            "relationships": [
                {
                    "id": "future-relationship",
                    "name": "Future relationship",
                    "source_id": "A",
                    "target_id": "B",
                }
            ],
        }
    )

    result = normalize_change(state=base_state, change=change)

    assert "arch.missing_interface_endpoint" in {
        issue.code for issue in result.issues.errors
    }


def test_modified_endpoint_must_exist_after_the_change(
    base_state: CompleteState,
) -> None:
    """Modifying an interface cannot create a missing or removed endpoint."""
    missing = _change(
        patches={"interfaces": [{"id": "A-to-D", "consumer": "not-present"}]}
    )
    removed = _change(
        patches={
            "systems": [{"id": "B", "change_type": "removed"}],
            "interfaces": [{"id": "A-to-D", "consumer": "B"}],
        }
    )

    assert [
        issue.code
        for issue in normalize_change(state=base_state, change=missing).issues.errors
    ] == ["arch.missing_interface_endpoint"]
    assert "arch.missing_interface_endpoint" in {
        issue.code
        for issue in normalize_change(state=base_state, change=removed).issues.errors
    }


def test_invalid_planned_add_cannot_satisfy_a_dependent_reference(
    base_state: CompleteState,
) -> None:
    """Invalid or asserted-changed additions are unavailable to dependent entities."""
    change = _change(
        patches={
            "applications": [
                {
                    "id": "phantom-app",
                    "name": "Phantom",
                    "change_type": "changed",
                },
                {"id": "orphan-app", "name": "Orphan", "parent": "missing"},
            ],
            "interfaces": [
                {
                    "id": "phantom-interface",
                    "name": "Phantom interface",
                    "provider": "app-a",
                    "consumer": "phantom-app",
                },
                {
                    "id": "orphan-interface",
                    "name": "Orphan interface",
                    "provider": "app-a",
                    "consumer": "orphan-app",
                },
            ],
        }
    )

    result = normalize_change(state=base_state, change=change)

    codes = [issue.code for issue in result.issues.errors]
    assert "arch.modify_before_add" in codes
    assert "arch.missing_parent" in codes
    assert codes.count("arch.missing_interface_endpoint") == 2
    assert not any(
        operation.entity_id in {"phantom-interface", "orphan-interface"}
        for operation in result.change.operations
    )


def test_added_entity_id_is_unique_across_kinds(base_state: CompleteState) -> None:
    """A sparse change cannot introduce a stable ID already used by another kind."""
    change = _change(
        patches={
            "interfaces": [
                {
                    "id": "A",
                    "name": "Conflicting interface",
                    "provider": "app-a",
                    "consumer": "B",
                }
            ]
        }
    )

    result = normalize_change(state=base_state, change=change)

    assert [issue.code for issue in result.issues.errors] == ["arch.duplicate_id"]
    assert result.change.operations == []


@pytest.mark.parametrize(
    "patches,code",
    [
        (
            {
                "systems": [
                    {"id": "A", "description": "First"},
                    {"id": "A", "description": "Second"},
                ]
            },
            "arch.duplicate_operation",
        ),
        (
            {
                "systems": [
                    {"id": "A", "description": "Changed", "expected": {"name": "Wrong"}}
                ]
            },
            "arch.stale_precondition",
        ),
        (
            {"applications": [{"id": "app-a", "parent": "missing-system"}]},
            "arch.invalid_move",
        ),
        (
            {"systems": [{"id": "A", "unset": ["name"]}]},
            "arch.incompatible_field_change",
        ),
        (
            {"applications": [{"id": "new-app", "name": "New", "parent": "missing"}]},
            "arch.missing_parent",
        ),
    ],
)
def test_operation_precondition_validation(
    base_state: CompleteState, patches: dict[str, Any], code: str
) -> None:
    """Existence, stale values, parents, duplicates, and fields fail precisely."""
    result = normalize_change(state=base_state, change=_change(patches=patches))
    assert code in {issue.code for issue in result.issues.errors}


def test_cascade_system_removal(base_state: CompleteState) -> None:
    """cascade-system-removal: descendants and connected interfaces are removed."""
    change = _change(patches={"systems": [{"id": "D", "change_type": "removed"}]})
    result = normalize_change(state=base_state, change=change)
    removed = {
        (item.entity_kind, item.entity_id): item for item in result.change.operations
    }

    assert set(removed) == {
        ("system", "D"),
        ("application", "app-d"),
        ("component", "cmp-d"),
        ("interface", "A-to-D"),
    }
    assert removed[("interface", "A-to-D")].generated is True
    assert removed[("component", "cmp-d")].initiating_ancestor == "D"


def test_cascade_explicit_child_dedup(base_state: CompleteState) -> None:
    """cascade-explicit-child-dedup: explicit child and cascade normalize once."""
    change = _change(
        patches={
            "systems": [{"id": "D", "change_type": "removed"}],
            "applications": [{"id": "app-d", "change_type": "removed"}],
        }
    )
    result = normalize_change(state=base_state, change=change)
    app_removals = [
        item
        for item in result.change.operations
        if item.kind == "remove" and item.entity_id == "app-d"
    ]

    assert len(app_removals) == 1
    assert app_removals[0].generated is False
    assert app_removals[0].initiating_ancestor == "D"
