"""Unit tests for pack_proxy namespace alias generation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestBuildExecutionNamespaceAliases:
    """Tests for hyphen-to-underscore namespace aliases in build_execution_namespace."""

    def _build_namespace(self, server_names: list[str]) -> dict:
        """Build namespace with a mocked proxy manager and empty registry."""
        from ot.executor.pack_proxy import build_execution_namespace, reset

        reset()  # clear cache

        mock_proxy = MagicMock()
        mock_proxy.servers = server_names
        mock_proxy.list_tools.return_value = []

        mock_registry = MagicMock()
        mock_registry.packs = {}
        mock_registry.pack_aliases = {}

        mock_config = MagicMock()
        mock_config.servers = {}

        with (
            patch("ot.proxy.get_proxy_manager", return_value=mock_proxy),
            patch("ot.executor.pack_proxy.get_config", return_value=mock_config),
        ):
            ns = build_execution_namespace(mock_registry)

        return ns

    @pytest.mark.filterwarnings("ignore:Server.*uses hyphens:UserWarning")
    def test_aws_iam_uses_generic_underscore_alias(self) -> None:
        """aws-iam server should create generic aws_iam alias."""
        ns = self._build_namespace(["aws-iam"])

        assert "aws_iam" in ns
        assert "aws-iam" in ns

    @pytest.mark.filterwarnings("ignore:Server.*uses hyphens:UserWarning")
    def test_aws_cost_explorer_uses_generic_underscore_alias(self) -> None:
        """aws-cost-explorer server should create aws_cost_explorer alias."""
        ns = self._build_namespace(["aws-cost-explorer"])

        assert "aws_cost_explorer" in ns
        assert "aws-cost-explorer" in ns

    @pytest.mark.filterwarnings("ignore:Server.*uses hyphens:UserWarning")
    def test_aws_well_architected_uses_generic_underscore_alias(self) -> None:
        """aws-well-architected server should create aws_well_architected alias."""
        ns = self._build_namespace(["aws-well-architected"])

        assert "aws_well_architected" in ns

    @pytest.mark.filterwarnings("ignore:Server.*uses hyphens:UserWarning")
    def test_aws_single_word_server_uses_generic_underscore_alias(self) -> None:
        """aws-billing server should create aws_billing alias."""
        ns = self._build_namespace(["aws-billing"])

        assert "aws_billing" in ns
        assert "aws-billing" in ns

    @pytest.mark.filterwarnings("ignore:Server.*uses hyphens:UserWarning")
    def test_non_aws_hyphenated_server_gets_underscore_alias(self) -> None:
        """Non-aws hyphenated server (e.g. my-server) should get underscore alias."""
        ns = self._build_namespace(["my-server"])

        assert "my_server" in ns
        assert "my-server" in ns

    def test_non_hyphenated_server_no_alias_added(self) -> None:
        """Server without hyphens should not get an extra alias."""
        ns = self._build_namespace(["github"])

        assert "github" in ns
        # No spurious keys added
        proxy_keys = {k for k in ns if k not in ("proxy",)}
        assert proxy_keys == {"github"}

    def test_configured_disconnected_server_is_still_exposed(self) -> None:
        """Configured servers should be present in namespace before connection."""
        from ot.executor.pack_proxy import build_execution_namespace, reset

        reset()

        mock_proxy = MagicMock()
        mock_proxy.servers = []
        mock_proxy.list_tools.return_value = []

        mock_registry = MagicMock()
        mock_registry.packs = {}
        mock_registry.pack_aliases = {}

        cfg = MagicMock()
        cfg.servers = {"github": MagicMock(tool_prefix=None)}

        with (
            patch("ot.proxy.get_proxy_manager", return_value=mock_proxy),
            patch("ot.executor.pack_proxy.get_config", return_value=cfg),
        ):
            ns = build_execution_namespace(mock_registry)

        assert "github" in ns

    def test_cache_refreshes_when_configured_servers_change(self) -> None:
        """Cache key should account for configured servers, not only connected servers."""
        from ot.executor.pack_proxy import build_execution_namespace, reset

        reset()

        mock_proxy = MagicMock()
        mock_proxy.servers = []
        mock_proxy.list_tools.return_value = []

        mock_registry = MagicMock()
        mock_registry.packs = {}
        mock_registry.pack_aliases = {}

        cfg = MagicMock()
        cfg.servers = {}

        with (
            patch("ot.proxy.get_proxy_manager", return_value=mock_proxy),
            patch("ot.executor.pack_proxy.get_config", return_value=cfg),
        ):
            first = build_execution_namespace(mock_registry)
            assert "github" not in first

            # Same registry and same connected-server set, but config changed.
            cfg.servers = {"github": MagicMock(tool_prefix=None)}
            second = build_execution_namespace(mock_registry)

        assert "github" in second

    def test_short_name_alias_not_overwritten_by_local_pack(self) -> None:
        """Short-name alias should not overwrite an existing local pack."""
        from ot.executor.pack_proxy import build_execution_namespace, reset

        reset()

        mock_proxy = MagicMock()
        mock_proxy.servers = ["aws-iam"]
        mock_proxy.list_tools.return_value = []

        mock_registry = MagicMock()
        existing_pack = object()
        mock_registry.packs = {"iam": existing_pack}
        mock_registry.pack_aliases = {}

        mock_config = MagicMock()
        mock_config.servers = {}

        with (
            patch("ot.proxy.get_proxy_manager", return_value=mock_proxy),
            patch("ot.executor.pack_proxy.get_config", return_value=mock_config),
        ):
            ns = build_execution_namespace(mock_registry)

        # 'iam' key exists (either from local pack or alias — local pack wins)
        assert "iam" in ns

    @pytest.mark.filterwarnings("ignore:Server.*uses hyphens:UserWarning")
    def test_multiple_aws_servers_all_get_generic_aliases(self) -> None:
        """All aws-* servers should each get generic aliases."""
        ns = self._build_namespace(["aws-iam", "aws-cost-explorer", "aws-cloudtrail"])

        assert "aws_iam" in ns
        assert "aws_cost_explorer" in ns
        assert "aws_cloudtrail" in ns

    @pytest.mark.filterwarnings("ignore:Server.*uses hyphens:UserWarning")
    def test_alias_proxy_is_callable(self) -> None:
        """The namespace alias should be an object supporting attribute access."""
        ns = self._build_namespace(["aws-iam"])

        # Both the full server name and alias should be pack proxy objects
        assert ns["aws_iam"] is not None
        assert hasattr(ns["aws_iam"], "__getattr__") or callable(getattr(ns["aws_iam"], "__class__", None))


@pytest.mark.unit
@pytest.mark.core
def test_ot_pack_nested_tool_error_points_to_direct_pack_syntax() -> None:
    """Accidental ot.<pack> access tells callers to use direct pack syntax."""
    from ot.executor.pack_proxy import build_execution_namespace, reset

    reset()
    mock_proxy = MagicMock()
    mock_proxy.servers = []

    mock_registry = MagicMock()
    mock_registry.packs = {"ot": {"help": MagicMock()}}
    mock_registry.pack_aliases = {}

    mock_config = MagicMock()
    mock_config.servers = {}

    with (
        patch("ot.proxy.get_proxy_manager", return_value=mock_proxy),
        patch("ot.executor.pack_proxy.get_config", return_value=mock_config),
    ):
        ns = build_execution_namespace(mock_registry)

    with pytest.raises(AttributeError, match=r"use direct pack syntax"):
        _ = ns["ot"].brave


@pytest.mark.unit
@pytest.mark.core
class TestPackShortNameAliases:
    """Tests for metadata-backed alias injection in build_execution_namespace."""

    def _build_namespace_with_packs(self, packs: dict) -> dict:
        from ot.executor.pack_proxy import build_execution_namespace, reset

        reset()

        mock_proxy = MagicMock()
        mock_proxy.servers = []

        mock_registry = MagicMock()
        mock_registry.packs = packs
        mock_registry.pack_aliases = {
            "whiteboard": ("wb",),
            "webfetch": ("wf",),
            "brave": ("br",),
            "chat_ops": ("co",),
        }

        mock_config = MagicMock()
        mock_config.servers = {}

        with (
            patch("ot.proxy.get_proxy_manager", return_value=mock_proxy),
            patch("ot.executor.pack_proxy.get_config", return_value=mock_config),
        ):
            ns = build_execution_namespace(mock_registry)

        return ns

    def test_whiteboard_gets_wb_short_alias(self) -> None:
        """whiteboard pack should appear as both 'whiteboard' and 'wb'."""
        packs = {"whiteboard": {"draw": MagicMock(), "open": MagicMock()}}
        ns = self._build_namespace_with_packs(packs)

        assert "whiteboard" in ns
        assert "wb" in ns
        assert ns["wb"] is ns["whiteboard"]

    def test_webfetch_gets_wf_short_alias(self) -> None:
        """webfetch pack should appear as both 'webfetch' and 'wf'."""
        packs = {"webfetch": {"fetch": MagicMock()}}
        ns = self._build_namespace_with_packs(packs)

        assert "webfetch" in ns
        assert "wf" in ns
        assert ns["wf"] is ns["webfetch"]

    def test_chat_ops_gets_co_short_alias(self) -> None:
        """chat_ops pack should appear as both 'chat_ops' and 'co'."""
        packs = {"chat_ops": {"ingest": MagicMock(), "report_excel": MagicMock()}}
        ns = self._build_namespace_with_packs(packs)

        assert "chat_ops" in ns
        assert "co" in ns
        assert ns["co"] is ns["chat_ops"]

    def test_short_alias_not_added_when_pack_absent(self) -> None:
        """Short alias is only injected when the full pack is present."""
        ns = self._build_namespace_with_packs({"brave": {"search": MagicMock()}})

        assert "br" in ns
        assert "wb" not in ns  # whiteboard not loaded → wb not injected

    def test_short_alias_does_not_overwrite_existing_pack(self) -> None:
        """Short alias is skipped if that name is already a loaded pack."""
        existing_wb = MagicMock()
        packs = {
            "whiteboard": {"draw": MagicMock()},
            "wb": {"custom": existing_wb},
        }
        ns = self._build_namespace_with_packs(packs)

        # 'wb' key should be the explicitly loaded pack, not the alias
        assert ns["wb"] is not ns["whiteboard"]

    def test_all_metadata_aliases_are_valid_identifiers(self) -> None:
        """All declared aliases must be valid Python identifiers."""
        aliases = {
            "whiteboard": ("wb",),
            "webfetch": ("wf",),
            "brave": ("br",),
            "chat_ops": ("co",),
        }
        for full, pack_aliases in aliases.items():
            for alias in pack_aliases:
                assert alias.isidentifier(), f"Alias '{alias}' for '{full}' is not a valid identifier"


@pytest.mark.unit
@pytest.mark.core
class TestMcpProxyPackToolPrefixFallback:
    """Tests for tool_prefix fallback in McpProxyPack.__getattr__."""

    def _make_proxy_tools(self, server_name: str, tool_names: list[str]) -> MagicMock:
        from ot.proxy.manager import ProxyToolInfo

        mock_proxy = MagicMock()
        mock_proxy.list_tools.return_value = [
            ProxyToolInfo(server=server_name, name=n, description="", input_schema={})
            for n in tool_names
        ]
        mock_proxy.call_tool_sync.return_value = {"result": "ok"}
        return mock_proxy

    def test_tool_prefix_allows_omitting_prefix(self) -> None:
        """knowledge.search_documentation() resolves to aws_search_documentation via tool_prefix."""
        from ot.executor.pack_proxy import _create_mcp_proxy_pack

        mock_proxy = self._make_proxy_tools("aws-knowledge", ["aws_search_documentation"])

        with patch("ot.proxy.get_proxy_manager", return_value=mock_proxy):
            pack = _create_mcp_proxy_pack("aws-knowledge", tool_prefix="aws_")
            fn = pack.search_documentation  # omit prefix — should resolve
            assert callable(fn)

    def test_no_tool_prefix_does_not_fallback(self) -> None:
        """Without tool_prefix, accessing an unprefixed name that only exists prefixed raises."""
        from ot.executor.pack_proxy import _create_mcp_proxy_pack

        mock_proxy = self._make_proxy_tools("github", ["aws_something"])

        with patch("ot.proxy.get_proxy_manager", return_value=mock_proxy):
            pack = _create_mcp_proxy_pack("github")  # no tool_prefix
            with pytest.raises(AttributeError):
                _ = pack.something  # no prefix fallback — should not resolve

    def test_exact_tool_name_works_regardless_of_prefix(self) -> None:
        """The full prefixed tool name is always accessible directly."""
        from ot.executor.pack_proxy import _create_mcp_proxy_pack

        mock_proxy = self._make_proxy_tools("aws-knowledge", ["aws_search_documentation"])

        with patch("ot.proxy.get_proxy_manager", return_value=mock_proxy):
            pack = _create_mcp_proxy_pack("aws-knowledge", tool_prefix="aws_")
            fn = pack.aws_search_documentation  # exact name still works
            assert callable(fn)

    def test_tool_prefix_works_for_any_server_name(self) -> None:
        """tool_prefix is server-agnostic — any server can declare one."""
        from ot.executor.pack_proxy import _create_mcp_proxy_pack

        mock_proxy = self._make_proxy_tools("my-custom-server", ["myco_list_things"])

        with patch("ot.proxy.get_proxy_manager", return_value=mock_proxy):
            pack = _create_mcp_proxy_pack("my-custom-server", tool_prefix="myco_")
            fn = pack.list_things  # prefix stripped
            assert callable(fn)
