"""Strict YAML validation for proxied MCP server configuration."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestValidProxyConfiguration:
    """Current HTTP, authentication, and stdio shapes load successfully."""

    def test_valid_server_shapes_load(self, write_config) -> None:
        from ot.config.loader import load_config

        config_path = write_config(
            {
                "servers": {
                    "plain_http": {
                        "type": "http",
                        "url": "http://localhost:9000/mcp",
                        "headers": {"X-Project": "docs"},
                    },
                    "oauth_http": {
                        "type": "http",
                        "url": "https://oauth.mcp.test/mcp",
                        "auth": {
                            "type": "oauth",
                            "scopes": [" write ", "read", "write"],
                        },
                    },
                    "bearer_http": {
                        "type": "http",
                        "url": "https://bearer.mcp.test/mcp",
                        "auth": {"type": "bearer", "token": "${MCP_TOKEN}"},
                    },
                    "local_stdio": {
                        "type": "stdio",
                        "command": "uvx",
                        "args": ["mcp-server"],
                        "env": {"MODE": "test"},
                        "inherit_env": True,
                        "timeout": 45,
                    },
                }
            }
        )

        config = load_config(config_path)

        assert config.servers["oauth_http"].auth is not None
        assert config.servers["oauth_http"].auth.scopes == ["write", "read"]
        assert config.servers["bearer_http"].auth is not None
        assert config.servers["bearer_http"].auth.token == "${MCP_TOKEN}"
        assert config.servers["local_stdio"].command == "uvx"

    def test_environment_backed_bearer_expands_when_client_is_created(
        self, write_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ot.config.loader import load_config
        from ot.proxy.manager import ProxyManager

        config_path = write_config(
            {
                "servers": {
                    "secure": {
                        "type": "http",
                        "url": "https://secure.mcp.test/mcp",
                        "auth": {"type": "bearer", "token": "${MCP_TOKEN}"},
                    }
                }
            }
        )
        config = load_config(config_path)
        monkeypatch.setenv("MCP_TOKEN", "expanded-token")

        with (
            patch("ot.proxy.manager.BearerAuth") as bearer_auth,
            patch("ot.proxy.manager.StreamableHttpTransport"),
            patch("ot.proxy.manager.Client"),
        ):
            ProxyManager()._create_http_client("secure", config.servers["secure"])

        bearer_auth.assert_called_once_with("expanded-token")


@pytest.mark.unit
@pytest.mark.core
class TestInvalidProxyConfiguration:
    """Invalid combinations fail on the YAML configuration path."""

    @pytest.mark.parametrize(
        ("server", "message"),
        [
            ({"type": "http"}, "http server requires a non-empty url"),
            (
                {"type": "http", "url": "ftp://files.mcp.test/mcp"},
                "http server url must use http:// or https://",
            ),
            (
                {"type": "http", "url": "https://mcp.test/mcp", "command": None},
                "http server forbids fields: command",
            ),
            (
                {"type": "http", "url": "https://mcp.test/mcp", "args": []},
                "http server forbids fields: args",
            ),
            (
                {"type": "http", "url": "https://mcp.test/mcp", "env": {}},
                "http server forbids fields: env",
            ),
            (
                {
                    "type": "http",
                    "url": "https://mcp.test/mcp",
                    "inherit_env": False,
                },
                "http server forbids fields: inherit_env",
            ),
            ({"type": "stdio"}, "stdio server requires a non-empty command"),
            (
                {"type": "stdio", "command": "uvx", "url": None},
                "stdio server forbids fields: url",
            ),
            (
                {"type": "stdio", "command": "uvx", "headers": {}},
                "stdio server forbids fields: headers",
            ),
            (
                {
                    "type": "stdio",
                    "command": "uvx",
                    "auth": {"type": "oauth"},
                },
                "stdio server forbids fields: auth",
            ),
            (
                {"type": "stdio", "command": "uvx", "timeout": 0},
                "greater than 0",
            ),
            (
                {
                    "type": "http",
                    "url": "https://mcp.test/mcp",
                    "auth": {"type": "bearer"},
                },
                "bearer auth requires a non-empty token",
            ),
            (
                {
                    "type": "http",
                    "url": "https://mcp.test/mcp",
                    "auth": {
                        "type": "bearer",
                        "token": "token",
                        "scopes": ["read"],
                    },
                },
                "bearer auth forbids scopes",
            ),
            (
                {
                    "type": "http",
                    "url": "https://mcp.test/mcp",
                    "auth": {
                        "type": "bearer",
                        "token": "token",
                        "scopes": [],
                    },
                },
                "bearer auth forbids scopes",
            ),
            (
                {
                    "type": "http",
                    "url": "https://mcp.test/mcp",
                    "auth": {"type": "oauth", "token": "token"},
                },
                "oauth auth forbids token",
            ),
            (
                {
                    "type": "http",
                    "url": "https://mcp.test/mcp",
                    "auth": {"type": "oauth", "token": None},
                },
                "oauth auth forbids token",
            ),
            (
                {
                    "type": "http",
                    "url": "https://mcp.test/mcp",
                    "auth": {"type": "oauth", "scopes": ["read", " "]},
                },
                "oauth scope entries must be non-empty",
            ),
        ],
    )
    def test_invalid_server_shape_names_server_and_rule(
        self, write_config, server: dict[str, object], message: str
    ) -> None:
        from ot.config.loader import load_config

        config_path = write_config({"servers": {"bad_server": server}})

        with pytest.raises(ValueError) as raised:
            load_config(config_path)

        error = str(raised.value)
        assert "bad_server" in error
        assert message in error

    @pytest.mark.parametrize(
        ("servers", "message"),
        [
            (
                {
                    "foo-bar": {"type": "stdio", "command": "first"},
                    "foo_bar": {"type": "stdio", "command": "second"},
                },
                "'foo-bar' and 'foo_bar'",
            ),
            (
                {"proxy": {"type": "stdio", "command": "reserved"}},
                "reserved namespace 'proxy'",
            ),
        ],
    )
    def test_ambiguous_server_names_fail(
        self,
        write_config,
        servers: dict[str, dict[str, str]],
        message: str,
    ) -> None:
        from ot.config.loader import load_config

        config_path = write_config({"servers": servers})

        with pytest.raises(ValueError, match=message):
            load_config(config_path)

    def test_unrelated_server_names_remain_valid(self, write_config) -> None:
        from ot.config.loader import load_config

        config_path = write_config(
            {
                "servers": {
                    "docs-api": {"type": "stdio", "command": "docs"},
                    "billing_api": {"type": "stdio", "command": "billing"},
                }
            }
        )

        assert set(load_config(config_path).servers) == {"docs-api", "billing_api"}
