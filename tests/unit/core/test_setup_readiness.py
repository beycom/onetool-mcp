from __future__ import annotations

import pytest

from ot.catalog import (
    PACK_CATALOG,
    ActivationCondition,
    InstallExtra,
    PackRequirement,
    RequirementKind,
    RuntimePackFacts,
    compose_catalog,
)
from ot.setup import ReadinessStatus, evaluate_pack_readiness

pytestmark = [pytest.mark.unit, pytest.mark.core]


def _item(runtime: RuntimePackFacts | None):
    composed = compose_catalog({"brave": runtime} if runtime else {})
    return next(item for item in composed if item.guidance.pack == "brave")


def test_absent_optional_pack_reports_missing_extra_without_mutation() -> None:
    report = evaluate_pack_readiness(
        _item(None),
        secret_is_set=lambda _name: False,
        server_states={},
    )

    assert report.checks[0].status is ReadinessStatus.MISSING_EXTRA
    assert report.checks[0].next_step == (
        "Install onetool-mcp[util], then reload OneTool."
    )
    assert not report.ready


def test_readiness_classifies_all_requirement_kinds_and_invalid_config() -> None:
    requirements = (
        PackRequirement(
            kind=RequirementKind.LIB,
            name="fixture-lib",
            import_name="fixture_lib",
            install_extra=InstallExtra.UTIL,
            purpose="Use fixture library",
        ),
        PackRequirement(
            kind=RequirementKind.CLI,
            name="Fixture CLI",
            executable="fixture",
            purpose="Run fixture executable",
        ),
        PackRequirement(
            kind=RequirementKind.SECRET,
            name="FIXTURE_TOKEN",
            purpose="Authenticate fixture requests",
        ),
        PackRequirement(
            kind=RequirementKind.CONFIG,
            name="model",
            purpose="Select a fixture model",
        ),
        PackRequirement(
            kind=RequirementKind.SERVER,
            name="fixture_server",
            purpose="Provide fixture tools",
        ),
        PackRequirement(
            kind=RequirementKind.SECRET,
            name="OPTIONAL_TOKEN",
            purpose="Enable optional workflow",
            optional=True,
            activation=ActivationCondition(field="optional_enabled", equals=True),
        ),
    )
    runtime = RuntimePackFacts(
        requirements=requirements,
        active_config={"model": "", "optional_enabled": False},
        config_errors=(
            {
                "path": "timeout",
                "message": "Input should be greater than or equal to 1",
                "type": "greater_than_equal",
            },
        ),
    )

    report = evaluate_pack_readiness(
        _item(runtime),
        secret_is_set=lambda _name: False,
        server_states={},
        library_available=lambda _name: False,
        executable_available=lambda _name: False,
    )

    assert [check.status for check in report.checks] == [
        ReadinessStatus.MISSING_LIBRARY,
        ReadinessStatus.MISSING_EXECUTABLE,
        ReadinessStatus.UNSET_SECRET,
        ReadinessStatus.MISSING_CONFIG,
        ReadinessStatus.UNCONFIGURED_SERVER,
        ReadinessStatus.INACTIVE_OPTIONAL,
        ReadinessStatus.INVALID_CONFIG,
    ]
    assert not report.ready


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            {"enabled": False, "connected": False, "status": "disconnected"},
            ReadinessStatus.DISABLED_SERVER,
        ),
        (
            {"enabled": True, "connected": False, "status": "connecting"},
            ReadinessStatus.CONNECTING_SERVER,
        ),
        (
            {"enabled": True, "connected": False, "status": "failed"},
            ReadinessStatus.DISCONNECTED_SERVER,
        ),
        (
            {"enabled": True, "connected": True, "status": "connected"},
            ReadinessStatus.READY,
        ),
    ],
)
def test_server_readiness_states(
    state: dict[str, object],
    expected: ReadinessStatus,
) -> None:
    runtime = RuntimePackFacts(
        requirements=(
            PackRequirement(
                kind=RequirementKind.SERVER,
                name="fixture_server",
                purpose="Provide fixture tools",
            ),
        ),
    )

    report = evaluate_pack_readiness(
        _item(runtime),
        secret_is_set=lambda _name: True,
        server_states={"fixture_server": state},
    )

    assert report.checks[0].status is expected
    assert report.ready is (expected is ReadinessStatus.READY)


def test_optional_missing_requirement_does_not_make_pack_unready() -> None:
    runtime = RuntimePackFacts(
        requirements=(
            PackRequirement(
                kind=RequirementKind.LIB,
                name="optional",
                import_name="optional",
                install_extra=InstallExtra.UTIL,
                purpose="Enable optional workflow",
                optional=True,
            ),
        ),
    )

    report = evaluate_pack_readiness(
        _item(runtime),
        secret_is_set=lambda _name: True,
        server_states={},
        library_available=lambda _name: False,
    )

    assert report.checks[0].status is ReadinessStatus.MISSING_LIBRARY
    assert report.ready


def test_catalog_fixture_remains_the_real_brave_entry() -> None:
    assert next(item for item in PACK_CATALOG if item.pack == "brave").extra is InstallExtra.UTIL
