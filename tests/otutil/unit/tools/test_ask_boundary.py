"""ctx.ask / mem.ask route through ot_llm.transform, inheriting its boundary (p22 2.5).

The untrusted-data system message lives in ot_llm.transform() (tested in test_llm.py).
These regression guards ensure both askers keep routing through transform() so a
future refactor that bypasses it is caught.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.tools
def test_ctx_ask_path_routes_to_ot_llm_transform() -> None:
    """The services LLM hook used by ctx.ask() is ot_llm.transform()."""
    from ot.services import get_services
    from ottools import ot_llm

    spy = MagicMock(return_value="answer")
    services = get_services()
    previous = services.llm_service
    try:
        with patch.object(ot_llm, "transform", spy):
            services.register_llm(ot_llm.transform)
            services.llm_transform(data="stored content", prompt="q?")
        spy.assert_called_once()
        assert spy.call_args.kwargs["data"] == "stored content"
    finally:
        services.llm_service = previous


@pytest.mark.unit
@pytest.mark.tools
def test_mem_ask_routes_to_ot_llm_transform() -> None:
    """mem.ask() calls ot_llm.transform() with the retrieved content as data."""
    import importlib

    # The submodule name `ask` is shadowed by the exported `ask` function in the
    # package namespace, so pull the module object from sys.modules directly.
    mem_ask = importlib.import_module("otutil.tools._mem.ask")

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1, "t", "stored content")

    spy = MagicMock(return_value="1. answer")
    with patch.object(mem_ask, "_get_connection", return_value=mock_conn), patch(
        "ottools.ot_llm.transform", spy
    ):
        mem_ask.ask(topic="t", q="what?")

    spy.assert_called_once()
    assert spy.call_args.kwargs["data"] == "stored content"
