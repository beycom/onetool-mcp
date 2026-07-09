"""Integration tests for the whiteboard (excalidraw) tool pack.

Drives a real browser via Playwright against the live Excalidraw canvas.
Requires: Playwright MCP server running + network access to excalidraw.com.

Run:
    uv run pytest tests/otdev/integration/tools/test_excalidraw.py -m "integration and tools" -v
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.network, pytest.mark.tools, pytest.mark.pydoll]


@pytest.fixture(scope="session", autouse=True)
def _browser_session():
    """Close the whiteboard browser after this module's tests finish."""
    yield
    from otdev.tools import excalidraw

    with contextlib.suppress(Exception):
        excalidraw.close()


@pytest.fixture(autouse=True)
def _clean_canvas():
    """Open a fresh whiteboard before each test; clear canvas after."""
    from otdev.tools import excalidraw

    result = excalidraw.open()
    if "Error" in result:
        pytest.fail(f"whiteboard open() failed (playwright not available?): {result}")
    yield
    with contextlib.suppress(Exception):
        excalidraw.clear()


def test_draw_and_read_scene() -> None:
    """draw() adds shapes and edges incrementally; read_scene() reflects the canvas."""
    from otdev.tools import excalidraw

    # Draw two shapes
    result = excalidraw.draw(input='p["P"]; q["Q"]')
    assert "shape" in result, f"draw() returned: {result!r}"

    # Incremental: draw a third shape and an edge
    excalidraw.draw(input='r["R"]; p-->q')
    scene = excalidraw.read_scene()
    assert "p" in scene and "q" in scene and "r" in scene, f"shapes missing: {scene}"
    assert "1 edges" in excalidraw.read_scene(info="min"), "edge not in canvas"

    # Elbow edge type is preserved in canvas
    excalidraw.draw(input='a["A"] x:50,y:50; b["B"] x:400,y:300; a --> b {at:elbow}')
    scene_full = excalidraw.read_scene(info="full")
    edges_section = scene_full.split("Edges:")[1] if "Edges:" in scene_full else ""
    assert "at:elbow" in edges_section, f"elbow arrow not in scene: {edges_section}"


def test_erase_style_and_clear() -> None:
    """erase() removes targets and dangling edges; style() updates properties; clear() empties canvas."""
    from otdev.tools import excalidraw

    excalidraw.draw(input='keep["Keep"]; gone["Gone"]; a["A"]; b["B"]; a-->b')

    # Erase one shape — others remain
    result = excalidraw.erase(ids=["gone"])
    assert "erased" in result, f"erase() returned: {result!r}"
    scene = excalidraw.read_scene()
    assert "gone" not in scene, "'gone' still present after erase"
    assert "keep" in scene, "'keep' accidentally removed"

    # Erase a node that has an edge — edge removed too
    result = excalidraw.erase(ids=["a"])
    assert "dangling" in result, "expected dangling-edge message"
    assert "0 edges" in excalidraw.read_scene(info="min"), "edge persists after node erase"

    # Style a remaining shape
    excalidraw.style(ids=["keep"], style="bc:#ff0000")
    box_line = next(
        (ln for ln in excalidraw.read_scene().splitlines() if ln.strip().startswith("keep")),
        None,
    )
    assert box_line and "bc:#ff0000" in box_line, f"style not applied: {box_line}"

    # Clear empties the whole canvas
    excalidraw.clear()
    assert "0 shapes, 0 edges" in excalidraw.read_scene(info="min"), "canvas not empty after clear()"


@pytest.mark.slow
def test_save_and_load(tmp_path: Path) -> None:
    """save() writes a valid Excalidraw JSON; load() restores shapes and Python state."""
    from otdev.tools import excalidraw

    excalidraw.draw(input='x["X"]; y["Y"]; x-->y')
    save_path = str(tmp_path / "diagram.excalidraw")
    result = excalidraw.save(file=save_path)
    assert "saved" in result.lower(), f"save() returned: {result!r}"

    saved = json.loads(Path(save_path).read_text())
    assert saved.get("type") == "excalidraw"
    assert "elements" in saved
    assert any(e.get("id") == "__otDSL" for e in saved["elements"]), "DSL not embedded in saved file"

    # Clear canvas + Python state, then reload
    excalidraw.clear()
    result = excalidraw.load(file=save_path)
    assert "loaded" in result.lower(), f"load() returned: {result!r}"
    assert "2 shapes" in result, f"shapes not restored: {result!r}"

    from otdev.tools._excalidraw import session as _session

    state = _session.load()
    assert "x" in state["shapes"] and "y" in state["shapes"], "Python state not restored after load"
