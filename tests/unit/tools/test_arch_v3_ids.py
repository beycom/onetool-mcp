"""Generated id tests for architecture schema v3."""

from __future__ import annotations

import pytest

from otdev.tools._arch.v3.ids import assign_missing_ids, next_id
from otdev.tools._arch.v3.model import Architecture, Container, Subsystem, System

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_assignment_uses_max_plus_one_padding_and_per_kind_sequences() -> None:
    architecture = Architecture.model_construct(
        schema_version=3,
        milestones=[],
        timelines=None,
        systems=[
            System(id="s-0001", name="First"),
            System(id="s-0009", name="Ninth"),
            System.model_construct(id=None, name="Generated"),
        ],
        subsystems=[
            Subsystem.model_construct(id=None, name="Generated", parent="s-0001"),
        ],
        containers=[
            Container(id="c-0003", name="Third", parent="s-0001"),
            Container.model_construct(id=None, name="Generated", parent="s-0001"),
        ],
        components=[],
        code=[],
        users=[],
        interfaces=[],
        relationships=[],
    )

    assigned = assign_missing_ids(architecture)

    assert assigned == {
        "systems": [(2, "s-0010")],
        "subsystems": [(0, "ss-0001")],
        "containers": [(1, "c-0004")],
    }
    assert next_id("code", {"cd-9999"}) == "cd-10000"
