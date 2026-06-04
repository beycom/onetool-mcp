"""Shared browser-facing Admin App for OneTool."""

from __future__ import annotations

__all__ = ["create_app", "serve_admin_app"]


def __getattr__(name: str) -> object:
    if name == "create_app":
        from onetool.admin.app import create_app

        return create_app
    if name == "serve_admin_app":
        from onetool.admin.server import serve_admin_app

        return serve_admin_app
    raise AttributeError(name)
