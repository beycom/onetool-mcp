"""Uvicorn runner for the shared Admin App."""

from __future__ import annotations

from pathlib import Path

import uvicorn

from onetool.admin.app import create_app
from onetool.admin.models import AdminSettings


def serve_admin_app(
    *,
    ot_dir: Path,
    port: int = 8760,
    direct_start_port: int = 8765,
    scan_max: int = 10,
) -> None:
    """Run the shared Admin App until interrupted."""
    settings = AdminSettings(
        ot_dir=ot_dir,
        port=port,
        direct_start_port=direct_start_port,
        scan_max=scan_max,
    )
    uvicorn.run(
        create_app(settings=settings),
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
