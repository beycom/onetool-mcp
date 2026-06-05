"""Starlette app factory for the shared browser-facing Admin App."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from http import HTTPStatus
from importlib import resources
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from onetool.admin.models import AdminSettings
from onetool.admin.services import DISPLAY_PREFIX, AdminService

if TYPE_CHECKING:
    from starlette.requests import Request


def create_app(*, settings: AdminSettings) -> Starlette:
    """Create the shared Admin App ASGI application."""
    service = AdminService(settings=settings)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> Any:
        try:
            yield
        finally:
            await service.aclose()

    return Starlette(
        debug=False,
        lifespan=lifespan,
        routes=[
            Route("/", _index, methods=["GET"]),
            Route("/assets/{asset_path:path}", _asset, methods=["GET"]),
            Route("/api/admin/health", _health, methods=["GET"]),
            Route("/api/admin/register", _register(service), methods=["POST"]),
            Route("/api/admin/scan", _scan(service), methods=["POST"]),
            Route("/api/admin/instances", _instances(service), methods=["GET"]),
            Route("/api/admin/display/refresh", _refresh(service), methods=["POST"]),
            Route(
                "/api/admin/instances/{identity}/display/status",
                _proxy_get(service, f"{DISPLAY_PREFIX}/status"),
                methods=["GET"],
            ),
            Route(
                "/api/admin/instances/{identity}/display/messages",
                _messages(service),
                methods=["GET", "POST"],
            ),
            Route(
                "/api/admin/instances/{identity}/display/messages/{message_id}",
                _message(service),
                methods=["GET"],
            ),
            Route(
                "/api/admin/instances/{identity}/display/messages/{message_id}/payload",
                _payload(service),
                methods=["GET"],
            ),
            Route(
                "/api/admin/instances/{identity}/display/events",
                _events(service),
                methods=["GET"],
            ),
            Route(
                "/api/admin/instances/{identity}/display/preview",
                _preview(service),
                methods=["GET"],
            ),
            Route(
                "/api/admin/instances/{identity}/display/asset",
                _asset_proxy(service),
                methods=["GET"],
            ),
            Route(
                "/api/admin/instances/{identity}/display/focus/{message_id}",
                _focus(service),
                methods=["POST"],
            ),
            Route(
                "/api/admin/instances/{identity}/display/open",
                _open(service),
                methods=["POST"],
            ),
        ],
    )


async def _index(request: Request) -> Response:
    del request
    return HTMLResponse(_index_html())


async def _asset(request: Request) -> Response:
    asset_path = request.path_params.get("asset_path")
    if not isinstance(asset_path, str) or ".." in asset_path.split("/"):
        return JSONResponse({"error": "not found"}, status_code=HTTPStatus.NOT_FOUND)
    try:
        asset = resources.files("onetool_admin_ui.dist").joinpath("assets", asset_path)
    except ModuleNotFoundError:
        return JSONResponse({"error": "not found"}, status_code=HTTPStatus.NOT_FOUND)
    if not asset.is_file():
        return JSONResponse({"error": "not found"}, status_code=HTTPStatus.NOT_FOUND)
    return Response(asset.read_bytes(), media_type=_guess_asset_type(asset_path))


async def _health(request: Request) -> Response:
    del request
    return JSONResponse({"status": "ok", "service": "onetool-admin"})


Endpoint = Callable[["Request"], Awaitable[Response]]


def _scan(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        del request
        instances = await service.scan()
        return JSONResponse({"instances": instances})

    return endpoint


def _register(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("registration payload must be an object")
            instances = await service.register(payload=payload)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_REQUEST)
        return JSONResponse({"instances": instances})

    return endpoint


def _instances(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        del request
        return JSONResponse({"instances": service.store.list_instances()})

    return endpoint


def _refresh(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        del request
        return JSONResponse({"instances": await service.refresh_displays()})

    return endpoint


def _proxy_get(service: AdminService, direct_path: str) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        try:
            payload = await service.proxy_get(identity=identity, path=direct_path)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return JSONResponse(payload)

    return endpoint


def _messages(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        query = str(request.url.query)
        direct_path = f"{DISPLAY_PREFIX}/messages{f'?{query}' if query else ''}"
        try:
            if request.method == "POST":
                payload = await request.json()
                result = await service.proxy_post(identity=identity, path=DISPLAY_PREFIX + "/messages", payload=payload)
                await service.display_message_list(
                    identity=identity,
                    path=f"{DISPLAY_PREFIX}/messages?tail=true&limit=500",
                )
            else:
                result = await service.display_message_list(identity=identity, path=direct_path)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return JSONResponse(result)

    return endpoint


def _events(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        try:
            payload = await service.display_events(identity=identity)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return JSONResponse(payload)

    return endpoint


def _message(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        message_id = quote(str(request.path_params["message_id"]))
        try:
            payload = await service.proxy_get(
                identity=identity,
                path=f"{DISPLAY_PREFIX}/messages/{message_id}",
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return JSONResponse(payload)

    return endpoint


def _payload(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        message_id = quote(str(request.path_params["message_id"]))
        try:
            payload = await service.proxy_get(
                identity=identity,
                path=f"{DISPLAY_PREFIX}/messages/{message_id}/payload",
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return JSONResponse(_rewrite_payload_urls(identity=identity, payload=payload))

    return endpoint


def _preview(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        query = str(request.url.query)
        try:
            payload = await service.proxy_get(
                identity=identity,
                path=f"{DISPLAY_PREFIX}/preview{f'?{query}' if query else ''}",
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return JSONResponse(payload)

    return endpoint


def _asset_proxy(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        query = str(request.url.query)
        try:
            data, media_type = await service.proxy_asset(
                identity=identity,
                path=f"{DISPLAY_PREFIX}/asset{f'?{query}' if query else ''}",
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return Response(data, media_type=media_type)

    return endpoint


def _focus(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        message_id = quote(str(request.path_params["message_id"]))
        try:
            payload = await service.proxy_post(
                identity=identity,
                path=f"{DISPLAY_PREFIX}/focus/{message_id}",
                payload={},
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return JSONResponse(payload)

    return endpoint


def _open(service: AdminService) -> Endpoint:
    async def endpoint(request: Request) -> Response:
        identity = str(request.path_params["identity"])
        try:
            payload = await request.json()
            result = await service.proxy_post(
                identity=identity,
                path=f"{DISPLAY_PREFIX}/open",
                payload=payload,
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTPStatus.BAD_GATEWAY)
        return JSONResponse(result)

    return endpoint


def _index_html() -> str:
    try:
        return (
            resources.files("onetool_admin_ui.dist")
            .joinpath("index.html")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError):
        return (
            "<!doctype html><html><head><title>OneTool Admin</title></head>"
            "<body><div id=\"onetool-admin-root\">Admin UI assets are not built.</div></body></html>"
        )


def _rewrite_payload_urls(*, identity: str, payload: dict[str, object]) -> dict[str, object]:
    next_payload = dict(payload)
    metadata = next_payload.get("metadata")
    if isinstance(metadata, dict):
        payload_info = metadata.get("payload")
        if isinstance(payload_info, dict) and isinstance(payload_info.get("path"), str):
            encoded = quote(str(payload_info["path"]))
            next_payload["file_url"] = f"/api/admin/instances/{identity}/display/preview?path={encoded}"
            next_payload["open_url"] = f"/api/admin/instances/{identity}/display/open"
            if metadata.get("kind") == "image":
                next_payload["image_url"] = f"/api/admin/instances/{identity}/display/asset?path={encoded}"
    return next_payload


def _guess_asset_type(path: str) -> str:
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "css": "text/css",
        "js": "text/javascript",
        "map": "application/json",
        "wasm": "application/wasm",
    }.get(suffix, "application/octet-stream")
