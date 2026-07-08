"""Shared fixtures for the otdev test suites (unit + integration).

Currently hosts the arch tool pack helpers shared between
``tests/otdev/unit/tools/test_arch.py`` and
``tests/otdev/integration/tools/test_arch.py``:

- ``ARCH_FIXTURES``: path to the arch fixture directory.
- ``fake_render_engine``: monkeypatches ``otdev.tools.arch._execute_render_engine``
  with a fake that writes a placeholder SVG instead of shelling out to ``d2``.
- ``build_arch_workbook``: builds an ``.xlsx`` workbook from a
  ``{sheet_name: rows}`` mapping (first row of each sheet is the header).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ARCH_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "arch"

_PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
)


@pytest.fixture
def fake_render_engine(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace ``otdev.tools.arch._execute_render_engine`` with a fake render.

    The fake writes a placeholder SVG to ``render_context["paths"]["output"]``
    and reports success, so ``arch.generate()`` runs without the real ``d2``
    CLI. The default fake is installed as soon as the fixture is requested;
    call the returned installer with ``svg="..."`` to swap in a custom SVG
    payload for the rendered outputs.
    """
    from otdev.tools import arch

    def _install(svg: str = _PLACEHOLDER_SVG) -> None:
        def _fake_render(
            *, target_config: object, render_context: dict[str, Any]
        ) -> tuple[bool, dict[str, Any]]:
            _ = target_config
            Path(str(render_context["paths"]["output"])).write_text(svg, encoding="utf-8")
            return True, {"command": "fake-render", "target": "solution", "engine": "d2"}

        monkeypatch.setattr(arch, "_execute_render_engine", _fake_render)

    _install()
    return _install


@pytest.fixture
def build_arch_workbook() -> Callable[[Path, dict[str, list[list[Any]]]], Path]:
    """Build an ``.xlsx`` workbook at ``path`` from ``{sheet_name: rows}``.

    Sheets are created in mapping order; each sheet's first row is its
    header. Returns the workbook path.
    """
    openpyxl = pytest.importorskip("openpyxl")

    def _build(path: Path, sheets: dict[str, list[list[Any]]]) -> Path:
        workbook = openpyxl.Workbook()
        first_sheet = True
        for sheet_name, rows in sheets.items():
            if first_sheet:
                worksheet = workbook.active
                worksheet.title = sheet_name
                first_sheet = False
            else:
                worksheet = workbook.create_sheet(sheet_name)
            for row in rows:
                worksheet.append(row)
        workbook.save(path)
        workbook.close()
        return path

    return _build
