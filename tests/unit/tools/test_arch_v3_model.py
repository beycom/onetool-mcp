"""Focused model tests for architecture schema v3."""

from __future__ import annotations

import pytest

from otdev.tools._arch.v3.model import Architecture

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def test_revision_rows_may_share_an_id() -> None:
    architecture = Architecture.model_validate(
        {
            "schema_version": 3,
            "milestones": [{"id": "phase-1", "name": " First phase "}],
            "systems": [
                {"id": "payments", "name": "Payments"},
                {"id": "payments", "name": "Payment platform", "start_in": "phase-1"},
            ],
            "subsystems": [],
            "containers": [],
            "components": [],
            "code": [],
            "users": [],
            "interfaces": [
                {
                    "id": "payments-api",
                    "name": "Payments API",
                    "provider": "payments",
                    "consumer": "customer",
                    "call_direction": " consumer_to_provider ",
                }
            ],
            "relationships": [],
        }
    )

    assert architecture.milestones[0].name == "First phase"
    assert architecture.systems[1].start_in == "phase-1"
    assert architecture.interfaces[0].call_direction == "consumer_to_provider"
    assert [system.id for system in architecture.systems] == ["payments", "payments"]
