"""Repository absence proofs for superseded architecture contracts."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from otdev.tools import arch

pytestmark = [pytest.mark.unit, pytest.mark.tools]

ROOT = Path(__file__).parents[4]
ARCH_ROOT = ROOT / "src/otdev/tools/_arch"


def test_no_legacy_revision_runtime() -> None:
    """Superseded revision modules and vocabulary are absent."""
    removed_modules = {
        "bundle.py",
        "config.py",
        "drawio.py",
        "exporters.py",
        "generate.py",
        "ingest.py",
        "models.py",
        "render_styles.py",
        "roundtrip.py",
        "system_model.py",
        "validate.py",
    }
    assert not any((ARCH_ROOT / name).exists() for name in removed_modules)
    public_and_models = (
        (ROOT / "src/otdev/tools/arch.py").read_text(encoding="utf-8")
        + (ARCH_ROOT / "v2/models.py").read_text(encoding="utf-8")
        + (ARCH_ROOT / "v2/api.py").read_text(encoding="utf-8")
    ).lower()
    for removed in ("revision_set", "revision-id"):
        assert removed not in public_and_models


def test_no_project_grouping_runtime() -> None:
    """Project-scoped grouping is absent from the public and runtime models."""
    public_and_models = (
        (ROOT / "src/otdev/tools/arch.py").read_text(encoding="utf-8")
        + (ARCH_ROOT / "v2/models.py").read_text(encoding="utf-8")
        + (ARCH_ROOT / "v2/api.py").read_text(encoding="utf-8")
    ).lower()
    for removed in ("project_scope", "projectscope"):
        assert removed not in public_and_models


def test_no_d2_runtime() -> None:
    """no-d2-runtime: architecture has no renderer, template, config, or dependency path."""
    templates = ROOT / "src/ot/config/global_templates/arch-templates"
    assert not templates.exists() or not any(path.is_file() for path in templates.rglob("*"))
    assert not (ROOT / "src/ot/config/global_templates/arch.yaml").exists()
    package = (ARCH_ROOT / "frontend/package.json").read_text(encoding="utf-8").lower()
    exporter = (ARCH_ROOT / "v2/exporter.py").read_text(encoding="utf-8").lower()
    assert '"d2"' not in package
    assert "drawio.svg" not in exporter
    assert " d2 " not in exporter


def test_no_deployment_runtime() -> None:
    """no-deployment-runtime: deployment is only named by the rejection boundary."""
    model_source = (ARCH_ROOT / "v2/models.py").read_text(encoding="utf-8").lower()
    viewgraph_source = (ARCH_ROOT / "v2/viewgraph.py").read_text(encoding="utf-8").lower()
    assert "deployment" not in model_source
    assert "deployment" not in viewgraph_source


def test_no_v1_aliases() -> None:
    """Old operation aliases, fixtures, specs, and generated layouts are absent."""
    assert set(arch.__all__) == {
        "bundle",
        "convert",
        "diff",
        "export",
        "generate",
        "init",
        "resolve",
        "validate",
    }
    for name in ("bundle_solution", "export_yaml", "import_yaml"):
        assert not hasattr(arch, name)
    assert list(inspect.signature(arch.generate).parameters) == [
        "input_path",
        "output_path",
        "selections",
        "force",
    ]
    old_fixtures = ROOT / "tests/otdev/fixtures/arch"
    assert not old_fixtures.exists() or not any(path.is_file() for path in old_fixtures.rglob("*"))
    for name in (
        "tool-arch-drawio-export",
        "tool-arch-model-centric-rendering",
        "tool-arch-solution-report",
        "tool-arch-validation-warnings",
    ):
        assert not (ROOT / f"openspec/specs/otdev/{name}/spec.md").exists()


def test_no_embedded_drawio_svg() -> None:
    """Draw.io export contains native cells instead of embedded SVG payloads."""
    exporter = (ARCH_ROOT / "v2/exporter.py").read_text(encoding="utf-8").lower()
    export_script = (
        ARCH_ROOT / "frontend/scripts/export-likec4.mjs"
    ).read_text(encoding="utf-8").lower()
    assert "drawio.svg" not in exporter
    assert "image/svg+xml" not in export_script
    assert "data:image/svg" not in export_script


def test_likec4_scripts_consume_streaming_stdin() -> None:
    """Pinned Node boundaries avoid synchronous fd-0 reads that can raise EAGAIN."""
    for name in ("compile-likec4.mjs", "export-likec4.mjs"):
        source = (ARCH_ROOT / f"frontend/scripts/{name}").read_text(encoding="utf-8")
        assert "readFileSync(0" not in source
        assert "for await (const chunk of process.stdin)" in source
