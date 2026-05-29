"""Unit tests for diagram tool pack."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestOutputDir:
    """Test _resolve_output_dir does not create directories eagerly."""

    def test_does_not_create_directory(self, tmp_path):
        from otdev.tools.diagram import _resolve_output_dir

        target = tmp_path / "new_diagrams"
        assert not target.exists()

        _resolve_output_dir(str(target))

        assert not target.exists(), "_resolve_output_dir should not mkdir"

    def test_returns_resolved_path(self, tmp_path):
        from otdev.tools.diagram import _resolve_output_dir

        target = tmp_path / "output"
        result = _resolve_output_dir(str(target))
        assert result == target.resolve()


@pytest.mark.unit
@pytest.mark.tools
class TestDiagramPack:
    """Test diagram pack structure."""

    def test_pack_name(self):
        from otdev.tools import diagram

        assert diagram.pack == "diagram"

    def test_has_all_exports(self):
        from otdev.tools import diagram

        # Diagram should export rendering functions
        assert hasattr(diagram, "__all__")
        # Check that key functions exist
        expected = {"render_diagram", "list_providers"}
        assert expected.issubset(set(diagram.__all__))

    def test_functions_are_callable(self):
        from otdev.tools import diagram

        for name in diagram.__all__:
            func = getattr(diagram, name)
            assert callable(func), f"{name} should be callable"


@pytest.mark.unit
@pytest.mark.tools
class TestGetTemplate:
    """Test get_template falls back to bundled global templates."""

    def _make_template_config(self, file_path: str) -> object:
        from otdev.tools.diagram import TemplateRef

        return TemplateRef(
            provider="mermaid",
            diagram_type="sequence",
            description="Test template",
            file=file_path,
        )

    def test_loads_from_global_templates_when_not_in_config_dir(self, tmp_path):
        """File missing from config dir → falls back to global templates bundle."""
        from ot.paths import get_global_templates_dir
        from otdev.tools.diagram import get_template

        bundled = get_global_templates_dir() / "diagram-templates" / "api-flow.mmd"
        assert bundled.exists(), "bundled api-flow.mmd must exist in global_templates"

        fake_config_dir = tmp_path / "onetool"
        fake_config_dir.mkdir()

        template_cfg = self._make_template_config("templates/diagram/api-flow.mmd")
        mock_templates = {"api-flow": template_cfg}

        with (
            patch("otdev.tools.diagram._get_config") as mock_cfg,
            patch("ot.paths.get_config_dir", return_value=fake_config_dir),
        ):
            mock_cfg.return_value.templates = mock_templates
            result = get_template(name="api-flow")

        assert "Template: api-flow" in result
        assert "Provider: mermaid" in result
        assert "--- Source ---" in result

    def test_config_dir_takes_precedence_over_global(self, tmp_path):
        """Local config dir file is used when it exists."""
        from otdev.tools.diagram import get_template

        local_dir = tmp_path / "onetool" / "templates" / "diagram"
        local_dir.mkdir(parents=True)
        local_file = local_dir / "api-flow.mmd"
        local_file.write_text("sequenceDiagram\n  A->>B: local override")

        template_cfg = self._make_template_config("templates/diagram/api-flow.mmd")
        mock_templates = {"api-flow": template_cfg}

        with (
            patch("otdev.tools.diagram._get_config") as mock_cfg,
            patch("ot.paths.get_config_dir", return_value=tmp_path / "onetool"),
        ):
            mock_cfg.return_value.templates = mock_templates
            result = get_template(name="api-flow")

        assert "local override" in result

    def test_unknown_template_returns_error(self):
        """Unknown template name returns helpful error."""
        from otdev.tools.diagram import get_template

        with patch("otdev.tools.diagram._get_config") as mock_cfg:
            mock_cfg.return_value.templates = {}
            result = get_template(name="nonexistent")

        assert "not found" in result.lower()

    def test_bundled_templates_all_resolvable(self):
        """All templates in the default config have files in global_templates."""
        from ot.paths import get_global_templates_dir

        global_dir = get_global_templates_dir()
        template_names = ["api-flow", "state-machine", "class-diagram", "project-gantt", "feature-mindmap"]
        for name in template_names:
            # map name to expected file path from diagram.yaml
            file_map = {
                "api-flow": "diagram-templates/api-flow.mmd",
                "state-machine": "diagram-templates/state-machine.mmd",
                "class-diagram": "diagram-templates/class-diagram.mmd",
                "project-gantt": "diagram-templates/project-gantt.mmd",
                "feature-mindmap": "diagram-templates/feature-mindmap.mmd",
            }
            path = global_dir / file_map[name]
            assert path.exists(), f"Bundled template file missing: {file_map[name]}"


@pytest.mark.unit
@pytest.mark.tools
class TestDiagramRegressionFixes:
    """Regression tests for provider inference and batch status fields."""

    def test_render_diagram_infers_provider_from_compound_extension(self, tmp_path):
        from otdev.tools import diagram

        source_file = tmp_path / "chart.vg.json"
        source_file.write_text('{"$schema":"https://vega.github.io/schema/vega/v5.json"}')

        mock_cfg = type(
            "Cfg",
            (),
            {
                "backend": type("Backend", (), {"timeout": 5.0})(),
                "output": type("Output", (), {"save_source": False, "naming": "{provider}_{name}_{timestamp}"})(),
            },
        )()

        with (
            patch("otdev.tools.diagram._get_config", return_value=mock_cfg),
            patch("otdev.tools.diagram._render_via_kroki", return_value=b"<svg/>"),
            patch("otdev.tools.diagram._resolve_output_dir", return_value=tmp_path),
            patch("otdev.tools.diagram._get_kroki_get_url", return_value="https://kroki.invalid/share"),
        ):
            result = diagram.render_diagram(source_file=str(source_file), output_format="svg")

        assert "Rendered:" in result
        assert "VEGA" in result.upper()

    def test_render_directory_discovers_compound_extensions(self, tmp_path):
        from otdev.tools import diagram

        (tmp_path / "a.vg.json").write_text("{}")
        (tmp_path / "b.vl.json").write_text("{}")

        seen_providers = []

        def _fake_render_file(source_file, provider, output_format, output_path, timeout):  # noqa: ANN001
            _ = source_file, output_format, output_path, timeout
            seen_providers.append(provider)
            return {"name": "ok", "status": "success", "file": "out.svg"}

        with (
            patch("otdev.tools.diagram._is_self_hosted", return_value=True),
            patch("otdev.tools.diagram._render_file", side_effect=_fake_render_file),
        ):
            result = diagram.render_directory(directory=str(tmp_path))

        assert "Completed: 2/2" in result
        assert sorted(seen_providers) == ["vega", "vegalite"]

    def test_get_render_status_includes_batch_progress_fields(self):
        from otdev.tools import diagram

        task_id = "batch-test"
        with diagram._render_tasks_lock:  # noqa: SLF001
            diagram._render_tasks[task_id] = {  # noqa: SLF001
                "status": "completed",
                "type": "batch",
                "total": 3,
                "completed": 2,
                "failed": 1,
                "results": [
                    {"name": "a", "status": "success"},
                    {"name": "b", "status": "failed"},
                ],
                "started_at": "now",
                "completed_at": "later",
            }

        result = diagram.get_render_status(task_id=task_id)

        assert "Total: 3" in result
        assert "Completed: 2" in result
        assert "Failed: 1" in result
        assert "Result summary: success=1, failed=1" in result

    def test_list_providers_focus_only_has_clean_separator(self):
        from otdev.tools import diagram

        result = diagram.list_providers(focus_only=True)

        assert "Focus Providers (with full guidance)" in result
        assert "=" * 40 in result
        assert "=Focus Providers" not in result

    def test_reset_runtime_cache_clears_backend_cache(self):
        from otdev.tools import diagram

        diagram._cached_backend["url"] = "https://cached.example.test"  # noqa: SLF001
        diagram._cached_backend["is_self_hosted"] = True  # noqa: SLF001
        diagram._cached_backend["timestamp"] = 123.0  # noqa: SLF001

        diagram.reset_runtime_cache()

        assert diagram._cached_backend["url"] is None  # noqa: SLF001
        assert diagram._cached_backend["is_self_hosted"] is None  # noqa: SLF001
        assert diagram._cached_backend["timestamp"] == 0.0  # noqa: SLF001
