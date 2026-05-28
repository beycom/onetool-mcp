"""Unit tests for arch tool pack."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from otdev.tools._arch.config import (
    ArchConfig,
    ConfigResolutionError,
    resolve_path_with_fallback,
)

pytestmark = [pytest.mark.unit, pytest.mark.tools]

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "arch"


class TestArchPackStructure:
    def test_pack_name_and_exports(self) -> None:
        from otdev.tools import arch

        assert arch.pack == "arch"
        assert set(arch.__all__) == {
            "validate",
            "generate",
            "export_yaml",
            "import_yaml",
            "bundle_solution",
        }


class TestValidate:
    def test_validate_success_payload(self) -> None:
        from otdev.tools.arch import validate

        result = validate(input_path=str(_FIXTURES / "architecture.xlsx"))

        assert result["ok"] is True
        assert result["operation"] == "validate"
        assert result["valid"] is True
        assert result["summary"]["errors"] == 0
        assert "issues" in result

    def test_validate_failure_payload_shape(self) -> None:
        from otdev.tools.arch import validate

        result = validate(input_path=str(_FIXTURES / "architecture_invalid.xlsx"))

        assert result["ok"] is False
        assert result["operation"] == "validate"
        assert result["valid"] is False
        assert result["error"]["code"] == "validation_failed"
        assert isinstance(result["error"]["details"], dict)


class TestGenerate:
    def test_generate_rejects_unknown_profile(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
            profile="unknown",
        )

        assert result["ok"] is False
        assert result["operation"] == "generate"
        assert result["error"]["code"] == "config_error"
        assert "Unknown tools.arch.profile 'unknown'" in result["error"]["message"]

    def test_generate_rejects_profile_and_profile_yaml_together(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
            profile="simple",
            profile_yaml="data:\n  direction: left\n",
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "config_error"
        assert "only one of profile or profile_yaml" in result["error"]["message"]

    def test_generate_rejects_invalid_profile_yaml(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
            profile_yaml="data: [",
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "config_error"
        assert "Invalid profile_yaml" in result["error"]["message"]

    def test_generate_rejects_schema_invalid_profile_yaml(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
            profile_yaml="legacy_mode: true\n",
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "config_error"
        assert "Invalid profile_yaml profile config" in result["error"]["message"]

    def test_generate_returns_clear_error_when_d2_cli_is_missing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        def _raise_not_found(*args: object, **kwargs: object) -> object:
            _ = args, kwargs
            raise FileNotFoundError("[Errno 2] No such file or directory: 'd2'")

        monkeypatch.setattr(arch.subprocess, "run", _raise_not_found)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["operation"] == "generate"
        assert result["error"]["code"] == "engine_command_not_found"
        assert "Install D2 CLI: https://github.com/terrastruct/d2" in result["error"]["message"]

    def test_generate_uses_profile_yaml_as_the_run_profile(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        def _fake_render(*, target_config: object, render_context: dict[str, object]) -> tuple[bool, dict[str, object]]:
            _ = target_config
            Path(str(render_context["paths"]["output"])).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
                encoding="utf-8",
            )
            return True, {"command": "fake-render", "target": "solution", "engine": "d2"}

        monkeypatch.setattr(arch, "_execute_render_engine", _fake_render)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
            profile_yaml="data:\n  direction: left\n",
        )

        assert result["ok"] is True
        assert result["profile"] == "profile_yaml"
        solution_files = [Path(item) for item in result["files"]["solution"]]
        sys_d2_files = [item for item in solution_files if item.name.endswith("-sys.d2")]
        assert sys_d2_files
        d2_text = sys_d2_files[0].read_text(encoding="utf-8")
        assert "direction: left" in d2_text

    def test_generate_uses_generate_argument_for_solution_title(
        self,
        tmp_path: Path,
    ) -> None:
        from otdev.tools import arch

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
            title="ACME Title",
        )

        assert result["ok"] is True
        index_path = Path(result["files"]["solution"][0])
        index_text = index_path.read_text(encoding="utf-8")
        assert "ACME Title" in index_text

    def test_generate_applies_integration_templates_to_solution_d2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].data = {
            "show_integration_labels": True,
            "integration_labels": "[{{ row.id }}] {{ row.name }}",
            "show_arrowhead_labels": True,
            "arrowhead_labels": "{{ row.id }}",
        }
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is True
        solution_files = [Path(item) for item in result["files"]["solution"]]
        sys_d2_files = [item for item in solution_files if item.name.endswith("-sys.d2")]
        assert sys_d2_files
        d2_text = sys_d2_files[0].read_text(encoding="utf-8")
        assert '[int_user_api] User to API' in d2_text
        assert 'source-arrowhead.label: "int_user_api"' in d2_text
        assert 'target-arrowhead.label: "int_user_api"' in d2_text

    def test_generate_rejects_removed_format_argument(self) -> None:
        from otdev.tools.arch import generate

        with pytest.raises(TypeError):
            generate(input_path=str(_FIXTURES / "architecture.xlsx"), format="solution")  # type: ignore[call-arg]

    def test_generate_with_tag_filters(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        unfiltered = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path / "all"),
        )
        filtered = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
            include_tags=["core"],
            exclude_tags=["deprecated"],
        )

        assert unfiltered["ok"] is True
        assert filtered["ok"] is True
        assert filtered["summary"]["counts"]["sys"] < unfiltered["summary"]["counts"]["sys"]

    def test_generate_validation_failure_shape(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture_invalid.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "validation_failed"
        assert "issues" in result

    def test_generate_solution_html_contains_embedded_svg_and_rich_tables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        def _fake_render(*, target_config: object, render_context: dict[str, object]) -> tuple[bool, dict[str, object]]:
            _ = target_config
            Path(str(render_context["paths"]["output"])).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
                encoding="utf-8",
            )
            return True, {"command": "fake-render", "target": "solution", "engine": "d2"}

        monkeypatch.setattr(arch, "_execute_render_engine", _fake_render)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is True
        solution_files = [Path(item) for item in result["files"]["solution"]]
        html_candidates = [item for item in solution_files if item.suffix == ".html" and item.name != "index.html"]
        assert html_candidates
        html_path = html_candidates[0]
        html = html_path.read_text(encoding="utf-8")
        assert "<svg" in html
        assert "ag-grid-community@32" in html
        assert "initAgGridTable" in html

    def test_generate_solution_applies_profile_data_to_system_d2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].data = {"system_diagram_direction": "left"}
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)

        def _fake_render(*, target_config: object, render_context: dict[str, object]) -> tuple[bool, dict[str, object]]:
            _ = target_config
            Path(str(render_context["paths"]["output"])).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
                encoding="utf-8",
            )
            return True, {"command": "fake-render", "target": "solution", "engine": "d2"}

        monkeypatch.setattr(arch, "_execute_render_engine", _fake_render)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is True
        solution_files = [Path(item) for item in result["files"]["solution"]]
        sys_d2_files = [item for item in solution_files if item.name.endswith("-sys.d2")]
        assert sys_d2_files
        d2_text = sys_d2_files[0].read_text(encoding="utf-8")
        assert "direction: left" in d2_text

    def test_generate_solution_applies_direction_alias_to_system_d2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].data = {"direction": "up"}
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)

        def _fake_render(*, target_config: object, render_context: dict[str, object]) -> tuple[bool, dict[str, object]]:
            _ = target_config
            Path(str(render_context["paths"]["output"])).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
                encoding="utf-8",
            )
            return True, {"command": "fake-render", "target": "solution", "engine": "d2"}

        monkeypatch.setattr(arch, "_execute_render_engine", _fake_render)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is True
        solution_files = [Path(item) for item in result["files"]["solution"]]
        sys_d2_files = [item for item in solution_files if item.name.endswith("-sys.d2")]
        assert sys_d2_files
        d2_text = sys_d2_files[0].read_text(encoding="utf-8")
        assert "direction: up" in d2_text

    def test_build_system_d2_merges_integrations_with_template_arrowheads(self, tmp_path: Path) -> None:
        from otdev.tools.arch import _build_entity_graph, _build_system_d2

        template_path = tmp_path / "system.d2.j2"
        template_path.write_text(
            "\n".join(
                [
                    'direction: {{ profile_data.direction | default(profile_data.system_diagram_direction | default("right")) }}',
                    "{% for edge in model.system_view.integration_edges -%}",
                    '{{ edge.src_path }} -> {{ edge.dst_path }}: "{{ edge.label }}" {',
                    "  class: {{ edge.direction_class }}",
                    "{% if edge.source_arrowhead_id -%}",
                    '  source-arrowhead.label: "{{ edge.source_arrowhead_id }}"',
                    "{% endif -%}",
                    "{% if edge.target_arrowhead_id -%}",
                    '  target-arrowhead.label: "{{ edge.target_arrowhead_id }}"',
                    "{% endif -%}",
                    "}",
                    "{% endfor -%}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_b", "name": "System B"},
            ],
            "app": [],
            "cmp": [],
            "int": [
                {"id": "int_1", "key": "1", "name": "Flow One", "src": "sys_a", "dst": "sys_b", "type": "api"},
                {"id": "int_2", "key": "2", "name": "Flow Two", "src": "sys_a", "dst": "sys_b", "type": "batch"},
            ],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="sys",
            entities=entities,
            graph=graph,
            template_path=template_path,
            profile_data={
                "merge_integrations": True,
                "show_integration_labels": True,
                "integration_labels": "[{{ row.key }}] {{ row.name }}",
                "show_arrowhead_labels": True,
                "arrowhead_labels": "{{ row.key }}",
                "direction": "up",
            },
        )

        assert rendered.count("->") == 1
        assert "[1] Flow One\\n[2] Flow Two" in rendered
        assert 'source-arrowhead.label: "1\\n2"' in rendered
        assert 'target-arrowhead.label: "1\\n2"' in rendered
        assert "direction: up" in rendered

    def test_build_system_d2_hides_integration_labels_when_disabled(self, tmp_path: Path) -> None:
        from otdev.tools.arch import _build_entity_graph, _build_system_d2

        template_path = tmp_path / "system.d2.j2"
        template_path.write_text(
            "\n".join(
                [
                    "{% for edge in model.system_view.integration_edges -%}",
                    '{{ edge.src_path }} -> {{ edge.dst_path }}: "{{ edge.label }}" {',
                    "  class: {{ edge.direction_class }}",
                    "}",
                    "{% endfor -%}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_b", "name": "System B"},
            ],
            "app": [],
            "cmp": [],
            "int": [
                {"id": "int_1", "key": "1", "name": "Flow One", "src": "sys_a", "dst": "sys_b", "type": "api"},
            ],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="sys",
            entities=entities,
            graph=graph,
            template_path=template_path,
            profile_data={
                "merge_integrations": False,
                "show_integration_labels": False,
            },
        )

        assert '-> "sys_b": "" {' in rendered
        assert "Flow One (api)" not in rendered

    def test_solution_system_context_uses_integration_key_field(self) -> None:
        from otdev.tools.arch import _build_entity_graph, _build_solution_system_context

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [],
            "cmp": [],
            "int": [
                {
                    "id": "int_1",
                    "key": "K-01",
                    "name": "Flow One",
                    "src": "sys_a",
                    "dst": "sys_a",
                    "type": "api",
                }
            ],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_system_context(
            system_id="sys_a",
            entities=entities,
            graph=graph,
            svg_by_level={"sys": "<svg/>", "app": "<svg/>", "cmp": "<svg/>"},
            workbook_diagrams=[],
        )

        assert context["integrations_data"][0]["key"] == "K-01"
        assert context["integrations_columns"][0]["title"] == "Key"
        assert context["integrations_columns"][0]["field"] == "key"
        assert [item["label"] for item in context["diagrams"]] == ["System", "Application", "Component"]
        assert context["additional_diagrams"] == []

    def test_solution_system_context_splits_additional_diagrams(self) -> None:
        from otdev.tools.arch import _build_entity_graph, _build_solution_system_context

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [],
            "cmp": [],
            "int": [],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_system_context(
            system_id="sys_a",
            entities=entities,
            graph=graph,
            svg_by_level={"sys": "<svg/>", "app": "<svg/>", "cmp": "<svg/>"},
            workbook_diagrams=[
                {
                    "name": "Sequence A",
                    "description": "<p>Desc</p>",
                    "svg_path": "images/sys_a-01-seq_a.svg",
                    "svg": "<svg/>",
                }
            ],
        )

        assert [item["label"] for item in context["diagrams"]] == ["System", "Application", "Component"]
        assert len(context["additional_diagrams"]) == 1
        assert context["additional_diagrams"][0]["label"] == "Sequence A"

    def test_generate_solution_inlines_styles_into_system_d2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from otdev.tools import arch

        def _fake_render(*, target_config: object, render_context: dict[str, object]) -> tuple[bool, dict[str, object]]:
            _ = target_config
            Path(str(render_context["paths"]["output"])).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
                encoding="utf-8",
            )
            return True, {"command": "fake-render", "target": "solution", "engine": "d2"}

        monkeypatch.setattr(arch, "_execute_render_engine", _fake_render)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is True
        solution_files = [Path(item) for item in result["files"]["solution"]]
        style_candidates = [item for item in solution_files if item.name == "styles.d2"]
        assert not style_candidates
        sys_d2_files = [item for item in solution_files if item.name.endswith("-sys.d2")]
        assert sys_d2_files
        d2_text = sys_d2_files[0].read_text(encoding="utf-8")
        assert "{% include" not in d2_text
        assert "# Diagram Legend" not in d2_text

    def test_generate_reports_solution_format_in_summary(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is True
        assert result["summary"]["formats"] == ["solution"]

    def test_generate_reports_missing_template_variable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].system_engine = "echo {{ missing_required }} > {{ output }}"
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "template_variable_error"

    def test_generate_rejects_legacy_system_diagram_template_variables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        def _fake_render(*, target_config: object, render_context: dict[str, object]) -> tuple[bool, dict[str, object]]:
            _ = target_config
            Path(str(render_context["paths"]["output"])).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
                encoding="utf-8",
            )
            return True, {"command": "fake-render", "target": "solution", "engine": "d2"}

        legacy_template = tmp_path / "legacy-system.d2.j2"
        legacy_template.write_text("title: {{ title_name }}\n", encoding="utf-8")
        (tmp_path / "styles.d2").write_text("", encoding="utf-8")

        config = ArchConfig()
        config.profiles["simple"].system_diagram = str(legacy_template)
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)
        monkeypatch.setattr(arch, "_execute_render_engine", _fake_render)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "config_error"
        assert "system_diagram template" in result["error"]["message"]
        assert "model.system_view" in result["error"]["message"]

    def test_generate_rejects_legacy_engine_context_variables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].system_engine = "echo {{ paths.input }} > {{ output }}"
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "template_variable_error"

    def test_generate_rejects_legacy_flat_integration_template_variables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].data = {
            "show_integration_labels": True,
            "integration_labels": "[{{ key }}] {{ name }}",
        }
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "config_error"
        assert "Failed rendering tools.arch.profiles.<name>.data.integration_labels" in result["error"]["message"]

    def test_generate_rejects_unsafe_system_id_for_output_paths(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        openpyxl = pytest.importorskip("openpyxl")

        workbook_path = tmp_path / "unsafe-system-id.xlsx"
        wb = openpyxl.Workbook()
        sys_ws = wb.active
        sys_ws.title = "sys"
        sys_ws.append(["id", "name"])
        sys_ws.append(["sys;bad", "System Bad"])

        app_ws = wb.create_sheet("app")
        app_ws.append(["id", "name", "sys"])
        app_ws.append(["app_bad", "App Bad", "sys;bad"])

        cmp_ws = wb.create_sheet("cmp")
        cmp_ws.append(["id", "name", "app"])
        cmp_ws.append(["cmp_bad", "Cmp Bad", "app_bad"])

        int_ws = wb.create_sheet("int")
        int_ws.append(["id", "src", "dst"])
        int_ws.append(["int_bad", "app_bad", "cmp_bad"])

        usr_ws = wb.create_sheet("usr")
        usr_ws.append(["id", "name", "app"])
        usr_ws.append(["usr_bad", "User Bad", "app_bad"])

        wb.save(workbook_path)
        wb.close()

        result = generate(
            input_path=str(workbook_path),
            output_dir=str(tmp_path / "out"),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "validation_failed"
        assert result["issues"]["errors"][0]["code"] == "invalid_value"

    def test_generate_rejects_unsafe_diagram_file_fragment(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        openpyxl = pytest.importorskip("openpyxl")

        workbook_path = tmp_path / "unsafe-diagram-file.xlsx"
        wb = openpyxl.Workbook()
        sys_ws = wb.active
        sys_ws.title = "sys"
        sys_ws.append(["id", "name"])
        sys_ws.append(["sys_ok", "System OK"])

        app_ws = wb.create_sheet("app")
        app_ws.append(["id", "name", "sys"])
        app_ws.append(["app_ok", "App OK", "sys_ok"])

        cmp_ws = wb.create_sheet("cmp")
        cmp_ws.append(["id", "name", "app"])
        cmp_ws.append(["cmp_ok", "Cmp OK", "app_ok"])

        int_ws = wb.create_sheet("int")
        int_ws.append(["id", "src", "dst"])
        int_ws.append(["int_ok", "app_ok", "cmp_ok"])

        usr_ws = wb.create_sheet("usr")
        usr_ws.append(["id", "name", "app"])
        usr_ws.append(["usr_ok", "User OK", "app_ok"])

        diagram_ws = wb.create_sheet("diagram")
        diagram_ws.append(["file", "name", "sys", "description"])
        diagram_ws.append(["seq;bad.d2", "Unsafe", "sys_ok", "Unsafe file path"])

        wb.save(workbook_path)
        wb.close()

        result = generate(
            input_path=str(workbook_path),
            output_dir=str(tmp_path / "out"),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "validation_failed"
        assert result["issues"]["diagram"]["errors"][0]["code"] == "invalid_value"

    def test_apply_tag_filters_supports_multiline_tags(self) -> None:
        from otdev.tools._arch.exporters import apply_tag_filters

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys-a", "name": "System A", "tags": "core\nplatform"}],
            "app": [{"id": "app-a", "name": "App A", "sys": "sys-a"}],
            "cmp": [{"id": "cmp-a", "name": "Cmp A", "app": "app-a"}],
            "int": [],
            "usr": [],
        }

        filtered = apply_tag_filters(
            entities=entities,
            include_tags=["platform"],
            exclude_tags=None,
        )
        assert len(filtered["sys"]) == 1
        assert filtered["sys"][0]["id"] == "sys-a"


class TestTemplateResolution:
    def test_template_override_path_falls_back_to_bundled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        missing_config_dir = tmp_path / "cfg"
        bundled = tmp_path / "bundled"
        bundled.mkdir(parents=True)
        target = bundled / "arch-templates" / "solution" / "default"
        target.mkdir(parents=True)
        (target / "base.html").write_text("ok", encoding="utf-8")

        monkeypatch.setattr("otdev.tools._arch.config.get_config_dir", lambda: missing_config_dir)
        monkeypatch.setattr("otdev.tools._arch.config.get_global_templates_dir", lambda: bundled)

        path = resolve_path_with_fallback(
            configured_path="templates/arch/solution/default",
            fallback_relative="arch-templates/solution/default",
        )
        assert path == target.resolve()

    def test_missing_custom_relative_path_has_no_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        missing_config_dir = tmp_path / "cfg"
        bundled = tmp_path / "bundled"
        bundled.mkdir(parents=True)
        monkeypatch.setattr("otdev.tools._arch.config.get_config_dir", lambda: missing_config_dir)
        monkeypatch.setattr("otdev.tools._arch.config.get_global_templates_dir", lambda: bundled)

        with pytest.raises(ConfigResolutionError, match="Configured relative path not found"):
            resolve_path_with_fallback(
                configured_path="arch-templates/solution/default",
                fallback_relative="arch-templates/solution/default",
            )

    def test_absolute_missing_path_has_no_fallback(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing" / "template.j2"
        with pytest.raises(ConfigResolutionError):
            resolve_path_with_fallback(
                configured_path=str(missing),
                fallback_relative="arch-templates/solution/default",
            )


class TestConfigStrictness:
    def test_config_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            ArchConfig.model_validate({"legacy_mode": True})

    def test_config_rejects_legacy_orchestration_shape(self) -> None:
        with pytest.raises(ValidationError):
            ArchConfig.model_validate(
                {
                    "orchestration": {"profile": "simple"}
                }
            )

    def test_config_rejects_removed_sequence_keys(self) -> None:
        with pytest.raises(ValidationError):
            ArchConfig.model_validate(
                {
                    "profiles": {
                        "simple": {
                            "sequence_engine": "d2 {{ input }} {{ output }}",
                        }
                    }
                }
            )

    def test_config_rejects_removed_profile_title_key(self) -> None:
        with pytest.raises(ValidationError):
            ArchConfig.model_validate(
                {
                    "profiles": {
                        "simple": {
                            "title": "Legacy Title",
                        }
                    }
                }
            )

    def test_config_rejects_removed_profile_include_tags_key(self) -> None:
        with pytest.raises(ValidationError):
            ArchConfig.model_validate(
                {
                    "profiles": {
                        "simple": {
                            "include_tags": ["core"],
                        }
                    }
                }
            )

    def test_config_rejects_removed_profile_output_format_key(self) -> None:
        with pytest.raises(ValidationError):
            ArchConfig.model_validate(
                {
                    "profiles": {
                        "simple": {
                            "output_format": "markdown",
                        }
                    }
                }
            )

    def test_config_rejects_removed_profile_single_file_key(self) -> None:
        with pytest.raises(ValidationError):
            ArchConfig.model_validate(
                {
                    "profiles": {
                        "simple": {
                            "single_file": False,
                        }
                    }
                }
            )

class TestStructuredErrors:
    def test_export_yaml_error_payload_shape(self, tmp_path: Path) -> None:
        from otdev.tools.arch import export_yaml

        result = export_yaml(
            input_path=str(tmp_path / "missing-input"),
            output_path=str(tmp_path / "out.yaml"),
        )

        assert result["ok"] is False
        assert result["operation"] == "export_yaml"
        assert set(result["error"]) == {"code", "message", "details"}

    def test_import_yaml_error_payload_shape(self, tmp_path: Path) -> None:
        from otdev.tools.arch import import_yaml

        result = import_yaml(
            input_path=str(tmp_path / "missing.yaml"),
            template_path=str(_FIXTURES / "architecture_template.xlsx"),
            output_path=str(tmp_path / "out.xlsx"),
        )

        assert result["ok"] is False
        assert result["operation"] == "import_yaml"
        assert set(result["error"]) == {"code", "message", "details"}

    def test_bundle_error_payload_shape(self, tmp_path: Path) -> None:
        from otdev.tools.arch import bundle_solution

        result = bundle_solution(directory=str(tmp_path / "missing-solution"))

        assert result["ok"] is False
        assert result["operation"] == "bundle_solution"
        assert set(result["error"]) == {"code", "message", "details"}
