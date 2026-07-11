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

from tests.otdev.conftest import ARCH_FIXTURES

pytestmark = [pytest.mark.unit, pytest.mark.tools]

_FIXTURES = ARCH_FIXTURES


def _system_view_debug_template(tmp_path: Path) -> Path:
    template_path = tmp_path / "system.d2.j2"
    template_path.write_text(
        "\n".join(
            [
                "{% for block in model.system_view.system_blocks -%}",
                "block={{ block.id }} placeholder={{ block.placeholder }}",
                "{% for app in block.apps -%}",
                "app={{ block.id }}.{{ app.id }}",
                "{% for cmp in app.components -%}",
                "cmp={{ block.id }}.{{ app.id }}.{{ cmp.id }}",
                "{% endfor -%}",
                "{% endfor -%}",
                "{% for direct in block.direct_components -%}",
                "direct={{ block.id }}.{{ direct.id }}",
                "{% endfor -%}",
                "{% endfor -%}",
                "{% for edge in model.system_view.interface_edges -%}",
                "edge={{ edge.start_path }} {{ edge.operator }} {{ edge.end_path }}",
                "{% endfor -%}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return template_path


def _project_view_debug_template(tmp_path: Path) -> Path:
    template_path = tmp_path / "project.d2.j2"
    template_path.write_text(
        "\n".join(
            [
                "title={{ model.project_view.title_name }} stage={{ model.project_view.stage_name }}",
                "detail={{ model.project_view.detail_level }} connect={{ model.project_view.connect_level }}",
                "{% for block in model.project_view.system_blocks -%}",
                "block={{ block.id }} placeholder={{ block.placeholder }}",
                "{% for app in block.apps -%}",
                "app={{ block.id }}.{{ app.id }}",
                "{% for cmp in app.components -%}",
                "cmp={{ block.id }}.{{ app.id }}.{{ cmp.id }}",
                "{% endfor -%}",
                "{% endfor -%}",
                "{% endfor -%}",
                "{% for edge in model.project_view.interface_edges -%}",
                "edge={{ edge.start_path }} {{ edge.operator }} {{ edge.end_path }}",
                "{% endfor -%}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return template_path


def _secondary_detail_entities() -> dict[str, list[dict[str, object]]]:
    return {
        "sys": [
            {"id": "sys_a", "name": "System A"},
            {"id": "sys_b", "name": "System B"},
        ],
        "app": [
            {"id": "app_a", "name": "App A", "sys": "sys_a"},
            {"id": "app_b", "name": "App B", "sys": "sys_b"},
        ],
        "cmp": [
            {"id": "cmp_a", "name": "Component A", "app": "app_a"},
            {"id": "cmp_b", "name": "Component B", "app": "app_b"},
        ],
        "interface": [
            {
                "id": "interface_cmp",
                "key": "CMP",
                "name": "Component Flow",
                "provider": "cmp_b",
                "consumer": "cmp_a",
            },
        ],
        "usr": [],
    }


def _project_entities() -> dict[str, list[dict[str, object]]]:
    return {
        "sys": [
            {"id": "sys_a", "name": "System A"},
            {"id": "sys_b", "name": "System B"},
        ],
        "app": [
            {"id": "app_a", "name": "App A", "sys": "sys_a"},
            {"id": "app_b", "name": "App B", "sys": "sys_b"},
        ],
        "cmp": [
            {"id": "cmp_a", "name": "Component A", "app": "app_a"},
            {"id": "cmp_b", "name": "Component B", "app": "app_b"},
        ],
        "interface": [
            {
                "id": "interface_ab",
                "key": "AB",
                "name": "A to B",
                "provider": "cmp_b",
                "consumer": "cmp_a",
            }
        ],
        "usr": [],
        "project": [
            {
                "id": "wallet",
                "name": "Wallet Project",
                "detail_level": "cmp",
                "connect_level": "cmp",
                "owner": "platform",
                "priority": "P1",
            }
        ],
        "project_scope": [
            {
                "project": "wallet",
                "stage": "current",
                "item_type": "system",
                "item_id": "sys_a",
                "change_type": "existing",
            },
            {
                "project": "wallet",
                "stage": "target",
                "item_type": "interface",
                "item_id": "interface_ab",
                "change_type": "new",
                "priority": "P1",
            },
        ],
        "diagram": [],
    }


class TestArchPackStructure:
    def test_pack_name_and_exports(self) -> None:
        from otdev.tools import arch

        assert arch.pack == "arch"
        # Subset check: the public entry points must stay exported, but new
        # exports may be added without breaking this test.
        assert {
            "validate",
            "generate",
            "export_yaml",
            "import_yaml",
            "bundle_solution",
        } <= set(arch.__all__)


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

    def test_validate_requires_interface_provider_and_consumer(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        result = validate_entities(
            entities={
                "sys": [{"id": "sys_a", "name": "System A"}],
                "app": [],
                "cmp": [],
                "interface": [{"id": "interface_1"}],
                "usr": [],
            }
        )

        error_fields = {
            item["details"]["field"]
            for item in result["issues"]["errors"]
            if item["code"] == "missing_required_field"
        }
        assert result["valid"] is False
        assert {"provider", "consumer"} <= error_fields

    def test_validate_accepts_user_defined_interaction_type_and_arrow_directions(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        for arrow_direction in ("consumer_to_provider", "provider_to_consumer", "none", "bidirectional"):
            result = validate_entities(
                entities={
                    "sys": [{"id": "sys_a", "name": "System A"}],
                    "app": [],
                    "cmp": [],
                    "interface": [
                        {
                            "id": f"int_{arrow_direction}",
                            "provider": "sys_a",
                            "consumer": "sys_a",
                            "interaction_type": "partner_managed_callback",
                            "arrow_direction": arrow_direction,
                        }
                    ],
                    "usr": [],
                }
            )

            assert result["valid"] is True

    def test_validate_rejects_invalid_arrow_direction(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        result = validate_entities(
            entities={
                "sys": [{"id": "sys_a", "name": "System A"}],
                "app": [],
                "cmp": [],
                "interface": [
                    {
                        "id": "interface_1",
                        "provider": "sys_a",
                        "consumer": "sys_a",
                        "arrow_direction": "reverse",
                    }
                ],
                "usr": [],
            }
        )

        assert result["valid"] is False
        assert any(
            item["details"].get("field") == "arrow_direction"
            and item["details"].get("value") == "reverse"
            for item in result["issues"]["errors"]
        )

    def test_validate_accepts_project_scope_references(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        result = validate_entities(entities=_project_entities())

        assert result["valid"] is True

    def test_validate_rejects_invalid_project_scope_reference(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        entities = _project_entities()
        entities["project_scope"][1]["item_id"] = "missing_interface"

        result = validate_entities(entities=entities)

        assert result["valid"] is False
        assert any(
            item["code"] == "invalid_reference"
            and item["details"].get("sheet") == "project_scope"
            and item["details"].get("item_type") == "interface"
            for item in result["issues"]["errors"]
        )

    def test_validate_rejects_invalid_project_levels(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        entities = _project_entities()
        entities["project"][0]["detail_level"] = "component"
        entities["project"][0]["connect_level"] = "component"

        result = validate_entities(entities=entities)

        assert result["valid"] is False
        error_fields = {
            item["details"]["field"]
            for item in result["issues"]["errors"]
            if item["code"] == "invalid_value"
        }
        assert {"detail_level", "connect_level"} <= error_fields

    def test_validate_accepts_component_with_direct_system_reference(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        result = validate_entities(
            entities={
                "sys": [{"id": "sys_a", "name": "System A"}],
                "app": [],
                "cmp": [{"id": "cmp_direct", "name": "Direct Component", "sys": "sys_a"}],
                "interface": [],
                "usr": [],
            }
        )

        assert result["valid"] is True

    def test_validate_rejects_component_with_unknown_system_reference(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        result = validate_entities(
            entities={
                "sys": [{"id": "sys_a", "name": "System A"}],
                "app": [],
                "cmp": [{"id": "cmp_direct", "name": "Direct Component", "sys": "sys_missing"}],
                "interface": [],
                "usr": [],
            }
        )

        assert result["valid"] is False
        assert any(
            item["code"] == "invalid_reference" and item["details"].get("field") == "sys"
            for item in result["issues"]["errors"]
        )

    def test_validate_rejects_component_without_any_parent_reference(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        result = validate_entities(
            entities={
                "sys": [{"id": "sys_a", "name": "System A"}],
                "app": [],
                "cmp": [{"id": "cmp_orphan", "name": "Orphan Component"}],
                "interface": [],
                "usr": [],
            }
        )

        assert result["valid"] is False
        assert any(
            item["code"] == "missing_reference"
            and "application or a system" in item["message"]
            for item in result["issues"]["errors"]
        )

    def test_validate_rejects_duplicate_ids_across_sheets(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        result = validate_entities(
            entities={
                "sys": [{"id": "billing", "name": "Billing System"}],
                "app": [{"id": "billing", "name": "Billing App", "sys": "billing"}],
                "cmp": [],
                "interface": [],
                "usr": [],
            }
        )

        assert result["valid"] is False
        assert any(
            item["code"] == "duplicate_id" and item["details"].get("sheets") == ["sys", "app"]
            for item in result["issues"]["errors"]
        )


class TestEntityAliases:
    def test_workbook_ingest_accepts_long_sheet_names(
        self, tmp_path: Path, build_arch_workbook: object
    ) -> None:
        from otdev.tools._arch.ingest import ingest_workbooks

        workbook_path = build_arch_workbook(
            tmp_path / "architecture.xlsx",
            {
                "system": [["id", "name"], ["sys_a", "System A"]],
                "application": [["id", "name", "system"], ["app_a", "App A", "sys_a"]],
                "components": [["id", "name", "application"], ["cmp_a", "Component A", "app_a"]],
                "interface": [["id", "provider", "consumer"], ["interface_1", "cmp_a", "app_a"]],
                "user": [["id", "name", "application"], ["usr_a", "User A", "app_a"]],
            },
        )

        entities = ingest_workbooks(workbook_paths=[workbook_path])

        assert entities["sys"][0]["id"] == "sys_a"
        assert entities["app"][0]["system"] == "sys_a"
        assert entities["cmp"][0]["application"] == "app_a"
        assert entities["interface"][0]["id"] == "interface_1"
        assert entities["usr"][0]["id"] == "usr_a"

    def test_workbook_ingest_rejects_duplicate_sheet_aliases(self, tmp_path: Path) -> None:
        from otdev.tools._arch.ingest import IngestError, ingest_workbooks

        openpyxl = pytest.importorskip("openpyxl")

        workbook_path = tmp_path / "architecture.xlsx"
        wb = openpyxl.Workbook()
        wb.active.title = "int"
        wb.create_sheet("interface")
        wb.save(workbook_path)
        wb.close()

        with pytest.raises(IngestError, match="multiple sheets for 'interface'"):
            ingest_workbooks(workbook_paths=[workbook_path])

    def test_yaml_loader_accepts_short_and_long_sections(self, tmp_path: Path) -> None:
        from otdev.tools._arch.roundtrip import load_yaml_entities

        yaml_path = tmp_path / "architecture.yaml"
        yaml_path.write_text(
            "\n".join(
                [
                    "system:",
                    "  - id: sys_a",
                    "    name: System A",
                    "application:",
                    "  - id: app_a",
                    "    name: App A",
                    "    system: sys_a",
                    "components:",
                    "  - id: cmp_a",
                    "    name: Component A",
                    "    application: app_a",
                    "int:",
                    "  - id: interface_1",
                    "    provider: cmp_a",
                    "    consumer: app_a",
                    "usr: []",
                ]
            ),
            encoding="utf-8",
        )

        entities, _passthrough = load_yaml_entities(input_path=yaml_path)

        assert entities["sys"][0]["id"] == "sys_a"
        assert entities["app"][0]["system"] == "sys_a"
        assert entities["cmp"][0]["application"] == "app_a"
        assert entities["interface"][0]["id"] == "interface_1"

    def test_yaml_loader_rejects_duplicate_section_aliases(self, tmp_path: Path) -> None:
        from otdev.tools._arch.roundtrip import RoundtripError, load_yaml_entities

        yaml_path = tmp_path / "architecture.yaml"
        yaml_path.write_text(
            "\n".join(
                [
                    "int: []",
                    "interface: []",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(RoundtripError, match="multiple sections for 'interface'"):
            load_yaml_entities(input_path=yaml_path)


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
        from otdev.tools._arch import generate as arch_generate

        def _raise_not_found(*args: object, **kwargs: object) -> object:
            _ = args, kwargs
            raise FileNotFoundError("[Errno 2] No such file or directory: 'd2'")

        monkeypatch.setattr(arch_generate.subprocess, "run", _raise_not_found)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["operation"] == "generate"
        assert result["error"]["code"] == "engine_command_not_found"
        assert "Install D2 CLI: https://github.com/terrastruct/d2" in result["error"]["message"]

    def test_generate_returns_timeout_error_when_engine_hangs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import subprocess

        from otdev.tools import arch
        from otdev.tools._arch import generate as arch_generate

        seen_timeouts: list[object] = []

        def _raise_timeout(*args: object, **kwargs: object) -> object:
            _ = args
            seen_timeouts.append(kwargs.get("timeout"))
            raise subprocess.TimeoutExpired(cmd="d2", timeout=kwargs.get("timeout") or 0)

        monkeypatch.setattr(arch_generate.subprocess, "run", _raise_timeout)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["operation"] == "generate"
        assert result["error"]["code"] == "engine_command_timeout"
        assert (
            f"timed out after {arch_generate._RENDER_TIMEOUT_SECONDS}s"
            in result["error"]["message"]
        )
        assert result["error"]["details"]["timeout_seconds"] == arch_generate._RENDER_TIMEOUT_SECONDS
        assert seen_timeouts and all(
            value == arch_generate._RENDER_TIMEOUT_SECONDS for value in seen_timeouts
        )

    def test_generate_uses_profile_yaml_as_the_run_profile(
        self,
        tmp_path: Path,
        fake_render_engine: object,
    ) -> None:
        from otdev.tools import arch

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
        fake_render_engine: object,
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

    def test_generate_applies_interface_templates_to_solution_d2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_render_engine: object,
    ) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].data = {
            "show_interface_labels": True,
            "interface_labels": "[{{ row.id }}] {{ row.name }}",
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
        assert '[interface_user_api] User to API' in d2_text
        assert 'source-arrowhead.label: "interface_user_api"' in d2_text
        assert 'target-arrowhead.label: "interface_user_api"' in d2_text

    def test_generate_rejects_removed_format_argument(self) -> None:
        from otdev.tools.arch import generate

        with pytest.raises(TypeError):
            generate(input_path=str(_FIXTURES / "architecture.xlsx"), format="solution")  # type: ignore[call-arg]

    def test_generate_with_tag_filters(self, tmp_path: Path, fake_render_engine: object) -> None:
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
        fake_render_engine: object,
    ) -> None:
        from otdev.tools import arch

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
        fake_render_engine: object,
    ) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].data = {"direction": "left"}
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
        assert "direction: left" in d2_text

    def test_generate_solution_ignores_removed_direction_alias(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_render_engine: object,
    ) -> None:
        """The legacy system_diagram_direction alias no longer applies; default is up."""
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].data = {"system_diagram_direction": "left"}
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
        assert "direction: up" in d2_text

    def test_generate_solution_emits_project_pages(
        self,
        tmp_path: Path,
        fake_render_engine: object,
        build_arch_workbook: object,
    ) -> None:
        from otdev.tools import arch

        workbook_path = build_arch_workbook(
            tmp_path / "project.xlsx",
            {
                "sys": [
                    ["id", "name"],
                    ["sys_a", "System A"],
                    ["sys_b", "System B"],
                ],
                "app": [
                    ["id", "name", "sys"],
                    ["app_a", "App A", "sys_a"],
                    ["app_b", "App B", "sys_b"],
                ],
                "cmp": [
                    ["id", "name", "app"],
                    ["cmp_a", "Component A", "app_a"],
                    ["cmp_b", "Component B", "app_b"],
                ],
                "interface": [
                    ["id", "key", "name", "provider", "consumer"],
                    ["interface_ab", "AB", "A to B", "cmp_b", "cmp_a"],
                ],
                "usr": [["id", "name", "app"]],
                "project": [
                    ["id", "name", "detail_level", "connect_level", "owner", "priority"],
                    ["wallet", "Wallet Project", "cmp", "cmp", "platform", "P1"],
                ],
                "project_scope": [
                    ["project", "stage", "item_type", "item_id", "change_type", "priority"],
                    ["wallet", "current", "system", "sys_a", "existing", "P2"],
                    ["wallet", "target", "interface", "interface_ab", "new", "P1"],
                ],
            },
        )

        result = arch.generate(input_path=str(workbook_path), output_dir=str(tmp_path / "out"))

        assert result["ok"] is True
        solution_files = [Path(item) for item in result["files"]["solution"]]
        project_page = Path(result["output_dir"]) / "solution" / "project-wallet.html"
        assert project_page in solution_files
        index_html = (Path(result["output_dir"]) / "solution" / "index.html").read_text(
            encoding="utf-8"
        )
        project_html = project_page.read_text(encoding="utf-8")
        target_d2 = Path(result["output_dir"]) / "solution" / "images" / "project-wallet-target.d2"
        target_d2_text = target_d2.read_text(encoding="utf-8")

        assert "Wallet Project" in index_html
        assert 'href="project-wallet.html"' in index_html
        assert "Stages" in project_html
        assert "Scope" in project_html
        assert "P1" in project_html
        assert '"sys_a"."app_a"."cmp_a" -> "sys_b"."app_b"."cmp_b"' in target_d2_text

    def test_build_project_d2_uses_project_detail_and_connect_levels(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_project_d2 as _build_project_d2

        entities = _project_entities()
        graph = _build_entity_graph(entities=entities)

        rendered = _build_project_d2(
            project_id="wallet",
            stage="target",
            entities=entities,
            graph=graph,
            template_path=_project_view_debug_template(tmp_path),
            profile_data={},
        )

        assert "detail=cmp connect=cmp" in rendered
        assert "cmp=sys_a.app_a.cmp_a" in rendered
        assert "cmp=sys_b.app_b.cmp_b" in rendered
        assert 'edge="sys_a"."app_a"."cmp_a" -> "sys_b"."app_b"."cmp_b"' in rendered

    def test_build_system_d2_merges_interfaces_with_template_arrowheads(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        template_path = tmp_path / "system.d2.j2"
        template_path.write_text(
            "\n".join(
                [
                    'direction: {{ profile_data.direction | default(profile_data.system_diagram_direction | default("right")) }}',
                    "{% for edge in model.system_view.interface_edges -%}",
                    '{{ edge.start_path }} {{ edge.operator }} {{ edge.end_path }}: "{{ edge.label }}" {',
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
            "interface": [
                {
                    "id": "interface_1",
                    "key": "1",
                    "name": "Flow One",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                    "interaction_type": "api_call",
                },
                {
                    "id": "interface_2",
                    "key": "2",
                    "name": "Flow Two",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                    "interaction_type": "batch_export",
                },
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
                "merge_interfaces": True,
                "show_interface_labels": True,
                "interface_labels": "[{{ row.key }}] {{ row.name }}",
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

    def test_build_system_d2_hides_interface_labels_when_disabled(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        template_path = tmp_path / "system.d2.j2"
        template_path.write_text(
            "\n".join(
                [
                    "{% for edge in model.system_view.interface_edges -%}",
                    '{{ edge.start_path }} {{ edge.operator }} {{ edge.end_path }}: "{{ edge.label }}" {',
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
            "interface": [
                {
                    "id": "interface_1",
                    "key": "1",
                    "name": "Flow One",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                    "interaction_type": "api_call",
                },
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
                "merge_interfaces": False,
                "show_interface_labels": False,
            },
        )

        assert '-> "sys_b": "" {' in rendered
        assert "Flow One (api_call)" not in rendered

    @pytest.mark.parametrize(
        ("arrow_direction", "expected_edge"),
        [
            ("consumer_to_provider", 'edge="sys_a" -> "sys_b"'),
            ("provider_to_consumer", 'edge="sys_b" -> "sys_a"'),
            ("none", 'edge="sys_a" -- "sys_b"'),
            ("bidirectional", 'edge="sys_a" <-> "sys_b"'),
        ],
    )
    def test_build_system_d2_supports_interface_arrow_directions(
        self,
        tmp_path: Path,
        arrow_direction: str,
        expected_edge: str,
    ) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_b", "name": "System B"},
            ],
            "app": [],
            "cmp": [],
            "interface": [
                {
                    "id": "interface_1",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                    "arrow_direction": arrow_direction,
                },
            ],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="sys",
            entities=entities,
            graph=graph,
            template_path=_system_view_debug_template(tmp_path),
            profile_data={"show_interface_labels": False},
        )

        assert expected_edge in rendered

    def test_build_system_d2_defaults_secondary_systems_to_system_detail(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities = _secondary_detail_entities()
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="cmp",
            entities=entities,
            graph=graph,
            template_path=_system_view_debug_template(tmp_path),
            profile_data={"show_interface_labels": False},
        )

        assert "cmp=sys_a.app_a.cmp_a" in rendered
        assert "block=sys_b placeholder=True" in rendered
        assert "app=sys_b.app_b" not in rendered
        assert 'edge="sys_a"."app_a"."cmp_a" -> "sys_b"' in rendered

    def test_build_system_d2_renders_secondary_systems_at_app_detail(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities = _secondary_detail_entities()
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="sys",
            entities=entities,
            graph=graph,
            template_path=_system_view_debug_template(tmp_path),
            profile_data={
                "secondary_system_detail": "app",
                "show_interface_labels": False,
            },
        )

        assert "block=sys_b placeholder=False" in rendered
        assert "app=sys_b.app_b" in rendered
        assert "cmp=sys_b.app_b.cmp_b" not in rendered
        assert 'edge="sys_a" -> "sys_b"."app_b"' in rendered

    def test_build_system_d2_renders_and_connects_secondary_systems_at_cmp_detail(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities = _secondary_detail_entities()
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="app",
            entities=entities,
            graph=graph,
            template_path=_system_view_debug_template(tmp_path),
            profile_data={
                "secondary_system_detail": "cmp",
                "secondary_system_connect_level": "cmp",
                "show_interface_labels": False,
            },
        )

        assert "cmp=sys_b.app_b.cmp_b" in rendered
        assert 'edge="sys_a"."app_a" -> "sys_b"."app_b"."cmp_b"' in rendered

    def test_build_system_d2_matches_secondary_detail_to_primary_diagram_level(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities = _secondary_detail_entities()
        graph = _build_entity_graph(entities=entities)
        template_path = _system_view_debug_template(tmp_path)

        app_rendered = _build_system_d2(
            system_id="sys_a",
            level="app",
            entities=entities,
            graph=graph,
            template_path=template_path,
            profile_data={
                "secondary_system_detail": "match_primary",
                "show_interface_labels": False,
            },
        )
        cmp_rendered = _build_system_d2(
            system_id="sys_a",
            level="cmp",
            entities=entities,
            graph=graph,
            template_path=template_path,
            profile_data={
                "secondary_system_detail": "match_primary",
                "secondary_system_connect_level": "lowest_visible",
                "show_interface_labels": False,
            },
        )

        assert "app=sys_b.app_b" in app_rendered
        assert "cmp=sys_b.app_b.cmp_b" not in app_rendered
        assert "cmp=sys_b.app_b.cmp_b" in cmp_rendered
        assert 'edge="sys_a"."app_a"."cmp_a" -> "sys_b"."app_b"."cmp_b"' in cmp_rendered

    def test_build_system_d2_rejects_invalid_secondary_profile_options(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities = _secondary_detail_entities()
        graph = _build_entity_graph(entities=entities)

        with pytest.raises(ConfigResolutionError, match="secondary_system_detail"):
            _build_system_d2(
                system_id="sys_a",
                level="sys",
                entities=entities,
                graph=graph,
                template_path=_system_view_debug_template(tmp_path),
                profile_data={"secondary_system_detail": "component"},
            )

        with pytest.raises(ConfigResolutionError, match="secondary_system_connect_level"):
            _build_system_d2(
                system_id="sys_a",
                level="sys",
                entities=entities,
                graph=graph,
                template_path=_system_view_debug_template(tmp_path),
                profile_data={"secondary_system_connect_level": "component"},
            )

    def test_solution_system_context_uses_interface_key_field(self) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_system_context as _build_solution_system_context

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [],
            "cmp": [],
            "interface": [
                {
                    "id": "interface_1",
                    "key": "K-01",
                    "name": "Flow One",
                    "provider": "sys_a",
                    "consumer": "sys_a",
                    "interaction_type": "api_call",
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

        assert context["interfaces_data"][0]["key"] == "K-01"
        assert context["interfaces_columns"][0]["title"] == "Key"
        assert context["interfaces_columns"][0]["field"] == "key"
        assert [item["label"] for item in context["diagrams"]] == ["System", "Application", "Component"]
        assert context["additional_diagrams"] == []

    def test_solution_system_context_splits_additional_diagrams(self) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_system_context as _build_solution_system_context

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [],
            "cmp": [],
            "interface": [],
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

    def test_generate_solution_inlines_styles_into_system_d2(
        self, tmp_path: Path, fake_render_engine: object
    ) -> None:
        from otdev.tools import arch

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

    def test_generate_reports_solution_format_in_summary(
        self, tmp_path: Path, fake_render_engine: object
    ) -> None:
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
        fake_render_engine: object,
    ) -> None:
        from otdev.tools import arch

        legacy_template = tmp_path / "legacy-system.d2.j2"
        legacy_template.write_text("title: {{ title_name }}\n", encoding="utf-8")
        (tmp_path / "styles.d2").write_text("", encoding="utf-8")

        config = ArchConfig()
        config.profiles["simple"].system_diagram = str(legacy_template)
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)

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

    def test_generate_rejects_legacy_flat_interface_template_variables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        config = ArchConfig()
        config.profiles["simple"].data = {
            "show_interface_labels": True,
            "interface_labels": "[{{ key }}] {{ name }}",
        }
        monkeypatch.setattr(arch, "get_arch_config", lambda: config)

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "config_error"
        assert "Failed rendering tools.arch.profiles.<name>.data.interface_labels" in result["error"]["message"]

    def test_generate_rejects_unsafe_system_id_for_output_paths(
        self, tmp_path: Path, build_arch_workbook: object
    ) -> None:
        from otdev.tools.arch import generate

        workbook_path = build_arch_workbook(
            tmp_path / "unsafe-system-id.xlsx",
            {
                "sys": [["id", "name"], ["sys;bad", "System Bad"]],
                "app": [["id", "name", "sys"], ["app_bad", "App Bad", "sys;bad"]],
                "cmp": [["id", "name", "app"], ["cmp_bad", "Cmp Bad", "app_bad"]],
                "interface": [["id", "provider", "consumer"], ["interface_bad", "cmp_bad", "app_bad"]],
                "usr": [["id", "name", "app"], ["usr_bad", "User Bad", "app_bad"]],
            },
        )

        result = generate(
            input_path=str(workbook_path),
            output_dir=str(tmp_path / "out"),
        )

        assert result["ok"] is False
        assert result["error"]["code"] == "validation_failed"
        assert result["issues"]["errors"][0]["code"] == "invalid_value"

    def test_generate_rejects_unsafe_diagram_file_fragment(
        self, tmp_path: Path, build_arch_workbook: object
    ) -> None:
        from otdev.tools.arch import generate

        workbook_path = build_arch_workbook(
            tmp_path / "unsafe-diagram-file.xlsx",
            {
                "sys": [["id", "name"], ["sys_ok", "System OK"]],
                "app": [["id", "name", "sys"], ["app_ok", "App OK", "sys_ok"]],
                "cmp": [["id", "name", "app"], ["cmp_ok", "Cmp OK", "app_ok"]],
                "interface": [["id", "provider", "consumer"], ["interface_ok", "cmp_ok", "app_ok"]],
                "usr": [["id", "name", "app"], ["usr_ok", "User OK", "app_ok"]],
                "diagram": [
                    ["file", "name", "sys", "description"],
                    ["seq;bad.d2", "Unsafe", "sys_ok", "Unsafe file path"],
                ],
            },
        )

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
            "interface": [],
            "usr": [],
        }

        filtered = apply_tag_filters(
            entities=entities,
            include_tags=["platform"],
            exclude_tags=None,
        )
        assert len(filtered["sys"]) == 1
        assert filtered["sys"][0]["id"] == "sys-a"


def _project_class_debug_template(tmp_path: Path) -> Path:
    template_path = tmp_path / "project.d2.j2"
    template_path.write_text(
        "\n".join(
            [
                "{% for block in model.project_view.system_blocks -%}",
                "block={{ block.id }} change={{ block.change_class | default('NONE') }}",
                "{% for app in block.apps -%}",
                "app={{ block.id }}.{{ app.id }} change={{ app.change_class | default('NONE') }}",
                "{% for cmp in app.components -%}",
                "cmp={{ block.id }}.{{ app.id }}.{{ cmp.id }} change={{ cmp.change_class | default('NONE') }}",
                "{% endfor -%}",
                "{% endfor -%}",
                "{% for direct in block.direct_components -%}",
                "direct={{ block.id }}.{{ direct.id }} change={{ direct.change_class | default('NONE') }}",
                "{% endfor -%}",
                "{% endfor -%}",
                "{% for edge in model.project_view.interface_edges -%}",
                "edge={{ edge.start_path }} {{ edge.operator }} {{ edge.end_path }} "
                "direction={{ edge.direction_class }} "
                "interaction={{ edge.interaction_class | default('NONE') }} "
                "change={{ edge.change_class | default('NONE') }}",
                "{% endfor -%}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return template_path


def _system_edge_class_debug_template(tmp_path: Path) -> Path:
    template_path = tmp_path / "system.d2.j2"
    template_path.write_text(
        "\n".join(
            [
                "{% for edge in model.system_view.interface_edges -%}",
                "edge={{ edge.start_path }} {{ edge.operator }} {{ edge.end_path }} "
                "direction={{ edge.direction_class }} "
                "interaction={{ edge.interaction_class | default('NONE') }}",
                "{% endfor -%}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return template_path


class TestChangeTypeAndInteractionStyling:
    """Tasks 2.6 and 3.4: change-class / interaction-class context wiring."""

    @staticmethod
    def _entities() -> dict[str, list[dict[str, object]]]:
        return {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_b", "name": "System B"},
            ],
            "app": [{"id": "app_a", "name": "App A", "sys": "sys_a"}],
            "cmp": [{"id": "cmp_a", "name": "Component A", "app": "app_a"}],
            "interface": [
                {
                    "id": "interface_ab",
                    "key": "AB",
                    "name": "A to B",
                    "provider": "sys_b",
                    "consumer": "cmp_a",
                    "interaction_type": "API",
                },
            ],
            "usr": [],
            "project": [
                {
                    "id": "wallet",
                    "name": "Wallet Project",
                    "detail_level": "cmp",
                    "connect_level": "cmp",
                },
            ],
            "project_scope": [
                # interface scoped 'existing' at 'current': neutral edge styling,
                # but pulls in sys_b/cmp_a/app_a as unscoped (no own row) nodes.
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "interface",
                    "item_id": "interface_ab",
                    "change_type": "existing",
                },
                # cmp_a scoped directly, differently per stage.
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "component",
                    "item_id": "cmp_a",
                    "change_type": "impacted",
                },
                {
                    "project": "wallet",
                    "stage": "target",
                    "item_type": "component",
                    "item_id": "cmp_a",
                    "change_type": "new",
                },
            ],
        }

    def test_change_class_varies_by_stage(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_project_d2 as _build_project_d2

        entities = self._entities()
        graph = _build_entity_graph(entities=entities)
        template_path = _project_class_debug_template(tmp_path)

        current_rendered = _build_project_d2(
            project_id="wallet",
            stage="current",
            entities=entities,
            graph=graph,
            template_path=template_path,
            profile_data={},
        )
        target_rendered = _build_project_d2(
            project_id="wallet",
            stage="target",
            entities=entities,
            graph=graph,
            template_path=template_path,
            profile_data={},
        )

        assert "cmp=sys_a.app_a.cmp_a change=ChangeImpacted" in current_rendered
        assert "cmp=sys_a.app_a.cmp_a change=ChangeNew" in target_rendered

    def test_change_class_neutral_for_existing_and_unscoped(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_project_d2 as _build_project_d2

        entities = self._entities()
        graph = _build_entity_graph(entities=entities)

        rendered = _build_project_d2(
            project_id="wallet",
            stage="current",
            entities=entities,
            graph=graph,
            template_path=_project_class_debug_template(tmp_path),
            profile_data={},
        )

        # sys_b is only reached via the (existing-scoped) interface endpoint,
        # never has its own scope row -> unscoped, no change_class.
        assert "block=sys_b change=NONE" in rendered
        # sys_a owns the scoped component but is not itself scoped -> the
        # parent system block must not inherit the app/cmp change_class.
        assert "block=sys_a change=NONE" in rendered
        # interface_ab is scoped 'existing' -> neutral edge styling.
        edge_lines = [line for line in rendered.splitlines() if line.startswith("edge=")]
        assert edge_lines
        assert all(line.endswith("change=NONE") for line in edge_lines)

    def test_edge_change_class_for_non_existing_scoped_interface(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_project_d2 as _build_project_d2

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_b", "name": "System B"},
            ],
            "app": [],
            "cmp": [],
            "interface": [
                {
                    "id": "interface_ab",
                    "key": "AB",
                    "name": "A to B",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                },
            ],
            "usr": [],
            "project": [{"id": "wallet", "name": "Wallet Project"}],
            "project_scope": [
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "interface",
                    "item_id": "interface_ab",
                    "change_type": "removed",
                },
            ],
        }
        graph = _build_entity_graph(entities=entities)

        rendered = _build_project_d2(
            project_id="wallet",
            stage="current",
            entities=entities,
            graph=graph,
            template_path=_project_class_debug_template(tmp_path),
            profile_data={},
        )

        assert "change=ChangeRemoved" in [
            line for line in rendered.splitlines() if line.startswith("edge=")
        ][0]

    def test_scope_table_change_type_badge_html(self) -> None:
        from otdev.tools._arch.system_model import (
            build_entity_graph as _build_entity_graph,
            build_solution_project_context as _build_solution_project_context,
        )

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [],
            "cmp": [],
            "interface": [],
            "usr": [],
            "project": [{"id": "wallet", "name": "Wallet Project"}],
            "project_scope": [
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "system",
                    "item_id": "sys_a",
                    "change_type": "new",
                },
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "system",
                    "item_id": "sys_a",
                    "change_type": "removed",
                },
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "system",
                    "item_id": "sys_a",
                    "change_type": "existing",
                },
            ],
        }
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_project_context(
            project_id="wallet",
            entities=entities,
            graph=graph,
            svg_by_stage={},
        )

        badges = [row["change_type"] for row in context["scope_data"]]
        assert '<span class="badge" style="background:#2E7D32">New</span>' in badges
        assert '<span class="badge" style="background:#C62828">Removed</span>' in badges
        assert "existing" in badges
        assert not any("existing" in badge and "<span" in badge for badge in badges)

    def test_interaction_class_for_all_recognized_values_and_fallback(
        self, tmp_path: Path
    ) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}, {"id": "sys_b", "name": "System B"}],
            "app": [],
            "cmp": [],
            "interface": [
                {"id": "i1", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "API"},
                {"id": "i2", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "Event"},
                {"id": "i3", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "Queue"},
                {"id": "i4", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "Batch"},
                {"id": "i5", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "File"},
                {"id": "i6", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "Pub/Sub"},
                {"id": "i7", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "REST"},
                {"id": "i8", "provider": "sys_b", "consumer": "sys_a"},
            ],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="sys",
            entities=entities,
            graph=graph,
            template_path=_system_edge_class_debug_template(tmp_path),
            profile_data={"merge_interfaces": False},
        )

        assert "interaction=IntApi" in rendered
        assert "interaction=IntEvent" in rendered
        assert "interaction=IntQueue" in rendered
        assert "interaction=IntBatch" in rendered
        assert "interaction=IntFile" in rendered
        assert "interaction=IntPubsub" in rendered
        assert rendered.count("interaction=NONE") == 2

    def test_interaction_class_coexists_with_focus_direction_class(
        self, tmp_path: Path
    ) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}, {"id": "sys_b", "name": "System B"}],
            "app": [],
            "cmp": [],
            "interface": [
                {
                    "id": "interface_1",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                    "arrow_direction": "consumer_to_provider",
                    "interaction_type": "queue",
                },
            ],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="sys",
            entities=entities,
            graph=graph,
            template_path=_system_edge_class_debug_template(tmp_path),
            profile_data={"merge_interfaces": False},
        )

        assert "direction=InterfaceFromFocus" in rendered
        assert "interaction=IntQueue" in rendered

    def test_interfaces_table_interaction_type_badge(self) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_system_context as _build_solution_system_context

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}, {"id": "sys_b", "name": "System B"}],
            "app": [],
            "cmp": [],
            "interface": [
                {"id": "i1", "key": "1", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "API"},
                {"id": "i2", "key": "2", "provider": "sys_b", "consumer": "sys_a", "interaction_type": "REST"},
            ],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_system_context(
            system_id="sys_a",
            entities=entities,
            graph=graph,
            svg_by_level={"sys": "", "app": "", "cmp": ""},
            workbook_diagrams=[],
        )

        by_id = {row["id"]: row["interaction_type"] for row in context["interfaces_data"]}
        assert by_id["i1"] == '<span class="badge">API</span>'
        assert by_id["i2"] == "REST"


def _system_link_debug_template(tmp_path: Path) -> Path:
    template_path = tmp_path / "system.d2.j2"
    template_path.write_text(
        "\n".join(
            [
                "{% for block in model.system_view.system_blocks -%}",
                "block={{ block.id }} link={{ block.link | default('NONE') }}",
                "{% for app in block.apps -%}",
                "app={{ block.id }}.{{ app.id }} link={{ app.link | default('NONE') }}",
                "{% endfor -%}",
                "{% endfor -%}",
                "{% for ext in model.system_view.external_nodes -%}",
                "ext={{ ext.id }} link={{ ext.link | default('NONE') }}",
                "{% endfor -%}",
                "{% for user in model.system_view.user_nodes -%}",
                "user={{ user.id }} link={{ user.link | default('NONE') }}",
                "{% endfor -%}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return template_path


class TestClickableNodesAndNavigation:
    """Tasks 4.4 and 5.4: D2 `link` fields and cross-page navigation wiring."""

    def test_app_node_links_to_owning_system_page_unknown_and_person_have_none(
        self, tmp_path: Path
    ) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [{"id": "app_a", "name": "App A", "sys": "sys_a"}],
            "cmp": [],
            "interface": [{"id": "i1", "provider": "sys_a", "consumer": "unknown_ext"}],
            "usr": [{"id": "user_1", "name": "User One", "app": "app_a"}],
        }
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="app",
            entities=entities,
            graph=graph,
            template_path=_system_link_debug_template(tmp_path),
            profile_data={},
        )

        assert "block=sys_a link=./sys_a.html" in rendered
        assert "app=sys_a.app_a link=./sys_a.html" in rendered
        assert "ext=unknown_ext link=NONE" in rendered
        assert "user=user_1 link=NONE" in rendered

    def test_related_projects_appears_via_app_scope_row_and_empty_for_untouched(
        self,
    ) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_system_context as _build_solution_system_context

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_untouched", "name": "Untouched System"},
            ],
            "app": [{"id": "app_a", "name": "App A", "sys": "sys_a"}],
            "cmp": [],
            "interface": [],
            "usr": [],
            "project": [{"id": "wallet", "name": "Wallet Project"}],
            "project_scope": [
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "application",
                    "item_id": "app_a",
                    "change_type": "new",
                },
            ],
        }
        graph = _build_entity_graph(entities=entities)

        context_a = _build_solution_system_context(
            system_id="sys_a",
            entities=entities,
            graph=graph,
            svg_by_level={"sys": "", "app": "", "cmp": ""},
            workbook_diagrams=[],
        )
        context_untouched = _build_solution_system_context(
            system_id="sys_untouched",
            entities=entities,
            graph=graph,
            svg_by_level={"sys": "", "app": "", "cmp": ""},
            workbook_diagrams=[],
        )

        assert context_a["related_projects"] == [
            {
                "id": "wallet",
                "name": "Wallet Project",
                "href": "project-wallet.html",
                "change_types": ["new"],
            }
        ]
        assert context_untouched["related_projects"] == []

    def test_scope_item_link_vs_plain_text_split(self) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_project_context as _build_solution_project_context

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [{"id": "app_a", "name": "App A", "sys": "sys_a"}],
            "cmp": [{"id": "cmp_a", "name": "Component A", "app": "app_a"}],
            "interface": [{"id": "iface_1", "provider": "sys_a", "consumer": "app_a"}],
            "usr": [],
            "project": [{"id": "wallet", "name": "Wallet Project"}],
            "project_scope": [
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "system",
                    "item_id": "sys_a",
                    "change_type": "existing",
                },
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "application",
                    "item_id": "app_a",
                    "change_type": "existing",
                },
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "component",
                    "item_id": "cmp_a",
                    "change_type": "existing",
                },
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "interface",
                    "item_id": "iface_1",
                    "change_type": "existing",
                },
                {
                    "project": "wallet",
                    "stage": "current",
                    "item_type": "system",
                    "item_id": "sys_unknown",
                    "change_type": "existing",
                },
            ],
        }
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_project_context(
            project_id="wallet",
            entities=entities,
            graph=graph,
            svg_by_stage={},
        )

        scope_data = context["scope_data"]
        assert scope_data[0]["item_id"] == '<a href="sys_a.html">sys_a</a>'
        assert scope_data[1]["item_id"] == '<a href="sys_a.html">app_a</a>'
        assert scope_data[2]["item_id"] == '<a href="sys_a.html">cmp_a</a>'
        assert scope_data[3]["item_id"] == "iface_1"
        assert scope_data[4]["item_id"] == "sys_unknown"
        assert any(col["field"] == "item_id" and col["formatter"] == "html" for col in context["scope_columns"])

    def test_generate_renders_index_backlink_on_system_and_project_pages_only(
        self,
        tmp_path: Path,
        fake_render_engine: object,
        build_arch_workbook: object,
    ) -> None:
        from otdev.tools import arch

        workbook_path = build_arch_workbook(
            tmp_path / "nav.xlsx",
            {
                "sys": [["id", "name"], ["sys_a", "System A"]],
                "app": [["id", "name", "sys"]],
                "cmp": [["id", "name", "app"]],
                "interface": [["id", "key", "name", "provider", "consumer"]],
                "usr": [["id", "name", "app"]],
                "project": [["id", "name"], ["wallet", "Wallet Project"]],
                "project_scope": [
                    ["project", "stage", "item_type", "item_id", "change_type"],
                    ["wallet", "current", "system", "sys_a", "existing"],
                ],
            },
        )

        result = arch.generate(input_path=str(workbook_path), output_dir=str(tmp_path / "out"))
        assert result["ok"] is True

        solution_dir = Path(result["output_dir"]) / "solution"
        system_html = (solution_dir / "sys_a.html").read_text(encoding="utf-8")
        project_html = (solution_dir / "project-wallet.html").read_text(encoding="utf-8")
        index_html = (solution_dir / "index.html").read_text(encoding="utf-8")

        assert 'href="index.html"' in system_html
        assert "Solution Index" in system_html
        assert 'href="index.html"' in project_html
        assert "Solution Index" in project_html
        assert "Solution Index" not in index_html


class TestDiagramLegend:
    """Task 6.3: legend context sourced from render_styles.py (D6); the
    `show_change_types` flag differs between system and project contexts."""

    def test_legend_context_contains_every_change_and_interaction_style(self) -> None:
        from otdev.tools._arch.render_styles import CHANGE_TYPE_STYLES, INTERACTION_TYPE_STYLES
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_system_context as _build_solution_system_context

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [],
            "cmp": [],
            "interface": [],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_system_context(
            system_id="sys_a",
            entities=entities,
            graph=graph,
            svg_by_level={"sys": "", "app": "", "cmp": ""},
            workbook_diagrams=[],
        )

        legend = context["legend"]
        change_labels = {item["label"] for item in legend["change_types"]}
        interaction_labels = {item["label"] for item in legend["interaction_types"]}
        assert change_labels == {style["label"] for style in CHANGE_TYPE_STYLES.values()}
        assert interaction_labels == {style["label"] for style in INTERACTION_TYPE_STYLES.values()}
        assert legend["direction_colors"]
        assert legend["node_classes"]

    def test_show_change_types_differs_between_project_and_system_context(self) -> None:
        from otdev.tools._arch.system_model import (
            build_entity_graph as _build_entity_graph,
            build_solution_project_context as _build_solution_project_context,
            build_solution_system_context as _build_solution_system_context,
        )

        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [],
            "cmp": [],
            "interface": [],
            "usr": [],
            "project": [{"id": "wallet", "name": "Wallet Project"}],
            "project_scope": [],
        }
        graph = _build_entity_graph(entities=entities)

        system_context = _build_solution_system_context(
            system_id="sys_a",
            entities=entities,
            graph=graph,
            svg_by_level={"sys": "", "app": "", "cmp": ""},
            workbook_diagrams=[],
        )
        project_context = _build_solution_project_context(
            project_id="wallet",
            entities=entities,
            graph=graph,
            svg_by_stage={},
        )

        assert system_context["show_change_types"] is False
        assert project_context["show_change_types"] is True


class TestSolutionIndexSummary:
    """Task 7.4: index summary-card aggregation and entity-table shapes (D7)."""

    @staticmethod
    def _entities() -> dict[str, list[dict[str, object]]]:
        return {
            "sys": [
                {"id": "sys_a", "name": "System A", "system_type": "internal"},
                {"id": "sys_b", "name": "System B", "system_type": "internal"},
                {"id": "sys_ext", "name": "External Vendor", "system_type": "external"},
            ],
            "app": [{"id": "app_a", "name": "App A", "sys": "sys_a"}],
            "cmp": [{"id": "cmp_a", "name": "Component A", "app": "app_a"}],
            "interface": [
                {
                    "id": "iface_api",
                    "name": "API Call",
                    "provider": "sys_a",
                    "consumer": "sys_b",
                    "interaction_type": "API",
                },
                {
                    "id": "iface_rest",
                    "name": "Legacy REST",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                    "interaction_type": "REST",
                },
            ],
            "usr": [],
            "project": [],
            "project_scope": [],
        }

    def test_aggregation_counts_include_unrecognized_interaction_type_by_literal_text(self) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_index_context as _build_solution_index_context

        entities = self._entities()
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_index_context(entities=entities, graph=graph)

        summary = context["summary_cards"]
        totals = {item["label"]: item["count"] for item in summary["totals"]}
        assert totals == {"Systems": 2, "Applications": 1, "Components": 1, "Interfaces": 2}

        interfaces_by_type = {item["label"]: item["count"] for item in summary["interfaces_by_type"]}
        assert interfaces_by_type == {"API": 1, "REST": 1}

    def test_zero_projects_omits_project_total_and_breakdown(self) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_index_context as _build_solution_index_context

        entities = self._entities()
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_index_context(entities=entities, graph=graph)

        summary = context["summary_cards"]
        assert "Projects" not in {item["label"] for item in summary["totals"]}
        assert summary["projects_by_status"] == []

    def test_entity_table_shapes_and_link_hrefs(self) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_solution_index_context as _build_solution_index_context

        entities = self._entities()
        entities["project"] = [{"id": "wallet", "name": "Wallet Project", "status": "active"}]
        graph = _build_entity_graph(entities=entities)

        context = _build_solution_index_context(entities=entities, graph=graph)
        tables = context["entity_tables"]

        assert set(tables) == {"systems", "applications", "components", "interfaces", "projects"}
        for table in tables.values():
            assert set(table) == {"title", "columns", "data"}

        systems_row = next(row for row in tables["systems"]["data"] if row["id"] == "sys_a")
        assert systems_row["name"] == '<a href="sys_a.html">System A</a>'
        assert all(row["id"] != "sys_ext" for row in tables["systems"]["data"])

        apps_row = tables["applications"]["data"][0]
        assert apps_row["name"] == '<a href="sys_a.html">App A</a>'
        assert apps_row["system"] == "sys_a"

        cmp_row = tables["components"]["data"][0]
        assert cmp_row["name"] == '<a href="sys_a.html">Component A</a>'

        iface_row = next(row for row in tables["interfaces"]["data"] if row["id"] == "iface_api")
        assert iface_row["provider"] == '<a href="sys_a.html">sys_a</a>'
        assert iface_row["consumer"] == '<a href="sys_b.html">sys_b</a>'

        project_row = tables["projects"]["data"][0]
        assert project_row["name"] == '<a href="project-wallet.html">Wallet Project</a>'


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
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"legacy_mode": True}, id="unknown-top-level-field"),
            pytest.param({"orchestration": {"profile": "simple"}}, id="legacy-orchestration-shape"),
            pytest.param(
                {"profiles": {"simple": {"sequence_engine": "d2 {{ input }} {{ output }}"}}},
                id="removed-sequence-engine-key",
            ),
            pytest.param(
                {"profiles": {"simple": {"title": "Legacy Title"}}},
                id="removed-profile-title-key",
            ),
            pytest.param(
                {"profiles": {"simple": {"include_tags": ["core"]}}},
                id="removed-profile-include-tags-key",
            ),
            pytest.param(
                {"profiles": {"simple": {"output_format": "markdown"}}},
                id="removed-profile-output-format-key",
            ),
            pytest.param(
                {"profiles": {"simple": {"single_file": False}}},
                id="removed-profile-single-file-key",
            ),
        ],
    )
    def test_config_rejects_unknown_and_removed_keys(self, payload: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            ArchConfig.model_validate(payload)

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

    def test_export_yaml_wraps_unexpected_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch

        def _boom(**kwargs: object) -> object:
            _ = kwargs
            raise RuntimeError("export boom")

        monkeypatch.setattr(arch, "ingest_input", _boom)

        result = arch.export_yaml(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_path=str(tmp_path / "out.yaml"),
        )

        assert result["ok"] is False
        assert result["operation"] == "export_yaml"
        assert result["error"]["code"] == "unexpected_error"
        assert "export boom" in result["error"]["message"]
        assert "traceback" in result["error"]["details"]

    def test_import_yaml_wraps_unexpected_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch

        def _boom(**kwargs: object) -> object:
            _ = kwargs
            raise RuntimeError("import boom")

        monkeypatch.setattr(arch, "load_yaml_entities", _boom)

        result = arch.import_yaml(
            input_path=str(tmp_path / "in.yaml"),
            template_path=str(tmp_path / "template.xlsx"),
            output_path=str(tmp_path / "out.xlsx"),
        )

        assert result["ok"] is False
        assert result["operation"] == "import_yaml"
        assert result["error"]["code"] == "unexpected_error"
        assert "import boom" in result["error"]["message"]
        assert "traceback" in result["error"]["details"]

    def test_bundle_solution_wraps_unexpected_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch

        def _boom(**kwargs: object) -> object:
            _ = kwargs
            raise RuntimeError("bundle boom")

        monkeypatch.setattr(arch, "bundle_solution_directory", _boom)

        result = arch.bundle_solution(directory=str(tmp_path))

        assert result["ok"] is False
        assert result["operation"] == "bundle_solution"
        assert result["error"]["code"] == "unexpected_error"
        assert "bundle boom" in result["error"]["message"]
        assert "traceback" in result["error"]["details"]

    def test_bundle_solution_reports_missing_beautifulsoup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        from otdev.tools import arch

        solution_dir = tmp_path / "solution"
        solution_dir.mkdir()
        (solution_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        # None in sys.modules makes `from bs4 import ...` raise ImportError.
        monkeypatch.setitem(sys.modules, "bs4", None)

        result = arch.bundle_solution(directory=str(solution_dir))

        assert result["ok"] is False
        assert result["operation"] == "bundle_solution"
        assert result["error"]["code"] == "bundle_error"
        assert "beautifulsoup4 is required" in result["error"]["message"]
        assert "onetool-mcp[dev]" in result["error"]["message"]

    def test_render_markdown_reports_missing_markdown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        from otdev.tools._arch import system_model
        from otdev.tools._arch.models import MissingDependencyError

        monkeypatch.setattr(system_model, "_md_converter", None)
        # None in sys.modules makes `import markdown` raise ImportError.
        monkeypatch.setitem(sys.modules, "markdown", None)

        with pytest.raises(MissingDependencyError, match="onetool-mcp\\[dev\\]"):
            system_model.render_markdown("**bold**")


class TestRenderingPolish:
    def test_profile_data_code_defaults_match_bundled_arch_yaml(self) -> None:
        """Code fallback defaults must equal the bundled arch.yaml profile data."""
        import yaml

        from ot.paths import get_global_templates_dir
        from otdev.tools._arch import system_model

        bundled = yaml.safe_load(
            (get_global_templates_dir() / "arch.yaml").read_text(encoding="utf-8")
        )
        data = bundled["tools"]["arch"]["profiles"]["simple"]["data"]

        assert data["merge_interfaces"] == system_model.DEFAULT_MERGE_INTERFACES
        assert data["show_interface_labels"] == system_model.DEFAULT_SHOW_INTERFACE_LABELS
        assert data["show_arrowhead_labels"] == system_model.DEFAULT_SHOW_ARROWHEAD_LABELS
        assert data["interface_labels"] == system_model.DEFAULT_INTERFACE_LABELS_TEMPLATE
        assert data["arrowhead_labels"] == system_model.DEFAULT_ARROWHEAD_LABELS_TEMPLATE
        assert data["direction"] == system_model.DEFAULT_DIRECTION
        assert data["secondary_system_detail"] == system_model.DEFAULT_SECONDARY_SYSTEM_DETAIL
        assert data["secondary_system_connect_level"] == system_model.DEFAULT_SECONDARY_CONNECT_LEVEL

        # The runtime fallback when a profile omits `direction` is the
        # `default("up")` literal inside the bundled D2 templates, not the
        # Python constant -- so the templates must carry the same value.
        # Glob rather than naming files: the template set is being
        # refactored (a shared include may appear); at least one *.d2.j2
        # must pin the constant's literal.
        d2_template_dir = get_global_templates_dir() / "arch-templates" / "d2"
        d2_templates = sorted(d2_template_dir.glob("*.d2.j2"))
        assert d2_templates, f"no bundled d2 templates found in {d2_template_dir}"
        direction_literal = f'default("{system_model.DEFAULT_DIRECTION}")'
        assert any(
            direction_literal in template.read_text(encoding="utf-8")
            for template in d2_templates
        ), f"no d2 template carries the {direction_literal} fallback"

    def test_build_system_d2_renders_direct_system_component(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        entities = {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_b", "name": "System B"},
            ],
            "app": [],
            "cmp": [{"id": "cmp_direct", "name": "Direct Component", "sys": "sys_a"}],
            "interface": [
                {
                    "id": "interface_direct",
                    "key": "D1",
                    "name": "Direct Flow",
                    "provider": "sys_b",
                    "consumer": "cmp_direct",
                }
            ],
            "usr": [],
        }
        graph = _build_entity_graph(entities=entities)

        rendered = _build_system_d2(
            system_id="sys_a",
            level="cmp",
            entities=entities,
            graph=graph,
            template_path=_system_view_debug_template(tmp_path),
            profile_data={"show_interface_labels": False},
        )

        assert "direct=sys_a.cmp_direct" in rendered
        assert 'edge="sys_a"."cmp_direct" -> "sys_b"' in rendered

    def test_build_system_d2_uses_neutral_class_for_undirected_edges(self, tmp_path: Path) -> None:
        from otdev.tools._arch.system_model import build_entity_graph as _build_entity_graph, build_system_d2 as _build_system_d2

        template_path = tmp_path / "system.d2.j2"
        template_path.write_text(
            "\n".join(
                [
                    "{% for edge in model.system_view.interface_edges -%}",
                    "edge={{ edge.start_path }} {{ edge.operator }} {{ edge.end_path }} class={{ edge.direction_class }}",
                    "{% endfor -%}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        entities = {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_b", "name": "System B"},
            ],
            "app": [],
            "cmp": [],
            "interface": [
                {
                    "id": "interface_bidi",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                    "arrow_direction": "bidirectional",
                },
                {
                    "id": "interface_none",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                    "arrow_direction": "none",
                },
                {
                    "id": "interface_directed",
                    "provider": "sys_b",
                    "consumer": "sys_a",
                },
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
            profile_data={"show_interface_labels": False, "merge_interfaces": False},
        )

        assert 'edge="sys_a" <-> "sys_b" class=Interface' in rendered
        assert 'edge="sys_a" -- "sys_b" class=Interface' in rendered
        assert 'edge="sys_a" -> "sys_b" class=InterfaceFromFocus' in rendered

    def test_wrap_label_breaks_words_longer_than_max_width(self) -> None:
        from otdev.tools._arch.system_model import _wrap_label

        wrapped = _wrap_label("Supercalifragilisticexpialidocious Service", 10)

        lines = wrapped.strip('"').split("\\n")
        assert all(len(line) <= 10 for line in lines)
        assert "".join(lines).replace(" ", "") == "SupercalifragilisticexpialidociousService"

    def test_generate_clears_stale_solution_outputs(
        self,
        tmp_path: Path,
        fake_render_engine: object,
    ) -> None:
        from otdev.tools import arch

        stale_file = tmp_path / "solution" / "removed-system.html"
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_text("<html>stale</html>", encoding="utf-8")

        result = arch.generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path),
        )

        assert result["ok"] is True
        assert not stale_file.exists()


class TestRoundtripStrictness:
    def test_load_yaml_rejects_unknown_section(self, tmp_path: Path) -> None:
        from otdev.tools._arch.roundtrip import RoundtripError, load_yaml_entities

        yaml_path = tmp_path / "model.yaml"
        yaml_path.write_text(
            "\n".join(
                [
                    "sys:",
                    "  - id: sys_a",
                    "    name: System A",
                    "integrations:",
                    "  - id: interface_1",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(RoundtripError, match="unknown section 'integrations'"):
            load_yaml_entities(input_path=yaml_path)

    def test_import_yaml_rejects_fields_without_template_columns(self, tmp_path: Path) -> None:
        from otdev.tools._arch.roundtrip import RoundtripError, import_yaml_into_template

        openpyxl = pytest.importorskip("openpyxl")

        template_path = tmp_path / "template.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "sys"
        ws.append(["id", "name"])
        wb.save(template_path)
        wb.close()

        entities = {
            "sys": [{"id": "sys_a", "name": "System A", "owner": "platform"}],
        }

        with pytest.raises(RoundtripError, match=r"no columns for fields \['owner'\]"):
            import_yaml_into_template(
                entities=entities,
                template_path=template_path,
                output_path=tmp_path / "out.xlsx",
            )


class TestIngestStrictness:
    def test_workbook_ingest_rejects_colliding_headers(self, tmp_path: Path) -> None:
        from otdev.tools._arch.ingest import IngestError, ingest_workbooks

        openpyxl = pytest.importorskip("openpyxl")

        workbook_path = tmp_path / "collide.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "sys"
        ws.append(["id", "Sys ID", "sys id"])
        ws.append(["sys_a", "a", "b"])
        wb.save(workbook_path)
        wb.close()

        with pytest.raises(IngestError, match="collide after normalization"):
            ingest_workbooks(workbook_paths=[workbook_path])


class TestListCellEncoding:
    def test_parse_cell_list_parses_bracketed_values(self) -> None:
        from otdev.tools._arch.models import parse_cell_list

        assert parse_cell_list("[core;internal]", separator=";") == ["core", "internal"]
        assert parse_cell_list("[ core ; internal ]", separator=";") == ["core", "internal"]
        assert parse_cell_list("[core]", separator=";") == ["core"]
        assert parse_cell_list("[]", separator=";") == []

    def test_parse_cell_list_leaves_unbracketed_scalars(self) -> None:
        from otdev.tools._arch.models import parse_cell_list

        assert parse_cell_list("core, internal", separator=";") == "core, internal"
        assert parse_cell_list("core", separator=";") == "core"
        assert parse_cell_list(3, separator=";") == 3

    def test_parse_cell_list_honors_configured_separator(self) -> None:
        from otdev.tools._arch.models import parse_cell_list

        assert parse_cell_list("[core|internal]", separator="|") == ["core", "internal"]
        # A different separator inside is not split.
        assert parse_cell_list("[core;internal]", separator="|") == ["core;internal"]

    def test_format_cell_list_roundtrips_with_parse(self) -> None:
        from otdev.tools._arch.models import format_cell_list, parse_cell_list

        assert format_cell_list(["core", "internal"], separator=";") == "[core;internal]"
        assert format_cell_list([], separator=";") == "[]"
        assert format_cell_list("scalar", separator=";") == "scalar"
        roundtripped = parse_cell_list(
            format_cell_list(["a", "b", "c"], separator=";"), separator=";"
        )
        assert roundtripped == ["a", "b", "c"]

    def test_ingest_parses_bracketed_cell_into_list(self, tmp_path: Path) -> None:
        from otdev.tools._arch.ingest import ingest_workbooks

        openpyxl = pytest.importorskip("openpyxl")
        workbook_path = tmp_path / "lists.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "sys"
        ws.append(["id", "name", "tags"])
        ws.append(["sys_a", "System A", "[core;internal]"])
        wb.save(workbook_path)
        wb.close()

        entities = ingest_workbooks(workbook_paths=[workbook_path])
        assert entities["sys"][0]["tags"] == ["core", "internal"]

    def test_ingest_honors_config_list_separator(self, tmp_path: Path) -> None:
        from otdev.tools._arch.ingest import ingest_workbooks

        openpyxl = pytest.importorskip("openpyxl")
        workbook_path = tmp_path / "lists.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "sys"
        ws.append(["id", "name", "tags"])
        ws.append(["sys_a", "System A", "[core|internal]"])
        wb.save(workbook_path)
        wb.close()

        entities = ingest_workbooks(workbook_paths=[workbook_path], list_cell_separator="|")
        assert entities["sys"][0]["tags"] == ["core", "internal"]


class TestConfigListSeparator:
    def test_default_list_cell_separator_is_semicolon(self) -> None:
        assert ArchConfig().list_cell_separator == ";"

    def test_list_cell_separator_is_configurable(self) -> None:
        cfg = ArchConfig(list_cell_separator="|")
        assert cfg.list_cell_separator == "|"


class TestYamlInputParity:
    def _write_valid_model_yaml(self, path: Path) -> None:
        import yaml as _yaml

        model = {
            "sys": [{"id": "sys_a", "name": "System A", "tags": ["core", "internal"]}],
            "app": [{"id": "app_a", "name": "App A", "sys": "sys_a"}],
            "cmp": [{"id": "cmp_a", "name": "Component A", "app": "app_a"}],
            "interface": [{"id": "i1", "provider": "sys_a", "consumer": "app_a"}],
            "usr": [],
        }
        path.write_text(_yaml.safe_dump(model, sort_keys=False), encoding="utf-8")

    def test_validate_accepts_yaml_input(self, tmp_path: Path) -> None:
        from otdev.tools.arch import validate

        yaml_path = tmp_path / "model.yaml"
        self._write_valid_model_yaml(yaml_path)

        result = validate(input_path=str(yaml_path))

        assert result["ok"] is True
        assert result["valid"] is True

    def test_validate_reports_yaml_input_errors(self, tmp_path: Path) -> None:
        from otdev.tools.arch import validate

        import yaml as _yaml

        bad = {
            "sys": [{"id": "sys_a", "name": "System A"}],
            "app": [{"id": "app_a", "name": "App A", "sys": "sys_missing"}],
            "cmp": [],
            "interface": [],
            "usr": [],
        }
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text(_yaml.safe_dump(bad, sort_keys=False), encoding="utf-8")

        result = validate(input_path=str(yaml_path))

        assert result["valid"] is False
        assert any(
            item["code"] == "invalid_reference" for item in result["issues"]["errors"]
        )

    def test_generate_accepts_yaml_input(self, tmp_path: Path, fake_render_engine: object) -> None:
        from otdev.tools import arch

        yaml_path = tmp_path / "model.yaml"
        self._write_valid_model_yaml(yaml_path)

        result = arch.generate(input_path=str(yaml_path), output_dir=str(tmp_path / "out"))

        assert result["ok"] is True
        assert result["files"]["solution"]


class TestRenderStyles:
    def test_render_styles_appear_verbatim_in_styles_d2(self) -> None:
        from ot.paths import get_global_templates_dir
        from otdev.tools._arch.render_styles import (
            CHANGE_TYPE_STYLES,
            DIRECTION_STYLES,
            INTERACTION_TYPE_STYLES,
        )

        styles_path = (
            get_global_templates_dir() / "arch-templates" / "d2" / "styles.d2"
        )
        styles_text = styles_path.read_text(encoding="utf-8")

        for entry in CHANGE_TYPE_STYLES.values():
            assert entry["d2_class"] in styles_text
            assert entry["color"] in styles_text

        for entry in INTERACTION_TYPE_STYLES.values():
            assert entry["d2_class"] in styles_text

        for d2_class, entry in DIRECTION_STYLES.items():
            assert d2_class in styles_text
            assert entry["color"] in styles_text

    def test_normalize_interaction_type_maps_recognized_values(self) -> None:
        from otdev.tools._arch.render_styles import normalize_interaction_type

        assert normalize_interaction_type("API") == "api"
        assert normalize_interaction_type("Pub/Sub") == "pubsub"
        assert normalize_interaction_type("REST") is None
        assert normalize_interaction_type(None) is None
        assert normalize_interaction_type("") is None


class TestDrawioEmitter:
    """Unit tests for the pure-function drawio emitter (Phase A of
    arch-drawio-editable-svg): `build_mxfile`, `extract_geometry`,
    `inject_content` (src/otdev/tools/_arch/drawio.py)."""

    # A checked-in minimal D2 0.7.1 SVG snippet exercising: a linked node
    # (`<a href>`-wrapped `<g class="<base64>">`, design D6), an unlinked
    # sibling node `<g>` at the same tree depth (D6 "flat siblings"), an
    # edge group (base64 decodes to a "(a -&gt; b)[0]" form and must be
    # skipped), and two non-path group classes d2 emits internally
    # (`shape`, `appendix-icon`) that must not be mistaken for node paths.
    # base64("sys_a") == "c3lzX2E=", base64("sys_a.app_a") == "c3lzX2EuYXBwX2E=",
    # base64("(sys_a -&gt; app_a)[0]") == "KHN5c19hIC0mZ3Q7IGFwcF9hKVswXQ==".
    _SAMPLE_SVG = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="0 0 480 439">'
        '<a href="./sys_a.html">'
        '<g class="c3lzX2E= System">'
        '<g class="shape"><rect x="0.000000" y="29.000000" width="261.000000" height="197.000000" /></g>'
        "</g>"
        "</a>"
        '<g class="c3lzX2EuYXBwX2E= App">'
        '<g class="shape"><rect x="30.000000" y="70.000000" width="201.000000" height="126.000000" /></g>'
        "</g>"
        '<g class="KHN5c19hIC0mZ3Q7IGFwcF9hKVswXQ==">'
        '<path d="M0,0 L1,1" />'
        "</g>"
        '<g class="shape"><rect x="0" y="0" width="10" height="10" /></g>'
        '<g class="appendix-icon"><rect x="0" y="0" width="1" height="1" /></g>'
        "</svg>"
    )

    def _sample_render_context(self) -> dict[str, object]:
        """A minimal but representative render-context fragment matching
        `model.system_view`/`model.project_view` shape (user_nodes,
        external_nodes, system_blocks, interface_edges) as assembled by
        `build_system_d2`/`build_project_d2` in system_model.py: labels are
        D2-quoted (`_quote_d2`/`_wrap_label`) and edge endpoint paths are
        D2 quoted-dotted path strings (`_node_path_for_level`)."""
        return {
            "user_nodes": [{"id": "usr_1", "label": '"User One"'}],
            "external_nodes": [{"id": "ext_1", "label": '"External Sys"'}],
            "system_blocks": [
                {
                    "id": "sys_a",
                    "label": '"System A"',
                    "placeholder": False,
                    "direct_components": [],
                    "apps": [
                        {
                            "id": "app_a",
                            "label": '"App A"',
                            "components": [
                                {"id": "cmp_a", "label": '"Component A"', "class": "DB"},
                            ],
                        }
                    ],
                }
            ],
            "interface_edges": [
                {
                    "start_path": '"sys_a"."app_a"."cmp_a"',
                    "operator": "->",
                    "end_path": '"usr_1"',
                    "label": "Get Data",
                },
            ],
        }

    def test_extract_geometry_matches_linked_and_unlinked_groups(self) -> None:
        from otdev.tools._arch.drawio import extract_geometry

        geometry = extract_geometry(self._SAMPLE_SVG)

        assert geometry == {
            "sys_a": (0.0, 29.0, 261.0, 197.0),
            "sys_a.app_a": (30.0, 70.0, 201.0, 126.0),
        }
        # The edge group and the two non-path group classes must not leak in.
        assert "(sys_a -> app_a)[0]" not in geometry
        assert len(geometry) == 2

    def test_extract_geometry_never_raises_on_malformed_svg(self) -> None:
        from otdev.tools._arch.drawio import extract_geometry

        assert extract_geometry("") == {}
        assert extract_geometry("<not-valid-xml") == {}
        assert extract_geometry("<svg><g class=\"not base64!!\"></g></svg>") == {}

    def test_build_mxfile_structure(self) -> None:
        import xml.etree.ElementTree as ET

        from otdev.tools._arch.drawio import build_mxfile

        context = self._sample_render_context()
        geometry = {
            "sys_a": (0.0, 29.0, 261.0, 197.0),
            "sys_a.app_a": (30.0, 70.0, 201.0, 126.0),
            "sys_a.app_a.cmp_a": (60.0, 100.0, 141.0, 66.0),
        }

        mxfile_xml = build_mxfile(
            user_nodes=context["user_nodes"],  # type: ignore[arg-type]
            external_nodes=context["external_nodes"],  # type: ignore[arg-type]
            system_blocks=context["system_blocks"],  # type: ignore[arg-type]
            interface_edges=context["interface_edges"],  # type: ignore[arg-type]
            geometry=geometry,
        )

        mxfile = ET.fromstring(mxfile_xml)
        assert mxfile.tag == "mxfile"
        assert mxfile.get("host") == "onetool-arch"

        diagrams = mxfile.findall("diagram")
        assert len(diagrams) == 1
        graph_models = diagrams[0].findall("mxGraphModel")
        assert len(graph_models) == 1

        cells = {cell.get("id"): cell for cell in mxfile.findall(".//mxCell")}

        # One vertex per node, correct label, correct parent nesting.
        assert cells["usr_1"].get("value") == "User One"
        assert cells["usr_1"].get("parent") == "1"
        assert cells["ext_1"].get("value") == "External Sys"
        assert cells["ext_1"].get("parent") == "1"
        assert cells["sys_a"].get("value") == "System A"
        assert cells["sys_a"].get("parent") == "1"
        assert cells["sys_a"].get("container") == "1"
        assert cells["sys_a.app_a"].get("value") == "App A"
        assert cells["sys_a.app_a"].get("parent") == "sys_a"
        assert cells["sys_a.app_a"].get("container") == "1"
        assert cells["sys_a.app_a.cmp_a"].get("value") == "Component A"
        assert cells["sys_a.app_a.cmp_a"].get("parent") == "sys_a.app_a"
        assert "container" not in cells["sys_a.app_a.cmp_a"].keys()

        # Edge cell bound to endpoint ids (quotes stripped from D2 paths).
        edge_cells = [cell for cell in mxfile.findall(".//mxCell") if cell.get("edge") == "1"]
        assert len(edge_cells) == 1
        assert edge_cells[0].get("source") == "sys_a.app_a.cmp_a"
        assert edge_cells[0].get("target") == "usr_1"
        assert edge_cells[0].get("value") == "Get Data"
        assert "orthogonalEdgeStyle" in (edge_cells[0].get("style") or "")

        # Standard draw.io root cells present.
        assert cells["0"].get("id") == "0"
        assert cells["1"].get("parent") == "0"

    def test_build_mxfile_grid_fallback_for_missing_geometry(self) -> None:
        import xml.etree.ElementTree as ET

        from otdev.tools._arch.drawio import build_mxfile

        # Two top-level nodes plus two components under the same app --
        # none present in the geometry map -- exercising the deterministic
        # grid fallback (design D7) both at the root level and inside a
        # container, with no extracted geometry anywhere.
        user_nodes = [{"id": "usr_1", "label": '"User One"'}]
        external_nodes = [{"id": "ext_1", "label": '"Ext Sys"'}]
        system_blocks = [
            {
                "id": "sys_a",
                "label": '"System A"',
                "placeholder": False,
                "direct_components": [],
                "apps": [
                    {
                        "id": "app_a",
                        "label": '"App A"',
                        "components": [
                            {"id": "cmp_a", "label": '"Component A"', "class": "DB"},
                            {"id": "cmp_b", "label": '"Component B"', "class": "API"},
                        ],
                    }
                ],
            }
        ]

        # Generation succeeds regardless of missing geometry.
        mxfile_xml = build_mxfile(
            user_nodes=user_nodes,
            external_nodes=external_nodes,
            system_blocks=system_blocks,
            interface_edges=[],
            geometry={},
        )
        assert 'host="onetool-arch"' in mxfile_xml

        mxfile = ET.fromstring(mxfile_xml)
        cells = {cell.get("id"): cell for cell in mxfile.findall(".//mxCell")}

        def _box(node_id: str) -> tuple[float, float, float, float]:
            geom = cells[node_id].find("mxGeometry")
            assert geom is not None
            return (
                float(geom.get("x", "nan")),
                float(geom.get("y", "nan")),
                float(geom.get("width", "nan")),
                float(geom.get("height", "nan")),
            )

        all_ids = ("usr_1", "ext_1", "sys_a", "sys_a.app_a", "sys_a.app_a.cmp_a", "sys_a.app_a.cmp_b")
        for node_id in all_ids:
            _x, _y, w, h = _box(node_id)
            assert w > 0
            assert h > 0

        # Top-level siblings (shared coordinate frame, parent="1") don't overlap.
        top_level_origins = {_box("usr_1")[:2], _box("ext_1")[:2], _box("sys_a")[:2]}
        assert len(top_level_origins) == 3

        # Fallback components under the same app (shared coordinate frame,
        # parent="sys_a.app_a") don't overlap either.
        assert _box("sys_a.app_a.cmp_a")[:2] != _box("sys_a.app_a.cmp_b")[:2]

        # Deterministic and reproducible: rerunning yields identical boxes.
        mxfile_xml_again = build_mxfile(
            user_nodes=user_nodes,
            external_nodes=external_nodes,
            system_blocks=system_blocks,
            interface_edges=[],
            geometry={},
        )
        assert mxfile_xml_again == mxfile_xml

    def test_inject_content_round_trip(self) -> None:
        import xml.etree.ElementTree as ET

        from otdev.tools._arch.drawio import build_mxfile, inject_content

        context = self._sample_render_context()
        mxfile_xml = build_mxfile(
            user_nodes=context["user_nodes"],  # type: ignore[arg-type]
            external_nodes=context["external_nodes"],  # type: ignore[arg-type]
            system_blocks=context["system_blocks"],  # type: ignore[arg-type]
            interface_edges=context["interface_edges"],  # type: ignore[arg-type]
            geometry={
                "sys_a": (0.0, 29.0, 261.0, 197.0),
                "sys_a.app_a": (30.0, 70.0, 201.0, 126.0),
                "sys_a.app_a.cmp_a": (60.0, 100.0, 141.0, 66.0),
            },
        )

        injected_svg = inject_content(self._SAMPLE_SVG, mxfile_xml)

        # Visual markup preserved verbatim; only the root `content` attribute added.
        assert "<a href=" in injected_svg
        assert 'class="c3lzX2E= System"' in injected_svg

        root = ET.fromstring(injected_svg)
        assert root.tag.endswith("}svg") or root.tag == "svg"
        content = root.get("content")
        assert content is not None

        # `content` round-trips through an XML parser back to a well-formed
        # mxfile whose cells match what build_mxfile produced.
        parsed_mxfile = ET.fromstring(content)
        assert parsed_mxfile.tag == "mxfile"
        assert parsed_mxfile.get("host") == "onetool-arch"
        cell_ids = {cell.get("id") for cell in parsed_mxfile.findall(".//mxCell")}
        assert {"sys_a", "sys_a.app_a", "sys_a.app_a.cmp_a", "usr_1"} <= cell_ids
        assert len(parsed_mxfile.findall("diagram")) == 1

    def test_svg_markup_strips_content_attribute(self) -> None:
        """`svg_markup()` (system_model.py) must strip the draw.io `content`
        attribute from the root `<svg>` opening tag so inline HTML markup
        never carries the embedded model (design D9)."""
        from otdev.tools._arch.drawio import build_mxfile, inject_content
        from otdev.tools._arch.system_model import svg_markup as _svg_markup

        context = self._sample_render_context()
        mxfile_xml = build_mxfile(
            user_nodes=context["user_nodes"],  # type: ignore[arg-type]
            external_nodes=context["external_nodes"],  # type: ignore[arg-type]
            system_blocks=context["system_blocks"],  # type: ignore[arg-type]
            interface_edges=context["interface_edges"],  # type: ignore[arg-type]
            geometry={},
        )
        injected_svg = inject_content(self._SAMPLE_SVG, mxfile_xml)
        assert 'content="' in injected_svg  # sanity: fixture actually has one

        markup = _svg_markup(injected_svg)

        assert "content=" not in markup
        assert "<mxfile" not in markup
        # Visual markup (namespaces, node groups) is otherwise unaffected.
        assert 'class="c3lzX2E= System"' in markup
        assert markup.startswith("<svg")

    def test_svg_markup_no_content_attribute_is_a_no_op(self) -> None:
        from otdev.tools._arch.system_model import svg_markup as _svg_markup

        assert _svg_markup(self._SAMPLE_SVG).startswith("<svg")
        assert _svg_markup(self._SAMPLE_SVG) == self._SAMPLE_SVG[self._SAMPLE_SVG.find("<svg") :]

    def test_drawio_export_toggle_rejects_non_boolean(self) -> None:
        """The `drawio_export` profile `data` toggle (design D10) must raise
        `ConfigResolutionError` for a non-boolean value rather than silently
        coercing it -- generation fails fast rather than guessing intent."""
        from otdev.tools.arch import _resolve_drawio_export_toggle

        with pytest.raises(ConfigResolutionError, match="drawio_export"):
            _resolve_drawio_export_toggle({"drawio_export": "yes"})

    def test_drawio_export_toggle_defaults_true_and_honors_explicit_bool(self) -> None:
        from otdev.tools.arch import _resolve_drawio_export_toggle

        assert _resolve_drawio_export_toggle({}) is True
        assert _resolve_drawio_export_toggle({"drawio_export": False}) is False
        assert _resolve_drawio_export_toggle({"drawio_export": True}) is True


class TestArchDiagramSheet:
    def test_generates_workbook_diagram_and_embeds_it_in_system_page(
        self,
        tmp_path: Path,
        fake_render_engine: object,
        build_arch_workbook: object,
    ) -> None:
        from otdev.tools import arch

        build_arch_workbook(
            tmp_path / "core.xlsx",
            {
                "sys": [["id", "name"], ["sys_core", "Core"]],
                "app": [["id", "name", "sys"], ["app_core", "App Core", "sys_core"]],
                "cmp": [["id", "name", "app"], ["cmp_core", "Cmp Core", "app_core"]],
                "interface": [
                    ["id", "provider", "consumer", "name"],
                    ["interface_1", "cmp_core", "app_core", "calls"],
                ],
                "usr": [["id", "name", "app"], ["usr_a", "User A", "app_core"]],
            },
        )

        diagram_dir = tmp_path / "seq"
        diagram_dir.mkdir(parents=True, exist_ok=True)
        (diagram_dir / "seq_aws.d2").write_text(
            'title: "AWS Sequence Example"\na -> b: "request"\n',
            encoding="utf-8",
        )

        build_arch_workbook(
            tmp_path / "diagrams.xlsx",
            {
                "diagram": [
                    ["file", "name", "sys", "description"],
                    [
                        "seq/seq_aws.d2",
                        "AWS Sequence Example",
                        "sys_core",
                        "Example of a sequence diagram",
                    ],
                ],
            },
        )

        fake_render_engine(
            svg='<svg xmlns="http://www.w3.org/2000/svg"><text x="1" y="9">ok</text></svg>'
        )

        result = arch.generate(
            input_path=str(tmp_path / "*.xlsx"),
            output_dir=str(tmp_path / "out"),
        )

        assert result["ok"] is True
        assert Path(result["files"]["solution"][0]).exists()
        assert result["summary"]["diagram_rows"] == 1
        system_page = Path(result["output_dir"]) / "solution" / "sys_core.html"
        html = system_page.read_text(encoding="utf-8")
        assert "Additional Diagrams" in html
        assert 'name="diagram-tabs"' in html
        assert 'name="additional-diagram-tabs"' in html
        assert 'data-tab-group="diagram-tabs"' in html
        assert 'data-tab-group="additional-diagram-tabs"' in html
        assert 'input[data-tab-group][data-tab-target]' in html
        assert 'aria-label="AWS Sequence Example"' in html
        assert "AWS Sequence Example" in html
        assert "<svg" in html


class TestIncrementalGeneration:
    """Incremental output reuse, stale sweep, and `force` (spec: Regenerated solution output)."""

    _SVG = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'

    def _workbook(self, build_arch_workbook: object, path: Path) -> Path:
        return build_arch_workbook(
            path,
            {
                "sys": [
                    ["id", "name"],
                    ["sys_a", "System A"],
                    ["sys_b", "System B"],
                ],
                "app": [["id", "name", "sys"], ["app_a", "App A", "sys_a"]],
                "cmp": [["id", "name", "app"]],
                "interface": [["id", "key", "name", "provider", "consumer"]],
                "usr": [["id", "name", "app"]],
            },
        )

    def _install_counting_render(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        from otdev.tools._arch import generate as arch_generate

        calls: list[str] = []

        def _fake_render(
            *, target_config: object, render_context: dict[str, object]
        ) -> tuple[bool, dict[str, object]]:
            _ = target_config
            output = str(render_context["paths"]["output"])  # type: ignore[index]
            calls.append(output)
            Path(output).write_text(self._SVG, encoding="utf-8")
            return True, {"command": "fake-render", "target": "solution", "engine": "d2"}

        monkeypatch.setattr(arch_generate, "_execute_render_engine", _fake_render)
        return calls

    def test_unchanged_rerun_skips_all_engine_renders(
        self, tmp_path: Path, build_arch_workbook: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch

        calls = self._install_counting_render(monkeypatch)
        workbook = self._workbook(build_arch_workbook, tmp_path / "arch.xlsx")
        out_dir = tmp_path / "out"

        first = arch.generate(input_path=str(workbook), output_dir=str(out_dir))
        assert first["ok"] is True
        assert first["summary"]["renders"]["executed"] > 0
        assert first["summary"]["renders"]["skipped"] == 0
        first_call_count = len(calls)

        second = arch.generate(input_path=str(workbook), output_dir=str(out_dir))
        assert second["ok"] is True
        assert second["summary"]["renders"]["executed"] == 0
        assert second["summary"]["renders"]["skipped"] == first["summary"]["renders"]["executed"]
        assert len(calls) == first_call_count

    def test_model_change_rerenders_only_affected_diagrams(
        self, tmp_path: Path, build_arch_workbook: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch

        calls = self._install_counting_render(monkeypatch)
        workbook = self._workbook(build_arch_workbook, tmp_path / "arch.xlsx")
        out_dir = tmp_path / "out"
        assert arch.generate(input_path=str(workbook), output_dir=str(out_dir))["ok"] is True
        calls.clear()

        build_arch_workbook(
            tmp_path / "arch.xlsx",
            {
                "sys": [
                    ["id", "name"],
                    ["sys_a", "System A"],
                    ["sys_b", "System B Renamed"],
                ],
                "app": [["id", "name", "sys"], ["app_a", "App A", "sys_a"]],
                "cmp": [["id", "name", "app"]],
                "interface": [["id", "key", "name", "provider", "consumer"]],
                "usr": [["id", "name", "app"]],
            },
        )
        result = arch.generate(input_path=str(workbook), output_dir=str(out_dir))

        assert result["ok"] is True
        assert result["summary"]["renders"]["executed"] == 3
        assert result["summary"]["renders"]["skipped"] == 3
        assert all("sys_b" in Path(item).name for item in calls)

    def test_stale_files_removed_after_successful_run(
        self, tmp_path: Path, build_arch_workbook: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch

        self._install_counting_render(monkeypatch)
        workbook = self._workbook(build_arch_workbook, tmp_path / "arch.xlsx")
        out_dir = tmp_path / "out"
        assert arch.generate(input_path=str(workbook), output_dir=str(out_dir))["ok"] is True

        solution_dir = out_dir / "solution"
        stale_page = solution_dir / "stale.html"
        stale_image = solution_dir / "images" / "stale.svg"
        stale_page.write_text("old", encoding="utf-8")
        stale_image.write_text("old", encoding="utf-8")

        result = arch.generate(input_path=str(workbook), output_dir=str(out_dir))

        assert result["ok"] is True
        assert not stale_page.exists()
        assert not stale_image.exists()
        assert (solution_dir / "index.html").exists()

    def test_stale_files_retained_when_run_fails(
        self, tmp_path: Path, build_arch_workbook: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch
        from otdev.tools._arch import generate as arch_generate

        self._install_counting_render(monkeypatch)
        workbook = self._workbook(build_arch_workbook, tmp_path / "arch.xlsx")
        out_dir = tmp_path / "out"
        assert arch.generate(input_path=str(workbook), output_dir=str(out_dir))["ok"] is True

        solution_dir = out_dir / "solution"
        stale_page = solution_dir / "stale.html"
        stale_page.write_text("old", encoding="utf-8")
        index_page = solution_dir / "index.html"

        def _failing_render(
            *, target_config: object, render_context: dict[str, object]
        ) -> tuple[bool, dict[str, object]]:
            _ = target_config, render_context
            return False, {
                "code": "engine_command_failed",
                "message": "boom",
                "details": {},
            }

        monkeypatch.setattr(arch_generate, "_execute_render_engine", _failing_render)
        result = arch.generate(input_path=str(workbook), output_dir=str(out_dir), force=True)

        assert result["ok"] is False
        assert stale_page.exists()
        assert index_page.exists()

    def test_force_rerenders_everything(
        self, tmp_path: Path, build_arch_workbook: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch

        calls = self._install_counting_render(monkeypatch)
        workbook = self._workbook(build_arch_workbook, tmp_path / "arch.xlsx")
        out_dir = tmp_path / "out"
        first = arch.generate(input_path=str(workbook), output_dir=str(out_dir))
        assert first["ok"] is True
        first_call_count = len(calls)

        result = arch.generate(input_path=str(workbook), output_dir=str(out_dir), force=True)

        assert result["ok"] is True
        assert result["summary"]["renders"]["executed"] == first["summary"]["renders"]["executed"]
        assert result["summary"]["renders"]["skipped"] == 0
        assert len(calls) == 2 * first_call_count

    def test_drawio_toggle_flip_forces_rerender_despite_unchanged_d2(
        self, tmp_path: Path, build_arch_workbook: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from otdev.tools import arch

        calls = self._install_counting_render(monkeypatch)
        workbook = self._workbook(build_arch_workbook, tmp_path / "arch.xlsx")
        out_dir = tmp_path / "out"

        first = arch.generate(
            input_path=str(workbook),
            output_dir=str(out_dir),
            profile_yaml="data:\n  drawio_export: true\n",
        )
        assert first["ok"] is True
        calls.clear()

        result = arch.generate(
            input_path=str(workbook),
            output_dir=str(out_dir),
            profile_yaml="data:\n  drawio_export: false\n",
        )

        assert result["ok"] is True
        assert result["summary"]["renders"]["executed"] == first["summary"]["renders"]["executed"]
        assert result["summary"]["renders"]["skipped"] == 0
        assert calls


class TestValidationWarnings:
    """Non-blocking warnings (spec: tool-arch-validation-warnings)."""

    @staticmethod
    def _entities(**overrides: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
        entities: dict[str, list[dict[str, object]]] = {
            "sys": [{"id": "sys_a", "name": "System A", "_sheet_row": 2}],
            "app": [{"id": "app_a", "name": "App A", "sys": "sys_a", "_sheet_row": 2}],
            "cmp": [],
            "interface": [],
            "usr": [],
            "project": [],
            "project_scope": [],
        }
        entities.update(overrides)
        return entities

    def test_orphan_system_flagged(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        result = validate_entities(entities=self._entities())

        assert result["valid"] is True
        codes = [item["code"] for item in result["issues"]["warnings"]]
        assert "orphan_system" in codes
        orphan = next(item for item in result["issues"]["warnings"] if item["code"] == "orphan_system")
        assert orphan["details"]["id"] == "sys_a"
        assert result["summary"]["warnings"] == len(result["issues"]["warnings"])

    def test_system_connected_via_owned_app_not_flagged(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        entities = self._entities(
            sys=[
                {"id": "sys_a", "name": "System A", "_sheet_row": 2},
                {"id": "sys_b", "name": "System B", "_sheet_row": 3},
            ],
            interface=[
                {
                    "id": "int_1",
                    "provider": "app_a",
                    "consumer": "sys_b",
                    "_sheet_row": 2,
                }
            ],
        )
        result = validate_entities(entities=entities)

        assert result["valid"] is True
        assert not any(item["code"] == "orphan_system" for item in result["issues"]["warnings"])

    def test_duplicate_name_in_same_sheet_flagged(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        entities = self._entities(
            app=[
                {"id": "app_a", "name": "Billing", "sys": "sys_a", "_sheet_row": 2},
                {"id": "app_b", "name": " billing ", "sys": "sys_a", "_sheet_row": 3},
            ],
        )
        result = validate_entities(entities=entities)

        duplicates = [item for item in result["issues"]["warnings"] if item["code"] == "duplicate_name"]
        assert len(duplicates) == 1
        assert duplicates[0]["details"]["sheet"] == "app"
        assert sorted(duplicates[0]["details"]["ids"]) == ["app_a", "app_b"]

    def test_same_name_across_sheets_not_flagged(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        entities = self._entities(
            app=[{"id": "app_a", "name": "System A", "sys": "sys_a", "_sheet_row": 2}],
        )
        result = validate_entities(entities=entities)

        assert not any(item["code"] == "duplicate_name" for item in result["issues"]["warnings"])

    def test_self_interface_flagged(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        entities = self._entities(
            interface=[
                {"id": "int_1", "provider": "app_a", "consumer": "app_a", "_sheet_row": 2}
            ],
        )
        result = validate_entities(entities=entities)

        assert result["valid"] is True
        loops = [item for item in result["issues"]["warnings"] if item["code"] == "self_interface"]
        assert len(loops) == 1
        assert loops[0]["details"]["value"] == "app_a"

    def test_warnings_alongside_errors_keep_valid_false(self) -> None:
        from otdev.tools._arch.validate import validate_entities

        entities = self._entities(
            app=[
                # Unknown system reference -> blocking error; system A stays orphaned.
                {"id": "app_a", "name": "App A", "sys": "sys_missing", "_sheet_row": 2},
            ],
        )
        result = validate_entities(entities=entities)

        assert result["valid"] is False
        assert result["issues"]["errors"]
        assert result["issues"]["warnings"]
        assert result["summary"]["errors"] == len(result["issues"]["errors"])
        assert result["summary"]["warnings"] == len(result["issues"]["warnings"])

    def test_warning_only_workbook_validates_and_generates(
        self,
        tmp_path: Path,
        build_arch_workbook: object,
        fake_render_engine: object,
    ) -> None:
        from otdev.tools import arch

        workbook = build_arch_workbook(
            tmp_path / "arch.xlsx",
            {
                "sys": [["id", "name"], ["sys_a", "System A"]],
                "app": [["id", "name", "sys"], ["app_a", "App A", "sys_a"]],
                "cmp": [["id", "name", "app"]],
                "interface": [["id", "key", "name", "provider", "consumer"]],
                "usr": [["id", "name", "app"]],
            },
        )

        validation = arch.validate(input_path=str(workbook))
        assert validation["ok"] is True
        assert validation["valid"] is True
        assert any(
            item["code"] == "orphan_system" for item in validation["issues"]["warnings"]
        )
        assert validation["summary"]["warnings"] == len(validation["issues"]["warnings"])

        result = arch.generate(input_path=str(workbook), output_dir=str(tmp_path / "out"))
        assert result["ok"] is True
        assert result["summary"]["warnings"] == validation["summary"]["warnings"]
        assert any(
            item["code"] == "orphan_system" for item in result["issues"]["warnings"]
        )
