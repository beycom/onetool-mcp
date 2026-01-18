"""Unit tests for shortcuts (aliases and snippets)."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
def test_resolve_alias_no_aliases() -> None:
    """Verify resolve_alias returns code unchanged when no aliases."""
    from ot.config import OneToolConfig
    from ot.shortcuts import resolve_alias

    config = OneToolConfig()  # Empty config with no aliases
    code = "brave.web_search(query='test')"

    result = resolve_alias(code, config)
    assert result == code


@pytest.mark.unit
@pytest.mark.core
def test_resolve_alias_basic() -> None:
    """Verify resolve_alias replaces simple alias."""
    from ot.config import OneToolConfig
    from ot.shortcuts import resolve_alias

    config = OneToolConfig(alias={"ws": "brave.web_search"})
    code = "ws(query='test')"

    result = resolve_alias(code, config)
    assert result == "brave.web_search(query='test')"


@pytest.mark.unit
@pytest.mark.core
def test_resolve_alias_no_partial_match() -> None:
    """Verify resolve_alias doesn't match partial names."""
    from ot.config import OneToolConfig
    from ot.shortcuts import resolve_alias

    config = OneToolConfig(alias={"ws": "brave.web_search"})

    # aws should not be matched by ws
    code = "aws(query='test')"
    result = resolve_alias(code, config)
    assert result == "aws(query='test')"

    # obj.ws should not be matched (preceded by .)
    code = "obj.ws(query='test')"
    result = resolve_alias(code, config)
    assert result == "obj.ws(query='test')"


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_basic() -> None:
    """Verify parse_snippet extracts name and params."""
    from ot.shortcuts import parse_snippet

    result = parse_snippet("$wsq q=AI topic=ML")

    assert result.name == "wsq"
    assert result.params == {"q": "AI", "topic": "ML"}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_no_params() -> None:
    """Verify parse_snippet works with no parameters."""
    from ot.shortcuts import parse_snippet

    result = parse_snippet("$simple")

    assert result.name == "simple"
    assert result.params == {}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_multiline() -> None:
    """Verify parse_snippet handles multiline format."""
    from ot.shortcuts import parse_snippet

    code = """$wsq
q: What is AI?
topic: Machine Learning"""

    result = parse_snippet(code)

    assert result.name == "wsq"
    assert result.params == {"q": "What is AI?", "topic": "Machine Learning"}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_invalid() -> None:
    """Verify parse_snippet raises for invalid input."""
    from ot.shortcuts import parse_snippet

    with pytest.raises(ValueError, match="must start with"):
        parse_snippet("not_a_snippet")


@pytest.mark.unit
@pytest.mark.core
def test_expand_snippet_basic() -> None:
    """Verify expand_snippet renders Jinja2 template with params."""
    from ot.config import OneToolConfig, SnippetDef
    from ot.shortcuts import expand_snippet, parse_snippet

    config = OneToolConfig(
        snippets={
            "test_snip": SnippetDef(
                description="Test snippet",
                body='demo.call(name="{{ name }}")',
            )
        }
    )

    parsed = parse_snippet("$test_snip name=Alice")
    result = expand_snippet(parsed, config)

    assert result == 'demo.call(name="Alice")'


@pytest.mark.unit
@pytest.mark.core
def test_expand_snippet_with_defaults() -> None:
    """Verify expand_snippet uses default param values."""
    from ot.config import OneToolConfig, SnippetDef, SnippetParam
    from ot.shortcuts import expand_snippet, parse_snippet

    config = OneToolConfig(
        snippets={
            "count_snip": SnippetDef(
                description="Count snippet",
                params={"count": SnippetParam(default=5)},
                body="demo.items(count={{ count }})",
            )
        }
    )

    # Without providing count - should use default
    parsed = parse_snippet("$count_snip")
    result = expand_snippet(parsed, config)

    assert result == "demo.items(count=5)"


@pytest.mark.integration
@pytest.mark.core
def test_snippets_dir_loads_default_library() -> None:
    """Verify snippets_dir loads snippets from resources/config/snippets.yaml."""
    import tempfile
    from pathlib import Path

    import yaml

    from ot.config.loader import load_config
    from ot.shortcuts import expand_snippet, parse_snippet

    # Find the default snippets library
    project_root = Path(__file__).parent.parent.parent.parent
    snippets_yaml = project_root / "resources" / "config" / "snippets.yaml"

    if not snippets_yaml.exists():
        pytest.skip("Default snippets library not found")

    # Create minimal test config that references the snippets library
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": [str(snippets_yaml)],
                }
            )
        )

        config = load_config(config_path)

    # Verify snippets from default library are loaded
    assert "ot_find" in config.snippets, "Default snippet 'ot_find' not loaded"
    assert "brv_research" in config.snippets, (
        "Default snippet 'brv_research' not loaded"
    )
    assert "rg_todos" in config.snippets, "Default snippet 'rg_todos' not loaded"

    # Verify we can expand a snippet from the library
    parsed = parse_snippet("$ot_find pattern=search")
    result = expand_snippet(parsed, config)

    assert 'ot.tools(pattern="search"' in result


@pytest.mark.integration
@pytest.mark.core
def test_snippets_dir_inline_overrides_external() -> None:
    """Verify inline snippets override external snippets from snippets_dir."""
    import tempfile
    from pathlib import Path

    import yaml

    from ot.config.loader import load_config

    # Find the default snippets library
    project_root = Path(__file__).parent.parent.parent.parent
    snippets_yaml = project_root / "resources" / "config" / "snippets.yaml"

    if not snippets_yaml.exists():
        pytest.skip("Default snippets library not found")

    # Create config with both snippets_dir and inline snippets
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create config with inline snippet that has same name as one in default lib
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "snippets_dir": [str(snippets_yaml)],
                    "snippets": {
                        "ot_find": {"body": "custom.override()"},
                        "my_inline": {"body": "inline.snippet()"},
                    },
                }
            )
        )

        config = load_config(config_path)

    # Verify inline snippet exists and takes precedence
    assert "ot_find" in config.snippets
    assert config.snippets["ot_find"].body == "custom.override()"

    # Verify other inline snippets are present
    assert "my_inline" in config.snippets

    # Verify external snippets that weren't overridden are still present
    assert "brv_research" in config.snippets
