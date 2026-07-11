"""Integration tests for arch tool workflows."""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.otdev.conftest import ARCH_FIXTURES

pytestmark = [pytest.mark.integration, pytest.mark.tools]

_FIXTURES = ARCH_FIXTURES

_D2_MISSING = shutil.which("d2") is None
_requires_d2 = pytest.mark.skipif(_D2_MISSING, reason="d2 CLI not installed on PATH")


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

    def test_round_trip_preserves_extension_fields(
        self, tmp_path: Path, build_arch_workbook: object
    ) -> None:
        from otdev.tools.arch import export_yaml, import_yaml

        source = build_arch_workbook(
            tmp_path / "source.xlsx",
            {
                "sys": [["id", "name", "owner"], ["sys_a", "System A", "platform-team"]],
                "app": [["id", "name", "sys"], ["app_a", "App A", "sys_a"]],
                "cmp": [["id", "name", "app"], ["cmp_a", "Cmp A", "app_a"]],
                "interface": [["id", "provider", "consumer"], ["interface_1", "sys_a", "sys_a"]],
                "usr": [["id", "name", "app"], ["usr_a", "User A", "app_a"]],
            },
        )

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

    def test_round_trip_preserves_list_fields_and_passthrough_sheets(
        self, tmp_path: Path, build_arch_workbook: object
    ) -> None:
        from otdev.tools.arch import export_yaml, import_yaml

        openpyxl = pytest.importorskip("openpyxl")

        # Source workbook: a list-valued tags column + a non-canonical "notes" sheet.
        source = build_arch_workbook(
            tmp_path / "source.xlsx",
            {
                "sys": [["id", "name", "tags"], ["sys_a", "System A", "[core;internal]"]],
                "app": [["id", "name", "sys"], ["app_a", "App A", "sys_a"]],
                "cmp": [["id", "name", "app"], ["cmp_a", "Cmp A", "app_a"]],
                "interface": [["id", "provider", "consumer"], ["i1", "sys_a", "sys_a"]],
                "usr": [["id", "name"]],
                "notes": [["topic", "detail"], ["migration", "phase 1"]],
            },
        )

        # Excel -> YAML
        yaml1 = tmp_path / "model.yaml"
        assert export_yaml(input_path=str(source), output_path=str(yaml1))["ok"] is True
        payload1 = yaml.safe_load(yaml1.read_text(encoding="utf-8"))
        assert payload1["sys"][0]["tags"] == ["core", "internal"]  # native YAML list
        assert payload1["_passthrough"]["notes"]["headers"] == ["topic", "detail"]
        assert payload1["_passthrough"]["notes"]["rows"] == [["migration", "phase 1"]]

        # YAML -> Excel (template = original source, which has all needed columns/sheets)
        rebuilt = tmp_path / "rebuilt.xlsx"
        import_result = import_yaml(
            input_path=str(yaml1),
            template_path=str(source),
            output_path=str(rebuilt),
        )
        assert import_result["ok"] is True

        # The rebuilt workbook cell holds the bracketed encoding, and notes survived.
        wb2 = openpyxl.load_workbook(rebuilt)
        assert wb2["sys"]["C2"].value == "[core;internal]"
        assert "notes" in wb2.sheetnames
        assert [c.value for c in wb2["notes"][2]] == ["migration", "phase 1"]
        wb2.close()

        # Excel -> YAML again: must equal the first YAML (value-stable round-trip).
        yaml2 = tmp_path / "model2.yaml"
        assert export_yaml(input_path=str(rebuilt), output_path=str(yaml2))["ok"] is True
        payload2 = yaml.safe_load(yaml2.read_text(encoding="utf-8"))
        assert payload2 == payload1



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


class TestArchRenderNav:
    """arch-render-nav (Phase 8): change-type styling, interaction-type
    styling, clickable nodes, cross-page navigation, legend, and index
    summary/tables — rendered end-to-end with the real ``d2`` CLI.

    Guarded on ``d2`` availability (``_requires_d2``), matching how the rest
    of this suite treats other optional external binaries/services.
    """

    @_requires_d2
    def test_T1_fixture_solution_renders_class_arrays_links_and_nav(self, tmp_path: Path) -> None:
        from otdev.tools._arch.render_styles import CHANGE_TYPE_STYLES
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path / "out"),
        )
        assert result["ok"] is True, result

        solution_dir = Path(result["output_dir"]) / "solution"
        images_dir = solution_dir / "images"

        # (a) emitted .d2 sources contain class arrays AND link: attributes.
        system_d2 = (images_dir / "sys_core-sys.d2").read_text(encoding="utf-8")
        assert "class: [" in system_d2  # e.g. class: [InterfaceToFocus; IntBatch]
        assert 'link: "./' in system_d2

        project_current_d2 = (images_dir / "project-wallet-current.d2").read_text(encoding="utf-8")
        project_target_d2 = (images_dir / "project-wallet-target.d2").read_text(encoding="utf-8")
        assert 'link: "./' in project_current_d2
        # Node change-class array (app_api scoped 'new' in stage 'current').
        assert "class: [App; ChangeNew]" in project_current_d2
        # Edge direction + interaction + change class array.
        assert "class: [Interface; IntBatch; ChangeDependency]" in project_current_d2
        # Node change-class array in a different stage (sys_core scoped 'impacted' in 'target').
        assert "class: [System; ChangeImpacted]" in project_target_d2
        assert "class: [Interface; ChangeChanged]" in project_target_d2

        # (b) a system SVG contains <a hrefs to system pages.
        system_svg = (images_dir / "sys_core-sys.svg").read_text(encoding="utf-8")
        assert '<a href="./sys_core.html"' in system_svg
        assert '<a href="./sys_legacy.html"' in system_svg

        # (c) a project stage SVG reflects a change-class style: the
        # ChangeImpacted stroke color (from render_styles.py, the same source
        # the legend/badges read) is present in the rendered target-stage SVG.
        project_target_svg = (images_dir / "project-wallet-target.svg").read_text(encoding="utf-8")
        assert CHANGE_TYPE_STYLES["impacted"]["color"] in project_target_svg

        # (d) index.html contains summary cards AND five entity-table sections.
        index_html = (solution_dir / "index.html").read_text(encoding="utf-8")
        assert "stats stats-vertical" in index_html
        for key in ("systems", "applications", "components", "interfaces", "projects"):
            assert f'data-collapse="{key}-index-content"' in index_html

        # (e) system and project pages contain the index back-link AND the legend.
        system_html = (solution_dir / "sys_core.html").read_text(encoding="utf-8")
        project_html = (solution_dir / "project-wallet.html").read_text(encoding="utf-8")
        for page_html in (system_html, project_html):
            assert "Solution Index" in page_html
            assert 'id="legend-content"' in page_html

    @_requires_d2
    def test_neutral_model_has_no_class_arrays_or_change_int_classes(self, tmp_path: Path) -> None:
        """D3 fallback: a model with no projects, no interaction_type values,
        and no scope rows must emit scalar-only D2 classes — proves the
        byte-identical-diagram fallback (design D2/D3)."""
        from otdev.tools._arch.render_styles import CHANGE_TYPE_STYLES, INTERACTION_TYPE_STYLES
        from otdev.tools.arch import generate

        neutral_model = {
            "sys": [
                {"id": "sys_a", "name": "System A"},
                {"id": "sys_b", "name": "System B"},
            ],
            "app": [],
            "cmp": [],
            "interface": [
                {"id": "iface_1", "name": "A to B", "provider": "sys_a", "consumer": "sys_b"},
            ],
            "usr": [],
            "project": [],
            "project_scope": [],
            "diagram": [],
        }
        yaml_path = tmp_path / "neutral.yaml"
        yaml_path.write_text(yaml.safe_dump(neutral_model, sort_keys=False), encoding="utf-8")

        result = generate(input_path=str(yaml_path), output_dir=str(tmp_path / "out"))
        assert result["ok"] is True, result

        images_dir = Path(result["output_dir"]) / "solution" / "images"
        d2_files = sorted(images_dir.glob("*.d2"))
        assert d2_files, "expected at least one rendered .d2 source for the neutral model"

        change_and_interaction_classes = [style["d2_class"] for style in CHANGE_TYPE_STYLES.values()] + [
            style["d2_class"] for style in INTERACTION_TYPE_STYLES.values()
        ]
        for d2_path in d2_files:
            text = d2_path.read_text(encoding="utf-8")
            # Only inspect class *usage* lines (`class: X`, `class: [A; B]`) —
            # the static `styles.d2` include always defines the Change*/Int*
            # classes regardless of whether a diagram uses them, so scanning
            # the whole file would false-positive on the (unused) definitions.
            class_usage_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("class:")]
            assert class_usage_lines, f"expected at least one class assignment in {d2_path.name}"
            for line in class_usage_lines:
                assert "[" not in line, f"unexpected class array in {d2_path.name}: {line!r}"
                for class_name in change_and_interaction_classes:
                    assert class_name not in line, f"{class_name} leaked into {d2_path.name}: {line!r}"


class _FixtureModel:
    """Pure-data reimplementation of the diagram-view vertex-counting rules,
    built from the raw fixture rows (``architecture.yaml``, which mirrors
    ``architecture.xlsx``) with no imports from ``otdev.tools._arch`` -- so
    comparing these counts against the models embedded in the rendered SVGs
    cross-checks two independent computations rather than asserting
    ``drawio.build_mxfile`` against its own inputs.

    Rules mirrored (default profile):

    - system view: the focus system expands to the requested level; related
      internal systems render as placeholder blocks (default
      ``secondary_system_detail="sys"``); interface endpoints owned by
      unknown or external systems become external nodes; users attached to
      the focus system's apps become user nodes.
    - project view: scope rows pull in systems/apps/components/users;
      explicitly scoped systems expand fully, other systems only down to
      their scoped members; ``detail_level``/``connect_level`` come from the
      project row (default ``app``).
    """

    _LEVEL_RANK = {"sys": 0, "app": 1, "cmp": 2}

    def __init__(self, entities: dict[str, list[dict[str, Any]]]) -> None:
        self.entities = entities
        self.sys_rows = {str(row["id"]): row for row in entities["sys"]}
        self.app_to_sys: dict[str, str] = {}
        self.apps_by_sys: dict[str, list[str]] = {}
        for row in entities["app"]:
            app_id = str(row["id"])
            sys_id = str(row.get("sys") or row.get("system") or "")
            self.app_to_sys[app_id] = sys_id
            self.apps_by_sys.setdefault(sys_id, []).append(app_id)
        self.cmp_to_app: dict[str, str] = {}
        self.cmp_to_sys: dict[str, str] = {}
        self.cmps_by_app: dict[str, list[str]] = {}
        self.direct_cmps_by_sys: dict[str, list[str]] = {}
        for row in entities["cmp"]:
            cmp_id = str(row["id"])
            app_id = str(row.get("app") or row.get("application") or "")
            if app_id:
                self.cmp_to_app[cmp_id] = app_id
                self.cmp_to_sys[cmp_id] = self.app_to_sys.get(app_id, "")
                self.cmps_by_app.setdefault(app_id, []).append(cmp_id)
            else:
                sys_id = str(row.get("sys") or row.get("system") or "")
                self.cmp_to_sys[cmp_id] = sys_id
                self.direct_cmps_by_sys.setdefault(sys_id, []).append(cmp_id)
        self.usr_app: dict[str, str] = {}
        for row in entities["usr"]:
            self.usr_app[str(row["id"])] = str(row.get("app") or row.get("application") or "")

    def is_external(self, sys_id: str) -> bool:
        row = self.sys_rows.get(sys_id)
        if row is None:
            return True
        sys_type = str(row.get("system_type") or row.get("type") or "").strip().lower()
        return sys_type == "external"

    def internal_system_ids(self) -> list[str]:
        return [sys_id for sys_id in self.sys_rows if not self.is_external(sys_id)]

    def _owner_sys(self, endpoint: str) -> str:
        """Owning system of an interface endpoint; unknown ids count as
        external system ids (same rule the pipeline applies)."""
        if endpoint in self.sys_rows:
            return endpoint
        if endpoint in self.app_to_sys:
            return self.app_to_sys[endpoint]
        if endpoint in self.cmp_to_sys:
            return self.cmp_to_sys[endpoint]
        if endpoint in self.usr_app:
            return self.app_to_sys.get(self.usr_app[endpoint], "")
        return endpoint

    def _block_vertex_count(
        self,
        sys_id: str,
        level: str,
        *,
        app_ids: set[str] | None = None,
        cmp_ids: set[str] | None = None,
    ) -> int:
        """Vertices one system block contributes to the embedded model: the
        system box itself, plus its apps (level app/cmp) and its components
        (level cmp), optionally restricted to the given app/cmp id sets."""
        if level == "sys":
            return 1
        apps = self.apps_by_sys.get(sys_id, [])
        if app_ids is not None:
            apps = [app_id for app_id in apps if app_id in app_ids]
        count = 1 + len(apps)
        if level == "cmp":
            direct = self.direct_cmps_by_sys.get(sys_id, [])
            if cmp_ids is not None:
                direct = [cmp_id for cmp_id in direct if cmp_id in cmp_ids]
            count += len(direct)
            for app_id in apps:
                members = self.cmps_by_app.get(app_id, [])
                if cmp_ids is not None:
                    members = [cmp_id for cmp_id in members if cmp_id in cmp_ids]
                count += len(members)
        return count

    def expected_system_view_vertices(self, focus: str, level: str) -> int:
        related: set[str] = set()
        external: set[str] = set()
        for row in self.entities["interface"]:
            provider = str(row.get("provider") or "")
            consumer = str(row.get("consumer") or "")
            if not provider or not consumer:
                continue
            owners = {self._owner_sys(provider), self._owner_sys(consumer)}
            if focus not in owners:
                continue
            for owner in owners - {focus, ""}:
                if owner in self.sys_rows and not self.is_external(owner):
                    related.add(owner)
                else:
                    external.add(owner)
        user_count = sum(
            1
            for app_ref in self.usr_app.values()
            if app_ref == focus or self.app_to_sys.get(app_ref) == focus
        )
        count = user_count + len(external)
        count += self._block_vertex_count(focus, level)
        count += len(related)  # secondary systems render as placeholder blocks
        return count

    def project_stages(self, project_id: str) -> list[str]:
        stages: dict[str, None] = {}
        for row in self.entities["project_scope"]:
            if str(row.get("project") or "") != project_id:
                continue
            stage = str(row.get("stage") or "").strip()
            if stage:
                stages[stage] = None
        return list(stages)

    def expected_project_view_vertices(self, project_id: str, stage: str) -> int:
        project = next(
            row for row in self.entities["project"] if str(row["id"]) == project_id
        )
        detail = str(project.get("detail_level") or "app").strip().lower() or "app"
        connect = str(project.get("connect_level") or "app").strip().lower() or "app"
        connect_rank = (
            self._LEVEL_RANK[detail]
            if connect == "lowest_visible"
            else self._LEVEL_RANK[connect]
        )

        systems: set[str] = set()
        explicit_systems: set[str] = set()
        apps: set[str] = set()
        cmps: set[str] = set()
        users: set[str] = set()

        def add_endpoint(endpoint: str) -> None:
            if endpoint in self.usr_app:
                users.add(endpoint)
            elif endpoint in self.sys_rows:
                systems.add(endpoint)
            elif endpoint in self.app_to_sys:
                systems.add(self.app_to_sys[endpoint])
                if connect_rank >= self._LEVEL_RANK["app"]:
                    apps.add(endpoint)
            elif endpoint in self.cmp_to_sys:
                if self.cmp_to_sys[endpoint]:
                    systems.add(self.cmp_to_sys[endpoint])
                cmp_app = self.cmp_to_app.get(endpoint)
                if cmp_app and connect_rank >= self._LEVEL_RANK["app"]:
                    apps.add(cmp_app)
                if connect_rank >= self._LEVEL_RANK["cmp"]:
                    cmps.add(endpoint)
            elif endpoint:
                systems.add(endpoint)  # unknown id -> external node

        for row in self.entities["project_scope"]:
            if (
                str(row.get("project") or "") != project_id
                or str(row.get("stage") or "").strip() != stage
            ):
                continue
            item_type = str(row.get("item_type") or "").strip().lower()
            item_id = str(row.get("item_id") or "").strip()
            if not item_id:
                continue
            if item_type == "system":
                systems.add(item_id)
                explicit_systems.add(item_id)
            elif item_type == "application":
                apps.add(item_id)
                if self.app_to_sys.get(item_id):
                    systems.add(self.app_to_sys[item_id])
            elif item_type == "component":
                cmps.add(item_id)
                if self.cmp_to_sys.get(item_id):
                    systems.add(self.cmp_to_sys[item_id])
                if self.cmp_to_app.get(item_id):
                    apps.add(self.cmp_to_app[item_id])
            elif item_type == "interface":
                iface = next(
                    (
                        candidate
                        for candidate in self.entities["interface"]
                        if str(candidate.get("id") or "") == item_id
                    ),
                    None,
                )
                if iface is not None:
                    add_endpoint(str(iface.get("provider") or ""))
                    add_endpoint(str(iface.get("consumer") or ""))

        count = len(users)
        for sys_id in systems:
            if sys_id not in self.sys_rows or self.is_external(sys_id):
                count += 1  # rendered as an external node
            elif sys_id in explicit_systems:
                count += self._block_vertex_count(sys_id, detail)
            else:
                count += self._block_vertex_count(sys_id, detail, app_ids=apps, cmp_ids=cmps)
        return count


class TestArchDrawioExport:
    """arch-drawio-editable-svg (Phase C): every generated system/project
    diagram SVG doubles as an editable draw.io file (embedded ``mxfile``
    model in the SVG's ``content`` attribute, design D1-D5); inlined HTML
    markup and workbook diagrams never carry it (D9); the ``drawio_export``
    profile toggle disables the whole feature (D10); the base64-class SVG
    convention the geometry extractor depends on is pinned against the
    installed ``d2`` (D6/D7).

    Guarded on ``d2`` availability (``_requires_d2``), matching
    ``TestArchRenderNav``.
    """

    @staticmethod
    def _safe_fragment(value: str) -> str:
        """Local copy of the output-filename sanitizer (keep alnum plus
        ``._-``, replace the rest with ``_``) so stage names map to SVG
        filenames without importing arch internals."""
        cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value.strip())
        return cleaned.strip("._-") or "item"

    @staticmethod
    def _embedded_mxfile(svg_path: Path) -> ET.Element | None:
        """Parse the root `<svg>` element on disk and return its decoded
        `content` attribute reparsed as XML (`None` if the attribute is
        absent). `ET.fromstring` performs the XML-unescape as part of
        attribute parsing, matching the round-trip pattern already used by
        the Phase A unit tests (`test_inject_content_round_trip`)."""
        root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
        content = root.get("content")
        if content is None:
            return None
        return ET.fromstring(content)

    @_requires_d2
    def test_4_5_system_and_project_svgs_carry_well_formed_models_matching_node_counts(
        self, tmp_path: Path
    ) -> None:
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path / "out"),
        )
        assert result["ok"] is True, result

        solution_dir = Path(result["output_dir"]) / "solution"
        images_dir = solution_dir / "images"

        # Expected vertex counts are derived from the raw fixture rows
        # (architecture.yaml, the YAML mirror of architecture.xlsx) by a
        # pure-data reimplementation of the view-inclusion rules
        # (`_FixtureModel`), independent of the arch pipeline internals.
        model = _FixtureModel(
            yaml.safe_load((_FIXTURES / "architecture.yaml").read_text(encoding="utf-8"))
        )

        system_ids = model.internal_system_ids()
        assert system_ids, "fixture must define at least one system"

        for system_id in system_ids:
            for level in ("sys", "app", "cmp"):
                svg_path = images_dir / f"{system_id}-{level}.svg"
                assert svg_path.exists(), svg_path
                mxfile = self._embedded_mxfile(svg_path)
                assert mxfile is not None, f"{svg_path} missing embedded model"
                assert mxfile.tag == "mxfile"
                assert mxfile.get("host") == "onetool-arch"
                assert len(mxfile.findall("diagram")) == 1
                vertices = mxfile.findall('.//mxCell[@vertex="1"]')
                expected = model.expected_system_view_vertices(system_id, level)
                assert len(vertices) == expected, (str(svg_path), len(vertices), expected)

        project_ids = [str(row["id"]).strip() for row in model.entities.get("project", [])]
        assert project_ids, "fixture must define at least one project"

        for project_id in project_ids:
            for stage in model.project_stages(project_id):
                svg_path = images_dir / f"project-{project_id}-{self._safe_fragment(stage)}.svg"
                assert svg_path.exists(), svg_path
                mxfile = self._embedded_mxfile(svg_path)
                assert mxfile is not None, f"{svg_path} missing embedded model"
                vertices = mxfile.findall('.//mxCell[@vertex="1"]')
                expected = model.expected_project_view_vertices(project_id, stage)
                assert len(vertices) == expected, (str(svg_path), len(vertices), expected)

        # (c) generated HTML never carries the embedded model (strip invariant, D9).
        html_files = sorted(solution_dir.glob("*.html"))
        assert html_files
        for html_path in html_files:
            assert 'content="&lt;mxfile' not in html_path.read_text(encoding="utf-8")

        # (d) export anchors present with `.drawio.svg` download names (D8).
        system_html = (solution_dir / "sys_core.html").read_text(encoding="utf-8")
        for level in ("sys", "app", "cmp"):
            assert (
                f'<a href="images/sys_core-{level}.svg" '
                f'download="sys_core-{level}.drawio.svg" '
                'class="btn btn-xs btn-outline">Export to draw.io</a>' in system_html
            )

        project_html = (solution_dir / "project-wallet.html").read_text(encoding="utf-8")
        for stage in model.project_stages("wallet"):
            safe_stage = self._safe_fragment(stage)
            assert (
                f'<a href="images/project-wallet-{safe_stage}.svg" '
                f'download="project-wallet-{safe_stage}.drawio.svg" '
                'class="btn btn-xs btn-outline">Export to draw.io</a>' in project_html
            )

    @_requires_d2
    def test_4_5_workbook_diagram_svg_has_no_embedded_model(
        self, tmp_path: Path, build_arch_workbook: object
    ) -> None:
        """`architecture.xlsx`'s `diagram` sheet is empty (no workbook-defined
        diagrams in that fixture), so this scenario is built from a minimal
        synthetic workbook + a trivial `.d2` diagram file -- same shape as
        `TestArchDiagramSheet.test_generates_workbook_diagram_and_embeds_it_in_system_page`
        (now in the unit suite) -- but rendered with the real `d2` CLI (no
        `_execute_render_engine` mock), to prove workbook diagrams never
        receive an embedded model on the real rendering path, not just in a
        mocked unit test."""
        from otdev.tools.arch import generate

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

        result = generate(
            input_path=str(tmp_path / "*.xlsx"),
            output_dir=str(tmp_path / "out"),
        )
        assert result["ok"] is True, result

        images_dir = Path(result["output_dir"]) / "solution" / "images"
        workbook_svg = images_dir / "sys_core-01-seq_aws.svg"
        assert workbook_svg.exists(), sorted(p.name for p in images_dir.glob("*.svg"))
        assert self._embedded_mxfile(workbook_svg) is None

        # Contrast: the primary system-level diagram for the same system
        # (rendered from canonical-model structure) DOES carry one.
        system_svg = images_dir / "sys_core-sys.svg"
        assert self._embedded_mxfile(system_svg) is not None

    @_requires_d2
    def test_4_6_drawio_export_false_disables_content_and_export_anchors(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        result = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(tmp_path / "out"),
            profile_yaml="data:\n  drawio_export: false\n",
        )
        assert result["ok"] is True, result

        solution_dir = Path(result["output_dir"]) / "solution"
        images_dir = solution_dir / "images"

        svg_files = sorted(images_dir.glob("*.svg"))
        assert svg_files
        for svg_path in svg_files:
            assert self._embedded_mxfile(svg_path) is None, svg_path

        html_files = sorted(solution_dir.glob("*.html"))
        assert html_files
        for html_path in html_files:
            html = html_path.read_text(encoding="utf-8")
            assert "Export to draw.io" not in html
            assert 'content="&lt;mxfile' not in html

    @_requires_d2
    def test_4_7_geometry_extraction_convention_canary(self, tmp_path: Path) -> None:
        """Canary (design D6/D7): renders a minimal diagram with the
        installed `d2`, including a `./`-prefixed `link:`-carrying node, and
        asserts `extract_geometry`'s base64-class convention and
        `<a href>`-wrapper tolerance still hold. This must fail loudly if a
        future `d2` upgrade changes its SVG metadata encoding -- the whole
        point of exercising the real CLI here instead of only the checked-in
        unit-test SVG snippet (`TestDrawioEmitter._SAMPLE_SVG`)."""
        from otdev.tools._arch.drawio import extract_geometry

        d2_path = tmp_path / "canary.d2"
        svg_path = tmp_path / "canary.svg"
        d2_path.write_text(
            'sys_a: "System A" {\n'
            '  link: "./sys_a.html"\n'
            "}\n"
            'sys_b: "System B"\n'
            'sys_a -> sys_b: "calls"\n',
            encoding="utf-8",
        )

        # Same invocation shape as the default `system_engine` command
        # template (`d2 {{ input }} {{ output }} --layout elk`).
        process = subprocess.run(
            ["d2", str(d2_path), str(svg_path), "--layout", "elk"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert process.returncode == 0, process.stderr

        svg_text = svg_path.read_text(encoding="utf-8")

        # The linked node must actually be wrapped in an `<a href>` (design
        # D6) -- assert the wrapper is present so the tolerance exercised
        # below is proven, not just vacuously true because it never occurred.
        assert '<a href="./sys_a.html"' in svg_text

        geometry = extract_geometry(svg_text)

        assert set(geometry) == {"sys_a", "sys_b"}
        for path_id in ("sys_a", "sys_b"):
            _x, _y, w, h = geometry[path_id]
            assert w > 0
            assert h > 0


class TestArchIncrementalGeneration:
    @_requires_d2
    def test_second_run_skips_renders_and_matches_forced_run(self, tmp_path: Path) -> None:
        from otdev.tools.arch import generate

        def _snapshot(root: Path) -> dict[str, str]:
            # HTML pages embed generated_at timestamps; compare the stable
            # artifacts (d2 sources + svgs) by content and pages by presence.
            snapshot: dict[str, str] = {}
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(root))
                if path.suffix in {".d2", ".svg"}:
                    snapshot[rel] = path.read_text(encoding="utf-8")
                else:
                    snapshot[rel] = "<present>"
            return snapshot

        out_dir = tmp_path / "out"
        first = generate(input_path=str(_FIXTURES / "architecture.xlsx"), output_dir=str(out_dir))
        assert first["ok"] is True
        assert first["summary"]["renders"]["executed"] > 0

        second = generate(input_path=str(_FIXTURES / "architecture.xlsx"), output_dir=str(out_dir))
        assert second["ok"] is True
        assert second["summary"]["renders"]["executed"] == 0
        assert second["summary"]["renders"]["skipped"] == first["summary"]["renders"]["executed"]
        incremental_snapshot = _snapshot(out_dir / "solution")

        forced_dir = tmp_path / "forced"
        forced = generate(
            input_path=str(_FIXTURES / "architecture.xlsx"),
            output_dir=str(forced_dir),
            force=True,
        )
        assert forced["ok"] is True
        assert forced["summary"]["renders"]["skipped"] == 0
        forced_snapshot = _snapshot(forced_dir / "solution")

        assert incremental_snapshot.keys() == forced_snapshot.keys()
        for rel, content in incremental_snapshot.items():
            if rel.endswith(".d2"):
                assert content == forced_snapshot[rel], rel
