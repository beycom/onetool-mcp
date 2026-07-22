"""Generate the canonical compact Excel architecture-v2 fixture."""

from __future__ import annotations

from pathlib import Path

from otdev.tools._arch.v2.load import load_workspace
from otdev.tools._arch.v2.write import write_workspace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/otdev/fixtures/arch_v2/arch-v2-canonical.yaml"
OUTPUT = ROOT / "tests/otdev/fixtures/arch_v2/arch-v2-canonical.xlsx"


def main() -> None:
    """Write the paired workbook through the production deterministic writer."""
    workspace = load_workspace(SOURCE).workspace
    write_workspace(path=OUTPUT, workspace=workspace)


if __name__ == "__main__":
    main()
