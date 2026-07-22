"""Shared paths and factories for architecture schema-v2 tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from otdev.tools._arch.v2.load import load_workspace

if TYPE_CHECKING:
    from otdev.tools._arch.v2.models import ArchitectureWorkspace

ARCH_V2_FIXTURES = Path(__file__).parent / "fixtures" / "arch_v2"
CANONICAL_ARCH_V2_YAML = ARCH_V2_FIXTURES / "arch-v2-canonical.yaml"


def load_canonical_arch_v2_workspace() -> ArchitectureWorkspace:
    """Return a fresh canonical workspace so tests cannot share mutations."""
    return load_workspace(CANONICAL_ARCH_V2_YAML).workspace


def write_arch_v2_workspace_with_external_diagram(root: Path) -> Path:
    """Copy the canonical workspace and add one safe local external SVG."""
    root.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_load(CANONICAL_ARCH_V2_YAML.read_text(encoding="utf-8"))
    payload["diagrams"].append(
        {
            "id": "overview",
            "name": "Overview",
            "kind": "external",
            "source": "assets/overview.svg",
        }
    )
    source = root / "architecture.yaml"
    source.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    authored_view = root / "views" / "platform-delivery.c4"
    authored_view.parent.mkdir()
    authored_view.write_text(
        (ARCH_V2_FIXTURES / "views" / "platform-delivery.c4").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    asset = root / "assets" / "overview.svg"
    asset.parent.mkdir()
    asset.write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'><text>Offline overview</text></svg>",
        encoding="utf-8",
    )
    return source
