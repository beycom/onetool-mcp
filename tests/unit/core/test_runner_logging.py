"""Unit tests for runner logging metadata."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_prepare_command_records_snippet_metadata() -> None:
    """Snippet preparation keeps original command separate from expanded code."""
    from ot.config import OneToolConfig, SnippetDef
    from ot.executor.runner import prepare_command

    config = OneToolConfig(
        snippets={
            "test_snip": SnippetDef(
                description="Test snippet",
                body='ot.help(query="{{ topic }}")',
            )
        }
    )

    with patch("ot.config.get_config", return_value=config):
        prepared = prepare_command(":test_snip topic=logging")

    assert prepared.error is None
    assert prepared.original == ":test_snip topic=logging"
    assert prepared.command_type == "snippet"
    assert prepared.snippet == "test_snip"
    assert prepared.code == "ot.help(query='logging')"
    assert prepared.prepared_lines == 1
    assert prepared.prepared_length == len(prepared.code)
