"""Tests for bundled default snippet templates."""

from __future__ import annotations

import pytest
import yaml


def _load_default_snippets() -> dict:
    """Load bundled snippet definitions from the package template."""
    from ot.paths import get_global_templates_dir

    snippets_file = get_global_templates_dir() / "snippets.yaml"
    data = yaml.safe_load(snippets_file.read_text())
    return data["snippets"]


@pytest.mark.unit
@pytest.mark.core
def test_default_snippets_prioritize_internal_discovery_helpers() -> None:
    """Bundled snippets include universal OneTool discovery and proxy helpers."""
    snippets = _load_default_snippets()

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
    snippets = _load_default_snippets()

    assert "rg" not in snippets
    assert "rg_count" not in snippets
    assert "gh" not in snippets


@pytest.mark.unit
@pytest.mark.core
def test_default_snippets_expand_to_valid_python_with_quoted_values() -> None:
    """Bundled snippets safely quote parameter values in generated Python."""
    from ot.config.models import OneToolConfig, SnippetDef, SnippetParam
    from ot.shortcuts.snippets import ParsedSnippet, expand_snippet

    raw_snippets = _load_default_snippets()
    snippets = {
        name: SnippetDef(
            description=raw.get("description", ""),
            params={
                param_name: SnippetParam(**param_def)
                for param_name, param_def in (raw.get("params") or {}).items()
            },
            body=raw["body"],
        )
        for name, raw in raw_snippets.items()
    }
    config = OneToolConfig(snippets=snippets)
    sample_values = {
        "category": 'note "quoted"',
        "count": "2",
        "depth": "2",
        "file": 'docs/"quoted".pdf',
        "focus": 'edge "cases"',
        "format": 'markdown "quoted"',
        "glob": '*.py "quoted"',
        "i": "true",
        "info": 'default "quoted"',
        "lib": '/vercel/"next"',
        "links": "true",
        "limit": "3",
        "max": "100",
        "meta": "true",
        "mode": 'semantic "quoted"',
        "name": 'github "quoted"',
        "offset": "1",
        "output_dir": 'out/"quoted"',
        "p": 'key="value"',
        "packages": 'react,"express"',
        "path": 'docs/"quoted".md',
        "pattern": 'git"hub',
        "provider": 'openai "quoted"',
        "q": 'alpha "quoted"|beta',
        "schema": 'prices as {"item": "price"}',
        "tech": 'python "quoted"',
        "topic": 'projects/"quoted"',
        "url": 'https://en.wikipedia.org/wiki/Anthropic?x="y"',
    }

    for name, snippet_def in snippets.items():
        params = {
            param_name: sample_values[param_name]
            for param_name in snippet_def.params
            if param_name in sample_values
        }

        expanded = expand_snippet(
            ParsedSnippet(name=name, params=params, raw=f":{name}"),
            config,
        )

        compile(expanded, f"<snippet {name}>", "exec")
