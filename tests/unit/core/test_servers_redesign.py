"""Unit tests for redesigned ot.servers() and related agent-facing features."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_server_cfg(
    *,
    type_: str = "stdio",
    enabled: bool = True,
    source: str | None = None,
    instructions: str | None = None,
) -> MagicMock:
    cfg = MagicMock()
    cfg.type = type_
    cfg.enabled = enabled
    cfg.source = source
    cfg.instructions = instructions
    return cfg


def _make_proxy(
    connected: list[str] | None = None,
    tools_by_server: dict | None = None,
) -> MagicMock:
    proxy = MagicMock()
    connected = connected or []
    tools_by_server = tools_by_server or {}

    def get_connection(name: str):
        return MagicMock() if name in connected else None

    def list_tools(server: str | None = None):
        if server:
            return tools_by_server.get(server, [])
        return [t for ts in tools_by_server.values() for t in ts]

    proxy.get_connection.side_effect = get_connection
    proxy.list_tools.side_effect = list_tools
    proxy.get_error.return_value = None
    return proxy


@pytest.mark.unit
@pytest.mark.serve
class TestServersDefaultRedesign:
    """ot.servers() default returns {name, status, enabled, [call_as], [tool_count], [error]}."""

    def test_connected_server_has_tool_count(self) -> None:
        """tool_count is present and accurate when server is connected."""
        from ot.meta import servers

        mock_tools = [MagicMock(), MagicMock(), MagicMock()]
        proxy = _make_proxy(connected=["github"], tools_by_server={"github": mock_tools})
        cfg = MagicMock()
        cfg.servers = {"github": _make_server_cfg()}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="default")

        assert len(result) == 1
        assert result[0]["tool_count"] == 3
        assert result[0]["status"] == "connected"

    def test_disconnected_server_has_no_tool_count(self) -> None:
        """tool_count is absent when server is disconnected."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {"github": _make_server_cfg()}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="default")

        assert "tool_count" not in result[0]

    def test_hyphen_name_has_call_as(self) -> None:
        """Server with hyphen in name includes call_as field."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {"my-server": _make_server_cfg()}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="default")

        assert result[0]["call_as"] == "my_server"

    def test_underscore_name_has_no_call_as(self) -> None:
        """Server with valid Python name does not include call_as."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {"chrome_devtools": _make_server_cfg()}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="default")

        assert "call_as" not in result[0]

    def test_type_field_dropped(self) -> None:
        """type field is no longer in default output."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {"github": _make_server_cfg(type_="http")}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="default")

        assert "type" not in result[0]

    def test_aws_server_call_as_uses_generic_underscore_alias(self) -> None:
        """aws-iam → call_as = 'aws_iam'."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {"aws-iam": _make_server_cfg()}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="default")

        assert result[0]["call_as"] == "aws_iam"


@pytest.mark.unit
@pytest.mark.serve
class TestServersFullRedesign:
    """ot.servers(info='full') returns structured dicts, not markdown strings."""

    def test_returns_dicts_not_strings(self) -> None:
        """Each entry is a dict, not a markdown string."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {"github": _make_server_cfg(source="https://github.com/org/repo")}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="full")

        assert len(result) == 1
        assert isinstance(result[0], dict)

    def test_full_has_expected_fields(self) -> None:
        """Full entry has name, status, enabled, source, tool_count, tools."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {
            "github": _make_server_cfg(source="https://github.com/anthropics/github-mcp")
        }

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="full")

        entry = result[0]
        assert entry["name"] == "github"
        assert entry["status"] == "disconnected"
        assert entry["enabled"] is True
        assert entry["source"] == "https://github.com/anthropics/github-mcp"
        assert entry["tool_count"] == 0
        assert entry["tools"] == []

    def test_full_no_instructions(self) -> None:
        """Instructions are NOT in servers(info='full') — they belong in ot.help()."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {"github": _make_server_cfg(instructions="Use search_repositories.")}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="full")

        assert "instructions" not in result[0]

    def test_full_tools_use_safe_name_prefix(self) -> None:
        """Tool names in 'tools' list use the Python-safe server name."""
        from ot.meta import servers
        from ot.proxy.manager import ProxyToolInfo

        tool = ProxyToolInfo(
            server="my-server", name="list_items", description="", input_schema={}
        )
        proxy = MagicMock()
        proxy.get_connection.return_value = MagicMock()  # connected
        proxy.list_tools.return_value = [tool]
        proxy.get_error.return_value = None

        cfg = MagicMock()
        cfg.servers = {"my-server": _make_server_cfg()}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="full")

        assert "my_server.list_items" in result[0]["tools"]

    def test_full_hyphen_server_has_call_as(self) -> None:
        """Hyphenated server name includes call_as in full output."""
        from ot.meta import servers

        proxy = _make_proxy()
        cfg = MagicMock()
        cfg.servers = {"my-server": _make_server_cfg()}

        with patch("ot.meta._discovery.get_proxy_manager", return_value=proxy):
            with patch("ot.meta._discovery.get_config", return_value=cfg):
                result = servers(info="full")

        assert result[0]["call_as"] == "my_server"


@pytest.mark.unit
@pytest.mark.serve
class TestPackProxyRegistrationWarning:
    """pack_proxy.py: underscore name is primary; warning emitted for hyphen names."""

    def _build_namespace(self, server_names: list[str]) -> tuple[dict, list]:
        import warnings

        from ot.executor.pack_proxy import build_execution_namespace, reset

        reset()

        mock_proxy = MagicMock()
        mock_proxy.servers = server_names
        mock_proxy.list_tools.return_value = []

        mock_registry = MagicMock()
        mock_registry.packs = {}

        mock_config = MagicMock()
        mock_config.servers = {}

        with (
            patch("ot.proxy.get_proxy_manager", return_value=mock_proxy),
            patch("ot.executor.pack_proxy.get_config", return_value=mock_config),
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                ns = build_execution_namespace(mock_registry)

        return ns, list(caught)

    def test_hyphen_server_registered_under_underscore(self) -> None:
        """Hyphenated server's primary key is the underscore form."""
        ns, _ = self._build_namespace(["my-server"])
        assert "my_server" in ns

    def test_hyphen_server_alias_callable(self) -> None:
        """Hyphenated server key is also in namespace as an alias."""
        ns, _ = self._build_namespace(["my-server"])
        assert "my-server" in ns
        assert ns["my-server"] is ns["my_server"]

    def test_hyphen_server_emits_warning(self) -> None:
        """UserWarning is emitted when a hyphenated server is registered."""
        _, caught = self._build_namespace(["my-server"])
        assert any(issubclass(w.category, UserWarning) for w in caught)
        assert any("my-server" in str(w.message) for w in caught)

    def test_underscore_server_no_warning(self) -> None:
        """No warning emitted when server name is already a valid identifier."""
        _, caught = self._build_namespace(["chrome_devtools"])
        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert len(user_warnings) == 0

    def test_aws_server_warns_like_any_hyphenated_server(self) -> None:
        """aws-* servers use the same generic hyphen warning."""
        _, caught = self._build_namespace(["aws-iam"])
        assert any(issubclass(w.category, UserWarning) for w in caught)


@pytest.mark.unit
@pytest.mark.serve
class TestProxyToolNameNormalization:
    """ot.tools() and ot.tool_info() normalize proxy server names to underscore form."""

    def test_tools_proxy_names_use_underscore_form(self) -> None:
        """ot.tools() lists hyphen server tools as safe_name.tool, not hyphen.tool."""
        from ot.meta import tools
        from ot.proxy.manager import ProxyToolInfo

        tool = ProxyToolInfo(
            server="my-server", name="list_items", description="List items", input_schema={}
        )
        proxy = MagicMock()
        proxy.list_tools.return_value = [tool]

        registry = MagicMock()
        registry.packs = {}

        with (
            patch("ot.meta._discovery.get_proxy_manager", return_value=proxy),
            patch("ot.executor.tool_loader.load_tool_registry", return_value=registry),
        ):
            result = tools(info="min")

        assert "my_server.list_items" in result
        assert "my-server.list_items" not in result

    def test_tool_info_name_lookup_underscore(self) -> None:
        """tool_info(name='my_server.list_items') finds the tool."""
        from ot.meta import tool_info
        from ot.proxy.manager import ProxyToolInfo

        tool = ProxyToolInfo(
            server="my-server", name="list_items", description="List items", input_schema={}
        )
        proxy = MagicMock()
        proxy.list_tools.return_value = [tool]

        registry = MagicMock()
        registry.packs = {}

        with (
            patch("ot.meta._discovery.get_proxy_manager", return_value=proxy),
            patch("ot.executor.tool_loader.load_tool_registry", return_value=registry),
        ):
            result = tool_info(name="my_server.list_items")

        assert result is not None
        assert isinstance(result, dict)
        assert result["name"] == "my_server.list_items"

    def test_tool_info_pattern_underscore(self) -> None:
        """tool_info(pattern='my_server') returns results for hyphen-named server."""
        from ot.meta import tool_info
        from ot.proxy.manager import ProxyToolInfo

        tool = ProxyToolInfo(
            server="my-server", name="list_items", description="List items", input_schema={}
        )
        proxy = MagicMock()
        proxy.list_tools.return_value = [tool]

        registry = MagicMock()
        registry.packs = {}

        with (
            patch("ot.meta._discovery.get_proxy_manager", return_value=proxy),
            patch("ot.executor.tool_loader.load_tool_registry", return_value=registry),
        ):
            result = tool_info(pattern="my_server")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "my_server.list_items"


@pytest.mark.unit
@pytest.mark.serve
class TestFuzzySearchIncludesServers:
    """ot.help() fuzzy search surfaces server names in results."""

    def test_fuzzy_search_returns_servers_section(self) -> None:
        """help(query='play') fuzzy-matches 'playwright' and surfaces it in ## Servers."""
        from ot.meta import help

        proxy = MagicMock()
        proxy.list_tools.return_value = []
        proxy.servers = ["playwright", "github"]

        cfg = MagicMock()
        cfg.servers = {"playwright": _make_server_cfg(), "github": _make_server_cfg()}
        cfg.alias = {}

        registry = MagicMock()
        registry.packs = {}

        with (
            patch("ot.meta._discovery.get_proxy_manager", return_value=proxy),
            patch("ot.meta._discovery.get_config", return_value=cfg),
            patch("ot.meta._help.get_config", return_value=cfg),
            patch("ot.executor.tool_loader.load_tool_registry", return_value=registry),
            patch("ot.meta._help.snippets", return_value=[]),
            patch("ot.meta._help.aliases", return_value=[]),
        ):
            # "play" is a substring of "playwright" → score 1.0 → appears in results
            result = help(query="play")

        assert "## Servers" in result
        assert "playwright" in result

    def test_fuzzy_search_no_servers_when_no_match(self) -> None:
        """help(query='zzz') does not include ## Servers when nothing matches."""
        from ot.meta import help

        proxy = MagicMock()
        proxy.list_tools.return_value = []
        proxy.servers = []

        cfg = MagicMock()
        cfg.servers = {}
        cfg.alias = {}

        registry = MagicMock()
        registry.packs = {}

        with (
            patch("ot.meta._discovery.get_proxy_manager", return_value=proxy),
            patch("ot.meta._discovery.get_config", return_value=cfg),
            patch("ot.meta._help.get_config", return_value=cfg),
            patch("ot.executor.tool_loader.load_tool_registry", return_value=registry),
            patch("ot.meta._help.snippets", return_value=[]),
            patch("ot.meta._help.aliases", return_value=[]),
        ):
            result = help(query="zzznomatch")

        assert "## Servers" not in result


@pytest.mark.unit
@pytest.mark.serve
class TestFormatServerHelp:
    """_format_server_help() produces correct markdown sections."""

    def _make_proxy_tool(self, name: str, desc: str = "") -> MagicMock:
        t = MagicMock()
        t.name = name
        t.description = desc
        return t

    def test_basic_output(self) -> None:
        """Heading and status are always present."""
        from ot.meta._help_formatting import _format_server_help

        cfg = _make_server_cfg()
        result = _format_server_help("github", cfg, "disconnected", [])

        assert "# github server" in result
        assert "**Status:** disconnected" in result
        assert "**Guide:**" not in result

    def test_call_as_shown_for_hyphen_name(self) -> None:
        """Call-as line appears when server name contains hyphens."""
        from ot.meta._help_formatting import _format_server_help

        cfg = _make_server_cfg()
        result = _format_server_help("my-server", cfg, "disconnected", [])

        assert "**Call as:** `my_server`" in result

    def test_no_call_as_for_underscore_name(self) -> None:
        """No call-as line for valid Python identifier names."""
        from ot.meta._help_formatting import _format_server_help

        cfg = _make_server_cfg()
        result = _format_server_help("github", cfg, "connected", [])

        assert "Call as" not in result

    def test_source_shown_when_present(self) -> None:
        """Source URL appears when server_cfg.source is set."""
        from ot.meta._help_formatting import _format_server_help

        cfg = _make_server_cfg(source="https://github.com/org/repo")
        result = _format_server_help("github", cfg, "connected", [])

        assert "**Source:** https://github.com/org/repo" in result

    def test_instructions_yaml_only(self) -> None:
        """YAML instructions shown when native is empty."""
        from ot.meta._help_formatting import _format_server_help

        cfg = _make_server_cfg(instructions="Always call take_screenshot first.")
        result = _format_server_help("github", cfg, "connected", [], native_instructions="")

        assert "## Instructions" in result
        assert "Always call take_screenshot first." in result

    def test_instructions_native_and_yaml_combined(self) -> None:
        """Native instructions come first, YAML appended below."""
        from ot.meta._help_formatting import _format_server_help

        cfg = _make_server_cfg(instructions="Extra OneTool tip.")
        result = _format_server_help(
            "github", cfg, "connected", [], native_instructions="Native guidance."
        )

        assert "## Instructions" in result
        native_pos = result.index("Native guidance.")
        yaml_pos = result.index("Extra OneTool tip.")
        assert native_pos < yaml_pos

    def test_tools_section_with_safe_prefix(self) -> None:
        """Tool entries use the safe server name as prefix."""
        from ot.meta._help_formatting import _format_server_help

        tools = [self._make_proxy_tool("navigate_page", "Navigate to URL")]
        cfg = _make_server_cfg()
        result = _format_server_help("my-server", cfg, "connected", tools)

        assert "**my_server.navigate_page**" in result

    def test_no_instructions_section_when_empty(self) -> None:
        """No ## Instructions section when both native and YAML are empty."""
        from ot.meta._help_formatting import _format_server_help

        cfg = _make_server_cfg(instructions=None)
        result = _format_server_help("github", cfg, "connected", [], native_instructions="")

        assert "## Instructions" not in result
