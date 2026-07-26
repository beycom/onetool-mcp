"""Tests for standalone normalized dependency decorators."""

from __future__ import annotations

import pytest

from otpack.deps import requires_cli, requires_lib

pytestmark = [pytest.mark.unit, pytest.mark.pkg]


def test_requirement_decorators_emit_normalized_records() -> None:
    @requires_cli(
        "rg",
        purpose="Search files",
        authoritative_url="https://github.com/BurntSushi/ripgrep",
    )
    @requires_lib(
        "sqlalchemy",
        purpose="Database access",
        install_extra="[dev]",
        import_name="sqlalchemy",
        optional=True,
    )
    def tool() -> None:
        pass

    assert tool.__ot_requires__ == [
        {
            "kind": "lib",
            "name": "sqlalchemy",
            "purpose": "Database access",
            "install_extra": "[dev]",
            "import_name": "sqlalchemy",
            "optional": True,
        },
        {
            "kind": "cli",
            "name": "rg",
            "executable": "rg",
            "purpose": "Search files",
            "authoritative_url": "https://github.com/BurntSushi/ripgrep",
            "optional": False,
        },
    ]


def test_requires_lib_rejects_unknown_install_extra() -> None:
    with pytest.raises(ValueError, match="install_extra"):
        requires_lib(
            "sqlalchemy",
            purpose="Database access",
            install_extra="[everything]",
        )
