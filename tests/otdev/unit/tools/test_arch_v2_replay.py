"""Schema-v2 roadmap replay, comparison, and diagnostic tests."""

from __future__ import annotations

import json
from typing import Any

import pytest

from otdev.tools._arch.v2.compare import compare_states, materialize_change
from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.models import ArchitectureWorkspace, CompleteState
from otdev.tools._arch.v2.normalize import normalize_change
from otdev.tools._arch.v2.replay import replay_roadmap, validate_roadmap
from tests.otdev.arch_v2_fixtures import ARCH_V2_FIXTURES

pytestmark = [pytest.mark.unit, pytest.mark.tools]

FIXTURES = ARCH_V2_FIXTURES


@pytest.fixture
def canonical() -> ArchitectureWorkspace:
    """Load the canonical roadmap fixture through the production YAML loader."""
    return load_workspace(FIXTURES / "arch-v2-canonical.yaml").workspace


def _workspace(
    *,
    state: dict[str, Any],
    changes: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> ArchitectureWorkspace:
    return ArchitectureWorkspace.model_validate(
        {
            "schema_version": 2,
            "states": [state],
            "changes": changes,
            "roadmaps": [{"id": "delivery", "base": state["id"], "items": items}],
        }
    )


def _effect(operation: Any) -> str:
    """Return the semantic mutation independent of generated operation identity."""
    return json.dumps(
        {
            "kind": operation.kind,
            "entity_kind": operation.entity_kind,
            "entity_id": operation.entity_id,
            "values": operation.values,
            "unset": operation.unset,
            "from_parent": operation.from_parent,
            "to_parent": operation.to_parent,
        },
        sort_keys=True,
    )


def test_named_linear_roadmap_validation(canonical: ArchitectureWorkspace) -> None:
    """Named roadmaps require known changes and unique contiguous orders."""
    payload = canonical.model_dump(mode="python")
    payload["roadmaps"][0]["items"][1]["order"] = 3
    workspace = ArchitectureWorkspace.model_validate(payload)

    result = validate_roadmap(workspace=workspace, roadmap=workspace.roadmaps[0])

    assert [issue.code for issue in result.errors] == [
        "arch.non_contiguous_roadmap_orders"
    ]


def test_resolve_base_zero(canonical: ArchitectureWorkspace) -> None:
    """resolve-base-zero: base is the implicit complete order zero."""
    through = replay_roadmap(workspace=canonical, roadmap_id="preferred", through="base")
    order = replay_roadmap(workspace=canonical, roadmap_id="preferred", order=0)

    assert through.issues.errors == order.issues.errors == []
    assert through.resolved is not None
    assert order.resolved is not None
    assert through.resolved.order == order.resolved.order == 0
    assert through.resolved.state.model_copy(update={"id": "same"}) == order.resolved.state.model_copy(
        update={"id": "same"}
    )


def test_resolve_through_equals_order(canonical: ArchitectureWorkspace) -> None:
    """resolve-through-equals-order: ID and numeric endpoints are equivalent."""
    through = replay_roadmap(
        workspace=canonical,
        roadmap_id="preferred",
        through="arch-v2-change-2027",
    )
    order = replay_roadmap(workspace=canonical, roadmap_id="preferred", order=1)

    assert through.resolved is not None
    assert order.resolved is not None
    assert through.resolved.state == order.resolved.state
    assert [item.change_id for item in through.resolved.history] == [
        "arch-v2-change-2027"
    ]


def test_resolve_final_default(canonical: ArchitectureWorkspace) -> None:
    """resolve-final-default: an omitted endpoint selects the final change."""
    result = replay_roadmap(workspace=canonical, roadmap_id="preferred")

    assert result.resolved is not None
    assert result.resolved.order == 2
    assert result.resolved.through == "arch-v2-change-2028"
    assert {system.id for system in result.resolved.state.systems} >= {"A", "B", "C", "I"}


def test_modify_before_add_order_error() -> None:
    """modify-before-add-order-error: source order fails with an advisory dependency."""
    workspace = _workspace(
        state={"id": "base"},
        changes=[
            {
                "id": "modify-future",
                "name": "Modify future",
                "patches": {
                    "systems": [
                        {
                            "id": "future",
                            "change_type": "changed",
                            "description": "Changed too soon",
                        }
                    ]
                },
            },
            {
                "id": "add-future",
                "name": "Add future",
                "patches": {
                    "systems": [
                        {"id": "future", "change_type": "added", "name": "Future"}
                    ]
                },
            },
        ],
        items=[
            {"change": "modify-future", "order": 1},
            {"change": "add-future", "order": 2},
        ],
    )

    result = replay_roadmap(workspace=workspace, roadmap_id="delivery")

    assert result.resolved is None
    assert [issue.code for issue in result.issues.errors] == ["arch.modify_before_add"]
    assert result.issues.errors[0].details["suggested_dependency"] == "add-future"
    assert workspace.roadmaps[0].items[0].change == "modify-future"


def test_valid_order_sensitive_warning() -> None:
    """valid-order-sensitive-warning: valid alternate orders expose changed fields."""
    workspace = _workspace(
        state={
            "id": "base",
            "systems": [{"id": "shared", "name": "Shared", "description": "base"}],
        },
        changes=[
            {
                "id": "first",
                "name": "First",
                "patches": {"systems": [{"id": "shared", "description": "first"}]},
            },
            {
                "id": "second",
                "name": "Second",
                "patches": {"systems": [{"id": "shared", "description": "second"}]},
            },
        ],
        items=[
            {"change": "first", "order": 1},
            {"change": "second", "order": 2},
        ],
    )

    result = replay_roadmap(workspace=workspace, roadmap_id="delivery")

    assert [issue.code for issue in result.issues.warnings] == ["arch.order_sensitive"]
    assert result.issues.warnings[0].details == {
        "changes": ["first", "second"],
        "fields": ["description"],
    }


def test_stale_derived_precondition() -> None:
    """stale-derived-precondition: a changed derivation base rejects replay."""
    base = CompleteState.model_validate(
        {"id": "base", "systems": [{"id": "A", "name": "A", "description": "old"}]}
    )
    target = CompleteState.model_validate(
        {"id": "target", "systems": [{"id": "A", "name": "A", "description": "new"}]}
    )
    changed_base = base.model_copy(
        update={
            "systems": [
                base.systems[0].model_copy(update={"description": "unexpected"})
            ]
        }
    )
    comparison = compare_states(base=base, target=target, change_id="derived")
    derived = materialize_change(comparison=comparison, change_id="derived")

    result = normalize_change(state=changed_base, change=derived)

    assert [issue.code for issue in result.issues.errors] == ["arch.stale_precondition"]
    assert result.issues.errors[0].details["expected"] == "old"


def test_derived_change_equals_authored_2027(canonical: ArchitectureWorkspace) -> None:
    """derived-change-equals-authored-2027: net effects match sparse authored intent."""
    replayed = replay_roadmap(workspace=canonical, roadmap_id="preferred", order=1)
    assert replayed.resolved is not None
    derived = compare_states(
        base=canonical.states[0],
        target=replayed.resolved.state,
        change_id="arch-v2-change-2027",
    )
    authored = normalize_change(state=canonical.states[0], change=canonical.changes[0])

    assert {_effect(item) for item in derived.change.operations} == {
        _effect(item) for item in authored.change.operations
    }


def test_canceled_net_history() -> None:
    """canceled-net-history: net comparison omits transient entities but keeps history."""
    workspace = _workspace(
        state={"id": "base"},
        changes=[
            {
                "id": "add-transient",
                "name": "Add transient",
                "patches": {
                    "systems": [
                        {"id": "transient", "change_type": "added", "name": "Transient"}
                    ]
                },
            },
            {
                "id": "remove-transient",
                "name": "Remove transient",
                "patches": {
                    "systems": [{"id": "transient", "change_type": "removed"}]
                },
            },
        ],
        items=[
            {"change": "add-transient", "order": 1},
            {"change": "remove-transient", "order": 2},
        ],
    )
    replayed = replay_roadmap(workspace=workspace, roadmap_id="delivery")
    assert replayed.resolved is not None

    comparison = compare_states(
        base=workspace.states[0],
        target=replayed.resolved.state,
        contributing_history=replayed.resolved.history,
    )

    assert comparison.change.operations == []
    assert [item.kind for item in comparison.canceled_history] == ["add", "remove"]
    assert [item.change_id for item in comparison.contributing_history] == [
        "add-transient",
        "remove-transient",
    ]


def test_explicit_dependency_order_is_not_rewritten() -> None:
    """Declared dependencies fail in-place and report a stable suggested order."""
    workspace = _workspace(
        state={"id": "base"},
        changes=[
            {"id": "dependent", "name": "Dependent", "depends_on": ["foundation"]},
            {"id": "foundation", "name": "Foundation"},
        ],
        items=[
            {"change": "dependent", "order": 1},
            {"change": "foundation", "order": 2},
        ],
    )

    result = validate_roadmap(workspace=workspace, roadmap=workspace.roadmaps[0])

    assert [issue.code for issue in result.errors] == ["arch.invalid_dependency_order"]
    assert result.errors[0].details["suggested_order"] == "apply foundation before dependent"
    assert workspace.roadmaps[0].items[0].change == "dependent"
