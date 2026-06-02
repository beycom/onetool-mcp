from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003 - pytest fixture annotation only.
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from ot.display.server import ensure_server
from ot.display.state import STATE


@pytest.mark.unit
@pytest.mark.core
class TestDisplayServer:
    """Test local display server routes."""

    def test_server_binds_to_localhost(self) -> None:
        base_url = ensure_server()

        assert base_url.startswith("http://127.0.0.1:")

    def test_scoped_status_and_message_routes(self) -> None:
        base_url = ensure_server()
        status = STATE.status(base_url=base_url)
        token = status.url.split("token=", 1)[1]
        payload = {"kind": "text", "content": "route payload", "title": "Route"}

        created = _post_json(
            f"{base_url}/api/instances/{status.mcp_instance_id}/messages?{urlencode({'token': token})}",
            payload,
        )
        read = _get_json(
            f"{base_url}/api/instances/{status.mcp_instance_id}/messages/{created['id']}?{urlencode({'token': token})}"
        )

        assert created["id"].startswith("msg-")
        assert read["metadata"]["id"] == created["id"]
        assert read["preview"]["text"] == "route payload"

    def test_rejects_wrong_instance_token(self) -> None:
        base_url = ensure_server()
        status = STATE.status(base_url=base_url)

        with pytest.raises(HTTPError) as exc:
            _get_json(
                f"{base_url}/api/instances/{status.mcp_instance_id}/messages?token=wrong"
            )

        assert exc.value.code == 403

    def test_file_preview_allows_workspace_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace = tmp_path
        path = workspace / "result.txt"
        path.write_text("preview text", encoding="utf-8")
        monkeypatch.setenv("OT_CWD", str(workspace))
        base_url = ensure_server()
        status = STATE.status(base_url=base_url)
        token = status.url.split("token=", 1)[1]

        preview = _get_json(
            f"{base_url}/api/instances/{status.mcp_instance_id}/preview?{urlencode({'token': token, 'path': 'result.txt'})}"
        )

        assert preview["text"] == "preview text"

    def test_file_preview_respects_limit_without_full_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "result.txt"
        path.write_text("abcdef", encoding="utf-8")
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        base_url = ensure_server()
        status = STATE.status(base_url=base_url)
        token = status.url.split("token=", 1)[1]

        preview = _get_json(
            f"{base_url}/api/instances/{status.mcp_instance_id}/preview?{urlencode({'token': token, 'path': 'result.txt', 'limit': '3'})}"
        )

        assert preview["text"] == "abc"
        assert preview["truncated"] is True
        assert preview["size_bytes"] == 6
        assert preview["limit_bytes"] == 3

    def test_file_preview_denies_outside_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        monkeypatch.setenv("OT_CWD", str(workspace))
        base_url = ensure_server()
        status = STATE.status(base_url=base_url)
        token = status.url.split("token=", 1)[1]

        with pytest.raises(HTTPError) as exc:
            _get_json(
                f"{base_url}/api/instances/{status.mcp_instance_id}/preview?{urlencode({'token': token, 'path': '../outside.txt'})}"
            )

        assert exc.value.code == 403

    def test_payload_route_returns_inline_content(self) -> None:
        base_url = ensure_server()
        status = STATE.status(base_url=base_url)
        token = status.url.split("token=", 1)[1]
        created = _post_json(
            f"{base_url}/api/instances/{status.mcp_instance_id}/messages?{urlencode({'token': token})}",
            {"kind": "table", "content": [{"name": "Ada", "score": 10}]},
        )

        payload = _get_json(
            f"{base_url}/api/instances/{status.mcp_instance_id}/messages/{created['id']}/payload?{urlencode({'token': token})}"
        )

        assert payload["content"] == [{"name": "Ada", "score": 10}]
        assert payload["metadata"]["kind"] == "table"

    def test_asset_route_serves_allowed_image(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        image_path = tmp_path / "pixel.png"
        image_path.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        )
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        base_url = ensure_server()
        status = STATE.status(base_url=base_url)
        token = status.url.split("token=", 1)[1]

        with urlopen(
            f"{base_url}/api/instances/{status.mcp_instance_id}/asset?{urlencode({'token': token, 'path': 'pixel.png'})}",
            timeout=5,
        ) as response:
            assert response.headers["content-type"] == "image/png"
            assert response.read().startswith(b"\x89PNG")

    def test_open_route_validates_workspace_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "result.txt"
        target.write_text("ok", encoding="utf-8")
        monkeypatch.setenv("OT_CWD", str(tmp_path))
        opened_paths: list[Path] = []
        monkeypatch.setattr("ot.display.server._open_path", lambda path: opened_paths.append(path) is None or True)
        base_url = ensure_server()
        status = STATE.status(base_url=base_url)
        token = status.url.split("token=", 1)[1]

        result = _post_json(
            f"{base_url}/api/instances/{status.mcp_instance_id}/open?{urlencode({'token': token})}",
            {"path": "result.txt"},
        )

        assert result["opened"] is True
        assert result["path"] == str(target)
        assert opened_paths == [target]


def _get_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))
