"""Display routes for the local admin dashboard."""

from __future__ import annotations

import json
import subprocess
import sys
from http import HTTPStatus
from importlib import resources
from typing import TYPE_CHECKING

from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from ot.display.models import ShowRequest
from ot.display.state import STATE, resolve_allowed_path

DISPLAY_BOOTSTRAP_PLACEHOLDER = "<!-- ONETOOL_DISPLAY_BOOTSTRAP -->"

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.requests import Request

async def browser_entry(request: Request) -> Response:
    """Serve the packaged admin UI for browser routes."""
    browser_instance_id = request.path_params.get("browser_instance_id")
    if not isinstance(browser_instance_id, str):
        return HTMLResponse(_index_html(instance_id="", token=""))
    bootstrap = STATE.resolve_browser_instance(browser_instance_id=browser_instance_id)
    if bootstrap is None:
        return JSONResponse({"error": "not found"}, status_code=HTTPStatus.NOT_FOUND)
    instance_id, token = bootstrap
    return HTMLResponse(_index_html(instance_id=instance_id, token=token))


async def status(request: Request) -> Response:
    """Return current display instance status."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    return JSONResponse(STATE.status(base_url=_base_url(request)).model_dump(mode="json"))


async def messages(request: Request) -> Response:
    """List or create display messages."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    if request.method == "POST":
        payload = await request.json()
        show_request = ShowRequest.model_validate(payload)
        metadata = STATE.add_message(request=show_request)
        return JSONResponse({"id": metadata.id, "metadata": metadata.model_dump(mode="json")})
    message_list = STATE.list_messages(
        limit=_query_int(request, "limit", 100, minimum=1, maximum=500),
        offset=_query_int(request, "offset", 0, minimum=0, maximum=100000),
        tail=_query_bool(request, "tail", False),
        kind=request.query_params.get("kind"),
        source=request.query_params.get("source"),
    )
    return JSONResponse(message_list.model_dump(mode="json"))


async def message(request: Request) -> Response:
    """Return one display message record."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    message_read = STATE.read_message(id=str(request.path_params["message_id"]))
    if message_read is None:
        return JSONResponse({"error": "message not found"}, status_code=HTTPStatus.NOT_FOUND)
    return JSONResponse(message_read.model_dump(mode="json"))


async def payload(request: Request) -> Response:
    """Return one lazy browser payload view."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    payload_view = STATE.payload_view(
        id=str(request.path_params["message_id"]),
        base_url=_base_url(request),
    )
    if payload_view is None:
        return JSONResponse({"error": "message not found"}, status_code=HTTPStatus.NOT_FOUND)
    return JSONResponse(payload_view)


async def events(request: Request) -> Response:
    """Return queued display browser events."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    result = STATE.poll_events(
        instance_id=str(request.path_params["instance_id"]),
        token=request.query_params.get("token") or "",
    )
    return JSONResponse({"events": result or []})


async def preview(request: Request) -> Response:
    """Return a bounded text preview for an allowed workspace file."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    path = request.query_params.get("path")
    if path is None:
        return JSONResponse({"error": "path is required"}, status_code=HTTPStatus.BAD_REQUEST)
    try:
        resolved = resolve_allowed_path(path)
        limit = _query_int(request, "limit", 65536, minimum=1, maximum=262144)
        data, size = _read_bounded_file(resolved, limit=limit)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=HTTPStatus.FORBIDDEN)
    except OSError as exc:
        return JSONResponse({"error": str(exc)}, status_code=HTTPStatus.NOT_FOUND)
    return JSONResponse(
        {
            "path": str(resolved),
            "text": data[:limit].decode("utf-8", errors="replace"),
            "truncated": size > limit,
            "size_bytes": size,
            "limit_bytes": limit,
        }
    )


async def asset(request: Request) -> Response:
    """Return an allowed image asset."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    path = request.query_params.get("path")
    if path is None:
        return JSONResponse({"error": "path is required"}, status_code=HTTPStatus.BAD_REQUEST)
    try:
        resolved = resolve_allowed_path(path)
        if not resolved.is_file():
            return JSONResponse({"error": "not found"}, status_code=HTTPStatus.NOT_FOUND)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=HTTPStatus.FORBIDDEN)
    except OSError as exc:
        return JSONResponse({"error": str(exc)}, status_code=HTTPStatus.NOT_FOUND)
    return FileResponse(resolved, media_type=_guess_image_type(resolved.suffix.lower()))


async def focus(request: Request) -> Response:
    """Focus one display message."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    result = STATE.focus(id=str(request.path_params["message_id"]))
    if result is None:
        return JSONResponse({"error": "message not found"}, status_code=HTTPStatus.NOT_FOUND)
    return JSONResponse(result.model_dump(mode="json"))


async def open_path(request: Request) -> Response:
    """Open an allowed local file path through an explicit user action."""
    auth = _authorize(request)
    if auth is not None:
        return auth
    payload_data = await request.json()
    path = payload_data.get("path") if isinstance(payload_data, dict) else None
    if not isinstance(path, str):
        return JSONResponse({"error": "path is required"}, status_code=HTTPStatus.BAD_REQUEST)
    try:
        resolved = resolve_allowed_path(path)
    except PermissionError:
        return JSONResponse({"error": "forbidden"}, status_code=HTTPStatus.FORBIDDEN)
    opened = _open_path(resolved)
    return JSONResponse(
        {"status": "opened" if opened else "unavailable", "opened": opened, "path": str(resolved)}
    )


def _authorize(request: Request) -> JSONResponse | None:
    instance_id = str(request.path_params["instance_id"])
    token = request.query_params.get("token")
    if STATE.authorize(instance_id=instance_id, token=token):
        return None
    return JSONResponse({"error": "forbidden"}, status_code=HTTPStatus.FORBIDDEN)


def _base_url(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


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


def _guess_image_type(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")


def _read_bounded_file(path: Path, *, limit: int) -> tuple[bytes, int]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        return stream.read(limit), size


def _open_path(path: Path) -> bool:
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


def _index_html(*, instance_id: str, token: str) -> str:
    try:
        html = (
            resources.files("ot_display_ui.dist")
            .joinpath("index.html")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError):
        html = _fallback_html()
    payload = json.dumps({"instanceId": instance_id, "token": token})
    bootstrap = f"<script>window.__ONETOOL_DISPLAY_BOOTSTRAP__={payload};</script>"
    return _inject_display_bootstrap(html, bootstrap)


def _inject_display_bootstrap(html: str, bootstrap: str) -> str:
    """Inject display bootstrap without matching tags inside bundled scripts."""
    if DISPLAY_BOOTSTRAP_PLACEHOLDER in html:
        return html.replace(DISPLAY_BOOTSTRAP_PLACEHOLDER, bootstrap, 1)
    head, separator, tail = html.rpartition("</head>")
    if not separator:
        return f"{bootstrap}{html}"
    return f"{head}{bootstrap}{separator}{tail}"


def _fallback_html() -> str:
    return (
        "<!doctype html><html><head><title>OneTool Admin</title></head>"
        "<body><div id=\"onetool-display-root\">Admin UI assets are not built.</div></body></html>"
    )


routes = [
    Route("/", browser_entry, methods=["GET"]),
    Route("/display", browser_entry, methods=["GET"]),
    Route("/display/{browser_instance_id}", browser_entry, methods=["GET"]),
    Route("/api/display/instances/{instance_id}/status", status, methods=["GET"]),
    Route("/api/display/instances/{instance_id}/messages", messages, methods=["GET", "POST"]),
    Route("/api/display/instances/{instance_id}/messages/{message_id}", message, methods=["GET"]),
    Route(
        "/api/display/instances/{instance_id}/messages/{message_id}/payload",
        payload,
        methods=["GET"],
    ),
    Route("/api/display/instances/{instance_id}/events", events, methods=["GET"]),
    Route("/api/display/instances/{instance_id}/preview", preview, methods=["GET"]),
    Route("/api/display/instances/{instance_id}/asset", asset, methods=["GET"]),
    Route("/api/display/instances/{instance_id}/focus/{message_id}", focus, methods=["POST"]),
    Route("/api/display/instances/{instance_id}/open", open_path, methods=["POST"]),
]
