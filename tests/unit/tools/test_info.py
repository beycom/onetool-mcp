"""Unit tests for internal tool functions.

Tests that ot.tools() correctly handles pack.function names,
especially when multiple packs have functions with the same name.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from ot.config import OneToolConfig
from ot.prompts import PromptsConfig
from ot.proxy import ProxyToolInfo

if TYPE_CHECKING:
    from collections.abc import Generator


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def override_config() -> Generator[Any, None, None]:
    """Fixture to temporarily override OneToolConfig."""
    import ot.config.loader

    @contextmanager
    def _override(config: OneToolConfig) -> Generator[None, None, None]:
        old_config = ot.config.loader._config
        try:
            ot.config.loader._config = config
            yield
        finally:
            ot.config.loader._config = old_config

    yield _override


@pytest.fixture
def override_prompts() -> Generator[Any, None, None]:
    """Fixture to temporarily override PromptsConfig."""
    import ot.prompts

    @contextmanager
    def _override(prompts: PromptsConfig) -> Generator[None, None, None]:
        old_prompts = ot.prompts._prompts
        try:
            ot.prompts._prompts = prompts
            yield
        finally:
            ot.prompts._prompts = old_prompts

    yield _override


@pytest.fixture
def mock_proxy_manager() -> MagicMock:
    """Create a mock proxy manager."""
    mock = MagicMock()
    mock.servers = []
    mock.list_tools.return_value = []
    return mock


# ============================================================================
# Tool Discovery Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_tools_returns_correct_signatures_for_same_named_functions() -> None:
    """Verify ot.tools() returns correct info for functions with same name."""
    from ot.meta import tools

    result = tools(pattern="search", info="default")

    # Result is now a list of dicts
    tool_names = [t["name"] for t in result]
    tool_descs = " ".join(t.get("description", "") for t in result)

    # Each pack's search function should have its own signature
    assert "brave.search" in tool_names
    assert "ground.search" in tool_names

    # ground.search should mention Gemini/grounding (non-proxied function)
    assert "Gemini" in tool_descs or "grounding" in tool_descs


@pytest.mark.unit
@pytest.mark.serve
def test_tools_info_levels() -> None:
    """Verify info levels control output verbosity."""
    from ot.meta import tools

    # info="default" - name + description only (default)
    default_output = tools(info="default")
    assert isinstance(default_output, list)
    for tool in default_output:
        assert "name" in tool
        assert "description" in tool
        assert "signature" not in tool
        assert "source" not in tool

    # info="full" - includes source (list function, no signature)
    full_output = tools(info="full")
    assert isinstance(full_output, list)
    has_source = any("source" in t for t in full_output if isinstance(t, dict))
    assert has_source

    # info="min" - names only
    min_output = tools(info="min")
    assert isinstance(min_output, list)
    assert all(isinstance(t, str) for t in min_output)


@pytest.mark.unit
@pytest.mark.serve
def test_tools_pattern_filter_by_pack() -> None:
    """Verify pattern filter works to filter by pack prefix."""
    from ot.meta import tools

    result = tools(pattern="ot.", info="default")
    # Result is a list of dicts
    tool_names = [t["name"] for t in result]

    # Should only have ot pack tools
    assert any(name == "ot.tools" for name in tool_names)
    assert any(name == "ot.packs" for name in tool_names)
    assert any(name == "ot.status" for name in tool_names)

    # Should NOT have other pack tools
    assert not any(name.startswith("brave.") for name in tool_names)


@pytest.mark.unit
@pytest.mark.serve
def test_tool_info_pattern_with_full_info() -> None:
    """Verify tool_info with info=full returns detailed info including signature."""
    from ot.meta import tool_info

    result = tool_info(pattern="ot.tools", info="full")

    # Should return a list with matching tools
    assert isinstance(result, list)
    assert len(result) >= 1

    # Find ot.tools in results
    ottools = [t for t in result if isinstance(t, dict) and t["name"] == "ot.tools"]
    assert len(ottools) == 1
    tool = ottools[0]
    assert "signature" in tool
    assert "source" in tool


@pytest.mark.unit
@pytest.mark.serve
def test_tools_pattern_no_match_returns_empty() -> None:
    """Verify pattern with no matches returns empty list."""
    from ot.meta import tools

    result = tools(pattern="nonexistent_xyz_tool")

    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.unit
@pytest.mark.serve
def test_status_counts_all_tools() -> None:
    """Verify ot.status() counts all tools including duplicates."""
    from ot.meta import status

    result = status()

    # Result is now a dict directly
    assert "registry" in result
    assert "tool_count" in result["registry"]

    # The count should include all tools across packs
    # (not deduplicated by bare name)
    # We have at least 5 "search" functions in different packs
    # so total should be > 30 (rough estimate)
    count = result["registry"]["tool_count"]
    assert count >= 30, f"Expected at least 30 tools, got {count}"


@pytest.mark.unit
@pytest.mark.serve
def test_status_ignores_disabled_proxy_servers() -> None:
    """Disabled proxy server definitions should not degrade runtime status."""
    from pathlib import Path
    from types import SimpleNamespace

    from ot.meta import status

    cfg = SimpleNamespace(
        _config_dir=Path("/tmp/onetool/config"),
        tools_dir=[],
        include=[],
        servers={"disabled": SimpleNamespace(enabled=False)},
        direct=SimpleNamespace(host=SimpleNamespace(enabled=False)),
        stats=SimpleNamespace(enabled=False),
        get_log_dir_path=lambda: Path("/tmp/onetool/logs"),
        get_stats_file_path=lambda: Path("/tmp/onetool/stats.jsonl"),
        get_result_store_path=lambda: Path("/tmp/onetool/results"),
    )
    proxy = SimpleNamespace(
        get_connection=MagicMock(return_value=None),
        get_error=MagicMock(return_value=None),
        is_connecting=False,
    )
    registry = SimpleNamespace(packs={"pack": {"tool": object()}})

    with (
        patch("ot.meta._config_health.get_config", return_value=cfg),
        patch("ot.meta._config_health.get_proxy_manager", return_value=proxy),
        patch("ot.executor.tool_loader.load_tool_registry", return_value=registry),
    ):
        result = status()

    assert result["proxy"]["status"] == "ok"
    assert result["proxy"]["server_count"] == 0
    assert "servers" not in result["proxy"]
    assert not result["warnings"]
    proxy.get_connection.assert_not_called()


@pytest.mark.unit
@pytest.mark.serve
def test_config_returns_configuration() -> None:
    """Verify ot.config() returns configuration information."""
    from ot.meta import config

    result = config()

    # Result is now a dict directly
    assert "aliases" in result
    assert "snippets" in result
    assert "servers" in result


# ============================================================================
# Packs Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_packs_list_all() -> None:
    """Verify ot.packs() lists all packs."""
    from ot.meta import packs

    result = packs()

    # Should return a list of pack dicts (default level)
    assert isinstance(result, list)
    assert len(result) > 0

    # Should have ot pack
    pack_names = [p["name"] for p in result]
    assert "ot" in pack_names
    assert "brave" in pack_names

    # Each pack should have name, description (default level — no tool_count)
    for pack in result:
        assert "name" in pack
        assert "description" in pack
        assert "tool_count" not in pack


@pytest.mark.unit
@pytest.mark.serve
def test_packs_info_full() -> None:
    """Verify ot.packs(info=full) returns dicts with tool_names."""
    from ot.meta import packs

    result = packs(pattern="ot", info="full")

    # Should return list of dicts
    assert isinstance(result, list)
    assert len(result) >= 1

    # Find the ot pack result
    ot_pack = next((p for p in result if isinstance(p, dict) and p.get("name") == "ot"), None)
    assert ot_pack is not None
    assert "source" in ot_pack
    assert "description" in ot_pack
    assert "tool_names" in ot_pack
    assert "ot.tools" in ot_pack["tool_names"]
    assert "ot.packs" in ot_pack["tool_names"]


@pytest.mark.unit
@pytest.mark.serve
def test_packs_pattern_filter() -> None:
    """Verify ot.packs() filters by pattern."""
    from ot.meta import packs

    result = packs(pattern="brav")

    # Should return filtered list of dicts (default level)
    assert isinstance(result, list)
    pack_names = [p["name"] for p in result]
    assert "brave" in pack_names
    assert "ot" not in pack_names


@pytest.mark.unit
@pytest.mark.serve
def test_packs_pattern_no_match_returns_empty() -> None:
    """Verify ot.packs() with no matches returns empty list."""
    from ot.meta import packs

    result = packs(pattern="nonexistent_xyz")

    assert isinstance(result, list)
    assert len(result) == 0


# ============================================================================
# Short Alias Resolution Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_tool_info_resolves_short_alias_pattern() -> None:
    """Verify ot.tool_info(pattern='ctx') resolves to ot_context tools."""
    from ot.meta import tool_info

    result = tool_info(pattern="ctx")

    assert isinstance(result, list)
    assert len(result) >= 1
    # All results should be ot_context tools
    for entry in result:
        assert entry["name"].startswith("ot_context.")


@pytest.mark.unit
@pytest.mark.serve
def test_tool_info_resolves_short_alias_dotted_name() -> None:
    """Verify ot.tool_info(name='ctx.ask') resolves to ot_context.ask."""
    from ot.meta import tool_info

    result = tool_info(name="ctx.ask")

    assert isinstance(result, dict)
    assert result.get("name") == "ot_context.ask"


@pytest.mark.unit
@pytest.mark.serve
def test_tools_resolves_short_alias_pattern() -> None:
    """Verify ot.tools(pattern='ctx') resolves to ot_context tools."""
    from ot.meta import tools

    result = tools(pattern="ctx")

    assert isinstance(result, list)
    assert len(result) >= 1
    tool_names = [t["name"] for t in result]
    assert all(n.startswith("ot_context.") for n in tool_names)


@pytest.mark.unit
@pytest.mark.serve
def test_packs_resolves_short_alias_pattern() -> None:
    """Verify ot.packs(pattern='ctx') resolves to ot_context."""
    from ot.meta import packs

    result = packs(pattern="ctx")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["name"] == "ot_context"


@pytest.mark.unit
@pytest.mark.serve
def test_pack_info_resolves_short_alias() -> None:
    """Verify ot.pack_info(name='ctx') resolves to ot_context."""
    from ot.meta import pack_info

    result = pack_info(name="ctx")

    assert isinstance(result, dict)
    assert result.get("name") == "ot_context"
    assert "error" not in result


# ============================================================================
# Reload Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_reload_clears_config() -> None:
    """Verify ot.reload() clears and reloads configuration."""
    from ot.meta import reload

    result = reload()

    assert "OK" in result
    assert "reloaded" in result.lower()


@pytest.mark.unit
@pytest.mark.serve
def test_reload_resets_runtime_tool_caches() -> None:
    """Verify ot.reload() invokes registered runtime cache hooks."""
    from ot.meta import reload

    hook = MagicMock()
    with patch("ot.executor.tool_loader.load_tool_registry") as mock_load:
        from ot.services import get_services

        mock_load.side_effect = lambda: get_services().register_reload_hook(hook)
        result = reload()

    assert "OK" in result
    hook.assert_called_once_with()


@pytest.mark.unit
@pytest.mark.serve
def test_reload_clears_tool_and_helper_modules() -> None:
    """Verify ot.reload() clears tool modules and owned helper packages."""
    import sys
    from types import ModuleType

    from ot.meta import reload

    module_names = [
        "ot_tool.tools.custom",
        "ottools.ot_timer",
        "otdev.tools._localhist.core",
        "otutil.tools.file",
    ]
    unrelated = "otdev.not_tools"
    for name in module_names:
        sys.modules[name] = ModuleType(name)
    sentinel = ModuleType(unrelated)
    sys.modules[unrelated] = sentinel

    result = reload()

    assert "OK" in result
    for name in module_names:
        assert name not in sys.modules
    assert sys.modules[unrelated] is sentinel
    del sys.modules[unrelated]


# ============================================================================
# Aliases and Snippets Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_aliases_pattern_filter_exact(override_config: Any) -> None:
    """Verify ot.aliases() filters by pattern matching alias name."""
    from ot.meta import aliases

    with override_config(
        OneToolConfig(alias={"ws": "brave.web_search", "gs": "ground.search"})
    ):
        result = aliases(pattern="ws")
        # Result is list of dicts in default level
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "ws"
        assert result[0]["target"] == "brave.web_search"


@pytest.mark.unit
@pytest.mark.serve
def test_aliases_list_all(override_config: Any) -> None:
    """Verify ot.aliases() lists all aliases when called with no args."""
    from ot.meta import aliases

    with override_config(
        OneToolConfig(alias={"ws": "brave.web_search", "gs": "ground.search"})
    ):
        result = aliases()
        # Result is list of dicts (default level)
        assert isinstance(result, list)
        names = [a["name"] for a in result]
        targets = [a["target"] for a in result]
        assert "ws" in names
        assert "gs" in names
        assert "brave.web_search" in targets
        assert "ground.search" in targets


@pytest.mark.unit
@pytest.mark.serve
def test_aliases_pattern_filter(override_config: Any) -> None:
    """Verify ot.aliases() filters by pattern matching target."""
    from ot.meta import aliases

    with override_config(
        OneToolConfig(alias={"ws": "brave.web_search", "gs": "ground.search"})
    ):
        result = aliases(pattern="brave")
        # Result is list of dicts
        assert isinstance(result, list)
        names = [a["name"] for a in result]
        assert "ws" in names
        assert "gs" not in names


@pytest.mark.unit
@pytest.mark.serve
def test_aliases_pattern_no_match_returns_empty(override_config: Any) -> None:
    """Verify ot.aliases() with no matches returns empty list."""
    from ot.meta import aliases

    with override_config(OneToolConfig(alias={"ws": "brave.web_search"})):
        result = aliases(pattern="unknown_xyz")
        assert isinstance(result, list)
        assert len(result) == 0


@pytest.mark.unit
@pytest.mark.serve
def test_snippets_info_full(override_config: Any) -> None:
    """Verify ot.snippets(info=full) returns params as structured dicts, not a flat list."""
    from ot.config import SnippetDef, SnippetParam
    from ot.meta import snippets

    with override_config(
        OneToolConfig(
            snippets={
                "test_snip": SnippetDef(
                    description="Test snippet",
                    body="demo.call(q={{ q }}, path={{ path }})",
                    params={
                        "q": SnippetParam(description="Search query"),
                        "path": SnippetParam(default=".", description="Search path"),
                    },
                )
            }
        )
    ):
        result = snippets(pattern="test_snip", info="full")
        assert isinstance(result, list)
        assert len(result) == 1
        entry = result[0]
        assert isinstance(entry, dict)
        assert entry["name"] == "test_snip"
        assert entry["description"] == "Test snippet"
        # params must be a dict, not a flat list
        assert isinstance(entry["params"], dict)
        # required param has "required": True, no "default"
        assert entry["params"]["q"] == {"required": True, "description": "Search query"}
        # optional param has "default", no "required"
        assert entry["params"]["path"] == {"default": ".", "description": "Search path"}


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_info_required_flag(override_config: Any) -> None:
    """Verify ot.snippet_info() marks required params with required=True."""
    from ot.config import SnippetDef, SnippetParam
    from ot.meta import snippet_info

    with override_config(
        OneToolConfig(
            snippets={
                "rg": SnippetDef(
                    description="Search files",
                    body="rg.search(pattern={{ p }}, path={{ path }})",
                    params={
                        "p": SnippetParam(description="Pattern"),
                        "path": SnippetParam(default=".", description="Search path"),
                    },
                )
            }
        )
    ):
        result = snippet_info(name="rg")
        assert isinstance(result, dict)
        params = result["params"]
        # Required param: has "required": True, no "default"
        assert params["p"].get("required") is True
        assert "default" not in params["p"]
        # Optional param: has "default", no "required"
        assert params["path"]["default"] == "."
        assert "required" not in params["path"]


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_info_example_includes_meaningful_optional(override_config: Any) -> None:
    """Verify example includes first optional param with a non-trivial default."""
    from ot.config import SnippetDef, SnippetParam
    from ot.meta import snippet_info

    with override_config(
        OneToolConfig(
            snippets={
                "search": SnippetDef(
                    description="Search",
                    body="s.search(q={{ q }}, mode={{ mode }})",
                    params={
                        "q": SnippetParam(description="Query"),
                        "empty": SnippetParam(default="", description="Trivial empty"),
                        "mode": SnippetParam(default="semantic", description="Search mode"),
                    },
                )
            }
        )
    ):
        result = snippet_info(name="search")
        example = result["example"]
        # Required param always present
        assert 'q="..."' in example
        # Trivial default ("") skipped; meaningful default included
        assert "empty" not in example
        assert "mode=semantic" in example


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_info_pattern_returns_list(override_config: Any) -> None:
    """Verify ot.snippet_info(pattern=...) returns a list of matching snippet dicts."""
    from ot.config import SnippetDef, SnippetParam
    from ot.meta import snippet_info

    with override_config(
        OneToolConfig(
            snippets={
                "mem_search": SnippetDef(description="Search memory", body="mem.search()"),
                "mem_read": SnippetDef(
                    description="Read memory",
                    body="mem.read(topic={{ topic }})",
                    params={"topic": SnippetParam(description="Topic path")},
                ),
                "rg": SnippetDef(description="Ripgrep search", body="rg.search()"),
            }
        )
    ):
        result = snippet_info(pattern="mem")
        assert isinstance(result, list)
        assert len(result) == 2
        names = [e["name"] for e in result]
        assert "mem_search" in names
        assert "mem_read" in names
        assert "rg" not in names
        # Each entry has full detail (params, example)
        mem_read = next(e for e in result if e["name"] == "mem_read")
        assert "params" in mem_read
        assert "example" in mem_read
        assert mem_read["params"]["topic"].get("required") is True


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_info_no_args_returns_all(override_config: Any) -> None:
    """ot.snippet_info() with no args returns all snippets as a list."""
    from ot.config import SnippetDef
    from ot.meta import snippet_info

    with override_config(
        OneToolConfig(
            snippets={
                "rg": SnippetDef(description="Ripgrep search", body="rg.search()"),
                "mem": SnippetDef(description="Memory read", body="mem.read()"),
            }
        )
    ):
        result = snippet_info()
        assert isinstance(result, list)
        names = [e["name"] for e in result]
        assert "rg" in names
        assert "mem" in names


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_info_colon_prefix_hint(override_config: Any) -> None:
    """ot.snippet_info(name=':rg') returns a hint to drop the ':' prefix."""
    from ot.config import SnippetDef
    from ot.meta import snippet_info

    with override_config(
        OneToolConfig(
            snippets={"rg": SnippetDef(description="Ripgrep search", body="rg.search()")}
        )
    ):
        result = snippet_info(name=":rg")
        assert isinstance(result, dict)
        assert "error" in result
        assert "Did you mean 'rg'" in result["error"]
        assert ":" in result["error"]


@pytest.mark.unit
@pytest.mark.serve
def test_snippet_info_both_name_and_pattern_errors(override_config: Any) -> None:
    """ot.snippet_info(name=..., pattern=...) returns a mutual-exclusivity error."""
    from ot.config import SnippetDef
    from ot.meta import snippet_info

    with override_config(
        OneToolConfig(
            snippets={"rg": SnippetDef(description="Ripgrep search", body="rg.search()")}
        )
    ):
        result = snippet_info(name="rg", pattern="rg")
        assert isinstance(result, dict)
        assert "error" in result
        assert "not both" in result["error"]


@pytest.mark.unit
@pytest.mark.serve
def test_snippets_list_all(override_config: Any) -> None:
    """Verify ot.snippets() lists all snippets when called with no args."""
    from ot.config import SnippetDef
    from ot.meta import snippets

    with override_config(
        OneToolConfig(
            snippets={
                "snip1": SnippetDef(description="First snippet", body="one()"),
                "snip2": SnippetDef(description="Second snippet", body="two()"),
            }
        )
    ):
        result = snippets()
        # Result is list of dicts (default level)
        assert isinstance(result, list)
        names = [s["name"] for s in result]
        descs = [s["description"] for s in result]
        assert "snip1" in names
        assert "snip2" in names
        assert "First snippet" in descs
        assert "Second snippet" in descs


@pytest.mark.unit
@pytest.mark.serve
def test_snippets_pattern_filter(override_config: Any) -> None:
    """Verify ot.snippets() filters by pattern."""
    from ot.config import SnippetDef
    from ot.meta import snippets

    with override_config(
        OneToolConfig(
            snippets={
                "pkg_pypi": SnippetDef(description="Check PyPI packages", body="one()"),
                "pkg_npm": SnippetDef(description="Check NPM packages", body="two()"),
                "search_web": SnippetDef(description="Search web", body="three()"),
            }
        )
    ):
        result = snippets(pattern="pkg")
        # Result is list of dicts (default level)
        assert isinstance(result, list)
        names = [s["name"] for s in result]
        assert "pkg_pypi" in names
        assert "pkg_npm" in names
        assert "search_web" not in names


@pytest.mark.unit
@pytest.mark.serve
def test_snippets_pattern_no_match_returns_empty(override_config: Any) -> None:
    """Verify ot.snippets() with no matches returns empty list."""
    from ot.config import SnippetDef
    from ot.meta import snippets

    with override_config(OneToolConfig(snippets={"known": SnippetDef(body="demo()")})):
        result = snippets(pattern="unknown_xyz")
        assert isinstance(result, list)
        assert len(result) == 0


# ============================================================================
# Proxy Pack Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_packs_with_proxy(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.packs() includes proxy packs."""
    from unittest.mock import patch

    from ot.meta import packs

    # Create mock proxy tools
    mock_tools = [
        ProxyToolInfo(
            server="github",
            name="create_issue",
            description="Create a new issue",
            input_schema={},
        ),
        ProxyToolInfo(
            server="github",
            name="list_repos",
            description="List repositories",
            input_schema={},
        ),
    ]

    mock_proxy_manager.list_tools.return_value = mock_tools
    mock_proxy_manager.servers = ["github"]

    with patch("ot.meta._discovery.get_proxy_manager", return_value=mock_proxy_manager):
        result = packs(pattern="github", info="full")

    # Should generate from proxy tool list — returns dicts with tool_names
    assert isinstance(result, list)
    assert len(result) == 1
    pack_entry = result[0]
    assert isinstance(pack_entry, dict)
    assert pack_entry["name"] == "github"
    assert "github.create_issue" in pack_entry["tool_names"]
    assert "github.list_repos" in pack_entry["tool_names"]


@pytest.mark.unit
@pytest.mark.serve
def test_packs_with_config_descriptions(
    override_prompts: Any, mock_proxy_manager: MagicMock
) -> None:
    """Verify ot.packs() uses pack descriptions from prompts config."""
    from unittest.mock import patch

    from ot.meta import packs

    mock_proxy_manager.list_tools.return_value = []
    mock_proxy_manager.servers = []

    with override_prompts(
        PromptsConfig(
            instructions="Main instructions",
            packs={
                "brave": "Search the web, news, and images — fast, private, with batch support"
            },
        )
    ):
        with patch(
            "ot.meta._discovery.get_proxy_manager", return_value=mock_proxy_manager
        ):
            result = packs(pattern="brave", info="default")

    # Should include configured description
    assert isinstance(result, list)
    assert len(result) == 1
    pack_entry = result[0]
    assert isinstance(pack_entry, dict)
    assert pack_entry["name"] == "brave"
    assert "Search the web" in pack_entry["description"]


# ============================================================================
# Schema Helper Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_empty_schema() -> None:
    """Verify _schema_to_signature handles empty schema."""
    from ot.meta import _schema_to_signature

    result = _schema_to_signature("github.search", {})
    assert result == "github.search()"


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_required_params() -> None:
    """Verify _schema_to_signature handles required parameters."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            "query": {"type": "string"},
            "count": {"type": "integer"},
        },
        "required": ["query", "count"],
    }
    result = _schema_to_signature("github.search", schema)
    assert result == "github.search(count: int, query: str)"


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_optional_params_with_defaults() -> None:
    """Verify _schema_to_signature handles optional params with defaults."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["query"],
    }
    result = _schema_to_signature("github.search", schema)
    assert result == "github.search(query: str, limit: int = 10)"


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_optional_params_no_defaults() -> None:
    """Verify _schema_to_signature uses ellipsis for optional params without defaults."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            "query": {"type": "string"},
            "repo": {"type": "string"},
        },
        "required": ["query"],
    }
    result = _schema_to_signature("github.search", schema)
    assert result == "github.search(query: str, repo: str = ...)"


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_type_mapping() -> None:
    """Verify _schema_to_signature maps JSON Schema types to Python types."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            "text": {"type": "string"},
            "count": {"type": "integer"},
            "score": {"type": "number"},
            "enabled": {"type": "boolean"},
            "items": {"type": "array"},
            "data": {"type": "object"},
        },
        "required": ["text", "count", "score", "enabled", "items", "data"],
    }
    result = _schema_to_signature("test.func", schema)
    assert "text: str" in result
    assert "count: int" in result
    assert "score: float" in result
    assert "enabled: bool" in result
    assert "items: list" in result
    assert "data: dict" in result


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_union_types() -> None:
    """Verify _schema_to_signature handles JSON Schema union types (e.g., ["string", "null"])."""
    from ot.meta import _schema_to_signature

    # Test union with null (common pattern for optional values)
    schema = {
        "properties": {
            "userAgent": {"type": ["string", "null"]},
            "timeout": {"type": ["integer", "null"]},
        },
    }
    result = _schema_to_signature("test.func", schema)
    assert "userAgent: str | None = ..." in result
    assert "timeout: int | None = ..." in result


@pytest.mark.unit
@pytest.mark.serve
def test_schema_to_signature_union_multiple_types() -> None:
    """Verify _schema_to_signature handles multi-type unions."""
    from ot.meta import _schema_to_signature

    schema = {
        "properties": {
            # Value can be string, number, or null
            "value": {"type": ["string", "number", "null"]},
            # Just null type
            "empty": {"type": ["null"]},
        },
    }
    result = _schema_to_signature("test.func", schema)
    assert "value: str | float | None = ..." in result
    assert "empty: None = ..." in result


@pytest.mark.unit
@pytest.mark.serve
def test_parse_input_schema_extracts_descriptions() -> None:
    """Verify _parse_input_schema extracts argument descriptions."""
    from ot.meta import _parse_input_schema

    schema = {
        "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "limit": {"type": "integer", "description": "Maximum results to return"},
        },
        "required": ["query"],
    }
    result = _parse_input_schema(schema)
    assert "query: Search query string" in result
    assert "limit: Maximum results to return" in result


@pytest.mark.unit
@pytest.mark.serve
def test_parse_input_schema_missing_description() -> None:
    """Verify _parse_input_schema handles missing descriptions."""
    from ot.meta import _parse_input_schema

    schema = {
        "properties": {
            "query": {"type": "string"},
        },
        "required": ["query"],
    }
    result = _parse_input_schema(schema)
    assert "query: (no description)" in result


@pytest.mark.unit
@pytest.mark.serve
def test_parse_input_schema_empty() -> None:
    """Verify _parse_input_schema handles empty schema."""
    from ot.meta import _parse_input_schema

    result = _parse_input_schema({})
    assert result == []


@pytest.mark.unit
@pytest.mark.serve
def test_build_proxy_tool_info_default() -> None:
    """Verify _build_proxy_tool_info returns default (list) format."""
    from ot.meta import _build_proxy_tool_info

    result = _build_proxy_tool_info(
        "github.search",
        "Search GitHub",
        {"properties": {"query": {"type": "string"}}},
        "mcp:github",
        info="default",
    )
    assert result == {"name": "github.search", "description": "Search GitHub"}


@pytest.mark.unit
@pytest.mark.serve
def test_build_proxy_tool_info_min() -> None:
    """Verify _build_proxy_tool_info returns name only for min level (list mode)."""
    from ot.meta import _build_proxy_tool_info

    result = _build_proxy_tool_info(
        "github.search",
        "Search GitHub",
        {"properties": {"query": {"type": "string"}}},
        "mcp:github",
        info="min",
    )
    assert result == "github.search"


@pytest.mark.unit
@pytest.mark.serve
def test_build_proxy_tool_info_full_detail() -> None:
    """Verify _build_proxy_tool_info returns full detail format with schema-derived info."""
    from ot.meta import _build_proxy_tool_info

    schema = {
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "default": 10, "description": "Max results"},
        },
        "required": ["query"],
    }
    result = _build_proxy_tool_info(
        "github.search",
        "Search GitHub repositories",
        schema,
        "mcp:github",
        info="full",
        detail=True,
    )
    assert result["name"] == "github.search"
    assert result["description"] == "Search GitHub repositories"
    assert result["source"] == "mcp:github"
    assert "query: str" in result["signature"]
    assert "limit: int = 10" in result["signature"]
    assert "query: Search query" in result["args"]
    assert "limit: Max results" in result["args"]


@pytest.mark.unit
@pytest.mark.serve
def test_tools_proxy_returns_enriched_info(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.tool_info() returns enriched info for proxy tools."""
    from unittest.mock import patch

    from ot.meta import tool_info

    # Create mock proxy tool with input schema
    mock_tools = [
        ProxyToolInfo(
            server="github",
            name="search",
            description="Search GitHub code",
            input_schema={
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "repo": {"type": "string", "description": "Repository name"},
                },
                "required": ["query"],
            },
        ),
    ]

    mock_proxy_manager.list_tools.return_value = mock_tools
    mock_proxy_manager.servers = ["github"]

    with patch("ot.meta._discovery.get_proxy_manager", return_value=mock_proxy_manager):
        result = tool_info(pattern="github.search", info="full")

    assert isinstance(result, list)
    assert len(result) == 1
    tool = result[0]
    assert isinstance(tool, dict)
    assert tool["name"] == "github.search"
    assert tool["source"] == "mcp:github"
    # Signature should be derived from schema, not just (...)
    assert "query: str" in tool["signature"]
    assert "repo: str = ..." in tool["signature"]
    # Args should be extracted from schema descriptions
    assert "query: Search query" in tool["args"]
    assert "repo: Repository name" in tool["args"]


# ============================================================================
# ot.servers() Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
def test_servers_list_info(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.servers(info='min') returns server names only."""
    from unittest.mock import MagicMock as MM
    from unittest.mock import patch

    from ot.meta import servers

    # Mock config with servers
    mock_cfg = MM()
    mock_cfg.servers = {"chrome_devtools": MM(), "github": MM()}

    with patch("ot.meta._discovery.get_proxy_manager", return_value=mock_proxy_manager):
        with patch("ot.meta._discovery.get_config", return_value=mock_cfg):
            result = servers(info="min")

    assert result == ["chrome_devtools", "github"]


@pytest.mark.unit
@pytest.mark.serve
def test_servers_default_info(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.servers(info='default') returns server summaries."""
    from unittest.mock import MagicMock as MM
    from unittest.mock import patch

    from ot.meta import servers

    # Mock config with servers
    mock_devtools = MM()
    mock_devtools.type = "stdio"
    mock_devtools.enabled = True

    mock_cfg = MM()
    mock_cfg.servers = {"chrome_devtools": mock_devtools}

    mock_proxy_manager.get_connection.return_value = None  # Not connected
    mock_proxy_manager.list_tools.return_value = []

    with patch("ot.meta._discovery.get_proxy_manager", return_value=mock_proxy_manager):
        with patch("ot.meta._discovery.get_config", return_value=mock_cfg):
            result = servers(info="default")

    assert len(result) == 1
    assert result[0]["name"] == "chrome_devtools"
    assert "type" not in result[0]  # type field dropped
    assert result[0]["enabled"] is True
    assert result[0]["status"] == "disconnected"
    assert "tool_count" not in result[0]  # tool_count only present when connected
    assert "call_as" not in result[0]  # call_as only present when name has hyphens


@pytest.mark.unit
@pytest.mark.serve
def test_servers_full_returns_dict(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.servers(info='full') returns structured dicts, not markdown strings."""
    from unittest.mock import MagicMock as MM
    from unittest.mock import patch

    from ot.meta import servers

    mock_devtools = MM()
    mock_devtools.type = "stdio"
    mock_devtools.enabled = True
    mock_devtools.source = "https://github.com/ChromeDevTools/chrome-devtools-mcp"

    mock_cfg = MM()
    mock_cfg.servers = {"chrome_devtools": mock_devtools}

    mock_proxy_manager.get_connection.return_value = None  # Not connected
    mock_proxy_manager.get_error.return_value = None
    mock_proxy_manager.list_tools.return_value = []

    with patch("ot.meta._discovery.get_proxy_manager", return_value=mock_proxy_manager):
        with patch("ot.meta._discovery.get_config", return_value=mock_cfg):
            result = servers(pattern="chrome_devtools", info="full")

    assert len(result) == 1
    entry = result[0]
    assert isinstance(entry, dict)
    assert entry["name"] == "chrome_devtools"
    assert entry["status"] == "disconnected"
    assert entry["enabled"] is True
    assert entry["tool_count"] == 0
    assert entry["tools"] == []
    assert "call_as" not in entry  # no hyphens → no call_as
    assert "instructions" not in entry  # instructions live in ot.help(), not servers()


@pytest.mark.unit
@pytest.mark.serve
def test_servers_pattern_filter(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.servers(pattern=...) filters by name."""
    from unittest.mock import MagicMock as MM
    from unittest.mock import patch

    from ot.meta import servers

    mock_cfg = MM()
    mock_cfg.servers = {"chrome_devtools": MM(), "github": MM(), "gitlab": MM()}

    with patch("ot.meta._discovery.get_proxy_manager", return_value=mock_proxy_manager):
        with patch("ot.meta._discovery.get_config", return_value=mock_cfg):
            result = servers(pattern="git", info="min")

    assert result == ["github", "gitlab"]


@pytest.mark.unit
@pytest.mark.serve
def test_help_server_lookup(mock_proxy_manager: MagicMock) -> None:
    """Verify ot.help(query='servername') returns server info."""
    from unittest.mock import MagicMock as MM
    from unittest.mock import patch

    from ot.meta import help

    # Mock config with server
    mock_devtools = MM()
    mock_devtools.type = "stdio"
    mock_devtools.enabled = True
    mock_devtools.command = "npx"
    mock_devtools.args = ["-y", "chrome-devtools-mcp"]
    mock_devtools.instructions = "Browser automation tools."

    mock_cfg = MM()
    mock_cfg.servers = {"chrome_devtools": mock_devtools}
    mock_cfg.alias = {}

    mock_proxy_manager.get_connection.return_value = None
    mock_proxy_manager.servers = []
    mock_proxy_manager.list_tools.return_value = []
    mock_proxy_manager.get_server_instructions.return_value = ""

    with patch("ot.meta._discovery.get_proxy_manager", return_value=mock_proxy_manager):
        with patch("ot.meta._discovery.get_config", return_value=mock_cfg):
            with patch("ot.meta._help.get_config", return_value=mock_cfg):
                with patch("ot.proxy.get_proxy_manager", return_value=mock_proxy_manager):
                    result = help(query="chrome_devtools")

    assert "# chrome_devtools server" in result
    assert "## Instructions" in result
    assert "Browser automation tools." in result


# ============================================================================
# InfoLevel Validation Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.serve
class TestInfoLevelValidation:
    """Verify removed info= values raise ValueError, not silently fallthrough."""

    def test_tools_rejects_list(self) -> None:
        from ot.meta import tools

        with pytest.raises(ValueError, match="info='list' is not valid"):
            tools(info="list")  # type: ignore[arg-type]

    def test_tools_rejects_core(self) -> None:
        from ot.meta import tools

        with pytest.raises(ValueError, match="info='core' is not valid"):
            tools(info="core")  # type: ignore[arg-type]

    def test_tool_info_rejects_invalid(self) -> None:
        from ot.meta import tool_info

        with pytest.raises(ValueError, match="is not valid"):
            tool_info(pattern="brave", info="list")  # type: ignore[arg-type]

    def test_packs_rejects_invalid(self) -> None:
        from ot.meta import packs

        with pytest.raises(ValueError, match="is not valid"):
            packs(info="core")  # type: ignore[arg-type]

    def test_pack_info_rejects_invalid(self) -> None:
        from ot.meta import pack_info

        with pytest.raises(ValueError, match="is not valid"):
            pack_info(name="brave", info="core")  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.serve
def test_tool_info_miss_returns_did_you_mean() -> None:
    """Seam 3: an exact-name miss returns {error, did_you_mean}, not {}."""
    from ot.meta import tool_info

    result = tool_info(name="brave.serch")

    assert isinstance(result, dict)
    assert set(result.keys()) == {"error", "did_you_mean"}
    assert result["error"]
    assert result["did_you_mean"]
    assert "brave.search" in result["did_you_mean"]


@pytest.mark.unit
@pytest.mark.serve
def test_tool_info_miss_no_match_returns_empty_list() -> None:
    """Seam 3: a wildly-wrong name still returns did_you_mean=[], never a bare {}."""
    from ot.meta import tool_info

    result = tool_info(name="zzzzz.nonexistent")

    assert isinstance(result, dict)
    assert result["error"]
    assert result["did_you_mean"] == []


@pytest.mark.unit
@pytest.mark.serve
def test_tools_signatures_returns_oneliner_strings() -> None:
    """ot.tools(info='signatures') returns pack.tool(args) # desc one-liner strings."""
    from ot.meta import tools

    result = tools(pattern="brave.", info="signatures")

    assert isinstance(result, list)
    assert result
    assert all(isinstance(line, str) for line in result)
    line = next(x for x in result if x.startswith("brave.search("))
    assert "query" in line
    assert "  # " in line  # description separator


@pytest.mark.unit
@pytest.mark.serve
def test_tools_signatures_single_pack_only() -> None:
    """A single-pack pattern in signatures mode returns only that pack."""
    from ot.meta import tools

    result = tools(pattern="brave.", info="signatures")
    assert all(line.startswith("brave.") for line in result)


@pytest.mark.unit
@pytest.mark.serve
def test_tools_invalid_info_names_signatures() -> None:
    """The invalid-info error message names the signatures level."""
    from ot.meta import tools

    with pytest.raises(ValueError, match="signatures"):
        tools(info="bogus")


@pytest.mark.unit
@pytest.mark.serve
def test_tools_signatures_matches_index_format() -> None:
    """A sampled tool renders identically to the tool-index generator's line."""
    from ot.meta import tool_info, tools
    from ot.meta._signatures import short_description, signature_args

    detail = tool_info(name="brave.search", info="full")
    assert isinstance(detail, dict)
    expected = f"{detail['name']}({signature_args(detail['signature'])})"
    desc = short_description(detail["description"])
    if desc:
        expected = f"{expected}  # {desc}"
    sig_line = next(iter(tools(pattern="brave.search", info="signatures")))
    assert sig_line == expected
