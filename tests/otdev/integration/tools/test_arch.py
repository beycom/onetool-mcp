"""Integration tests for arch tool workflows."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.tools]

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "arch"


class TestArchRoundTrip:
    def test_export_then_import_round_trip(self, tmp_path: Path) -> None:
        from otdev.tools.arch import export_yaml, import_yaml

        yaml_path = tmp_path / "architecture.yaml"
        export_result = export_yaml(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_path=str(yaml_path),
        )
        assert export_result["ok"] is True
        assert yaml_path.exists()

        imported_path = tmp_path / "architecture-imported.xlsx"
        import_result = import_yaml(
            input_path=str(yaml_path),
            template_path=str(_FIXTURES / "architecture_template.xlsx"),
            output_path=str(imported_path),
        )
        assert import_result["ok"] is True
        assert imported_path.exists()
        assert import_result["validation"]["valid"] is True

    def test_round_trip_preserves_extension_fields(self, tmp_path: Path) -> None:
        from otdev.tools.arch import export_yaml, import_yaml

        openpyxl = pytest.importorskip("openpyxl")

        source = tmp_path / "source.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "sys"
        ws.append(["id", "name", "owner"])
        ws.append(["sys_a", "System A", "platform-team"])
        for sheet in ("app", "cmp", "int", "usr"):
            extra = wb.create_sheet(sheet)
            if sheet == "int":
                extra.append(["id", "src", "dst"])
                extra.append([f"{sheet}_1", "sys_a", "sys_a"])
            elif sheet == "app":
                extra.append(["id", "name", "sys"])
                extra.append(["app_a", "App A", "sys_a"])
            elif sheet == "cmp":
                extra.append(["id", "name", "app"])
                extra.append(["cmp_a", "Cmp A", "app_a"])
            else:
                extra.append(["id", "name", "app"])
                extra.append(["usr_a", "User A", "app_a"])
        wb.save(source)
        wb.close()

        yaml_path = tmp_path / "architecture.yaml"
        exported = export_yaml(input_path=str(source), output_path=str(yaml_path))
        assert exported["ok"] is True
        first_payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert first_payload["sys"][0]["owner"] == "platform-team"

        imported_path = tmp_path / "imported.xlsx"
        imported = import_yaml(
            input_path=str(yaml_path),
            template_path=str(source),
            output_path=str(imported_path),
        )
        assert imported["ok"] is True

        yaml_roundtrip = tmp_path / "roundtrip.yaml"
        exported_roundtrip = export_yaml(input_path=str(imported_path), output_path=str(yaml_roundtrip))
        assert exported_roundtrip["ok"] is True
        second_payload = yaml.safe_load(yaml_roundtrip.read_text(encoding="utf-8"))
        assert second_payload["sys"][0]["owner"] == "platform-team"


class TestArchDiagramSheet:
    def test_generates_workbook_diagram_and_embeds_it_in_system_page(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from otdev.tools import arch

        openpyxl = pytest.importorskip("openpyxl")

        core_wb = openpyxl.Workbook()
        sys_ws = core_wb.active
        sys_ws.title = "sys"
        sys_ws.append(["id", "name"])
        sys_ws.append(["sys_core", "Core"])

        app_ws = core_wb.create_sheet("app")
        app_ws.append(["id", "name", "sys"])
        app_ws.append(["app_core", "App Core", "sys_core"])

        cmp_ws = core_wb.create_sheet("cmp")
        cmp_ws.append(["id", "name", "app"])
        cmp_ws.append(["cmp_core", "Cmp Core", "app_core"])

        int_ws = core_wb.create_sheet("int")
        int_ws.append(["id", "src", "dst", "name"])
        int_ws.append(["int_1", "app_core", "cmp_core", "calls"])

        usr_ws = core_wb.create_sheet("usr")
        usr_ws.append(["id", "name", "app"])
        usr_ws.append(["usr_a", "User A", "app_core"])

        core_path = tmp_path / "core.xlsx"
        core_wb.save(core_path)
        core_wb.close()

        diagram_dir = tmp_path / "seq"
        diagram_dir.mkdir(parents=True, exist_ok=True)
        (diagram_dir / "seq_aws.d2").write_text(
            'title: "AWS Sequence Example"\na -> b: "request"\n',
            encoding="utf-8",
        )

        diagram_wb = openpyxl.Workbook()
        diagram_ws = diagram_wb.active
        diagram_ws.title = "diagram"
        diagram_ws.append(["file", "name", "sys", "description"])
        diagram_ws.append(
            [
                "seq/seq_aws.d2",
                "AWS Sequence Example",
                "sys_core",
                "Example of a sequence diagram",
            ]
        )
        diagram_path = tmp_path / "diagrams.xlsx"
        diagram_wb.save(diagram_path)
        diagram_wb.close()

        def _fake_render(*, target_config: object, render_context: dict[str, object]) -> tuple[bool, dict[str, object]]:
            _ = target_config
            Path(str(render_context["paths"]["output"])).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><text x="1" y="9">ok</text></svg>',
                encoding="utf-8",
            )
            return True, {"command": "fake-render", "target": "diagram", "engine": "d2"}

        monkeypatch.setattr(arch, "_execute_render_engine", _fake_render)
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


class TestArchSolutionBundle:
    def test_bundle_solution_inlines_svg_and_zips(self, tmp_path: Path) -> None:
        from otdev.tools.arch import bundle_solution

        solution_dir = tmp_path / "solution"
        solution_dir.mkdir()
        (solution_dir / "diagram.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>',
            encoding="utf-8",
        )
        html_path = solution_dir / "index.html"
        html_path.write_text('<html><body><img src="diagram.svg" /></body></html>', encoding="utf-8")

        result = bundle_solution(directory=str(solution_dir))

        assert result["ok"] is True
        assert Path(result["bundle_path"]).exists()
        assert result["inlined_svgs"] == 1
        assert "data-inlined-svg" in html_path.read_text(encoding="utf-8")

    def test_bundle_solution_includes_additional_files(self, tmp_path: Path) -> None:
        from otdev.tools.arch import bundle_solution

        solution_dir = tmp_path / "solution"
        solution_dir.mkdir()
        (solution_dir / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
        extra = tmp_path / "extra.txt"
        extra.write_text("extra", encoding="utf-8")

        result = bundle_solution(directory=str(solution_dir), include=str(extra))

        assert result["ok"] is True
        bundle_path = Path(result["bundle_path"])
        assert bundle_path.exists()
        with zipfile.ZipFile(bundle_path, "r") as zf:
            assert "data/extra.txt" in zf.namelist()
