"""Shared architecture schema-v2 test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.otdev.arch_v2_fixtures import (
    ARCH_V2_FIXTURES,
    load_canonical_arch_v2_workspace,
)

if TYPE_CHECKING:
    from pathlib import Path

    from otdev.tools._arch.v2.models import ArchitectureWorkspace


@pytest.fixture(scope="session")
def arch_v2_fixtures() -> Path:
    """Return the canonical architecture schema-v2 fixture directory."""
    return ARCH_V2_FIXTURES


@pytest.fixture
def canonical_arch_v2_workspace() -> ArchitectureWorkspace:
    """Return an isolated canonical architecture schema-v2 workspace."""
    return load_canonical_arch_v2_workspace()
