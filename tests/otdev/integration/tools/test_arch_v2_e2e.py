"""Production-path proof for every public schema-v2 architecture operation."""

from __future__ import annotations

from pathlib import Path

import pytest

from otdev.tools import arch

pytestmark = [pytest.mark.integration, pytest.mark.tools]


def test_all_public_operations_use_production_data(tmp_path: Path) -> None:
    """Every public operation completes without mock or hard-coded product data."""
    workspace = tmp_path / "workspace"
    assert arch.init(output_path=str(workspace))["ok"] is True
    source = workspace / "architecture.yaml"
    assert arch.validate(input_path=str(workspace))["valid"] is True

    converted = tmp_path / "converted.xlsx"
    assert arch.convert(input_path=str(source), output_path=str(converted))["ok"] is True
    base = tmp_path / "base.yaml"
    target = tmp_path / "target.yaml"
    assert arch.resolve(
        input_path=str(source),
        output_path=str(base),
        roadmap="preferred",
        order=0,
        output_state_id="e2e-base",
    )["ok"] is True
    assert arch.resolve(
        input_path=str(source),
        output_path=str(target),
        roadmap="preferred",
        order=1,
        output_state_id="e2e-target",
    )["ok"] is True
    derived = tmp_path / "derived.yaml"
    assert arch.diff(
        base_path=str(base),
        target_path=str(target),
        output_path=str(derived),
        change_id="e2e-derived",
    )["ok"] is True

    explorer = tmp_path / "explorer"
    assert arch.generate(
        input_path=str(workspace),
        output_path=str(explorer),
        selections=[{"roadmap": "preferred", "order": 1}],
    )["ok"] is True
    exports = tmp_path / "exports"
    assert arch.export(
        input_path=str(workspace),
        output_path=str(exports),
        formats=["svg", "drawio", "likec4", "yaml", "excel"],
        selections=[{"roadmap": "preferred", "order": 1}],
    )["ok"] is True
    bundle = tmp_path / "workspace.zip"
    assert arch.bundle(
        input_path=str(workspace),
        output_path=str(bundle),
    )["ok"] is True

    assert (explorer / "architecture-explorer.html").stat().st_size > 1_000_000
    assert (exports / "manifest.json").is_file()
    assert bundle.is_file()


def test_required_acceptance_proofs_are_not_skipped_or_xfailed() -> None:
    """Normative schema-v2 and browser proofs contain no skip/xfail escape hatch."""
    root = Path(__file__).parents[4]
    paths = [
        *root.glob("tests/otdev/**/*arch_v2*.py"),
        root / "src/otdev/tools/_arch/frontend/tests/explorer.test.ts",
        root / "src/otdev/tools/_arch/frontend/scripts/test-generated-explorer.mjs",
    ]
    forbidden = (
        "pytest.mark." + "skip",
        "pytest.mark." + "xfail",
        "." + "skip(",
        "." + "todo(",
    )
    for path in paths:
        source = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in source, path
