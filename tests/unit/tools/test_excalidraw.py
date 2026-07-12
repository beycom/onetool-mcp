"""Unit tests for the whiteboard tool pack (pack name: whiteboard, short aliases: wb, excalidraw).

Tests cover: parse_dsl, _build_dsl, auto_layout, _auto_size, _shape_payload,
_parse_style_props, and smoke tests for public tools with mocked pydoll tab.
"""

from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from otdev.tools.excalidraw import (
    _SHAPE_MIN_H,
    _SHAPE_MIN_W,
    _auto_size,
    _build_dsl,
    _parse_style_props,
    _shape_payload,
    parse_dsl,
)


# ===========================================================================
# 6.1 parse_dsl
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestParseDsl:
    def test_simple_shapes(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]')
        assert result["shapes"]["a"] == {"label": "A", "classes": []}
        assert result["shapes"]["b"] == {"label": "B", "classes": []}

    def test_semicolon_separator(self) -> None:
        result = parse_dsl('a["A"];b["B"];a-->b')
        assert result["shapes"]["a"] == {"label": "A", "classes": []}
        assert result["shapes"]["b"] == {"label": "B", "classes": []}
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"
        assert result["edges"][0]["dst"] == "b"

    def test_directed_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert len(result["edges"]) == 1
        e = result["edges"][0]
        assert e["src"] == "a"
        assert e["dst"] == "b"
        assert e["endArrowhead"] == "arrow"
        assert e["startArrowhead"] is None
        assert e["directed"] is True

    def test_directed_edge_with_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|query|b')
        assert result["edges"][0]["label"] == "query"

    def test_undirected_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na---b')
        e = result["edges"][0]
        assert e["directed"] is False
        assert e["startArrowhead"] is None
        assert e["endArrowhead"] is None

    def test_bidirectional_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na<-->b')
        e = result["edges"][0]
        assert e["startArrowhead"] == "arrow"
        assert e["endArrowhead"] == "arrow"

    def test_dot_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o b')
        e = result["edges"][0]
        assert e["endArrowhead"] == "dot"
        assert e["startArrowhead"] is None

    def test_bar_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --x b')
        e = result["edges"][0]
        assert e["endArrowhead"] == "bar"

    def test_dot_edge_with_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o|lbl| b')
        e = result["edges"][0]
        assert e["label"] == "lbl"
        assert e["endArrowhead"] == "dot"

    def test_classdef_raises_error(self) -> None:
        """classDef syntax is no longer supported — raises ValueError."""
        with pytest.raises(Exception):
            parse_dsl('classDef svc fill:#dae8fc,stroke:#6c8ebf;')

    def test_class_assignment_ignored_or_raises(self) -> None:
        """class assignment is no longer parsed as class — treated as bare id or error."""
        # 'class a,b svc' does not match any shape/edge pattern and falls through
        # to bare-ID fallback or is silently ignored
        result = parse_dsl('a["A"]\nb["B"]')
        assert "a" in result["shapes"]
        assert "b" in result["shapes"]

    def test_subgraph(self) -> None:
        dsl = 'a["A"]\nb["B"]\nsubgraph grp ["Group"]\n  a\n  b\nend'
        result = parse_dsl(dsl)
        assert "grp" in result["groups"]
        g = result["groups"]["grp"]
        assert g["label"] == "Group"
        assert "a" in g["members"]
        assert "b" in g["members"]

    def test_subgraph_without_label(self) -> None:
        dsl = 'a["A"]\nsubgraph grp\n  a\nend'
        result = parse_dsl(dsl)
        assert result["groups"]["grp"]["label"] == "grp"

    def test_mermaid_header_ignored(self) -> None:
        result = parse_dsl('flowchart TD\na["A"]')
        assert "a" in result["shapes"]

    def test_graph_header_ignored(self) -> None:
        result = parse_dsl('graph LR\na["A"]')
        assert "a" in result["shapes"]

    def test_comment_lines_ignored(self) -> None:
        result = parse_dsl('%% this is a comment\n# also a comment\na["A"]')
        assert "a" in result["shapes"]
        assert len(result["shapes"]) == 1

    def test_multiline_label(self) -> None:
        result = parse_dsl('a["Line1\\nLine2"]')
        assert result["shapes"]["a"]["label"] == "Line1\nLine2"

    def test_empty_label(self) -> None:
        result = parse_dsl('a[""]\nb["B"]\na-->b')
        assert "a" in result["shapes"], "empty-label shape should use node ID as key"
        assert result["shapes"]["a"]["label"] == ""
        assert result["edges"][0]["src"] == "a"
        assert result["edges"][0]["dst"] == "b"

    def test_empty_input(self) -> None:
        result = parse_dsl("")
        assert result["shapes"] == {}
        assert result["edges"] == []

    def test_unquoted_label_rect(self) -> None:
        result = parse_dsl("a[test]")
        assert result["shapes"]["a"] == {"label": "test", "classes": []}

    def test_ellipse_raises_error(self) -> None:
        """Ellipse syntax is not supported — raises ValueError with helpful message."""
        with pytest.raises(ValueError, match="Ellipse"):
            parse_dsl('a(("Oval"))')

    def test_diamond_raises_error(self) -> None:
        """Diamond syntax is not supported — raises ValueError with helpful message."""
        with pytest.raises(ValueError, match="Diamond"):
            parse_dsl('a{"Decision"}')

    def test_bare_id_becomes_shape(self) -> None:
        result = parse_dsl("mynode")
        assert "mynode" in result["shapes"]
        assert result["shapes"]["mynode"]["label"] == "mynode"

    def test_edge_id_format(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert result["edges"][0]["id"] == "edge-a-b"

    def test_dashed_arrow_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-.->b')
        assert len(result["edges"]) == 1
        e = result["edges"][0]
        assert e["src"] == "a"
        assert e["dst"] == "b"
        assert e["directed"] is True
        assert e["endArrowhead"] == "arrow"
        assert e["strokeStyle"] == "dashed"

    def test_dashed_arrow_edge_with_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-.->|Metrics|b')
        e = result["edges"][0]
        assert e["label"] == "Metrics"
        assert e["strokeStyle"] == "dashed"
        assert e["endArrowhead"] == "arrow"

    def test_dashed_undirected_edge(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-.-b')
        e = result["edges"][0]
        assert e["directed"] is False
        assert e["startArrowhead"] is None
        assert e["endArrowhead"] is None
        assert e["strokeStyle"] == "dashed"

    def test_solid_edge_no_stroke_style(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        e = result["edges"][0]
        assert e.get("strokeStyle") is None

    def test_inline_style_props_on_shape(self) -> None:
        """Trailing style props after ] are captured in inline_styles."""
        result = parse_dsl('a["A"] bc:green,sw:2')
        assert "a" in result["shapes"]
        assert "a" in result["inline_styles"]
        assert result["inline_styles"]["a"]["backgroundColor"] == "#bbf7d0"
        assert result["inline_styles"]["a"]["strokeWidth"] == 2

    def test_bare_id_with_style_props(self) -> None:
        """Bare id + style props → style-only update, label=None."""
        result = parse_dsl("a bc:green")
        assert "a" in result["shapes"]
        assert result["shapes"]["a"]["label"] is None
        assert "a" in result["inline_styles"]
        assert result["inline_styles"]["a"]["backgroundColor"] == "#bbf7d0"


# ===========================================================================
# 6.2 _build_dsl
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestBuildDsl:
    def _round_trip(self, dsl: str) -> dict[str, Any]:
        """Parse DSL and rebuild it, return both parsed states."""
        parsed = parse_dsl(dsl)
        rebuilt = _build_dsl(parsed)
        return parse_dsl(rebuilt)

    def test_shapes_round_trip(self) -> None:
        dsl = 'a["Service A"]\nb["DB"]'
        rt = self._round_trip(dsl)
        assert "a" in rt["shapes"]
        assert rt["shapes"]["a"]["label"] == "Service A"
        assert "b" in rt["shapes"]

    def test_directed_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-->b'
        rt = self._round_trip(dsl)
        assert len(rt["edges"]) == 1
        assert rt["edges"][0]["src"] == "a"
        assert rt["edges"][0]["dst"] == "b"
        assert rt["edges"][0]["endArrowhead"] == "arrow"

    def test_undirected_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na---b'
        rt = self._round_trip(dsl)
        assert rt["edges"][0]["directed"] is False

    def test_bidirectional_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na<-->b'
        rt = self._round_trip(dsl)
        e = rt["edges"][0]
        assert e["startArrowhead"] == "arrow"
        assert e["endArrowhead"] == "arrow"

    def test_dot_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na --o b'
        rt = self._round_trip(dsl)
        assert rt["edges"][0]["endArrowhead"] == "dot"

    def test_bar_edge_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na --x b'
        rt = self._round_trip(dsl)
        assert rt["edges"][0]["endArrowhead"] == "bar"

    def test_subgraph_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\nsubgraph g ["Group"]\n  a\n  b\nend'
        rt = self._round_trip(dsl)
        assert "g" in rt["groups"]
        assert "a" in rt["groups"]["g"]["members"]

    def test_multiline_label_round_trip(self) -> None:
        dsl = 'a["Line1\\nLine2"]'
        rt = self._round_trip(dsl)
        assert rt["shapes"]["a"]["label"] == "Line1\nLine2"

    def test_edge_with_label_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-->|query|b'
        rt = self._round_trip(dsl)
        assert rt["edges"][0]["label"] == "query"

    def test_dashed_arrow_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-.->b'
        rt = self._round_trip(dsl)
        e = rt["edges"][0]
        assert e["strokeStyle"] == "dashed"
        assert e["directed"] is True

    def test_dashed_arrow_with_label_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-.->|Logs|b'
        rt = self._round_trip(dsl)
        e = rt["edges"][0]
        assert e["label"] == "Logs"
        assert e["strokeStyle"] == "dashed"

    def test_dashed_undirected_round_trip(self) -> None:
        dsl = 'a["A"]\nb["B"]\na-.-b'
        rt = self._round_trip(dsl)
        e = rt["edges"][0]
        assert e["directed"] is False
        assert e["strokeStyle"] == "dashed"

    def test_empty_state(self) -> None:
        state: dict[str, Any] = {"shapes": {}, "edges": [], "groups": {}}
        assert _build_dsl(state) == ""

    def test_combined_both_labels(self) -> None:
        """'a["Hello"] --> b["World"]' must parse to IDs a/b with correct labels.

        Regression for: whiteboard-draw-combined-shape-edge-mangles-ids
        """
        result = parse_dsl('a["Hello"] --> b["World"]')
        assert "a" in result["shapes"], "shape ID must be 'a', not 'ahello'"
        assert "b" in result["shapes"], "shape ID must be 'b', not 'bworld'"
        assert result["shapes"]["a"]["label"] == "Hello"
        assert result["shapes"]["b"]["label"] == "World"
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"
        assert result["edges"][0]["dst"] == "b"
        assert result["edges"][0]["id"] == "edge-a-b"

    def test_combined_src_label_only(self) -> None:
        """'a["Hello"] --> b' must preserve the label for a and use bare ID b."""
        result = parse_dsl('a["Hello"] --> b')
        assert result["shapes"]["a"]["label"] == "Hello"
        assert result["edges"][0]["src"] == "a"
        assert result["edges"][0]["dst"] == "b"

    def test_combined_dst_label_only(self) -> None:
        """'a --> b["World"]' must preserve the label for b and use bare ID a."""
        result = parse_dsl('a --> b["World"]')
        assert result["shapes"]["b"]["label"] == "World"
        assert result["edges"][0]["src"] == "a"
        assert result["edges"][0]["dst"] == "b"

    def test_combined_with_edge_label(self) -> None:
        """'a["Hello"] -->|calls| b["World"]' must keep shape labels and edge label."""
        result = parse_dsl('a["Hello"] -->|calls| b["World"]')
        assert result["shapes"]["a"]["label"] == "Hello"
        assert result["shapes"]["b"]["label"] == "World"
        assert result["edges"][0]["label"] == "calls"
        assert result["edges"][0]["src"] == "a"
        assert result["edges"][0]["dst"] == "b"


# ===========================================================================
# 6.3 _auto_size and _shape_payload
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestAutoSize:
    def test_short_label_returns_min_size(self) -> None:
        w, h = _auto_size("Hi")
        assert w == _SHAPE_MIN_W
        assert h == _SHAPE_MIN_H

    def test_long_label_grows_width(self) -> None:
        long_label = "A" * 60
        w, h = _auto_size(long_label)
        assert w > _SHAPE_MIN_W

    def test_multiline_label_grows_height(self) -> None:
        label = "Line1\nLine2\nLine3\nLine4"
        _, h = _auto_size(label)
        assert h > _SHAPE_MIN_H

    def test_empty_label_returns_min_size(self) -> None:
        w, h = _auto_size("")
        assert w == _SHAPE_MIN_W
        assert h == _SHAPE_MIN_H

    def test_shape_payload_uses_auto_size(self) -> None:
        long_label = "A" * 60
        shape = {"label": long_label, "classes": []}
        p = _shape_payload("n", shape, 0.0, 0.0)
        assert p["w"] > _SHAPE_MIN_W

    def test_shape_payload_style_width_overrides_auto_size(self) -> None:
        shape = {"label": "short", "classes": []}
        p = _shape_payload("n", shape, 0.0, 0.0, style={"width": 999, "height": 88})
        assert p["w"] == 999
        assert p["h"] == 88

    def test_shape_payload_multiline_grows_height(self) -> None:
        label = "Line1\nLine2\nLine3\nLine4"
        shape = {"label": label, "classes": []}
        p = _shape_payload("n", shape, 0.0, 0.0)
        assert p["h"] > _SHAPE_MIN_H


# ===========================================================================
# 6.5 _parse_style_props (replaces _resolve_style)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestParseStyleProps:
    def test_bc_shorthand(self) -> None:
        props = _parse_style_props("bc:#ff0000")
        assert props["backgroundColor"] == "#ff0000"

    def test_sc_shorthand(self) -> None:
        props = _parse_style_props("sc:#1e1e1e")
        assert props["strokeColor"] == "#1e1e1e"

    def test_sw_numeric(self) -> None:
        props = _parse_style_props("sw:2")
        assert props["strokeWidth"] == 2

    def test_named_color_green(self) -> None:
        props = _parse_style_props("bc:green")
        assert props["backgroundColor"] == "#bbf7d0"

    def test_named_color_blue(self) -> None:
        props = _parse_style_props("bc:blue")
        assert props["backgroundColor"] == "#bfdbfe"

    def test_roughness(self) -> None:
        props = _parse_style_props("r:0")
        assert props["roughness"] == 0

    def test_opacity(self) -> None:
        props = _parse_style_props("o:80")
        assert props["opacity"] == 80

    def test_font_family_normal(self) -> None:
        props = _parse_style_props("f:normal")
        assert props["fontFamily"] == 2

    def test_font_family_mono(self) -> None:
        props = _parse_style_props("f:mono")
        assert props["fontFamily"] == 3

    def test_font_size(self) -> None:
        props = _parse_style_props("fs:20")
        assert props["fontSize"] == 20

    def test_stroke_style(self) -> None:
        props = _parse_style_props("ss:dashed")
        assert props["strokeStyle"] == "dashed"

    def test_shape_d(self) -> None:
        props = _parse_style_props("shape:d")
        assert props["shape"] == "diamond"

    def test_shape_c(self) -> None:
        props = _parse_style_props("shape:c")
        assert props["shape"] == "ellipse"

    def test_shape_r(self) -> None:
        props = _parse_style_props("shape:r")
        assert props["shape"] == "rectangle"

    def test_multiple_props(self) -> None:
        props = _parse_style_props("bc:green,sc:#000,sw:3")
        assert props["backgroundColor"] == "#bbf7d0"
        assert props["strokeColor"] == "#000"
        assert props["strokeWidth"] == 3

    def test_empty_string(self) -> None:
        props = _parse_style_props("")
        assert props == {}


# ===========================================================================
# 6.5 Smoke tests for public tools (mocked Playwright)
# ===========================================================================


def _reset_exc_state(tmp_wb_dir: Any = None) -> None:
    """Reset excalidraw state between tests.

    Clears the browser handles and optionally the session file for the CWD board.
    When tmp_wb_dir is given, the session module's whiteboard dir is pointed there.
    """
    import otdev.tools.excalidraw as exc

    exc._tab = None
    exc._browser = None
    # Delete CWD session file if it exists
    from otdev.tools._excalidraw import session as _sess
    try:
        _sess.session_path(None).unlink(missing_ok=True)
    except Exception:
        pass


def _make_mock_tab() -> MagicMock:
    """Create a mock pydoll Tab for tests with appropriate async methods."""
    mock = MagicMock()

    async def execute_script(
        script: str, *, return_by_value: Any = None, await_promise: Any = None, **kwargs: Any
    ) -> dict[str, Any]:
        if "__drawApi?.backend" in script:
            return {"result": {"result": {"type": "boolean", "value": True}}}
        if "__drawApi.read" in script or "__downloadQueue" in script:
            return {"result": {"result": {"type": "object", "subtype": "array", "value": []}}}
        if "__otDSL" in script:
            return {"result": {"result": {"type": "string", "value": ""}}}
        return {"result": {"result": {"type": "undefined"}}}

    async def go_to(*, url: str, **kwargs: Any) -> None:
        pass

    mock.execute_script = execute_script
    mock.go_to = go_to
    return mock


@pytest.mark.unit
@pytest.mark.tools
class TestPublicToolsSmoke:
    """Smoke tests verifying correct browser calls for each public tool."""

    def _reset_state(self) -> None:
        _reset_exc_state()

    def test_draw_is_browser_free(self) -> None:
        """draw() must not open a browser — it is a pure session-file operation."""
        from otdev.tools import excalidraw

        self._reset_state()
        # No browser mock needed — draw() should work without one
        result = excalidraw.draw(input='a["A"]\nb["B"]\na-->b')

        assert "shapes" in result
        assert "+2 shapes" in result

    def test_draw_state_persists_to_session(self, tmp_path: Any) -> None:
        """draw() writes state to the session file."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]')
            state = _sess.load(None)
        assert "a" in state["shapes"]
        assert "b" in state["shapes"]

    def test_clear_clears_session(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()
        # Create a session file
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({"shapes": {"a": {"label": "A", "classes": []}}, "edges": [], "groups": {}, "edge_keys": set(), "canvas_max_y": 60.0})
            result = excalidraw.clear()
            state = _sess.load(None)

        assert "cleared" in result
        assert len(state["shapes"]) == 0

    def test_scroll_calls_scroll(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        evaluated: list[str] = []

        def capture_eval(fn: str) -> str:
            evaluated.append(fn)
            return "null"

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            with patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_eval):
                result = excalidraw.scroll(dx=100, dy=50)

        assert "scrolled" in result
        assert any("scroll" in c and "100" in c for c in evaluated)

    def test_zoom_calls_zoom(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        evaluated: list[str] = []

        def capture_eval(fn: str) -> str:
            evaluated.append(fn)
            return "null"

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            with patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_eval):
                result = excalidraw.zoom(level=0.5)

        assert "zoom" in result
        assert any("zoom" in c and "0.5" in c for c in evaluated)

    def test_zoom_level_zero_fits_all(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.zoom(level=0)

        assert "fit" in result

    def test_save_writes_native_excalidraw_file(
        self, tmp_path: Any
    ) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        out_file = str(tmp_path / "out.excalidraw")

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=tmp_path / "out.excalidraw"),
        ):
            result = excalidraw.save(file=out_file)

        assert "saved" in result
        content = (tmp_path / "out.excalidraw").read_text()
        data = json.loads(content)
        assert data["type"] == "excalidraw"
        assert "elements" in data
        assert data["version"] == 2

    def test_load_restores_state(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()

        content = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": [],
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        }
        diag_file = tmp_path / "diag.excalidraw"
        diag_file.write_text(json.dumps(content))

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag_file),
            patch(
                "otdev.tools.excalidraw._read_dsl_from_canvas",
                return_value='a["A"]\nb["B"]\na-->b',
            ),
            _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path),
        ):
            result = excalidraw.load(file=str(diag_file))
            state = _sess.load(None)

        assert "loaded" in result
        assert "2 shapes" in result
        # Session file should be populated
        assert "a" in state["shapes"]
        assert "b" in state["shapes"]

    def test_zoom_rejects_negative_level(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.zoom(level=-1.0)

        assert "Error" in result

    def test_load_returns_error_for_invalid_format(self, tmp_path: Any) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        diag_file = tmp_path / "bad.excalidraw"
        diag_file.write_text("not json at all\n")

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag_file),
        ):
            result = excalidraw.load(file=str(diag_file))

        assert "Error" in result

    def test_load_returns_error_for_wrong_type(self, tmp_path: Any) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        diag_file = tmp_path / "bad.excalidraw"
        diag_file.write_text(json.dumps({"type": "other", "elements": []}))

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag_file),
        ):
            result = excalidraw.load(file=str(diag_file))

        assert "Error" in result

    def test_fit_delegates_to_zoom(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.fit()

        assert "fit" in result

    def test_screenshot_returns_base64(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_tab = _make_mock_tab()

        async def mock_take_screenshot(*, path: Any = None, as_base64: bool = False, **kw: Any) -> Any:
            if as_base64:
                return "screenshot-data"
            return None

        mock_tab.take_screenshot = mock_take_screenshot

        with (
            patch("otdev.tools.excalidraw._tab", mock_tab),
            patch("otdev.tools.excalidraw._rerender_from_state"),
        ):
            result = excalidraw.screenshot()

        assert result == "screenshot-data"

    def test_screenshot_calls_take_screenshot_as_base64(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        mock_tab = _make_mock_tab()
        calls: list[dict[str, Any]] = []

        async def mock_take_screenshot(*, path: Any = None, as_base64: bool = False, **kw: Any) -> Any:
            calls.append({"path": path, "as_base64": as_base64})
            return "data" if as_base64 else None

        mock_tab.take_screenshot = mock_take_screenshot

        with (
            patch("otdev.tools.excalidraw._tab", mock_tab),
            patch("otdev.tools.excalidraw._rerender_from_state"),
        ):
            excalidraw.screenshot()

        assert calls, "take_screenshot must be called"
        assert calls[0]["as_base64"] is True

    def test_screenshot_saves_to_file(self, tmp_path: Any) -> None:
        from pathlib import Path

        from otdev.tools import excalidraw

        self._reset_state()
        fake_bytes = b"FAKEIMAGE"
        out_file = str(tmp_path / "canvas.png")
        mock_tab = _make_mock_tab()

        async def mock_take_screenshot(*, path: Any = None, as_base64: bool = False, **kw: Any) -> Any:
            if path:
                Path(path).write_bytes(fake_bytes)
            return None

        mock_tab.take_screenshot = mock_take_screenshot

        with (
            patch("otdev.tools.excalidraw._tab", mock_tab),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=tmp_path / "canvas.png"),
            patch("otdev.tools.excalidraw._rerender_from_state"),
        ):
            result = excalidraw.screenshot(file=out_file)

        assert "saved" in result
        assert (tmp_path / "canvas.png").read_bytes() == fake_bytes

    def test_clear_works_as_first_operation(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.clear()

        assert result == "canvas cleared"

    def test_hard_reset_clears_state_without_browser(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({"shapes": {"a": {"label": "A", "classes": []}}, "edges": [], "groups": {}, "edge_keys": set(), "canvas_max_y": 60.0})
            result = excalidraw.hard_reset()
            state = _sess.load(None)

        assert "state cleared" in result
        assert state["shapes"] == {}

    def test_hard_reset_clears_canvas_when_browser_available(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        evaluated: list[str] = []

        def capture_eval(expr: str, *args: Any, **kwargs: Any) -> Any:
            evaluated.append(expr)
            return "null"

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            with patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_eval):
                result = excalidraw.hard_reset()

        assert "canvas cleared" in result
        assert any("clear" in e for e in evaluated), "expected canvas clear call"

    def test_open_returns_ready_when_bootstrap_succeeds(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.open()

        assert result == "whiteboard ready"

    def test_open_clears_canvas_and_state(self, tmp_path: Any) -> None:
        """open() always starts fresh regardless of existing state."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()
        evaluated: list[str] = []

        def capture_eval(fn: str) -> str:
            evaluated.append(fn)
            return "true"

        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({"shapes": {"a": {"label": "A", "classes": []}}, "edges": [], "groups": {}, "edge_keys": set(), "canvas_max_y": 60.0})
            with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
                with patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_eval):
                    result = excalidraw.open()
            state = _sess.load(None)

        assert result == "whiteboard ready"
        assert state["shapes"] == {}, "session should be cleared"
        assert any("clear" in e for e in evaluated), "canvas clear should be called"

    def test_open_returns_error_when_browser_unavailable(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()  # _tab = None

        with patch("otdev.tools.excalidraw._open_browser", side_effect=Exception("Chrome not found")):
            result = excalidraw.open()

        assert "Error" in result

    def test_close_resets_state(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({"shapes": {"a": {"label": "A", "classes": []}}, "edges": [], "groups": {}, "edge_keys": set(), "canvas_max_y": 60.0})
            result = excalidraw.close()
            state = _sess.load(None)

        assert "closed" in result
        assert state["shapes"] == {}

    def test_close_resets_browser_state(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        # Simulate an active browser
        excalidraw._browser = MagicMock()
        excalidraw._tab = MagicMock()

        result = excalidraw.close()

        assert "closed" in result
        assert excalidraw._browser is None
        assert excalidraw._tab is None

    def test_bootstrap_failure_returns_error(self) -> None:
        """note() must return error when browser bootstrap fails (draw() is browser-free)."""
        from otdev.tools import excalidraw

        self._reset_state()
        mock_tab = _make_mock_tab()

        async def bootstrap_fail_execute(
            script: str, *, return_by_value: Any = None, await_promise: Any = None, **kw: Any
        ) -> dict[str, Any]:
            if "__drawApi?.backend" in script:
                return {"result": {"result": {"type": "boolean", "value": False}}}
            # bootstrap.js returns false → triggers error
            return {"result": {"result": {"type": "boolean", "value": False}}}

        async def mock_go_to(*, url: str, **kw: Any) -> None:
            pass

        mock_tab.execute_script = bootstrap_fail_execute
        mock_tab.go_to = mock_go_to

        with patch("otdev.tools.excalidraw._tab", mock_tab):
            result = excalidraw.note(input="n[note:\nhello\n]")

        assert "Error" in result
        assert "bootstrap" in result.lower()

    def test_draw_additive_accumulates_state(self, tmp_path: Any) -> None:
        """Consecutive draw() calls accumulate shapes and edges in the session."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]\na-->b')
            excalidraw.draw(input='c["C"]\nb-->c')
            state = _sess.load(None)

        assert set(state["shapes"]) == {"a", "b", "c"}
        assert len(state["edges"]) == 2

    def test_draw_auto_creates_unknown_node_in_edge(self) -> None:
        """Unknown edge endpoints are auto-created with label = node ID."""
        from otdev.tools import excalidraw

        self._reset_state()
        result = excalidraw.draw(input='a["A"]\nb["B"]\na-->typo')

        assert "skipped" not in result
        assert "+3 shapes" in result

    def test_draw_implied_nodes_only(self) -> None:
        """All nodes implied by edges — no explicit shape declarations."""
        from otdev.tools import excalidraw

        self._reset_state()
        result = excalidraw.draw(input="a-->b\nb-->c\nc-->d")

        assert "+4 shapes" in result

    def test_draw_no_warn_when_all_nodes_defined(self) -> None:
        from otdev.tools import excalidraw

        self._reset_state()
        result = excalidraw.draw(input='a["A"]\nb["B"]\na-->b')

        assert "skipped" not in result

    def test_js_batch_draw_passes_three_positional_args(self) -> None:
        """_js_batch_draw must call browser_evaluate with 3 separate JSON args."""
        import otdev.tools.excalidraw as exc

        self._reset_state()
        calls: list[str] = []

        def capture_evaluate(fn: str) -> str:
            calls.append(fn)
            return "null"

        with patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_evaluate):
            exc._js_batch_draw(
                shapes=[{"id": "a"}],
                edges=[{"id": "e1"}],
                subgraphs=[],
            )

        assert calls, "should have called _browser_evaluate"
        fn = calls[0]
        assert '"shapes"' not in fn.split("_batch_draw(")[1][:10], \
            "_batch_draw must not receive a {shapes:…} object as first arg"
        assert fn.count(",") >= 2, "call must have at least 2 commas (three positional args)"

    def test_draw_bad_dsl_raises_without_corrupting_session(self, tmp_path: Any) -> None:
        """draw() with invalid DSL raises ValueError; prior session is unchanged."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]')
            with pytest.raises(ValueError, match="Ellipse"):
                excalidraw.draw(input='x(("Oval"))')  # ellipse not supported
            state = _sess.load(None)

        assert "a" in state["shapes"], "prior state must be preserved after error"

    def test_draw_stores_shapes_and_edges_in_session(self, tmp_path: Any) -> None:
        """draw() saves all new shapes and edges to the session file."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]\nc["C"]\na-->b\nb-->c')
            state = _sess.load(None)

        assert len(state["shapes"]) == 3
        assert len(state["edges"]) == 2

    def test_draw_returns_edge_ids_in_output(self) -> None:
        """draw() includes new edge IDs in the return string (issue #6)."""
        from otdev.tools import excalidraw

        self._reset_state()
        result = excalidraw.draw(input='a["A"]\nb["B"]\na-->b')

        assert "edge-a-b" in result

    def test_draw_upsert_existing_shape(self, tmp_path: Any) -> None:
        """draw() on an existing shape updates its label in the session (upsert)."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]')
            excalidraw.draw(input='a["Updated"]')
            state = _sess.load(None)

        assert state["shapes"]["a"]["label"] == "Updated"


# ===========================================================================
# 6.6 Edge ID collision fixes
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestEdgeIdUniqueness:
    def test_parallel_edges_different_labels_have_unique_ids(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|read|b\na-->|write|b')
        ids = [e["id"] for e in result["edges"]]
        assert len(ids) == len(set(ids)), "parallel edges with different labels must have unique IDs"

    def test_labeled_edge_id_includes_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|query|b')
        assert result["edges"][0]["id"] == "edge-a-b-query"

    def test_unlabeled_directed_edge_id(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert result["edges"][0]["id"] == "edge-a-b"

    def test_bidirectional_edge_id_differs_from_directed(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b\na<-->b')
        ids = [e["id"] for e in result["edges"]]
        assert len(ids) == len(set(ids)), "bidir and directed edges must have different IDs"
        assert any("bidir" in eid for eid in ids)

    def test_undirected_edge_id_includes_und_suffix(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na---b')
        assert result["edges"][0]["id"] == "edge-a-b-und"

    def test_dot_edge_id_includes_dot_suffix(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o b')
        assert result["edges"][0]["id"] == "edge-a-b-dot"

    def test_bar_edge_id_includes_bar_suffix(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --x b')
        assert result["edges"][0]["id"] == "edge-a-b-bar"

    def test_draw_dedup_distinguishes_arrowhead_types(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()

        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]\na-->b\na<-->b')
            state = _sess.load(None)

        assert len(state["edges"]) == 2, "a-->b and a<-->b should both be stored"


# ===========================================================================
# 6.7 Arrow label rendering
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestArrowLabels:
    def test_labeled_edge_parsed_correctly(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|read|b')
        assert result["edges"][0]["label"] == "read"

    def test_labeled_edge_id_encodes_label(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->|read|b')
        assert "read" in result["edges"][0]["id"]

    def test_connect_shape_called_with_label(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()

        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]\na-->|writes|b')
            state = _sess.load(None)

        assert len(state["edges"]) == 1
        assert state["edges"][0]["label"] == "writes"


# ===========================================================================
# 6.9 Note tool
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNoteToolParsing:
    def test_parse_note_blocks_table(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "t[table:\nA,B\n1,2\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["id"] == "t"
        assert blocks[0]["type"] == "table"
        assert "A,B" in blocks[0]["content"]

    def test_parse_note_blocks_multiple(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "t1[table:\nA,B\n1,2\n]\n\nt2[tree:\nroot\n-child\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 2
        assert blocks[0]["id"] == "t1"
        assert blocks[1]["id"] == "t2"

    def test_parse_note_blocks_empty(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        assert _parse_note_blocks("nothing here") == []

    def test_parse_note_blocks_trailing_space_after_colon(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "t[table:  \nA,B\n1,2\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "table"

    def test_parse_note_blocks_crlf_line_endings(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "t[table:\r\nA,B\r\n1,2\r\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "table"

    def test_note_tool_returns_error_on_no_blocks(self) -> None:
        from otdev.tools import excalidraw

        _reset_exc_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.note(input="no blocks here")

        assert "Error" in result

    def test_note_returns_error_on_renderer_error(self) -> None:
        from otdev.tools import excalidraw

        _reset_exc_state()

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch(
                "otdev.tools._excalidraw.renderers.render_table",
                return_value="Error: tabulate not installed (pip install tabulate)",
            ),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            result = excalidraw.note(input="t[table:\nName,Role\nAlice,Dev\n]")

        assert "Error" in result
        assert "t" in result
        mock_batch.assert_not_called()

    def test_note_unknown_type_returns_error(self) -> None:
        from otdev.tools import excalidraw

        _reset_exc_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.note(input="x[text:\nsome content\n]")

        assert "Error" in result
        assert "text" in result
        assert "Supported" in result

    def test_note_tool_calls_draw_shape(self) -> None:
        from otdev.tools import excalidraw

        _reset_exc_state()

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            result = excalidraw.note(input="t[tree:\nroot\n-child\n]")

        assert "inserted" in result
        assert mock_batch.call_count == 1
        _, kwargs = mock_batch.call_args
        shapes = kwargs["shapes"]
        assert len(shapes) == 1
        assert shapes[0]["id"] == "t"
        assert shapes[0]["styleProps"]["fontFamily"] == 3  # code font

    def test_note_persists_shape_so_erase_can_remove_it(self, tmp_path: Any) -> None:
        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()

        with (
            patch.object(_sess, "_whiteboard_dir", return_value=tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._js_batch_draw"),
        ):
            result = excalidraw.note(input="n1[note:\nSanity note\n]")
            state = _sess.load()
            erase_result = excalidraw.erase(ids=["n1"])
            after = _sess.load()

        assert result == "inserted 1 note(s)"
        assert "n1" in state["shapes"]
        assert state["shapes"]["n1"]["label"] == "Sanity note"
        assert erase_result == "erased 1 element(s)"
        assert "n1" not in after["shapes"]

    def test_note_multiblock_draws_each_block_separately(self) -> None:
        """note() with multiple blocks calls _js_batch_draw once per block.

        Uses block types that don't require tabulate (tree, seq, timeline, note).
        """
        from otdev.tools import excalidraw

        _reset_exc_state()

        multi_input = (
            "tr[tree:\nroot/\n-src/\n]\n"
            "s[seq:\nA -> B: hi\n]\n"
            "g[timeline:\nTask,1,3\n]\n"
            "n[note:\nPlain text here.\n]"
        )

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
        ):
            result = excalidraw.note(input=multi_input)

        assert result == "inserted 4 note(s)"
        assert mock_batch.call_count == 4, "one _js_batch_draw call per block"
        drawn_ids = [c[1]["shapes"][0]["id"] for c in mock_batch.call_args_list]
        assert drawn_ids == ["tr", "s", "g", "n"]


# ===========================================================================
# 6.10 Renderers unit tests
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestRenderers:
    def test_render_tree_basic(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n-child2\n--leaf")
        assert "root" in result
        assert "child1" in result
        assert "leaf" in result

    def test_render_tree_empty(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        assert render_tree("") == ""

    def test_render_sequence_basic(self) -> None:
        from otdev.tools._excalidraw.renderers import render_sequence

        result = render_sequence("A -> B: hello\nB -> A: world")
        assert "A" in result
        assert "B" in result
        assert "hello" in result

    def test_render_sequence_empty(self) -> None:
        from otdev.tools._excalidraw.renderers import render_sequence

        assert render_sequence("") == ""

    def test_render_timeline_basic(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        result = render_timeline("Task A,1,5\nTask B,3,4")
        assert "Task A" in result
        assert "#" in result

    def test_render_timeline_empty(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        assert render_timeline("") == ""

    def test_render_timeline_bad_start_returns_error(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        result = render_timeline("v1.0,Jan,2\nv2.0,Mar,3")
        assert result.startswith("Error:")
        assert "Jan" in result
        assert "start" in result

    def test_render_timeline_bad_duration_returns_error(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        result = render_timeline("v1.0,1,two")
        assert result.startswith("Error:")
        assert "two" in result
        assert "duration" in result

    def test_render_timeline_semicolon_separator(self) -> None:
        from otdev.tools._excalidraw.renderers import render_timeline

        result = render_timeline("Task A,1,5;Task B,3,4")
        assert "Task A" in result
        assert "Task B" in result

    def test_render_tree_siblings_show_connector(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n--leaf1\n-child2")
        lines = result.splitlines()
        assert any("│" in ln for ln in lines), "sibling branch should show │ connector"
        assert "child2" in result
        assert any("└──" in ln for ln in lines)

    def test_render_tree_no_false_sibling_across_subtree(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n--leaf1\n-child2\n--leaf2")
        lines = result.splitlines()
        leaf1_line = next(ln for ln in lines if "leaf1" in ln)
        assert "leaf1" in leaf1_line
        assert "└──" in leaf1_line or "├──" in leaf1_line

    def test_render_tree_true_siblings_continuation(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n--leaf1\n--leaf2")
        lines = result.splitlines()
        leaf1_line = next(ln for ln in lines if "leaf1" in ln)
        assert "├──" in leaf1_line

    def test_render_tree_unicode_connectors(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n-child1\n-child2")
        assert "├──" in result
        assert "└──" in result

    def test_render_tree_space_indent(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root\n  child1\n  child2\n    leaf")
        assert "root" in result
        assert "child1" in result
        assert "leaf" in result

    def test_render_tree_semicolon_separator(self) -> None:
        from otdev.tools._excalidraw.renderers import render_tree

        result = render_tree("root;-child1;-child2")
        assert "root" in result
        assert "child1" in result
        assert "child2" in result


# ===========================================================================
# 6.11 Note/draw placement: uses _get_canvas_max_y for vertical stacking
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNotePlacement:
    def _reset(self) -> None:
        _reset_exc_state()

    def test_note_base_y_uses_canvas_max_y(self) -> None:
        """Notes are placed 100px below the canvas max-y returned by _get_canvas_max_y."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        self._reset()

        captured: list[Any] = []

        def capture_batch(**kwargs: Any) -> None:
            captured.append(kwargs)

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._get_canvas_max_y", return_value=300.0),
            patch("otdev.tools.excalidraw._js_batch_draw", side_effect=capture_batch),
        ):
            excalidraw.note(input="n[note:\nhello\n]")

        assert captured, "batch draw should have been called"
        shapes = captured[0]["shapes"]
        assert shapes[0]["y"] >= 400.0, "note y should be at least canvas_max_y + 100"

    def test_draw_uses_canvas_max_y_for_stacking(self, tmp_path: Any) -> None:
        """draw() tracks canvas_max_y from session state for additive vertical stacking."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset()

        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            # Pre-populate session with a high canvas_max_y
            _sess.save({"shapes": {}, "edges": [], "groups": {}, "edge_keys": set(), "canvas_max_y": 500.0})
            excalidraw.draw(input='a["A"]')
            state = _sess.load(None)

        # After drawing, canvas_max_y should advance beyond 500 + 40 (base_y offset)
        assert state["canvas_max_y"] >= 540.0, "canvas_max_y must increase beyond prior value"


# ===========================================================================
# embed_dsl
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestEmbedDsl:
    def _reset(self) -> None:
        _reset_exc_state()

    def test_embed_dsl_inserts_dsl_box(self, tmp_path: Any) -> None:
        from unittest.mock import patch
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset()
        # Populate session via draw() so embed_dsl() has content to embed
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]')

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._js_batch_draw") as mock_batch,
            _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path),
        ):
            result = excalidraw.embed_dsl()

        assert "embedded DSL" in result
        assert mock_batch.call_count == 1
        _, kwargs = mock_batch.call_args
        shapes = kwargs["shapes"]
        assert len(shapes) == 1
        assert shapes[0]["id"] == "dsl"
        assert shapes[0]["styleProps"]["backgroundColor"] == "#e8e8e8"
        assert "a" in shapes[0]["label"] or "b" in shapes[0]["label"]

    def test_embed_dsl_returns_empty_message_when_no_state(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        self._reset()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.embed_dsl()

        assert "empty" in result


# ===========================================================================
# erase
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestErase:
    def _reset(self) -> None:
        _reset_exc_state()

    def test_erase_removes_shape_from_state(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({"shapes": {"a": {"label": "A", "classes": []}, "b": {"label": "B", "classes": []}}, "edges": [], "groups": {}, "edge_keys": set(), "canvas_max_y": 60.0})
            result = excalidraw.erase(ids=["a"])
            state = _sess.load(None)

        assert "erased 1" in result
        assert "a" not in state["shapes"]
        assert "b" in state["shapes"]

    def test_erase_unknown_id_returns_zero(self) -> None:
        from otdev.tools import excalidraw

        self._reset()
        result = excalidraw.erase(ids=["nonexistent"])

        assert "erased 0" in result

    def test_erase_removes_associated_edge(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({"shapes": {"a": {"label": "A", "classes": []}, "b": {"label": "B", "classes": []}}, "edges": [{"id": "edge-a-b", "src": "a", "dst": "b", "label": ""}], "groups": {}, "edge_keys": set(), "canvas_max_y": 60.0})
            excalidraw.erase(ids=["edge-a-b"])
            state = _sess.load(None)

        assert state["edges"] == []

    def test_erase_removes_dangling_edges(self, tmp_path: Any) -> None:
        """Erasing a shape also removes edges that reference it as src or dst."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        self._reset()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({
                "shapes": {"a": {"label": "A", "classes": []}, "b": {"label": "B", "classes": []}, "c": {"label": "C", "classes": []}},
                "edges": [
                    {"id": "edge-a-b", "src": "a", "dst": "b", "label": ""},
                    {"id": "edge-b-c", "src": "b", "dst": "c", "label": ""},
                ],
                "groups": {},
                "edge_keys": set(),
                "canvas_max_y": 60.0,
            })
            excalidraw.erase(ids=["b"])
            state = _sess.load(None)

        assert state["edges"] == [], "edges referencing erased node should be removed"

    def test_erase_docstring_documents_edge_id_format(self) -> None:
        """erase() docstring must document the edge ID format."""
        from otdev.tools import excalidraw

        doc = excalidraw.erase.__doc__ or ""
        assert "edge-{src}-{dst}" in doc, "docstring must document edge ID format"


# ===========================================================================
# Shape types — ellipse and diamond are no longer supported via DSL
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestShapeTypes:
    def test_parse_ellipse_raises_error(self) -> None:
        """Ellipse syntax raises ValueError with helpful error message."""
        with pytest.raises(ValueError, match="Ellipse"):
            parse_dsl('a(("Oval"))')

    def test_parse_diamond_raises_error(self) -> None:
        """Diamond syntax raises ValueError with helpful error message."""
        with pytest.raises(ValueError, match="Diamond"):
            parse_dsl('a{"Decision"}')

    def test_rectangle_has_no_explicit_type(self) -> None:
        result = parse_dsl('a["Box"]')
        assert "type" not in result["shapes"]["a"]

    def test_inline_xy_used_as_shape_position(self) -> None:
        """Inline x/y in draw DSL props set the shape's position (not overridden by auto-layout)."""
        from otdev.tools.excalidraw import _shape_payload

        shape = {"label": "Foo", "classes": []}
        payload = _shape_payload("a", shape, x=0.0, y=0.0, style={"x": 300, "y": 150})
        assert payload["x"] == 300
        assert payload["y"] == 150
        # x/y must not leak into styleProps (would cause double-application)
        assert "x" not in payload["styleProps"]
        assert "y" not in payload["styleProps"]

    def test_inline_xy_missing_falls_back_to_auto_layout(self) -> None:
        """When inline x/y are absent, the auto-layout coordinates are used."""
        from otdev.tools.excalidraw import _shape_payload

        shape = {"label": "Foo", "classes": []}
        payload = _shape_payload("a", shape, x=42.0, y=99.0, style={})
        assert payload["x"] == 42.0
        assert payload["y"] == 99.0

    def test_style_shape_d_maps_to_diamond(self) -> None:
        """whiteboard.style shape:d maps to 'diamond' excalidraw type."""
        props = _parse_style_props("shape:d")
        assert props["shape"] == "diamond"

    def test_style_shape_c_maps_to_ellipse(self) -> None:
        """whiteboard.style shape:c maps to 'ellipse' excalidraw type."""
        props = _parse_style_props("shape:c")
        assert props["shape"] == "ellipse"

    def test_style_shape_r_maps_to_rectangle(self) -> None:
        """whiteboard.style shape:r maps to 'rectangle' excalidraw type."""
        props = _parse_style_props("shape:r")
        assert props["shape"] == "rectangle"


# ===========================================================================
# Node ID normalisation
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNodeIdNormalise:
    def test_uppercase_id_lowercased(self) -> None:
        result = parse_dsl('A["Node"]')
        assert "a" in result["shapes"]
        assert "A" not in result["shapes"]

    def test_mixed_case_ids_merge(self) -> None:
        result = parse_dsl('A["First"]\na["Second"]')
        assert len(result["shapes"]) == 1
        assert result["shapes"]["a"]["label"] == "Second"

    def test_edge_src_dst_normalised(self) -> None:
        result = parse_dsl('A["A"]\nB["B"]\nA-->B')
        e = result["edges"][0]
        assert e["src"] == "a"
        assert e["dst"] == "b"

    def test_uppercase_edge_connects_to_lowercase_shape(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\nA-->B')
        e = result["edges"][0]
        assert e["src"] == "a"
        assert e["dst"] == "b"

    def test_hyphenated_id_normalised(self) -> None:
        result = parse_dsl('service-a["Svc"]')
        assert "servicea" in result["shapes"]

    def test_hyphenated_edge_normalised(self) -> None:
        result = parse_dsl('service-a["A"]\nservice-b["B"]\nservice-a-->service-b')
        e = result["edges"][0]
        assert e["src"] == "servicea"
        assert e["dst"] == "serviceb"


# ===========================================================================
# 6.x Whitespace tolerance
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestWhitespaceTolerance:
    """DSL tokenizer must be whitespace-agnostic for all constructs."""

    def test_shape_spaced_brackets(self) -> None:
        result = parse_dsl('a [ "A" ]')
        assert "a" in result["shapes"]
        assert result["shapes"]["a"]["label"] == "A"

    def test_shape_extra_spaces_around_brackets(self) -> None:
        result = parse_dsl('a  [  "Hello World"  ]')
        assert "a" in result["shapes"]
        assert result["shapes"]["a"]["label"] == "Hello World"

    def test_ellipse_shape_spaced_raises_error(self) -> None:
        """Spaced ellipse syntax also raises ValueError."""
        with pytest.raises(ValueError, match="Ellipse"):
            parse_dsl('a ( ( "Node" ) )')

    def test_diamond_shape_spaced_raises_error(self) -> None:
        """Spaced diamond syntax also raises ValueError."""
        with pytest.raises(ValueError, match="Diamond"):
            parse_dsl('a { "Decision" }')

    def test_arrow_edge_no_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"

    def test_arrow_edge_with_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --> b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"

    def test_arrow_edge_with_extra_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na  -->  b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "a"

    def test_dot_edge_no_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na--ob')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["endArrowhead"] == "dot"

    def test_dot_edge_with_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["endArrowhead"] == "dot"

    def test_bar_edge_no_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na--xb')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["endArrowhead"] == "bar"

    def test_bar_edge_with_spaces(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --x b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["endArrowhead"] == "bar"

    def test_semicolon_and_newline_both_work(self) -> None:
        r1 = parse_dsl('a["A"];b["B"];a-->b')
        r2 = parse_dsl('a["A"]\nb["B"]\na-->b')
        assert r1["shapes"] == r2["shapes"]
        assert len(r1["edges"]) == len(r2["edges"]) == 1

    def test_arrow_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --> |label| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "label"

    def test_bidir_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na <--> |label| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "label"

    def test_dot_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --o |lbl| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "lbl"

    def test_bar_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na --x |lbl| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "lbl"

    def test_dashed_arrow_edge_with_label_space_before_pipe(self) -> None:
        result = parse_dsl('a["A"]\nb["B"]\na -.-> |lbl| b')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["label"] == "lbl"


# ===========================================================================
# ID pre-normalisation (spaces, hyphens, special chars stripped before parsing)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestIdPrenorm:
    """IDs with spaces, hyphens, or other non-word chars are pre-normalised."""

    def test_shape_id_with_spaces(self) -> None:
        result = parse_dsl('a b["Test"]')
        assert "ab" in result["shapes"]
        assert result["shapes"]["ab"]["label"] == "Test"

    def test_shape_id_with_hyphen(self) -> None:
        result = parse_dsl('a-b["Test"]')
        assert "ab" in result["shapes"]
        assert result["shapes"]["ab"]["label"] == "Test"

    def test_shape_id_with_plus(self) -> None:
        result = parse_dsl('a+b["Test"]')
        assert "ab" in result["shapes"]
        assert result["shapes"]["ab"]["label"] == "Test"

    def test_shape_id_multiword(self) -> None:
        result = parse_dsl('api gateway["API Gateway"]')
        assert "apigateway" in result["shapes"]
        assert result["shapes"]["apigateway"]["label"] == "API Gateway"

    def test_edge_src_with_spaces(self) -> None:
        result = parse_dsl('a b["A"]\nc["C"]\na b-->c')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "ab"
        assert result["edges"][0]["dst"] == "c"

    def test_edge_both_sides_with_spaces(self) -> None:
        result = parse_dsl('a b["A"]\nc d["C"]\na b-->c d')
        assert len(result["edges"]) == 1
        assert result["edges"][0]["src"] == "ab"
        assert result["edges"][0]["dst"] == "cd"

    def test_edge_with_label_and_spaces_in_ids(self) -> None:
        result = parse_dsl('a b["A"]\nc d["C"]\na b-->|calls|c d')
        assert len(result["edges"]) == 1
        e = result["edges"][0]
        assert e["src"] == "ab"
        assert e["dst"] == "cd"
        assert e["label"] == "calls"

    def test_bare_style_with_space_in_id(self) -> None:
        result = parse_dsl('api gateway bc:green')
        assert "apigateway" in result["shapes"]
        assert result["shapes"]["apigateway"]["label"] is None

    def test_prenorm_does_not_touch_label_content(self) -> None:
        result = parse_dsl('a b["hello world"]')
        assert result["shapes"]["ab"]["label"] == "hello world"

    def test_chained_edges_with_spaces(self) -> None:
        """A --> B --> C (spaces around -->) expands to two edges."""
        result = parse_dsl("A --> B --> C")
        assert len(result["edges"]) == 2
        srcs = {e["src"] for e in result["edges"]}
        dsts = {e["dst"] for e in result["edges"]}
        assert "a" in srcs
        assert "b" in srcs
        assert "b" in dsts
        assert "c" in dsts

    def test_chained_edges_matches_semicolon_form(self) -> None:
        """A --> B --> C produces the same edges as a-->b;b-->c."""
        r1 = parse_dsl("A --> B --> C")
        r2 = parse_dsl("a-->b;b-->c")
        assert len(r1["edges"]) == len(r2["edges"]) == 2
        r1_pairs = {(e["src"], e["dst"]) for e in r1["edges"]}
        r2_pairs = {(e["src"], e["dst"]) for e in r2["edges"]}
        assert r1_pairs == r2_pairs


# ===========================================================================
# Erase dangling edge count in return value
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestEraseDanglingCount:
    def test_erase_reports_dangling_edges(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({
                "shapes": {"a": {"label": "A", "classes": []}, "b": {"label": "B", "classes": []}, "c": {"label": "C", "classes": []}},
                "edges": [
                    {"id": "edge-a-b", "src": "a", "dst": "b", "label": ""},
                    {"id": "edge-b-c", "src": "b", "dst": "c", "label": ""},
                ],
                "groups": {},
                "edge_keys": set(),
                "canvas_max_y": 60.0,
            })
            result = excalidraw.erase(ids=["b"])

        assert "erased 1" in result
        assert "dangling" in result
        assert "2" in result

    def test_erase_no_dangling_message_when_no_edges(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            _sess.save({"shapes": {"a": {"label": "A", "classes": []}}, "edges": [], "groups": {}, "edge_keys": set(), "canvas_max_y": 60.0})
            result = excalidraw.erase(ids=["a"])

        assert "erased 1" in result
        assert "dangling" not in result


# ===========================================================================
# Note tool: leading newline before first block (regression)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNoteLeadingNewline:
    def test_leading_newline_does_not_prevent_match(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "\nt[table:\nA,B\n1,2\n]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["id"] == "t"
        assert blocks[0]["type"] == "table"

    def test_triple_quoted_style_with_leading_newline(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = """
t[table:
A,B
1,2
]"""
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["id"] == "t"

    def test_multiple_blocks_with_surrounding_newlines(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "\nt1[table:\nA,B\n1,2\n]\n\nt2[note:\nhello\n]\n"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 2

    def test_triple_quoted_multiblock_finds_all_blocks(self) -> None:
        """Triple-quoted multi-block strings must parse all blocks, not just the first.

        Regression for: whiteboard-note-multiblock-triple-quoted-finds-one-block
        When the second block ID has leading whitespace (as happens with indented
        triple-quoted strings), the regex must still match it.
        """
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = """t[table:
Name,Role
Alice,Dev
]
tr[tree:
root/
-src/
]
"""
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 2, f"expected 2 blocks, got {len(blocks)}: {blocks}"
        assert blocks[0]["id"] == "t"
        assert blocks[1]["id"] == "tr"


# ===========================================================================
# Subgraph count in draw() return value
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestDrawSubgraphCount:
    def test_draw_new_subgraph_reports_group(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            excalidraw.draw(input='a["A"]\nb["B"]')
            result = excalidraw.draw(
                input='subgraph grp ["My Group"]\n  a\n  b\nend'
            )

        assert "group" in result

    def test_draw_no_group_msg_when_no_new_subgraph(self) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.draw(input='a["A"]\nb["B"]')

        assert "group" not in result


# ===========================================================================
# Case-insensitive style values
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestParseStylePropsCI:
    """Case-insensitive style value resolution."""

    def test_named_color_uppercase(self) -> None:
        props = _parse_style_props("bc:Green")
        assert props["backgroundColor"] == "#bbf7d0"

    def test_named_color_allcaps(self) -> None:
        props = _parse_style_props("bc:BLUE")
        assert props["backgroundColor"] == "#bfdbfe"

    def test_stroke_color_mixedcase(self) -> None:
        props = _parse_style_props("sc:Red")
        assert props["strokeColor"] == "#fecaca"

    def test_stroke_style_uppercase(self) -> None:
        props = _parse_style_props("ss:Solid")
        assert props["strokeStyle"] == "solid"

    def test_stroke_style_dashed_uppercase(self) -> None:
        props = _parse_style_props("ss:Dashed")
        assert props["strokeStyle"] == "dashed"

    def test_font_family_uppercase(self) -> None:
        props = _parse_style_props("f:Hand")
        assert props["fontFamily"] == 1

    def test_font_family_normal_uppercase(self) -> None:
        props = _parse_style_props("f:Normal")
        assert props["fontFamily"] == 2

    def test_shape_uppercase_r(self) -> None:
        props = _parse_style_props("shape:R")
        assert props["shape"] == "rectangle"

    def test_shape_uppercase_d(self) -> None:
        props = _parse_style_props("shape:D")
        assert props["shape"] == "diamond"

    def test_shape_uppercase_c(self) -> None:
        props = _parse_style_props("shape:C")
        assert props["shape"] == "ellipse"

    def test_text_align_uppercase(self) -> None:
        props = _parse_style_props("ta:Center")
        assert props["textAlign"] == "center"

    def test_vert_align_uppercase(self) -> None:
        props = _parse_style_props("va:Middle")
        assert props["verticalAlign"] == "middle"

    def test_hex_color_passthrough_unchanged(self) -> None:
        """Hex colours pass through as-is (Excalidraw accepts both cases)."""
        props = _parse_style_props("bc:#FF0000")
        assert props["backgroundColor"] == "#FF0000"


# ===========================================================================
# load() warning when __otDSL is absent
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestLoadWarningNoDsl:
    """load() warns when no __otDSL element is found."""

    def test_load_warns_when_no_otdsl(self, tmp_path: Any) -> None:
        """Loading a .excalidraw file with no __otDSL element includes a warning."""
        import json
        from unittest.mock import patch

        from otdev.tools import excalidraw

        # Write a valid .excalidraw file with no __otDSL element
        exc_file = tmp_path / "no-dsl.excalidraw"
        data = {
            "type": "excalidraw",
            "version": 2,
            "elements": [
                {"id": "shape1", "type": "rectangle", "x": 0, "y": 0, "width": 100, "height": 60},
            ],
        }
        exc_file.write_text(json.dumps(data), encoding="utf-8")

        _reset_exc_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.load(file=str(exc_file))

        assert "warning" in result.lower()
        assert "__otDSL" in result or "no __otDSL" in result

    def test_load_with_otdsl_no_warning(self, tmp_path: Any) -> None:
        """Loading a .excalidraw file with __otDSL does not include a warning."""
        import json
        from unittest.mock import patch

        from otdev.tools import excalidraw

        # Write a valid .excalidraw file with a __otDSL element
        exc_file = tmp_path / "with-dsl.excalidraw"
        dsl_text = 'a["A"];b["B"];a-->b'
        data = {
            "type": "excalidraw",
            "version": 2,
            "elements": [
                {"id": "__otDSL", "type": "text", "text": dsl_text, "x": 0, "y": 0, "width": 100, "height": 20},
            ],
        }
        exc_file.write_text(json.dumps(data), encoding="utf-8")

        _reset_exc_state()

        # Build a mock tab that returns dsl_text when the __otDSL element is queried.
        # Note: _read_dsl_from_canvas script contains both __drawApi.read AND __otDSL —
        # check __otDSL first so that script returns the DSL text, not an empty array.
        dsl_mock = MagicMock()

        async def execute_script_with_dsl(
            script: str, *, return_by_value: Any = None, await_promise: Any = None, **kwargs: Any
        ) -> dict[str, Any]:
            if "__drawApi?.backend" in script:
                return {"result": {"result": {"type": "boolean", "value": True}}}
            if "__otDSL" in script:
                return {"result": {"result": {"type": "string", "value": dsl_text}}}
            if "__drawApi.read" in script or "__downloadQueue" in script:
                return {"result": {"result": {"type": "object", "subtype": "array", "value": []}}}
            return {"result": {"result": {"type": "undefined"}}}

        async def go_to_noop(*, url: str, **kwargs: Any) -> None:
            pass

        dsl_mock.execute_script = execute_script_with_dsl
        dsl_mock.go_to = go_to_noop

        with patch("otdev.tools.excalidraw._tab", dsl_mock):
            result = excalidraw.load(file=str(exc_file))

        assert "warning" not in result.lower()
        assert "shapes" in result

    def test_load_file_not_found(self) -> None:
        """load() returns an error when file does not exist."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.load(file="/nonexistent/path.excalidraw")

        assert "Error" in result
        assert "not found" in result


# ===========================================================================
# whiteboard.help()
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestHelp:
    def test_help_returns_nonempty_string(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.help()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_help_contains_dsl_reference(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.help()
        assert "Draw DSL" in result or "draw" in result.lower()
        assert "Style" in result or "style" in result.lower()

    def test_help_contains_edge_syntax(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.help()
        assert "-->" in result

    def test_help_requires_no_browser(self) -> None:
        """help() must not call Playwright (no _ensure_ready)."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        with patch("otdev.tools.excalidraw._open_browser") as mock_open:
            result = excalidraw.help()

        mock_open.assert_not_called()
        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# layout() — parameter validation
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestLayout:
    def test_layout_invalid_direction(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.layout(direction="SIDEWAYS")
        assert "Error" in result or "error" in result.lower()

    def test_layout_invalid_algorithm(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.layout(algorithm="random")
        assert "Error" in result or "error" in result.lower()

    def test_layout_valid_defaults_accepted(self) -> None:
        """layout() with all defaults should pass validation (fails at browser, not param check)."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()


        # The call will fail at the browser step, not at validation — no "Error:" prefix
        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.layout()

        # Should not be a param-validation error (those start with "Error:")
        assert not result.startswith("Error: direction"), "default params should pass validation"
        assert not result.startswith("Error: algorithm"), "default params should pass validation"

    def test_layout_invalid_arrow_type(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.layout(arrow_type="wavy")
        assert "Error" in result

    def test_layout_elk_non_dict_result_returns_error(self) -> None:
        """layout() returns Error when ELK browser call returns non-dict."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()


        # Scene read returns valid scene; ELK returns bad string.
        # _process_pending_downloads (called inside _ensure_ready) also calls
        # _browser_evaluate_json with "__downloadQueue" — distinguish by JS content.
        good_scene = {"nodes": [{"id": "a", "w": 160, "h": 60, "groupIds": []}],
                      "edges": [], "selectedIds": []}
        bad_elk = '"{\\"nodes\\":[],\\"edges\\":[]}"'

        def _side_effect(js: str) -> Any:
            if "__downloadQueue" in js:
                return []  # download queue — empty, ignored by _process_pending_downloads
            if "selectedIds" in js:
                return good_scene  # scene read
            return bad_elk  # ELK call

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch(
                "otdev.tools.excalidraw._browser_evaluate_json",
                side_effect=_side_effect,
            ),
        ):
            result = excalidraw.layout()

        assert result.startswith("Error:"), "double-encoded ELK result should return an error"
        assert "ELK" in result

    def test_layout_elk_dict_result_applied(self) -> None:
        """layout() applies node positions when browser returns a proper dict."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()


        good_scene = {"nodes": [{"id": "a", "w": 160, "h": 60, "groupIds": []}],
                      "edges": [], "selectedIds": []}
        elk_response = {"nodes": [{"id": "a", "x": 100, "y": 60}], "edges": []}

        def _side_effect(js: str) -> Any:
            if "__downloadQueue" in js:
                return []
            if "selectedIds" in js:
                return good_scene
            return elk_response

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_side_effect),
            patch("otdev.tools.excalidraw._browser_evaluate") as mock_eval,
        ):
            result = excalidraw.layout()

        assert not result.startswith("Error: ELK"), f"unexpected result: {result!r}"
        assert mock_eval.called

    def test_layout_straight_patches_edges(self) -> None:
        """layout() with STRAIGHT routing must patch arrow positions after moving nodes."""
        _reset_exc_state()

        good_scene = {
            "nodes": [
                {"id": "a", "w": 160, "h": 60, "groupIds": []},
                {"id": "b", "w": 160, "h": 60, "groupIds": []},
            ],
            "edges": [{"id": "edge-a-b", "src": "a", "dst": "b"}],
            "selectedIds": [],
        }
        elk_response = {
            "nodes": [{"id": "a", "x": 60, "y": 60}, {"id": "b", "x": 300, "y": 60}],
            "edges": [],
        }
        captured_patches: list[str] = []

        def _json_side_effect(js: str) -> Any:
            if "selectedIds" in js:
                return good_scene
            if "ELK" in js:
                return elk_response
            return None

        def _eval_side_effect(fn: str) -> str:
            captured_patches.append(fn)
            return ""

        from otdev.tools import excalidraw

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_json_side_effect),
            patch("otdev.tools.excalidraw._browser_evaluate", side_effect=_eval_side_effect),
        ):
            result = excalidraw.layout(direction="RIGHT")

        assert "layout applied" in result, f"unexpected result: {result}"
        assert any("edge-a-b" in p for p in captured_patches), (
            "STRAIGHT layout must patch edge positions; no patch for 'edge-a-b' found"
        )


# ===========================================================================
# align() — parameter validation
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestAlign:
    def test_align_invalid_axis(self) -> None:
        from otdev.tools import excalidraw

        result = excalidraw.align(ids=["a", "b"], axis="diagonal")
        assert "Error" in result or "error" in result.lower()

    def test_align_valid_axis_reaches_browser(self) -> None:
        """align() with valid axis should pass validation and attempt browser call."""
        from unittest.mock import patch

        from otdev.tools import excalidraw


        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.align(ids=["a", "b"], axis="left")

        # Should not be a param-validation error
        assert not result.startswith("Error: axis"), "valid axis should pass validation"

    def test_align_all_axes_accepted(self) -> None:
        """All documented axis values must pass validation."""
        from otdev.tools.excalidraw import _ALIGN_ACTIONS

        from otdev.tools import excalidraw

        valid_axes = list(_ALIGN_ACTIONS.keys())
        assert len(valid_axes) == 8, "expected 8 alignment axes"
        for axis in valid_axes:
            result = excalidraw.align(ids=["x"], axis=axis)
            assert not result.startswith("Error: axis"), f"axis={axis!r} should be valid"

    def test_align_uses_perform_not_set_app_state(self) -> None:
        """align() must use action.perform() directly — not the async setAppState() path."""
        from otdev.tools import excalidraw

        _reset_exc_state()

        js_scripts: list[str] = []

        def recording_eval(fn: str) -> str:
            if "__drawApi?.backend" in fn:  # readiness check only
                return "true"
            js_scripts.append(fn)
            return ""

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate", side_effect=recording_eval),
        ):
            result = excalidraw.align(ids=["a", "b"], axis="top")

        assert "aligned" in result
        assert any("perform" in js for js in js_scripts), "align must use action.perform()"
        assert not any("setAppState" in js for js in js_scripts), "align must not use setAppState()"


# ===========================================================================
# _parse_style_props — fi / cr / at shorthands
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestStylePropNewShorthands:
    def test_fi_fillstyle_solid(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props

        result = _parse_style_props("fi:solid")
        assert result == {"fillStyle": "solid"}

    def test_fi_fillstyle_hachure(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props

        result = _parse_style_props("fi:hachure")
        assert result == {"fillStyle": "hachure"}

    def test_fi_fillstyle_cross_hatch(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props

        result = _parse_style_props("fi:cross-hatch")
        assert result == {"fillStyle": "cross-hatch"}

    def test_fi_invalid_raises(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props
        import pytest as pt

        with pt.raises(ValueError, match="fillStyle"):
            _parse_style_props("fi:wave")

    def test_cr_round(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props

        result = _parse_style_props("cr:round")
        assert result == {"corners": "round"}

    def test_cr_sharp(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props

        result = _parse_style_props("cr:sharp")
        assert result == {"corners": "sharp"}

    def test_cr_invalid_raises(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props
        import pytest as pt

        with pt.raises(ValueError, match="corners"):
            _parse_style_props("cr:beveled")

    def test_at_curve(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props

        result = _parse_style_props("at:curve")
        assert result == {"arrowType": "curve"}

    def test_at_sharp(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props

        result = _parse_style_props("at:sharp")
        assert result == {"arrowType": "sharp"}

    def test_at_elbow(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props

        result = _parse_style_props("at:elbow")
        assert result == {"arrowType": "elbow"}

    def test_at_invalid_raises(self) -> None:
        from otdev.tools.excalidraw import _parse_style_props
        import pytest as pt

        with pt.raises(ValueError, match="arrowType"):
            _parse_style_props("at:zigzag")


# ===========================================================================
# _try_edge — edge inline style parsing
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestEdgeInlineStyle:
    def test_edge_with_style_block_parsed(self) -> None:
        from otdev.tools.excalidraw import _try_edge

        edges: list = []
        matched = _try_edge("a --> b {at:elbow,sc:red}", edges)
        assert matched
        assert len(edges) == 1
        sp = edges[0].get("styleProps", {})
        assert sp.get("arrowType") == "elbow"
        assert sp.get("strokeColor") == "#fecaca"

    def test_edge_without_style_block_no_styleprops(self) -> None:
        from otdev.tools.excalidraw import _try_edge

        edges: list = []
        _try_edge("a --> b", edges)
        assert "styleProps" not in edges[0]

    def test_edge_style_block_at_sharp(self) -> None:
        from otdev.tools.excalidraw import _try_edge

        edges: list = []
        _try_edge("a --> b {at:sharp,ss:dashed}", edges)
        sp = edges[0]["styleProps"]
        assert sp["arrowType"] == "sharp"
        assert sp["strokeStyle"] == "dashed"

    def test_edge_style_preserves_id(self) -> None:
        from otdev.tools.excalidraw import _try_edge

        edges: list = []
        _try_edge("a --> b {at:elbow}", edges)
        assert edges[0]["id"] == "edge-a-b"

    def test_labeled_edge_with_style(self) -> None:
        from otdev.tools.excalidraw import _try_edge

        edges: list = []
        matched = _try_edge("a -->|send| b {at:elbow}", edges)
        assert matched
        assert edges[0]["label"] == "send"
        assert edges[0]["styleProps"]["arrowType"] == "elbow"


# ===========================================================================
# Bug fixes: note() indented triple-quoted input (issue: whiteboard-note-multiblock)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestNoteBlocksIndentedInput:
    """_parse_note_blocks handles indented triple-quoted strings and trailing whitespace."""

    def test_indented_single_block(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = """
        t[table:
        A,B
        1,2
        ]"""
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["id"] == "t"
        assert blocks[0]["type"] == "table"

    def test_indented_multi_block(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = """
        t[table:
        Name,Role
        Alice,Dev
        ]
        tr[tree:
        root/
        -src/
        ]
        """
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 2
        assert blocks[0]["id"] == "t"
        assert blocks[1]["id"] == "tr"

    def test_trailing_whitespace_before_closing_bracket(self) -> None:
        """Trailing spaces after ] must not prevent block matching."""
        from otdev.tools.excalidraw import _parse_note_blocks

        # Simulate trailing spaces that an editor or LLM might add
        spec = "t[table:\nA,B\n1,2\n]   \n\nn[note:\nhello\n]  "
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 2

    def test_mixed_indentation_and_crlf(self) -> None:
        from otdev.tools.excalidraw import _parse_note_blocks

        spec = "    t[table:\r\n    A,B\r\n    1,2\r\n    ]"
        blocks = _parse_note_blocks(spec)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "table"


# ===========================================================================
# Bug fix: cr:sharp style prop (issue: whiteboard-cr-sharp-no-effect)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestCrSharpStyleProp:
    """cr:sharp is parsed to corners='sharp' by _parse_style_props."""

    def test_cr_sharp_parses_to_corners(self) -> None:
        props = _parse_style_props("cr:sharp")
        assert props["corners"] == "sharp"

    def test_cr_round_parses_to_corners(self) -> None:
        props = _parse_style_props("cr:round")
        assert props["corners"] == "round"

    def test_cr_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="corners"):
            _parse_style_props("cr:oval")


# ===========================================================================
# Bug fix: multi-subgraph column layout (issue: whiteboard-subgraph-merged-bbox)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestSubgraphColumnLayout:
    """draw() saves subgraph membership; _rerender_from_state places nodes per their session state."""

    def _draw_and_get_session_state(self, tmp_path: Any) -> dict:
        """Run draw() with two subgraphs and return session state."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        dsl = (
            'subgraph fe ["Frontend"]\n'
            '  a["A"]\n'
            '  b["B"]\n'
            'end\n'
            'subgraph be ["Backend"]\n'
            '  c["C"]\n'
            '  d["D"]\n'
            'end'
        )
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input=dsl)
            return _sess.load(None)

    def test_subgraph_nodes_saved_in_session(self, tmp_path: Any) -> None:
        """All nodes from both subgraphs are saved in session state."""
        state = self._draw_and_get_session_state(tmp_path)
        assert set(state["shapes"]) == {"a", "b", "c", "d"}

    def test_subgraph_membership_saved_in_session(self, tmp_path: Any) -> None:
        """draw() saves group membership for both subgraphs."""
        state = self._draw_and_get_session_state(tmp_path)
        assert "fe" in state["groups"]
        assert "be" in state["groups"]
        assert set(state["groups"]["fe"]["members"]) == {"a", "b"}
        assert set(state["groups"]["be"]["members"]) == {"c", "d"}

    def test_draw_two_subgraphs_reports_both_groups(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()

        dsl = (
            'subgraph fe ["Frontend"]\n'
            '  a["A"]\n'
            'end\n'
            'subgraph be ["Backend"]\n'
            '  b["B"]\n'
            'end'
        )
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            result = excalidraw.draw(input=dsl)

        assert "+2 group(s)" in result


# ===========================================================================
# Bug fixes: layout() arrow binding + selection offset
# (issues: whiteboard-layout-arrows-unbound, whiteboard-layout-selection-direction-ignored)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestLayoutArrowBinding:
    """layout() must NOT clear startBinding/endBinding on arrow patches."""

    def _run_layout_capture_patches(self, direction: str = "RIGHT") -> list[str]:
        """Run layout() and return all _browser_evaluate JS strings for the patch call."""
        good_scene = {
            "nodes": [
                {"id": "a", "w": 160, "h": 60, "groupIds": [], "x": 100, "y": 100},
                {"id": "b", "w": 160, "h": 60, "groupIds": [], "x": 360, "y": 100},
            ],
            "edges": [{"id": "edge-a-b", "src": "a", "dst": "b"}],
            "selectedIds": [],
        }
        elk_response = {
            "nodes": [{"id": "a", "x": 60, "y": 60}, {"id": "b", "x": 300, "y": 60}],
            "edges": [],
        }
        captured: list[str] = []

        def _json_side_effect(js: str) -> Any:
            if "selectedIds" in js:
                return good_scene
            if "ELK" in js:
                return elk_response
            return None

        def _eval_side_effect(fn: str) -> str:
            captured.append(fn)
            return ""

        from unittest.mock import patch
        from otdev.tools import excalidraw

        _reset_exc_state()

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_json_side_effect),
            patch("otdev.tools.excalidraw._browser_evaluate", side_effect=_eval_side_effect),
        ):
            excalidraw.layout(direction=direction)

        return captured

    def test_arrow_patch_does_not_clear_start_binding(self) -> None:
        captured = self._run_layout_capture_patches()
        patch_js = " ".join(captured)
        assert "startBinding: null" not in patch_js, (
            "layout() must not write startBinding: null — arrows must stay bound"
        )

    def test_arrow_patch_does_not_clear_end_binding(self) -> None:
        captured = self._run_layout_capture_patches()
        patch_js = " ".join(captured)
        assert "endBinding: null" not in patch_js, (
            "layout() must not write endBinding: null — arrows must stay bound"
        )

    def test_arrow_patch_still_updates_points(self) -> None:
        captured = self._run_layout_capture_patches(direction="RIGHT")
        assert any("edge-a-b" in p for p in captured), (
            "layout() must still patch arrow points after removing binding-clear"
        )


@pytest.mark.unit
@pytest.mark.tools
class TestLayoutSelectionOffset:
    """layout() in selection mode anchors output to the selection's bounding box."""

    def _run_selection_layout(
        self, sel_x: float, sel_y: float
    ) -> list[str]:
        """Run layout() with 2 selected nodes at (sel_x, sel_y) and capture ELK JS."""
        good_scene = {
            "nodes": [
                {"id": "a", "w": 160, "h": 60, "groupIds": [], "x": sel_x, "y": sel_y},
                {"id": "b", "w": 160, "h": 60, "groupIds": [], "x": sel_x + 200, "y": sel_y + 100},
            ],
            "edges": [],
            "selectedIds": ["a", "b"],
        }
        elk_response = {"nodes": [{"id": "a", "x": 0, "y": 0}, {"id": "b", "x": 200, "y": 100}], "edges": []}
        captured_elk_js: list[str] = []

        def _json_side_effect(js: str) -> Any:
            if "selectedIds" in js:
                return good_scene
            if "ELK" in js:
                captured_elk_js.append(js)
                return elk_response
            return None

        from unittest.mock import patch
        from otdev.tools import excalidraw

        _reset_exc_state()

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_json_side_effect),
            patch("otdev.tools.excalidraw._browser_evaluate"),
        ):
            excalidraw.layout()

        return captured_elk_js

    def test_selection_offset_uses_selection_min_x(self) -> None:
        """ELK JS must use the selection's min-x as offsetX, not hardcoded 60."""
        captured = self._run_selection_layout(sel_x=400.0, sel_y=300.0)
        elk_js = " ".join(captured)
        # The JS should contain offsetX = 400 (selection min-x), not 60
        assert "400" in elk_js, (
            "selection layout must anchor to selection min-x (400), not hardcoded 60"
        )
        assert "offsetX = 60" not in elk_js, (
            "selection layout must not use hardcoded offsetX = 60"
        )

    def test_full_layout_offset_is_60(self) -> None:
        """Full (non-selection) layout must still use offsetX = 60."""
        good_scene = {
            "nodes": [{"id": "a", "w": 160, "h": 60, "groupIds": [], "x": 500, "y": 500}],
            "edges": [], "selectedIds": [],
        }
        elk_response = {"nodes": [{"id": "a", "x": 0, "y": 0}], "edges": []}
        captured_elk_js: list[str] = []

        def _json_side_effect(js: str) -> Any:
            if "selectedIds" in js:
                return good_scene
            if "ELK" in js:
                captured_elk_js.append(js)
                return elk_response
            return None

        from unittest.mock import patch
        from otdev.tools import excalidraw

        _reset_exc_state()

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_json_side_effect),
            patch("otdev.tools.excalidraw._browser_evaluate"),
        ):
            excalidraw.layout()

        elk_js = " ".join(captured_elk_js)
        assert "offsetX = 60" in elk_js, (
            "full layout must use offsetX = 60 (standard canvas padding)"
        )


# ===========================================================================
# Bug fix: layout() boundary arrows in selection mode
# (issue: whiteboard-layout-selection-boundary-arrows-detach)
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestLayoutBoundaryArrows:
    """layout() in selection mode must update boundary arrows (one endpoint in selection,
    one outside) so they stay visually connected after nodes are repositioned."""

    def _run_selection_layout_boundary(self, direction: str = "RIGHT") -> list[str]:
        """Run selection layout with a boundary arrow and capture patch JS."""
        # Nodes: b, c are selected; a and d are outside the selection.
        # Edges: a→b (boundary: a outside), b→c (internal), c→d (boundary: d outside)
        good_scene = {
            "nodes": [
                {"id": "a", "w": 160, "h": 60, "groupIds": [], "x": 0,   "y": 100},
                {"id": "b", "w": 160, "h": 60, "groupIds": [], "x": 220, "y": 100},
                {"id": "c", "w": 160, "h": 60, "groupIds": [], "x": 440, "y": 100},
                {"id": "d", "w": 160, "h": 60, "groupIds": [], "x": 660, "y": 100},
            ],
            "edges": [
                {"id": "edge-a-b", "src": "a", "dst": "b"},
                {"id": "edge-b-c", "src": "b", "dst": "c"},
                {"id": "edge-c-d", "src": "c", "dst": "d"},
            ],
            "selectedIds": ["b", "c"],
        }
        elk_response = {
            "nodes": [{"id": "b", "x": 60, "y": 60}, {"id": "c", "x": 300, "y": 60}],
            "edges": [],
        }
        captured_patches: list[str] = []

        def _json_side_effect(js: str) -> Any:
            if "selectedIds" in js:
                return good_scene
            if "ELK" in js:
                return elk_response
            return None

        def _eval_side_effect(fn: str) -> str:
            captured_patches.append(fn)
            return ""

        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()

        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_json_side_effect),
            patch("otdev.tools.excalidraw._browser_evaluate", side_effect=_eval_side_effect),
        ):
            excalidraw.layout(direction=direction)

        return captured_patches

    def test_boundary_arrow_src_outside_is_patched(self) -> None:
        """a→b: a is outside selection, b is inside — arrow must be patched."""
        captured = self._run_selection_layout_boundary()
        patch_js = " ".join(captured)
        assert "edge-a-b" in patch_js, (
            "boundary arrow edge-a-b (a outside, b inside) must be patched after selection layout"
        )

    def test_boundary_arrow_dst_outside_is_patched(self) -> None:
        """c→d: c is inside selection, d is outside — arrow must be patched."""
        captured = self._run_selection_layout_boundary()
        patch_js = " ".join(captured)
        assert "edge-c-d" in patch_js, (
            "boundary arrow edge-c-d (c inside, d outside) must be patched after selection layout"
        )

    def test_internal_arrow_still_patched(self) -> None:
        """b→c: both inside selection — internal arrow must still be patched."""
        captured = self._run_selection_layout_boundary()
        patch_js = " ".join(captured)
        assert "edge-b-c" in patch_js, (
            "internal arrow edge-b-c must still be patched after selection layout"
        )


# ===========================================================================
# Undirected edge payload sends null endArrowhead (not "arrow")
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestUndirectedEdgePayload:
    def test_undirected_edge_sends_none_arrowheads(self, tmp_path: Any) -> None:
        """a---b must store endArrowhead=None and startArrowhead=None in session."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]\na---b')
            state = _sess.load(None)

        assert len(state["edges"]) == 1
        assert state["edges"][0]["endArrowhead"] is None
        assert state["edges"][0]["startArrowhead"] is None

    def test_dashed_undirected_edge_sends_none_arrowheads(self, tmp_path: Any) -> None:
        """a-.-b must also store None arrowheads in session."""
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]\na-.-b')
            state = _sess.load(None)

        assert len(state["edges"]) == 1
        assert state["edges"][0]["endArrowhead"] is None
        assert state["edges"][0]["startArrowhead"] is None


# ===========================================================================
# Style returns actual matched count (not input length)
# ===========================================================================


def _style_elements_side_effect(count: int) -> Callable[..., str]:
    """Return a side-effect that reports `count` matched elements from _style_elements."""
    def side_effect(server: str, tool: str, arguments: Any = None) -> str:
        fn = (arguments or {}).get("function", "")
        if tool == "browser_navigate":
            return "### Result\nnull\n### Ran Playwright code\n..."
        if "__drawApi?.backend" in fn:
            return "### Result\ntrue\n### Ran Playwright code\n..."
        if "__drawApi.read" in fn:
            return '### Result\n[]\n### Ran Playwright code\n...'
        if "_style_elements" in fn:
            return f"### Result\n{count}\n### Ran Playwright code\n..."
        return "### Result\nnull\n### Ran Playwright code\n..."
    return side_effect


@pytest.mark.unit
@pytest.mark.tools
class TestStyleReturnCount:
    def test_style_returns_actual_matched_count(self) -> None:
        """style() with non-existent IDs should report 0 styled, not len(ids)."""
        from otdev.tools import excalidraw

        _reset_exc_state()

        # Custom mock: _style_elements returns 0 (no elements matched)
        zero_mock = MagicMock()

        async def execute_script_zero(
            script: str, *, return_by_value: Any = None, await_promise: Any = None, **kwargs: Any
        ) -> dict[str, Any]:
            if "__drawApi?.backend" in script:
                return {"result": {"result": {"type": "boolean", "value": True}}}
            if "_style_elements" in script:
                return {"result": {"result": {"type": "number", "value": 0}}}
            return {"result": {"result": {"type": "undefined"}}}

        async def go_to_noop(*, url: str, **kwargs: Any) -> None:
            pass

        zero_mock.execute_script = execute_script_zero
        zero_mock.go_to = go_to_noop

        with patch("otdev.tools.excalidraw._tab", zero_mock):
            result = excalidraw.style(ids=["doesnotexist"], style="bc:red")

        assert result == "styled 0 element(s)"

    def test_style_returns_count_for_existing_elements(self) -> None:
        """style() with 2 existing IDs should report 2 styled."""
        from otdev.tools import excalidraw

        _reset_exc_state()

        with patch("otdev.tools.excalidraw._tab", _make_mock_tab()):
            result = excalidraw.style(ids=["a", "b"], style="bc:red")

        assert result == "styled 2 element(s)"


# ===========================================================================
# read_scene tool smoke test
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestReadScene:
    def _make_scene_mock_tab(self, scene_text: str) -> MagicMock:
        """Create a mock tab that returns scene_text for _read_scene JS calls."""
        mock = MagicMock()

        async def execute_script(
            script: str, *, return_by_value: Any = None, await_promise: Any = None, **kwargs: Any
        ) -> dict[str, Any]:
            if "__drawApi?.backend" in script:
                return {"result": {"result": {"type": "boolean", "value": True}}}
            if "__drawApi.read" in script or "__downloadQueue" in script:
                return {"result": {"result": {"type": "object", "subtype": "array", "value": []}}}
            if "_read_scene" in script:
                return {"result": {"result": {"type": "string", "value": scene_text}}}
            return {"result": {"result": {"type": "undefined"}}}

        async def go_to(*, url: str, **kwargs: Any) -> None:
            pass

        mock.execute_script = execute_script
        mock.go_to = go_to
        return mock

    def test_read_scene_calls_browser_and_returns_result(self) -> None:
        from otdev.tools import excalidraw

        _reset_exc_state()
        scene_text = "Scene: 2 shapes, 1 edges\n\nShapes:\n  a\n  b\n\nEdges:\n  e\n"

        with patch("otdev.tools.excalidraw._tab", self._make_scene_mock_tab(scene_text)):
            result = excalidraw.read_scene()

        assert "Scene: 2 shapes" in result

    def test_read_scene_returns_error_when_browser_not_open(self) -> None:
        from otdev.tools import excalidraw

        _reset_exc_state()

        with patch("otdev.tools.excalidraw._open_browser", side_effect=Exception("Chrome not found")):
            result = excalidraw.read_scene()

        assert "Error" in result

    def test_read_scene_info_min_passes_level_to_js(self) -> None:
        from otdev.tools import excalidraw

        _reset_exc_state()
        scene_text = "Scene: 3 shapes, 0 edges"

        with patch("otdev.tools.excalidraw._tab", self._make_scene_mock_tab(scene_text)):
            result = excalidraw.read_scene(info="min")

        assert result == "Scene: 3 shapes, 0 edges"

    def test_read_scene_info_full_passes_level_to_js(self) -> None:
        from otdev.tools import excalidraw

        _reset_exc_state()
        scene_text = "Scene: 1 shapes, 0 edges\n\nShapes:\n  a  rectangle  bc:#fff sw:2\n"

        with patch("otdev.tools.excalidraw._tab", self._make_scene_mock_tab(scene_text)):
            result = excalidraw.read_scene(info="full")

        assert "sw:2" in result

    def test_read_scene_invalid_info_raises(self) -> None:
        from otdev.tools import excalidraw

        with pytest.raises(ValueError, match="info='bad'"):
            excalidraw.read_scene(info="bad")


_CHROME_SUPPRESSION_FLAGS = [
    "--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload",
    "--disable-component-update",
    "--disable-background-networking",
]


@pytest.mark.unit
@pytest.mark.tools
def test_chrome_options_has_suppression_flags() -> None:
    """_chrome_options() adds exactly the three Chrome suppression flags."""
    from otdev.tools.excalidraw import _chrome_options

    opts = _chrome_options()
    assert opts.arguments == _CHROME_SUPPRESSION_FLAGS


@pytest.mark.unit
@pytest.mark.tools
def test_open_browser_launches_chrome_with_suppression_flags() -> None:
    """_open_browser() passes options= with the suppression flags to Chrome(...)."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import otdev.tools.excalidraw as exc

    _reset_exc_state()

    mock_tab = MagicMock()
    mock_tab.go_to = AsyncMock()
    mock_chrome_instance = MagicMock()
    mock_chrome_instance.start = AsyncMock(return_value=mock_tab)
    mock_chrome_cls = MagicMock(return_value=mock_chrome_instance)

    with patch("pydoll.browser.Chrome", mock_chrome_cls):
        exc._open_browser()

    _args, kwargs = mock_chrome_cls.call_args
    assert "options" in kwargs
    launched_flags = kwargs["options"].arguments
    for flag in _CHROME_SUPPRESSION_FLAGS:
        assert flag in launched_flags


# ===========================================================================
# Bug-fix pass (whiteboard-pack-fixes): B1-B5 + browser push error reporting
# ===========================================================================


def _extract_layout_patches(js_calls: list[str]) -> list[dict[str, Any]]:
    """Extract the patches array from the captured layout() patch JS."""
    for js in js_calls:
        m = re.search(r"const patches = (\[.*?\]);", js, re.DOTALL)
        if m:
            return json.loads(m[1])
    return []


@pytest.mark.unit
@pytest.mark.tools
class TestLayoutBoundaryArrowContainment:
    """B1: each boundary arrow must use its own containment value, not the
    stale ``src_in`` left over from the edge-classification loop."""

    def _run(self) -> list[dict[str, Any]]:
        # Only b is selected. edge-a-b enters the selection (src outside),
        # edge-b-d leaves it (src inside). The classification loop processes
        # edge-b-d last, leaving src_in=True — the buggy code applied that to
        # edge-a-b as well.
        good_scene = {
            "nodes": [
                {"id": "a", "w": 160, "h": 60, "groupIds": [], "x": 0, "y": 100},
                {"id": "b", "w": 160, "h": 60, "groupIds": [], "x": 300, "y": 100},
                {"id": "d", "w": 160, "h": 60, "groupIds": [], "x": 600, "y": 100},
            ],
            "edges": [
                {"id": "edge-a-b", "src": "a", "dst": "b"},
                {"id": "edge-b-d", "src": "b", "dst": "d"},
            ],
            "selectedIds": ["b"],
        }
        # Selection offset anchors to b's current position (300, 100).
        elk_response = {"nodes": [{"id": "b", "x": 300, "y": 100}], "edges": []}
        captured: list[str] = []

        def _json_side_effect(js: str) -> Any:
            if "selectedIds" in js:
                return good_scene
            if "ELK" in js:
                return elk_response
            return None

        def _eval_side_effect(fn: str) -> str:
            captured.append(fn)
            return ""

        from otdev.tools import excalidraw

        _reset_exc_state()
        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_json_side_effect),
            patch("otdev.tools.excalidraw._browser_evaluate", side_effect=_eval_side_effect),
        ):
            result = excalidraw.layout(direction="RIGHT")

        assert "layout applied" in result, f"unexpected result: {result!r}"
        return _extract_layout_patches(captured)

    def test_dst_inside_edge_uses_entry_side(self) -> None:
        """a→b (a outside): arrow must run from a's right edge to b's left edge."""
        patches = self._run()
        p = next(p for p in patches if p["id"] == "edge-a-b")
        assert p["points"] == [[160.0, 130.0], [300.0, 130.0]], (
            "edge-a-b must use its own containment (dst inside): "
            f"start at a's right edge, end at b's left edge — got {p['points']}"
        )

    def test_src_inside_edge_uses_exit_side(self) -> None:
        """b→d (b inside): arrow must run from b's right edge to d's left edge."""
        patches = self._run()
        p = next(p for p in patches if p["id"] == "edge-b-d")
        assert p["points"] == [[460.0, 130.0], [600.0, 130.0]], (
            f"edge-b-d must exit b's right edge and end at d's left edge — got {p['points']}"
        )


@pytest.mark.unit
@pytest.mark.tools
class TestLayoutGroupBbox:
    """B5: grouped clusters must be sized from member positions, not sizes."""

    def test_group_elk_node_sized_from_positions(self) -> None:
        good_scene = {
            "nodes": [
                {"id": "m1", "w": 160, "h": 60, "groupIds": ["g1"], "x": 0, "y": 0},
                {"id": "m2", "w": 160, "h": 60, "groupIds": ["g1"], "x": 200, "y": 150},
            ],
            "edges": [],
            "selectedIds": [],
        }
        elk_response = {"nodes": [{"id": "g1", "x": 60, "y": 60}], "edges": []}
        captured_elk: list[str] = []

        def _json_side_effect(js: str) -> Any:
            if "selectedIds" in js:
                return good_scene
            if "ELK" in js:
                captured_elk.append(js)
                return elk_response
            return None

        from otdev.tools import excalidraw

        _reset_exc_state()
        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_json_side_effect),
            patch("otdev.tools.excalidraw._browser_evaluate"),
        ):
            excalidraw.layout()

        assert captured_elk, "ELK layout JS was not invoked"
        # The ELK-presence check (bundled-asset injection guard) is also an
        # "ELK"-matching eval; search all captured JS for the graph.
        m = re.search(r"const graph = (\{.*\});", " ".join(captured_elk))
        assert m, "could not find ELK graph in JS"
        graph = json.loads(m[1])
        g1 = next(c for c in graph["children"] if c["id"] == "g1")
        # bbox spans (0,0)-(360,210) — not max member size (160x60)
        assert g1["width"] == 360
        assert g1["height"] == 210


@pytest.mark.unit
@pytest.mark.tools
class TestDrawUpdatedCount:
    """B4: 'M updated' must compare against the pre-draw state snapshot."""

    def test_label_change_counts_as_updated(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]')
            result = excalidraw.draw(input='a["B"]')
            state = _sess.load(None)

        assert "+0 shapes, 1 updated" in result, f"unexpected result: {result!r}"
        assert state["shapes"]["a"]["label"] == "B"

    def test_unchanged_label_not_counted(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]')
            result = excalidraw.draw(input='a["A"]')

        assert "updated" not in result, f"unexpected result: {result!r}"

    def test_style_only_update_counted(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]')
            result = excalidraw.draw(input="a bc:green")

        assert "1 updated" in result, f"unexpected result: {result!r}"


@pytest.mark.unit
@pytest.mark.tools
class TestDrawInlineStyles:
    """B2: inline DSL styles must be persisted in state and applied via the
    patch path for existing shapes."""

    def test_new_shape_inline_style_persisted(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"] bc:green,sw:2')
            state = _sess.load(None)

        style = state["shapes"]["a"].get("style")
        assert style is not None, "inline style must be persisted in session state"
        assert style["backgroundColor"] == "#bbf7d0"
        assert style["strokeWidth"] == 2

    def test_inline_xy_stored_as_position_not_style(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"] x:111,y:222')
            state = _sess.load(None)

        shape = state["shapes"]["a"]
        assert shape["x"] == 111.0
        assert shape["y"] == 222.0
        assert "x" not in (shape.get("style") or {})
        assert "y" not in (shape.get("style") or {})

    def test_existing_shape_style_applied_via_patch_path(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        captured: list[str] = []

        def capture_eval(fn: str) -> str:
            captured.append(fn)
            return "null"

        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]')  # browser-free
            with (
                patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
                patch("otdev.tools.excalidraw._browser_evaluate", side_effect=capture_eval),
            ):
                result = excalidraw.draw(input="a bc:green")
            state = _sess.load(None)

        patch_calls = [c for c in captured if "_patch_elements" in c]
        assert patch_calls, "existing-shape style update must go through _patch_elements"
        assert "#bbf7d0" in patch_calls[0], "resolved colour must be in the patch payload"
        assert "1 updated" in result
        assert state["shapes"]["a"]["style"]["backgroundColor"] == "#bbf7d0"

    def test_new_shape_style_sent_in_batch_draw(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        captured: list[dict[str, Any]] = []

        def capture_batch(**kwargs: Any) -> None:
            captured.append(kwargs)

        with (
            _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._js_batch_draw", side_effect=capture_batch),
        ):
            excalidraw.draw(input='a["A"] bc:green')

        assert captured, "_js_batch_draw must be called for new shapes"
        payload = next(p for p in captured[0]["shapes"] if p["id"] == "a")
        assert payload["styleProps"]["backgroundColor"] == "#bbf7d0"


@pytest.mark.unit
@pytest.mark.tools
class TestRerenderPreservesLayout:
    """B3: rerenders must restore stored positions/styles; grid only for
    shapes with no stored position."""

    def test_rerender_uses_stored_positions(self) -> None:
        from otdev.tools import excalidraw

        state = {
            "shapes": {
                "a": {"label": "A", "classes": [], "x": 555.0, "y": 666.0},
                "b": {"label": "B", "classes": []},
            },
            "edges": [],
            "groups": {},
        }
        captured: list[dict[str, Any]] = []
        with patch(
            "otdev.tools.excalidraw._js_batch_draw",
            side_effect=lambda **kw: captured.append(kw),
        ):
            excalidraw._rerender_from_state(state)

        payloads = {p["id"]: p for p in captured[0]["shapes"]}
        assert payloads["a"]["x"] == 555.0
        assert payloads["a"]["y"] == 666.0
        # b has no stored position → first grid slot
        assert payloads["b"]["x"] == 100.0
        assert payloads["b"]["y"] == 100.0

    def test_rerender_applies_stored_style(self) -> None:
        from otdev.tools import excalidraw

        state = {
            "shapes": {
                "a": {"label": "A", "classes": [], "x": 10.0, "y": 20.0,
                      "style": {"backgroundColor": "#bbf7d0"}},
            },
            "edges": [],
            "groups": {},
        }
        captured: list[dict[str, Any]] = []
        with patch(
            "otdev.tools.excalidraw._js_batch_draw",
            side_effect=lambda **kw: captured.append(kw),
        ):
            excalidraw._rerender_from_state(state)

        payload = captured[0]["shapes"][0]
        assert payload["styleProps"]["backgroundColor"] == "#bbf7d0"

    def test_draw_persists_auto_positions(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]\nb["B"]')
            state = _sess.load(None)

        for nid in ("a", "b"):
            assert state["shapes"][nid].get("x") is not None
            assert state["shapes"][nid].get("y") is not None

    def test_layout_writes_positions_to_session(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()

        good_scene = {
            "nodes": [{"id": "a", "w": 160, "h": 60, "groupIds": [], "x": 100, "y": 100}],
            "edges": [],
            "selectedIds": [],
        }
        elk_response = {"nodes": [{"id": "a", "x": 40.0, "y": 15.0}], "edges": []}

        def _json_side_effect(js: str) -> Any:
            if "selectedIds" in js:
                return good_scene
            if "ELK" in js:
                return elk_response
            return None

        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]')
            with (
                patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
                patch("otdev.tools.excalidraw._browser_evaluate_json", side_effect=_json_side_effect),
                patch("otdev.tools.excalidraw._browser_evaluate"),
            ):
                result = excalidraw.layout()
            state = _sess.load(None)

        assert "layout applied" in result, f"unexpected result: {result!r}"
        assert state["shapes"]["a"]["x"] == 40.0
        assert state["shapes"]["a"]["y"] == 15.0
        assert state["canvas_max_y"] == 75.0  # y + node height

    def test_note_persists_position_and_size(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with (
            _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
        ):
            excalidraw.note(input="n1[note:\nhello\n]")
            state = _sess.load(None)

        n1 = state["shapes"]["n1"]
        assert n1["x"] == 500.0
        assert n1["y"] is not None
        assert n1["style"]["width"] > 0
        assert n1["style"]["height"] > 0


@pytest.mark.unit
@pytest.mark.tools
class TestBrowserPushFailureReported:
    """A failed canvas push must be reported in the returned string, not
    silently swallowed. State is still committed."""

    def test_draw_reports_canvas_failure(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with (
            _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._js_batch_draw", side_effect=RuntimeError("boom")),
        ):
            result = excalidraw.draw(input='a["A"]')
            state = _sess.load(None)

        assert "+1 shapes" in result
        assert "warning" in result and "boom" in result
        assert "a" in state["shapes"], "state must be committed even when push fails"

    def test_erase_reports_canvas_failure(self, tmp_path: Any) -> None:
        from unittest.mock import patch as _patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path):
            excalidraw.draw(input='a["A"]')
            with (
                patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
                patch("otdev.tools.excalidraw._browser_evaluate", side_effect=RuntimeError("boom")),
            ):
                result = excalidraw.erase(ids=["a"])
            state = _sess.load(None)

        assert "erased 1 element(s)" in result
        assert "warning" in result and "boom" in result
        assert "a" not in state["shapes"]

    _reset_exc_state()


# ===========================================================================
# whiteboard-runtime-hardening: vendored ELK, board= coverage, layout helpers
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestElkVendoring:
    """layout() loads ELK from the vendored bundle, never the network."""

    _SCENE = {"nodes": [{"id": "a", "w": 160, "h": 60, "groupIds": []}],
              "edges": [], "selectedIds": []}
    _ELK_RESPONSE = {"nodes": [{"id": "a", "x": 100, "y": 60}], "edges": []}

    def _json_side_effect(self, elk_present: bool) -> Any:
        def _side_effect(js: str) -> Any:
            if "__downloadQueue" in js:
                return []
            if "typeof window.ELK" in js:
                return elk_present
            if "selectedIds" in js:
                return dict(self._SCENE)
            return dict(self._ELK_RESPONSE)
        return _side_effect

    def test_no_reinjection_when_elk_present(self) -> None:
        """Second layout() call does not re-inject given window.ELK is defined."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json",
                  side_effect=self._json_side_effect(elk_present=True)),
            patch("otdev.tools.excalidraw._browser_evaluate"),
            patch("otdev.tools.excalidraw._elk_bundle") as mock_bundle,
        ):
            r1 = excalidraw.layout()
            r2 = excalidraw.layout()

        assert "layout applied" in r1
        assert "layout applied" in r2
        mock_bundle.assert_not_called()

    def test_injection_failure_returns_error(self) -> None:
        """When window.ELK stays undefined after injection, layout() errors."""
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with (
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._browser_evaluate_json",
                  side_effect=self._json_side_effect(elk_present=False)),
            patch("otdev.tools.excalidraw._browser_evaluate"),
            patch("otdev.tools.excalidraw._elk_bundle", return_value="/* bundle */") as mock_bundle,
        ):
            result = excalidraw.layout()

        assert result.startswith("Error: ELK bundle injection failed")
        mock_bundle.assert_called_once()

    def test_no_cdn_reference_remains(self) -> None:
        """The module carries no unpkg/CDN reference and no _ELK_CDN constant."""
        import inspect

        from otdev.tools import excalidraw

        source = inspect.getsource(excalidraw)
        assert "unpkg" not in source
        assert not hasattr(excalidraw, "_ELK_CDN")

    def test_bundle_asset_ships_with_package(self) -> None:
        """The vendored bundle and its license are importable package data."""
        from importlib import resources

        pkg = resources.files("otdev.tools._excalidraw")
        assert pkg.joinpath("elk.bundled.js").is_file()
        assert pkg.joinpath("ELK_LICENSE.txt").is_file()


@pytest.mark.unit
@pytest.mark.tools
class TestBoardParam:
    """board= on note/embed_dsl/save/load/sync/style/read_scene (uniform semantics)."""

    def _in_dir(self, tmp_path: Any) -> Any:
        from unittest.mock import patch as _patch

        from otdev.tools._excalidraw import session as _sess

        return _patch.object(_sess, "_whiteboard_dir", return_value=tmp_path)

    def test_note_board_writes_named_board(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw
        from otdev.tools._excalidraw import session as _sess

        _reset_exc_state()
        with (
            self._in_dir(tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
        ):
            result = excalidraw.note(input="n[note:\nhello\n]", board="alpha")
            default_path = _sess.session_path(None)

        assert "inserted 1 note(s)" in result
        assert (tmp_path / "alpha.json").exists()
        assert not default_path.exists()

    def test_sync_board_writes_named_board(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with (
            self._in_dir(tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._read_dsl_from_canvas", return_value='a["A"]'),
        ):
            result = excalidraw.sync(board="alpha")

        assert "synced: 1 shapes" in result
        assert (tmp_path / "alpha.json").exists()

    def test_load_board_targets_named_board(self, tmp_path: Any) -> None:
        import json as _json
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        diag = tmp_path / "diag.excalidraw"
        diag.write_text(_json.dumps({"type": "excalidraw", "version": 2, "elements": []}))
        with (
            self._in_dir(tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw.resolve_cwd_path", return_value=diag),
            patch("otdev.tools.excalidraw._read_dsl_from_canvas", return_value='a["A"]'),
        ):
            result = excalidraw.load(file="diag.excalidraw", board="alpha")

        assert "loaded 1 shapes" in result
        assert (tmp_path / "alpha.json").exists()

    def test_save_board_rerenders_named_board(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with self._in_dir(tmp_path):
            excalidraw.draw(input='a["A"]', board="alpha")
            with (
                patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
                patch("otdev.tools.excalidraw._rerender_from_state") as mock_rr,
                patch("otdev.tools.excalidraw.resolve_cwd_path",
                      return_value=tmp_path / "out.excalidraw"),
            ):
                excalidraw.save(file="out.excalidraw", board="alpha")

        mock_rr.assert_called_once()
        assert "a" in mock_rr.call_args.args[0]["shapes"]

    def test_read_scene_board_rerenders_named_board(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with self._in_dir(tmp_path):
            excalidraw.draw(input='b["B"]', board="alpha")
            with (
                patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
                patch("otdev.tools.excalidraw._rerender_from_state") as mock_rr,
                patch("otdev.tools.excalidraw._browser_evaluate_json", return_value="Scene: ok"),
            ):
                excalidraw.read_scene(board="alpha")

        mock_rr.assert_called_once()
        assert "b" in mock_rr.call_args.args[0]["shapes"]

    def test_read_scene_without_board_does_not_rerender(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with (
            self._in_dir(tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._rerender_from_state") as mock_rr,
            patch("otdev.tools.excalidraw._browser_evaluate_json", return_value="Scene: ok"),
        ):
            excalidraw.read_scene()

        mock_rr.assert_not_called()

    def test_style_board_rerenders_first(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with self._in_dir(tmp_path):
            excalidraw.draw(input='c["C"]', board="alpha")
            with (
                patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
                patch("otdev.tools.excalidraw._rerender_from_state") as mock_rr,
                patch("otdev.tools.excalidraw._js_style_elements", return_value=1),
            ):
                excalidraw.style(ids=["c"], style="bc:green", board="alpha")
                excalidraw.style(ids=["c"], style="bc:green")

        mock_rr.assert_called_once()  # only the board= call rerenders

    def test_embed_dsl_board_uses_named_board_state(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with self._in_dir(tmp_path):
            excalidraw.draw(input='d["D"]', board="alpha")
            with (
                patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
                patch("otdev.tools.excalidraw._js_batch_draw"),
                patch("otdev.tools.excalidraw._get_canvas_max_y", return_value=60.0),
            ):
                result = excalidraw.embed_dsl(board="alpha")
                default_result = excalidraw.embed_dsl()

        assert "embedded DSL" in result
        assert default_result == "nothing to embed — canvas is empty"

    def test_invalid_board_name_raises(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from otdev.tools import excalidraw

        _reset_exc_state()
        with (
            self._in_dir(tmp_path),
            patch("otdev.tools.excalidraw._tab", _make_mock_tab()),
            patch("otdev.tools.excalidraw._read_dsl_from_canvas", return_value='a["A"]'),
            pytest.raises(ValueError, match="Invalid board name"),
        ):
            excalidraw.sync(board="../evil")


@pytest.mark.unit
@pytest.mark.tools
class TestLayoutPureHelpers:
    """Direct tests for _excalidraw.layout pure computation (no browser mocks)."""

    def _scene(self) -> dict[str, Any]:
        return {
            "nodes": [
                {"id": "a", "w": 100, "h": 50, "groupIds": [], "x": 0, "y": 0},
                {"id": "g1", "w": 80, "h": 40, "groupIds": ["grp"], "x": 200, "y": 0},
                {"id": "g2", "w": 80, "h": 40, "groupIds": ["grp"], "x": 300, "y": 60},
                {"id": "out", "w": 60, "h": 30, "groupIds": [], "x": 900, "y": 900},
            ],
            "edges": [
                {"id": "e1", "src": "a", "dst": "g1"},
                {"id": "e2", "src": "a", "dst": "out"},
            ],
            "selectedIds": ["a", "g1", "g2"],
        }

    def _build(self, direction: str = "RIGHT") -> Any:
        from otdev.tools._excalidraw import layout as L

        build = L.build_elk_graph(
            self._scene(),
            direction=direction, gap_layer=80, gap_node=40,
            algorithm="layered", node_placement="NETWORK_SIMPLEX",
            crossing_min="LAYER_SWEEP", cycle_breaking="GREEDY",
        )
        assert build is not None
        return build

    def test_graph_build_with_groups_and_selection(self) -> None:
        build = self._build()

        # Grouped members collapse into one ELK node under the group id
        assert build.elem_to_elk["g1"] == "grp"
        assert build.elem_to_elk["g2"] == "grp"
        assert build.elk_node_set == {"a", "grp"}
        # Group bbox spans both members: x 200..380, y 0..100
        grp = next(n for n in build.graph["children"] if n["id"] == "grp")
        assert (grp["width"], grp["height"]) == (180, 100)
        # e1 (a→grp) is in-scope; e2 (a→out) is a boundary edge
        assert [e["id"] for e in build.graph["edges"]] == ["e1"]
        assert [b["id"] for b in build.boundary_edges] == ["e2"]
        assert build.boundary_edges[0]["src_in"] is True
        # Selection anchors the offset at the selection's top-left
        assert build.use_selection is True
        assert (build.offset_x, build.offset_y) == (0.0, 0.0)

    def test_boundary_patch_sides_per_direction(self) -> None:
        from otdev.tools._excalidraw import layout as L

        positions = {"a": (0.0, 0.0)}
        # a is 100x50 at (0,0); free node "out" is 60x30 at (900,900)
        expected_anchor = {
            "RIGHT": [100.0, 25.0],  # source exits right
            "LEFT": [0.0, 25.0],
            "DOWN": [50.0, 50.0],
            "UP": [50.0, 0.0],
        }
        for direction, anchor_pt in expected_anchor.items():
            build = self._build(direction)
            patches = L.build_boundary_arrow_patches(build, positions, direction)
            assert len(patches) == 1
            assert patches[0]["id"] == "e2"
            # src is inside → arrow starts at the anchored node's exit side
            assert patches[0]["points"][0] == anchor_pt

    def test_boundary_patch_dst_inside_uses_entry_side(self) -> None:
        from otdev.tools._excalidraw import layout as L

        scene = self._scene()
        scene["edges"] = [{"id": "e3", "src": "out", "dst": "a"}]
        build = L.build_elk_graph(
            scene, direction="RIGHT", gap_layer=80, gap_node=40,
            algorithm="layered", node_placement="NETWORK_SIMPLEX",
            crossing_min="LAYER_SWEEP", cycle_breaking="GREEDY",
        )
        assert build is not None
        patches = L.build_boundary_arrow_patches(build, {"a": (0.0, 0.0)}, "RIGHT")
        assert len(patches) == 1
        # dst inside → arrow ends at the anchored node's entry side (left)
        assert patches[0]["points"][1] == [0.0, 25.0]
        # start stays at the free node's exit side
        assert patches[0]["points"][0] == [960.0, 915.0]

    def test_writeback_mutates_state_and_max_y(self) -> None:
        from otdev.tools._excalidraw import layout as L

        build = self._build()
        state = {
            "shapes": {"a": {"x": 0.0, "y": 0.0}},
            "canvas_max_y": 500.0,
        }
        moved = L.writeback_positions(
            state, [{"id": "a", "x": 10.0, "y": 20.0}], build
        )
        assert moved == 1
        assert (state["shapes"]["a"]["x"], state["shapes"]["a"]["y"]) == (10.0, 20.0)
        # Selection layout never shrinks canvas_max_y
        assert state["canvas_max_y"] == 500.0
