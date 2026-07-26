from __future__ import annotations

import pytest

from ot.catalog import InstallExtra, PackRequirement, RequirementKind
from ot.utils.deps import requires_cli, requires_lib

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_core_requirement_decorators_emit_typed_records() -> None:
    @requires_cli(
        "rg",
        purpose="Search files",
        authoritative_url="https://github.com/BurntSushi/ripgrep",
    )
    @requires_lib(
        "sqlalchemy",
        purpose="Database access",
        install_extra=InstallExtra.DEV,
        import_name="sqlalchemy",
        optional=True,
    )
    def tool() -> None:
        pass

    assert tool.__ot_requires__ == [
        PackRequirement(
            kind=RequirementKind.LIB,
            name="sqlalchemy",
            purpose="Database access",
            install_extra=InstallExtra.DEV,
            import_name="sqlalchemy",
            optional=True,
        ),
        PackRequirement(
            kind=RequirementKind.CLI,
            name="rg",
            purpose="Search files",
            executable="rg",
            authoritative_url="https://github.com/BurntSushi/ripgrep",
        ),
    ]
