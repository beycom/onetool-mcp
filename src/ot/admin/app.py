"""Starlette app factory for the local admin dashboard."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.routing import Route

from ot.admin.routes.health import health


def create_app() -> Starlette:
    """Create the local admin ASGI app."""
    return Starlette(
        debug=False,
        routes=[
            Route("/api/admin/health", health, methods=["GET"]),
        ],
    )
