"""Schema-v2 architecture contract tests."""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from pydantic import ValidationError

from otdev.tools import arch
from otdev.tools._arch.v2.models import (
    ArchitectureWorkspace,
    RoadmapItem,
    SavedView,
    ViewSelection,
)
from otdev.tools._arch.v2.result import (
    Issue,
    IssueCollection,
    OperationResult,
    ResultSummary,
)
from otdev.tools._arch.v2.selection import merge_selection, selection_identity

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_schema_v2_contract() -> None:
    """schema-v2-contract: complete state/change/roadmap/view models validate."""
    workspace = ArchitectureWorkspace.model_validate(
        {
            "schema_version": 2,
            "states": [
                {
                    "id": "base",
                    "systems": [{"id": "sys-a", "name": "A"}],
                }
            ],
            "changes": [
                {
                    "id": "2027",
                    "name": "2027 delivery",
                    "portfolio_code": "P-27",
                    "patches": {
                        "systems": [{"id": "sys-a", "description": "Changed"}]
                    },
                }
            ],
            "roadmaps": [
                {
                    "id": "preferred",
                    "base": "base",
                    "items": [{"change": "2027", "order": 1}],
                }
            ],
            "views": [{"id": "at-2027", "roadmap": "preferred", "through": "2027"}],
        }
    )

    assert workspace.schema_version == 2
    assert workspace.changes[0].model_extra == {"portfolio_code": "P-27"}
    assert workspace.roadmaps[0].items[0].order == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"state": "base", "roadmap": "preferred"},
        {"roadmap": "preferred", "through": "2027", "order": 1},
        {"state": "base", "focus": ["2027"]},
        {"state": "base", "include_future": True},
    ],
)
def test_selection_mutual_exclusion(payload: dict[str, Any]) -> None:
    """selection-mutual-exclusion: invalid selector combinations fail."""
    with pytest.raises(ValidationError):
        ViewSelection.model_validate(payload)


@pytest.mark.parametrize(
    "browse_by",
    ["system", "system_group", "change", "change_group", "tag"],
)
def test_selection_accepts_only_canonical_browse_kinds(browse_by: str) -> None:
    """The shared Python contract accepts every canonical browser browse kind."""
    selection = ViewSelection.model_validate({"browse_by": browse_by})

    assert selection.browse_by == browse_by


def test_selection_rejects_noncanonical_browse_kind() -> None:
    """Browse kinds have no aliases or compatibility paths."""
    with pytest.raises(ValidationError):
        ViewSelection.model_validate({"browse_by": "group"})


def test_selection_default_precedence() -> None:
    """selection-default-precedence: ad hoc values override saved/default values."""
    defaults = ViewSelection(roadmap="preferred", theme="clean", visibility="all")
    saved = SavedView(
        id="compare-2027",
        roadmap="preferred",
        through="2027",
        compare_from="base",
        visibility="changes_with_context",
    )

    resolved = merge_selection(
        defaults=defaults,
        saved=saved,
        adhoc={"visibility": "changes_only"},
    )

    assert resolved.theme == "clean"
    assert resolved.through == "2027"
    assert resolved.compare_from == "base"
    assert resolved.visibility == "changes_only"
    assert selection_identity(resolved) == selection_identity(resolved)


def test_result_count_reconciliation() -> None:
    """result-count-reconciliation: summary counts cannot hide diagnostics."""
    issue = Issue(code="arch.test", severity="error", message="failure")

    with pytest.raises(ValidationError, match=r"summary\.errors"):
        OperationResult(
            ok=False,
            operation="validate",
            valid=False,
            issues=IssueCollection(errors=[issue]),
            summary=ResultSummary(errors=0),
        )

    result = OperationResult(
        ok=False,
        operation="validate",
        valid=False,
        issues=IssueCollection(errors=[issue]),
        summary=ResultSummary(errors=1),
    )
    assert result.summary.errors == len(result.issues.errors)


def test_removed_v1_signatures_rejected() -> None:
    """removed-v1-signatures-rejected: only exact v2 tools and parameters remain."""
    assert arch.__all__ == [
        "bundle",
        "convert",
        "diff",
        "export",
        "generate",
        "init",
        "resolve",
        "validate",
    ]
    assert list(inspect.signature(arch.generate).parameters) == [
        "input_path",
        "output_path",
        "selections",
        "force",
    ]

    with pytest.raises(TypeError):
        arch.generate(  # type: ignore[call-arg]
            input_path="architecture.yaml",
            output_path="report.html",
            revision="2027",
        )


def test_roadmap_position_is_rejected_everywhere() -> None:
    """The removed roadmap field has no authored, selection, or API alias."""
    with pytest.raises(ValidationError):
        RoadmapItem.model_validate({"change": "2027", "position": 1})
    with pytest.raises(ValidationError):
        ViewSelection.model_validate({"roadmap": "preferred", "position": 1})
    with pytest.raises(TypeError):
        arch.resolve(  # type: ignore[call-arg]
            input_path="architecture.yaml",
            output_path="resolved.yaml",
            position=1,
        )
