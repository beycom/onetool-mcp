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
def test_parse_snippet_strips_quotes() -> None:
    """Verify parse_snippet strips outer quotes from values."""
    from ot.shortcuts import parse_snippet

    # Double quotes
    result = parse_snippet('$pkg packages="react, express"')
    assert result.name == "pkg"
    assert result.params == {"packages": "react, express"}

    # Single quotes
    result = parse_snippet("$pkg packages='react, express'")
    assert result.name == "pkg"
    assert result.params == {"packages": "react, express"}

    # Mixed quoted and unquoted
    result = parse_snippet('$test name="Alice" count=5')
    assert result.params == {"name": "Alice", "count": "5"}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_multiline_strips_quotes() -> None:
    """Verify parse_snippet strips outer quotes in multiline format."""
    from ot.shortcuts import parse_snippet

    code = '''$pkg
packages: "react, express"
limit: 10'''

    result = parse_snippet(code)
    assert result.name == "pkg"
    assert result.params == {"packages": "react, express", "limit": "10"}


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
def test_include_loads_snippets_library() -> None:
    """Verify include: loads snippets from bundled defaults via three-tier fallback."""
    import tempfile
    from pathlib import Path

    import yaml

    from ot.config.loader import load_config
    from ot.paths import get_bundled_config_dir
    from ot.shortcuts import expand_snippet, parse_snippet

    # Verify bundled snippets library exists
    try:
        bundled_dir = get_bundled_config_dir()
        snippets_yaml = bundled_dir / "snippets.yaml"
    except FileNotFoundError:
        pytest.skip("Bundled snippets library not found")

    if not snippets_yaml.exists():
        pytest.skip("Bundled snippets library not found")

    # Create minimal test config that includes snippets via three-tier fallback
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "inherit": "none",  # Disable inheritance to test include fallback
                    "include": ["snippets.yaml"],  # Falls back to bundled
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
def test_include_inline_overrides_included() -> None:
    """Verify inline snippets override snippets from include: files."""
    import tempfile
    from pathlib import Path

    import yaml

    from ot.config.loader import load_config
    from ot.paths import get_bundled_config_dir

    # Find the default snippets library from bundled defaults
    try:
        bundled_dir = get_bundled_config_dir()
        snippets_yaml = bundled_dir / "snippets.yaml"
    except FileNotFoundError:
        pytest.skip("Bundled snippets library not found")

    if not snippets_yaml.exists():
        pytest.skip("Bundled snippets library not found")

    # Create config with both include and inline snippets
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".onetool"
        config_dir.mkdir()

        # Create config with inline snippet that has same name as one in included lib
        config_path = config_dir / "ot-serve.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "include": [str(snippets_yaml)],
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
