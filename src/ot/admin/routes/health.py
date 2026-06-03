"""Admin health routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request


async def health(_request: Request) -> JSONResponse:
    """Return local admin service health."""
    return JSONResponse({"status": "ok", "service": "onetool-admin"})
