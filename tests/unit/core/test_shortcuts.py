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

    result = parse_snippet(":wsq q=AI topic=ML")

    assert result.name == "wsq"
    assert result.params == {"q": "AI", "topic": "ML"}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_strips_quotes() -> None:
    """Verify parse_snippet strips outer quotes from values."""
    from ot.shortcuts import parse_snippet

    # Double quotes
    result = parse_snippet(':pkg packages="react, express"')
    assert result.name == "pkg"
    assert result.params == {"packages": "react, express"}

    # Single quotes
    result = parse_snippet(":pkg packages='react, express'")
    assert result.name == "pkg"
    assert result.params == {"packages": "react, express"}

    # Mixed quoted and unquoted
    result = parse_snippet(':test name="Alice" count=5')
    assert result.params == {"name": "Alice", "count": "5"}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_multiline_strips_quotes() -> None:
    """Verify parse_snippet strips outer quotes in multiline format."""
    from ot.shortcuts import parse_snippet

    code = ''':pkg
packages: "react, express"
limit: 10'''

    result = parse_snippet(code)
    assert result.name == "pkg"
    assert result.params == {"packages": "react, express", "limit": "10"}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_underscore_name() -> None:
    """Verify parse_snippet correctly handles underscore snippet names."""
    from ot.shortcuts import parse_snippet

    # Single-line with params
    result = parse_snippet(":rg_count p=def ft=py")
    assert result.name == "rg_count"
    assert result.params == {"p": "def", "ft": "py"}

    # Multi-segment underscore
    result = parse_snippet(":mem_s q=asyncio")
    assert result.name == "mem_s"
    assert result.params == {"q": "asyncio"}

    # No params
    result = parse_snippet(":f_t")
    assert result.name == "f_t"
    assert result.params == {}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_hyphenated_name() -> None:
    """Verify parse_snippet correctly handles hyphenated snippet names (user-defined)."""
    from ot.shortcuts import parse_snippet

    result = parse_snippet(":my-snippet p=def")
    assert result.name == "my-snippet"
    assert result.params == {"p": "def"}

    result = parse_snippet(":a-b-c")
    assert result.name == "a-b-c"
    assert result.params == {}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_equals_in_quoted_value() -> None:
    """Verify parse_snippet handles = inside quoted values without truncating."""
    from ot.shortcuts import parse_snippet

    # = inside double-quoted value
    result = parse_snippet(':rg p="key=value" path=src')
    assert result.params == {"p": "key=value", "path": "src"}

    # = inside single-quoted value
    result = parse_snippet(":rg p='url=https' path=src")
    assert result.params == {"p": "url=https", "path": "src"}

    # Multiple = signs in quoted value
    result = parse_snippet(':rg p="a=b=c" path=src')
    assert result.params == {"p": "a=b=c", "path": "src"}

    # = in first param, no subsequent params
    result = parse_snippet(':rg p="key=val"')
    assert result.params == {"p": "key=val"}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_no_params() -> None:
    """Verify parse_snippet works with no parameters."""
    from ot.shortcuts import parse_snippet

    result = parse_snippet(":simple")

    assert result.name == "simple"
    assert result.params == {}


@pytest.mark.unit
@pytest.mark.core
def test_parse_snippet_multiline() -> None:
    """Verify parse_snippet handles multiline format."""
    from ot.shortcuts import parse_snippet

    code = """:wsq
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

    parsed = parse_snippet(":test_snip name=Alice")
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
    parsed = parse_snippet(":count_snip")
    result = expand_snippet(parsed, config)

    assert result == "demo.items(count=5)"


@pytest.mark.unit
@pytest.mark.core
def test_expand_snippet_prefix_resolution() -> None:
    """Verify expand_snippet resolves abbreviated param names via prefix matching.

    User provides short key 'q'; snippet defines full param 'query'.
    resolve_kwargs resolves q → query (param starts with key).
    """
    from ot.config import OneToolConfig, SnippetDef, SnippetParam
    from ot.shortcuts import expand_snippet, parse_snippet

    config = OneToolConfig(
        snippets={
            "g": SnippetDef(
                description="Search snippet",
                body='ground.search(query="{{ query }}")',
                params={"query": SnippetParam()},
            )
        }
    )

    # Prefix match: 'q' resolves to 'query'
    parsed = parse_snippet(":g q=test")
    result = expand_snippet(parsed, config)
    assert result == 'ground.search(query="test")'


@pytest.mark.unit
@pytest.mark.core
def test_expand_snippet_prefix_resolution_exact_wins() -> None:
    """Verify exact match takes precedence over prefix match."""
    from ot.config import OneToolConfig, SnippetDef, SnippetParam
    from ot.shortcuts import expand_snippet, parse_snippet

    config = OneToolConfig(
        snippets={
            "x": SnippetDef(
                description="Snippet with overlapping params",
                body='demo.call(quality="{{ quality }}", query="{{ query }}")',
                params={
                    "quality": SnippetParam(required=False, default=""),
                    "query": SnippetParam(required=False, default=""),
                },
            )
        }
    )

    # Exact match: 'query' resolves to 'query', not 'quality'
    parsed = parse_snippet(":x query=abc")
    result = expand_snippet(parsed, config)
    assert 'query="abc"' in result
    assert 'quality=""' in result


@pytest.mark.unit
@pytest.mark.core
def test_expand_snippet_prefix_resolution_first_in_order_wins() -> None:
    """Verify first param in YAML definition order wins on ambiguous prefix match."""
    from ot.config import OneToolConfig, SnippetDef, SnippetParam
    from ot.shortcuts import expand_snippet, parse_snippet

    config = OneToolConfig(
        snippets={
            "x": SnippetDef(
                description="Snippet with ambiguous params",
                body='demo.call(quality="{{ quality }}", query="{{ query }}")',
                params={
                    "quality": SnippetParam(required=False, default=""),
                    "query": SnippetParam(required=False, default=""),
                },
            )
        }
    )

    # 'q' is a prefix of both 'quality' and 'query'; first in definition order wins
    parsed = parse_snippet(":x q=abc")
    result = expand_snippet(parsed, config)
    assert 'quality="abc"' in result


@pytest.mark.unit
@pytest.mark.core
def test_expand_snippet_boolean_normalization() -> None:
    """Verify expand_snippet normalizes 'true'/'false' strings to Python booleans for bool params."""
    from ot.config import OneToolConfig, SnippetDef, SnippetParam
    from ot.shortcuts import expand_snippet, parse_snippet

    config = OneToolConfig(
        snippets={
            "wf": SnippetDef(
                description="Fetch URL",
                params={
                    "url": SnippetParam(required=True),
                    "links": SnippetParam(default=False),
                },
                body='wf.fetch(url="{{ url }}", include_links={{ links }})',
            )
        }
    )

    # links=true (YAML style) should render as True (valid Python)
    parsed = parse_snippet(":wf url=http://localhost links=true")
    result = expand_snippet(parsed, config)
    assert "include_links=True" in result

    # links=false (YAML style) should render as False (valid Python)
    parsed = parse_snippet(":wf url=http://localhost links=false")
    result = expand_snippet(parsed, config)
    assert "include_links=False" in result

    # Default (no links param) uses the bool default → False
    parsed = parse_snippet(":wf url=http://localhost")
    result = expand_snippet(parsed, config)
    assert "include_links=False" in result

    # Python-style True also works
    parsed = parse_snippet(":wf url=http://localhost links=True")
    result = expand_snippet(parsed, config)
    assert "include_links=True" in result


@pytest.mark.integration
@pytest.mark.core
def test_include_loads_snippets_library() -> None:
    """Verify include: loads snippets from external file and expands them correctly."""
    import tempfile
    from pathlib import Path

    import yaml

    from ot.config.loader import load_config
    from ot.shortcuts import expand_snippet, parse_snippet

    # Create self-contained test with known snippets (not dependent on external files)
    # Flat structure: .onetool/onetool.yaml with includes relative to .onetool/
    with tempfile.TemporaryDirectory() as tmpdir:
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir(parents=True)

        # Create a test snippets file alongside onetool.yaml
        test_snippets_path = onetool_dir / "test-snippets.yaml"
        test_snippets_path.write_text(
            yaml.dump(
                {
                    "snippets": {
                        "test_find": {
                            "description": "Test find snippet",
                            "body": 'ot.tools(pattern="{{ pattern }}")',
                        },
                        "test_search": {
                            "description": "Test search snippet",
                            "body": 'brave.search(query="{{ q }}")',
                        },
                        "test_todos": {
                            "description": "Test todos snippet",
                            "body": "rg.search(pattern='TODO')",
                        },
                    }
                }
            )
        )

        config_path = onetool_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["test-snippets.yaml"],
                }
            )
        )

        config = load_config(config_path)

    # Verify snippets from include file are loaded
    assert "test_find" in config.snippets, "Snippet 'test_find' not loaded"
    assert "test_search" in config.snippets, "Snippet 'test_search' not loaded"
    assert "test_todos" in config.snippets, "Snippet 'test_todos' not loaded"

    # Verify we can expand a snippet from the library
    parsed = parse_snippet(":test_find pattern=search")
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

    # Create self-contained test with known snippets (not dependent on external files)
    # Flat structure: .onetool/onetool.yaml with includes relative to .onetool/
    with tempfile.TemporaryDirectory() as tmpdir:
        onetool_dir = Path(tmpdir) / ".onetool"
        onetool_dir.mkdir(parents=True)

        # Create a test snippets file alongside onetool.yaml
        test_snippets_path = onetool_dir / "test-snippets.yaml"
        test_snippets_path.write_text(
            yaml.dump(
                {
                    "snippets": {
                        "shared_snippet": {"body": "original.call()"},
                        "external_only": {"body": "external.snippet()"},
                    }
                }
            )
        )

        # Create config with inline snippet that has same name as one in included lib
        config_path = onetool_dir / "onetool.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "version": 2,
                    "include": ["test-snippets.yaml"],
                    "snippets": {
                        "shared_snippet": {"body": "custom.override()"},
                        "my_inline": {"body": "inline.snippet()"},
                    },
                }
            )
        )

        config = load_config(config_path)

    # Verify inline snippet exists and takes precedence over included
    assert "shared_snippet" in config.snippets
    assert config.snippets["shared_snippet"].body == "custom.override()"

    # Verify other inline snippets are present
    assert "my_inline" in config.snippets

    # Verify external snippets that weren't overridden are still present
    assert "external_only" in config.snippets
    assert config.snippets["external_only"].body == "external.snippet()"
