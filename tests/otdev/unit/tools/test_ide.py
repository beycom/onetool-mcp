"""Unit tests for the IDE tool pack."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

CONNECTION_ID = "ot1"
OTHER_CONNECTION_ID = "lib"
BASE_URL = "http://127.0.0.1:58764/"


def _snapshot(connection_id: str = CONNECTION_ID) -> dict[str, object]:
    return {
        "protocol_version": 1,
        "snapshot": {
            "connection": {"id": connection_id},
            "workspace": {
                "name": "onetool-mcp",
                "workspace_folders": ["/repo"],
                "workspace_file": None,
            },
            "active_editor": {
                "visible_ranges": [{"start_line": 0, "end_line": 40}],
                "document": {
                    "path": "/repo/src/app.py",
                    "dirty": True,
                    "untitled": False,
                },
            },
            "selection": {
                "path": "/repo/src/app.py",
                "ranges": [
                    {
                        "start_line": 0,
                        "start_character": 0,
                        "end_line": 0,
                        "end_character": 5,
                    },
                    {
                        "start_line": 2,
                        "start_character": 1,
                        "end_line": 2,
                        "end_character": 4,
                    },
                ],
                "text": "first\nsecond",
            },
        },
    }


def _health(connection_id: str = CONNECTION_ID) -> dict[str, object]:
    return {
        "ok": True,
        "protocol_version": 1,
        "connection": {"id": connection_id},
        "workspace": {
            "name": "onetool-mcp",
            "workspace_folders": ["/repo"],
            "workspace_file": None,
        },
    }


def _mock_response(status_code: int, payload: object) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


@pytest.fixture(autouse=True)
def reset_ide_state() -> None:
    """Reset mutable IDE module state between tests."""
    from otdev.tools import ide

    ide.DEFAULT_CONNECTION_ID = None
    ide.DISCOVERED_BASE_URLS.clear()


@pytest.mark.unit
@pytest.mark.tools
class TestIdePack:
    def test_pack_exports_state_tools(self) -> None:
        from otdev.tools import ide

        assert ide.pack == "ide"
        assert ide.__all__ == [
            "connect",
            "editor",
            "file",
            "get_state",
            "paths",
            "sel",
            "state",
            "workspace",
        ]
        assert not hasattr(ide, "context")

    def test_connect_sets_and_persists_default_connection(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.post.return_value = _mock_response(200, _snapshot())

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide.set_project_state") as set_project_state,
            patch("otdev.tools.ide._get_http_client", return_value=client),
        ):
            result = ide.connect(id=CONNECTION_ID)

        _, kwargs = client.post.call_args
        assert json.loads(kwargs["content"]) == {
            "protocol_version": 1,
            "operation": "get_state",
            "connection_id": CONNECTION_ID,
        }
        assert result == {"id": CONNECTION_ID}
        assert ide.DEFAULT_CONNECTION_ID == CONNECTION_ID
        set_project_state.assert_called_once_with("ide", "connection_id", CONNECTION_ID)

    def test_state_uses_default_connection(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.post.return_value = _mock_response(200, _snapshot())

        with (
            patch("otdev.tools.ide.DEFAULT_CONNECTION_ID", CONNECTION_ID),
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            patch("otdev.tools.ide.get_effective_cwd", return_value=Path("/repo")),
        ):
            result = ide.state()

        _, kwargs = client.post.call_args
        assert json.loads(kwargs["content"])["connection_id"] == CONNECTION_ID
        assert result["connection"] == {"id": CONNECTION_ID}
        assert result["active_editor"]["document"]["dirty"] is True

    def test_state_uses_project_state_when_memory_default_missing(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.post.return_value = _mock_response(200, _snapshot())

        with (
            patch("otdev.tools.ide.get_project_state", return_value=CONNECTION_ID),
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            patch("otdev.tools.ide.get_effective_cwd", return_value=Path("/repo")),
        ):
            result = ide.state()

        assert result["connection"] == {"id": CONNECTION_ID}

    def test_id_override_does_not_replace_default_or_persisted_state(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.post.return_value = _mock_response(200, _snapshot(OTHER_CONNECTION_ID))

        with (
            patch("otdev.tools.ide.DEFAULT_CONNECTION_ID", CONNECTION_ID),
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide.set_project_state") as set_project_state,
            patch("otdev.tools.ide._get_http_client", return_value=client),
            patch("otdev.tools.ide.get_effective_cwd", return_value=Path("/repo")),
        ):
            result = ide.sel(id=OTHER_CONNECTION_ID)
            assert ide.DEFAULT_CONNECTION_ID == CONNECTION_ID

        _, kwargs = client.post.call_args
        assert json.loads(kwargs["content"])["connection_id"] == OTHER_CONNECTION_ID
        assert "first\nsecond" in result
        set_project_state.assert_not_called()

    def test_missing_default_failure(self) -> None:
        from otdev.tools.ide import IdeStateError, state

        with (
            patch("otdev.tools.ide.get_project_state", return_value=None),
            pytest.raises(IdeStateError, match=r"ide\.connect\(id=\.\.\.\)"),
        ):
            state()

    def test_unknown_connection_failure(self) -> None:
        from otdev.tools.ide import IdeStateError, state

        client = Mock()
        client.post.return_value = httpx.Response(404, text="unknown connection")

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            pytest.raises(IdeStateError, match="Unknown IDE connection id"),
        ):
            state(id=CONNECTION_ID)

    def test_include_filtering_and_workspace_grouping(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.post.return_value = _mock_response(200, _snapshot())

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            patch("otdev.tools.ide.get_effective_cwd", return_value=Path("/repo")),
        ):
            result = ide.state(id=CONNECTION_ID, include=["workspace"])

        assert set(result) == {"workspace"}
        assert result["workspace"]["workspace_folders"] == ["/repo"]

    def test_include_all_returns_all_sections(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.post.return_value = _mock_response(200, _snapshot())

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            patch("otdev.tools.ide.get_effective_cwd", return_value=Path("/repo")),
        ):
            result = ide.get_state(id=CONNECTION_ID, include="all")

        assert set(result) == {
            "connection",
            "selection",
            "active_editor",
            "workspace",
        }

    def test_invalid_include_rejected(self) -> None:
        from otdev.tools import ide

        with pytest.raises(ValueError, match="Accepted values"):
            ide.state(id=CONNECTION_ID, include=["selection", "diagnostics"])  # type: ignore[list-item]

    def test_absent_nullable_state_normalizes(self) -> None:
        from otdev.tools import ide

        payload = {
            "protocol_version": 1,
            "snapshot": {
                "connection": {"id": CONNECTION_ID},
                "workspace": {},
                "active_editor": None,
                "selection": None,
            },
        }
        client = Mock()
        client.post.return_value = _mock_response(200, payload)

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            patch("otdev.tools.ide.get_effective_cwd", return_value=Path("/repo")),
        ):
            result = ide.state(id=CONNECTION_ID)

        assert result["selection"] is None
        assert result["active_editor"] is None
        assert result["workspace"]["workspace_folders"] == []
        assert result["workspace"]["workspace_file"] is None

    def test_wrapper_tools_return_plain_text(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.post.return_value = _mock_response(200, _snapshot())

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            patch("otdev.tools.ide.get_effective_cwd", return_value=Path("/repo")),
        ):
            assert ide.file(id=CONNECTION_ID) == "/repo/src/app.py (dirty)"
            assert "Visible ranges: 0-40" in ide.editor(id=CONNECTION_ID)
            assert ide.workspace(id=CONNECTION_ID).splitlines()[0] == "onetool-mcp"
            assert ide.paths(id=CONNECTION_ID).splitlines() == [
                "/repo",
                "/repo/src/app.py",
            ]

    def test_workspace_mismatch_warns_but_state_remains(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.post.return_value = _mock_response(200, _snapshot())

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            patch("otdev.tools.ide.get_effective_cwd", return_value=Path("/different")),
        ):
            result = ide.state(id=CONNECTION_ID)

        assert "warnings" in result
        assert result["selection"]["path"] == "/repo/src/app.py"

    def test_bridge_unavailable_failure(self) -> None:
        from otdev.tools.ide import IdeStateError, state

        client = Mock()
        request = httpx.Request("POST", "http://127.0.0.1:58764/state")
        client.post.side_effect = httpx.ConnectError("refused", request=request)

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            pytest.raises(IdeStateError, match="IDE bridge unavailable"),
        ):
            state(id=CONNECTION_ID)

    def test_malformed_response_names_invalid_fields(self) -> None:
        from otdev.tools.ide import IdeStateError, state

        client = Mock()
        client.post.return_value = _mock_response(
            200,
            {
                "protocol_version": 1,
                "snapshot": {
                    "connection": {"id": CONNECTION_ID},
                    "active_editor": {"document": {"path": 123}},
                },
            },
        )

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            pytest.raises(IdeStateError, match="active_editor"),
        ):
            state(id=CONNECTION_ID)

    def test_protocol_mismatch_failure(self) -> None:
        from otdev.tools.ide import IdeStateError, state

        payload = _snapshot()
        payload["protocol_version"] = 99
        client = Mock()
        client.post.return_value = _mock_response(200, payload)

        with (
            patch("otdev.tools.ide._discover_base_url", return_value=BASE_URL),
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
            pytest.raises(IdeStateError, match="protocol mismatch"),
        ):
            state(id=CONNECTION_ID)

    def test_discovery_scans_until_matching_authenticated_health(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.get.side_effect = [
            _mock_response(200, _health("other")),
            _mock_response(200, _health(CONNECTION_ID)),
        ]

        with (
            patch("otdev.tools.ide._verify_response"),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
        ):
            result = ide._discover_base_url(connection_id=CONNECTION_ID)

        assert result == "http://127.0.0.1:58765/"
        assert ide.DISCOVERED_BASE_URLS[CONNECTION_ID] == result

    def test_discovery_ignores_unsigned_or_malformed_health(self) -> None:
        from otdev.tools import ide

        client = Mock()
        client.get.side_effect = [
            _mock_response(200, {"ok": True}),
            _mock_response(200, _health(CONNECTION_ID)),
        ]

        def verify_side_effect(*, response: httpx.Response, path: str) -> None:
            del path
            if response.json() == {"ok": True}:
                raise ide.IdeStateError("IDE bridge authentication failed")

        with (
            patch("otdev.tools.ide._verify_response", side_effect=verify_side_effect),
            patch("otdev.tools.ide._signed_headers", return_value={}),
            patch("otdev.tools.ide._get_http_client", return_value=client),
        ):
            result = ide._discover_base_url(connection_id=CONNECTION_ID)

        assert result == "http://127.0.0.1:58765/"

    def test_cached_base_url_reused(self) -> None:
        from otdev.tools import ide

        ide.DISCOVERED_BASE_URLS[CONNECTION_ID] = BASE_URL

        with patch("otdev.tools.ide._get_http_client") as get_client:
            result = ide._discover_base_url(connection_id=CONNECTION_ID)

        assert result == BASE_URL
        get_client.assert_not_called()

    def test_rescan_on_cached_bridge_auth_failure(self) -> None:
        from otdev.tools import ide

        ide.DISCOVERED_BASE_URLS[CONNECTION_ID] = BASE_URL
        parsed = ide.BridgeResponse.model_validate(_snapshot())

        with (
            patch(
                "otdev.tools.ide._request_state",
                side_effect=[ide.IdeStateError("IDE bridge authentication failed"), parsed],
            ),
            patch("otdev.tools.ide._discover_base_url", side_effect=[BASE_URL, "http://127.0.0.1:58765/"]),
        ):
            result = ide._bridge_get_state(connection_id=CONNECTION_ID)

        assert result.snapshot.connection.id == CONNECTION_ID

    def test_invalid_scan_config_rejected(self) -> None:
        from otdev.tools import ide

        cfg = ide.Config(port_start=65535, port_count=2)

        with pytest.raises(ide.IdeStateError, match="exceeds 65535"):
            ide._scan_base_urls(cfg)

    def test_explicit_base_url_overrides_discovery(self) -> None:
        from otdev.tools import ide

        with patch("otdev.tools.ide._get_config", return_value=ide.Config(base_url=BASE_URL)):
            assert ide._discover_base_url(connection_id=CONNECTION_ID) == BASE_URL
