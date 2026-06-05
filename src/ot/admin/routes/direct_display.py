"""Signed Direct API admin and display routes for the current MCP process."""

from __future__ import annotations

import json
import subprocess
import sys
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, cast

from starlette.responses import Response
from starlette.routing import Route

from ot.direct_api import PROTOCOL_VERSION
from ot.display.models import ShowRequest
from ot.display.state import STATE, resolve_allowed_path
from ot.runtime_meta import STARTED_AT, get_runtime_meta

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.requests import Request

API_VERSION = 1
MAX_ASSET_BYTES = 16 * 1024 * 1024


def create_routes(*, base_url: str) -> list[Route]:
    """Return signed admin/display routes for a Direct API app."""
    return [
        Route("/api/admin/bootstrap", _signed_json(_bootstrap, base_url=base_url), methods=["GET"]),
        Route("/api/admin/display/status", _signed_json(_status), methods=["GET"]),
        Route("/api/admin/display/messages", _signed_json(_messages), methods=["GET", "POST"]),
        Route("/api/admin/display/messages/{message_id}", _signed_json(_message), methods=["GET"]),
        Route(
            "/api/admin/display/messages/{message_id}/payload",
            _signed_json(_payload),
            methods=["GET"],
        ),
        Route("/api/admin/display/events", _signed_json(_events), methods=["GET"]),
        Route("/api/admin/display/preview", _signed_json(_preview), methods=["GET"]),
        Route("/api/admin/display/asset", _signed_binary(_asset), methods=["GET"]),
        Route(
            "/api/admin/display/focus/{message_id}",
            _signed_json(_focus),
            methods=["POST"],
        ),
        Route("/api/admin/display/open", _signed_json(_open_path), methods=["POST"]),
    ]


def _signed_json(handler: Any, **handler_kwargs: Any) -> Any:
    async def endpoint(request: Request) -> Response:
        from ot.direct_auth import (
            HmacAuthError,
            auth_error_response,
            signed_json_response,
            verify_request,
        )

        body = await request.body()
        path = request.url.path
        try:
            verify_request(
                method=request.method,
                path=path,
                body=body,
                headers=dict(request.headers),
            )
        except HmacAuthError as e:
            return cast("Response", auth_error_response(e, path=path))

        try:
            payload, status_code = await handler(request, body=body, **handler_kwargs)
        except ValueError as e:
            payload, status_code = {"error": str(e)}, HTTPStatus.BAD_REQUEST
        return cast(
            "Response",
            signed_json_response(dict(payload), path=path, status_code=int(status_code)),
        )

    return endpoint


def _signed_binary(handler: Any) -> Any:
    async def endpoint(request: Request) -> Response:
        from ot.direct_auth import (
            HmacAuthError,
            auth_error_response,
            sign_response,
            verify_request,
        )

        body = await request.body()
        path = request.url.path
        try:
            verify_request(
                method=request.method,
                path=path,
                body=body,
                headers=dict(request.headers),
            )
        except HmacAuthError as e:
            return cast("Response", auth_error_response(e, path=path))

        data, media_type, status_code = await handler(request, body=body)
        headers = sign_response(path=path, body=data, status_code=int(status_code))
        return Response(data, status_code=int(status_code), headers=headers, media_type=media_type)

    return endpoint


async def _bootstrap(
    request: Request, *, body: bytes, base_url: str
) -> tuple[dict[str, Any], int]:
    del request, body
    status = STATE.status()
    runtime = get_runtime_meta()
    return (
        {
            "protocol_version": PROTOCOL_VERSION,
            "api_version": API_VERSION,
            "identity": status.mcp_instance_id,
            "short_identity": status.mcp_instance_id.removeprefix("mcp-")[:16],
            "base_url": base_url,
            "cwd": runtime["cwd"],
            "config_path": runtime["config_path"],
            "config_dir": runtime["config_dir"],
            "started_at": STARTED_AT.isoformat(),
            "meta": runtime,
            "display": status.model_dump(mode="json"),
        },
        HTTPStatus.OK,
    )


async def _status(request: Request, *, body: bytes) -> tuple[dict[str, Any], int]:
    del request, body
    return STATE.status().model_dump(mode="json"), HTTPStatus.OK


async def _messages(request: Request, *, body: bytes) -> tuple[dict[str, Any], int]:
    if request.method == "POST":
        payload = json.loads(body.decode("utf-8") or "{}")
        show_request = ShowRequest.model_validate(payload)
        metadata = STATE.add_message(request=show_request)
        return {"id": metadata.id, "metadata": metadata.model_dump(mode="json")}, HTTPStatus.OK
    message_list = STATE.list_messages(
        limit=_query_int(request, "limit", 100, minimum=1, maximum=500),
        offset=_query_int(request, "offset", 0, minimum=0, maximum=100000),
        tail=_query_bool(request, "tail", False),
        kind=request.query_params.get("kind"),
        source=request.query_params.get("source"),
    )
    return message_list.model_dump(mode="json"), HTTPStatus.OK


async def _message(request: Request, *, body: bytes) -> tuple[dict[str, Any], int]:
    del body
    message = STATE.read_message(id=str(request.path_params["message_id"]))
    if message is None:
        return {"error": "message not found"}, HTTPStatus.NOT_FOUND
    return message.model_dump(mode="json"), HTTPStatus.OK


async def _payload(request: Request, *, body: bytes) -> tuple[dict[str, Any], int]:
    del body
    payload = STATE.payload_view(id=str(request.path_params["message_id"]))
    if payload is None:
        return {"error": "message not found"}, HTTPStatus.NOT_FOUND
    return payload, HTTPStatus.OK


async def _events(request: Request, *, body: bytes) -> tuple[dict[str, Any], int]:
    del request, body
    return {"events": STATE.poll_current_events()}, HTTPStatus.OK


async def _preview(request: Request, *, body: bytes) -> tuple[dict[str, Any], int]:
    del body
    path = request.query_params.get("path")
    if path is None:
        return {"error": "path is required"}, HTTPStatus.BAD_REQUEST
    try:
        resolved = resolve_allowed_path(path)
        limit = _query_int(request, "limit", 65536, minimum=1, maximum=262144)
        data, size = _read_bounded_file(resolved, limit=limit)
    except PermissionError:
        return {"error": "forbidden"}, HTTPStatus.FORBIDDEN
    except OSError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND
    return (
        {
            "path": str(resolved),
            "text": data[:limit].decode("utf-8", errors="replace"),
            "truncated": size > limit,
            "size_bytes": size,
            "limit_bytes": limit,
        },
        HTTPStatus.OK,
    )


async def _asset(request: Request, *, body: bytes) -> tuple[bytes, str, int]:
    del body
    path = request.query_params.get("path")
    if path is None:
        return _json_bytes({"error": "path is required"}), "application/json", HTTPStatus.BAD_REQUEST
    try:
        resolved = resolve_allowed_path(path)
        if not resolved.is_file():
            return _json_bytes({"error": "not found"}), "application/json", HTTPStatus.NOT_FOUND
        if resolved.stat().st_size > MAX_ASSET_BYTES:
            return _json_bytes({"error": "asset too large"}), "application/json", HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        return resolved.read_bytes(), _guess_image_type(resolved.suffix.lower()), HTTPStatus.OK
    except PermissionError:
        return _json_bytes({"error": "forbidden"}), "application/json", HTTPStatus.FORBIDDEN
    except OSError as exc:
        return _json_bytes({"error": str(exc)}), "application/json", HTTPStatus.NOT_FOUND


async def _focus(request: Request, *, body: bytes) -> tuple[dict[str, Any], int]:
    del body
    result = STATE.focus(id=str(request.path_params["message_id"]))
    if result is None:
        return {"error": "message not found"}, HTTPStatus.NOT_FOUND
    return result.model_dump(mode="json"), HTTPStatus.OK


async def _open_path(request: Request, *, body: bytes) -> tuple[dict[str, Any], int]:
    del request
    payload = json.loads(body.decode("utf-8") or "{}")
    path = payload.get("path") if isinstance(payload, dict) else None
    if not isinstance(path, str):
        return {"error": "path is required"}, HTTPStatus.BAD_REQUEST
    try:
        resolved = resolve_allowed_path(path)
    except PermissionError:
        return {"error": "forbidden"}, HTTPStatus.FORBIDDEN
    opened = _open_file(resolved)
    return {"status": "opened" if opened else "unavailable", "opened": opened, "path": str(resolved)}, HTTPStatus.OK


def _query_int(
    request: Request,
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = request.query_params.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


def _query_bool(request: Request, name: str, default: bool) -> bool:
    value = request.query_params.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _read_bounded_file(path: Path, *, limit: int) -> tuple[bytes, int]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        return stream.read(limit), size


def _guess_image_type(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")


def _open_file(path: Path) -> bool:
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


__all__ = ["API_VERSION", "MAX_ASSET_BYTES", "STARTED_AT", "create_routes"]
