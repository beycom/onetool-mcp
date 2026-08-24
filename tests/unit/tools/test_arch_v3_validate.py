"""Minimal validation-code tests for architecture schema v3."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from otdev.tools._arch.v3.model import Architecture, System
from otdev.tools._arch.v3.validate import validate

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _architecture(**updates: object) -> Architecture:
    payload: dict[str, object] = {
        "schema_version": 3,
        "milestones": [],
        "systems": [],
        "containers": [],
        "components": [],
        "code": [],
        "users": [],
        "interfaces": [],
        "relationships": [],
    }
    payload.update(updates)
    return Architecture.model_validate(payload)


def _missing_required() -> Architecture:
    architecture = _architecture()
    architecture.systems = [System.model_construct(id="system")]
    return architecture


@pytest.mark.parametrize(
    ("code", "build"),
    [
        ("missing_required", _missing_required),
        (
            "duplicate_id",
            lambda: _architecture(
                systems=[
                    {"id": "system", "name": "System"},
                    {"id": "system", "name": "System again"},
                ]
            ),
        ),
        (
            "unresolved_parent",
            lambda: _architecture(
                containers=[{"id": "child", "name": "Child", "parent": "missing"}]
            ),
        ),
        (
            "unresolved_endpoint",
            lambda: _architecture(
                users=[{"id": "user", "name": "User"}],
                interfaces=[
                    {
                        "id": "interface",
                        "name": "Interface",
                        "provider": "missing",
                        "consumer": "user",
                    }
                ],
            ),
        ),
        (
            "unresolved_milestone",
            lambda: _architecture(
                systems=[{"id": "system", "name": "System", "start_in": "missing"}]
            ),
        ),
        (
            "invalid_interval",
            lambda: _architecture(
                milestones=[
                    {"id": "m1", "name": "First"},
                    {"id": "m2", "name": "Second"},
                ],
                systems=[
                    {"id": "system", "name": "System", "start_in": "m2", "end_in": "m1"}
                ],
            ),
        ),
        (
            "containment_cycle",
            lambda: _architecture(
                containers=[
                    {"id": "a", "name": "A", "parent": "b"},
                    {"id": "b", "name": "B", "parent": "a"},
                ]
            ),
        ),
        (
            "ambiguous_parent",
            lambda: _architecture(
                systems=[
                    {"id": "root", "name": "Root"},
                    {"id": "parent", "name": "System"},
                ],
                containers=[
                    {"id": "parent", "name": "Container", "parent": "root"},
                    {"id": "child", "name": "Child", "parent": "parent"},
                ],
            ),
        ),
        (
            "reserved_milestone",
            lambda: _architecture(milestones=[{"id": "base", "name": "Reserved"}]),
        ),
        (
            "invalid_timeline",
            lambda: _architecture(timelines=[{"id": "timeline", "milestones": []}]),
        ),
        (
            "identical_revision",
            lambda: _architecture(
                milestones=[{"id": "m", "name": "Milestone"}],
                systems=[
                    {"id": "system", "name": "System"},
                    {"id": "system", "name": "System", "start_in": "m"},
                ],
            ),
        ),
        (
            "interval_clipped",
            lambda: _architecture(
                milestones=[{"id": "m", "name": "Milestone"}],
                systems=[{"id": "system", "name": "System", "end_in": "base"}],
                containers=[{"id": "child", "name": "Child", "parent": "system"}],
            ),
        ),
        (
            "unused_milestone",
            lambda: _architecture(milestones=[{"id": "m", "name": "Milestone"}]),
        ),
        (
            "never_live",
            lambda: _architecture(
                milestones=[
                    {"id": "scheduled", "name": "Scheduled"},
                    {"id": "unscheduled", "name": "Unscheduled"},
                ],
                timelines=[{"id": "timeline", "milestones": ["scheduled"]}],
                systems=[{"id": "system", "name": "System", "start_in": "unscheduled"}],
            ),
        ),
    ],
)
def test_each_finding_code_fires(code: str, build: Callable[[], Architecture]) -> None:
    assert code in {finding.code for finding in validate(build())}
