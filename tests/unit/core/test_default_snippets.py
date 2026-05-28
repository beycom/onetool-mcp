"""Tests for bundled default snippet templates."""

from __future__ import annotations

import pytest
import yaml


@pytest.mark.unit
@pytest.mark.core
def test_default_snippets_prioritize_internal_discovery_helpers() -> None:
    """Bundled snippets include universal OneTool discovery and proxy helpers."""
    from ot.paths import get_global_templates_dir

    snippets_file = get_global_templates_dir() / "snippets.yaml"
    data = yaml.safe_load(snippets_file.read_text())
    snippets = data["snippets"]

    for name in ["help", "tool", "servers", "server_on", "server_off", "reload", "status"]:
        assert name in snippets

    assert "ot.help(" in snippets["help"]["body"]
    assert "ot.tool_info(" in snippets["tool"]["body"]
    assert "ot.servers(" in snippets["servers"]["body"]
    assert "ot_servers.enable(" in snippets["server_on"]["body"]
    assert "ot_servers.disable(" in snippets["server_off"]["body"]


@pytest.mark.unit
@pytest.mark.core
def test_default_snippets_exclude_project_specific_helpers() -> None:
    """Repo-specific ripgrep and GitHub helpers do not ship as bundled defaults."""
    from ot.paths import get_global_templates_dir

    snippets_file = get_global_templates_dir() / "snippets.yaml"
    data = yaml.safe_load(snippets_file.read_text())
    snippets = data["snippets"]

    assert "rg" not in snippets
    assert "rg_count" not in snippets
    assert "gh" not in snippets
