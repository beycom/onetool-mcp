"""Unit tests for the shared browser-facing Admin App."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pytest

from onetool.admin.app import create_app
from onetool.admin.models import AdminSettings, DiscoveredInstance
from onetool.admin.services import AdminInstanceStore, AdminService

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.core
async def test_admin_app_serves_static_fallback(tmp_path: Path) -> None:
    """Admin App serves an HTML shell when generated assets are absent."""
    app = create_app(settings=AdminSettings(ot_dir=tmp_path))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "onetool-admin-root" in response.text


@pytest.mark.unit
@pytest.mark.core
async def test_admin_scan_stores_successful_instances(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scan stores successful signed probes in memory."""
    service = AdminService(settings=AdminSettings(ot_dir=tmp_path, direct_start_port=9000, scan_max=2))
    discovered = DiscoveredInstance(
        identity="mcp-alpha",
        short_identity="alpha",
        base_url="http://127.0.0.1:9000",
        cwd=str(tmp_path),
        started_at="2026-06-04T00:00:00+00:00",
        api_version=1,
        status="connected",
        display={"mcp_instance_id": "mcp-alpha", "message_count": 0},
    )

    async def fake_probe(*, base_url: str) -> DiscoveredInstance | None:
        return discovered if base_url.endswith(":9000") else None

    monkeypatch.setattr(service, "_probe", fake_probe)

    result = await service.scan()
    await service.aclose()

    assert [item["identity"] for item in result] == ["mcp-alpha"]
    assert service.store.get("mcp-alpha") is not None


@pytest.mark.unit
@pytest.mark.core
async def test_admin_scan_probes_candidate_ports_concurrently(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scan starts candidate port probes concurrently."""
    service = AdminService(settings=AdminSettings(ot_dir=tmp_path, direct_start_port=9000, scan_max=3))
    release = asyncio.Event()
    started: list[str] = []

    async def fake_probe(*, base_url: str) -> DiscoveredInstance | None:
        started.append(base_url)
        if len(started) == service.settings.scan_max:
            release.set()
        await release.wait()
        return None

    monkeypatch.setattr(service, "_probe", fake_probe)

    result = await service.scan()
    await service.aclose()

    assert result == []
    assert started == [
        "http://127.0.0.1:9000",
        "http://127.0.0.1:9001",
        "http://127.0.0.1:9002",
    ]


@pytest.mark.unit
@pytest.mark.core
async def test_admin_refresh_marks_failed_instance_disconnected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Batched display refresh updates successes and marks failures disconnected."""
    service = AdminService(settings=AdminSettings(ot_dir=tmp_path))
    service.store.upsert(
        DiscoveredInstance(
            identity="mcp-ok",
            short_identity="ok",
            base_url="http://127.0.0.1:9000",
            cwd=str(tmp_path),
            started_at="2026-06-04T00:00:00+00:00",
            api_version=1,
            status="connected",
            display={"message_count": 0},
        ),
        max_instances=service.settings.max_instances,
    )
    service.store.upsert(
        DiscoveredInstance(
            identity="mcp-gone",
            short_identity="gone",
            base_url="http://127.0.0.1:9001",
            cwd=str(tmp_path),
            started_at="2026-06-04T00:00:00+00:00",
            api_version=1,
            status="connected",
            display={"message_count": 0},
        ),
        max_instances=service.settings.max_instances,
    )

    async def fake_get(*, base_url: str, path: str, timeout: float = 1.0) -> dict[str, object]:
        del path, timeout
        if base_url.endswith(":9001"):
            raise RuntimeError("gone")
        return {"mcp_instance_id": "mcp-ok", "message_count": 3}

    monkeypatch.setattr(service.direct, "get", fake_get)

    result = await service.refresh_displays()
    await service.aclose()

    by_id = {item["identity"]: item for item in result}
    assert by_id["mcp-ok"]["display"]["message_count"] == 3
    assert by_id["mcp-gone"]["status"] == "disconnected"


@pytest.mark.unit
@pytest.mark.core
async def test_admin_proxy_failure_marks_disconnected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Failed signed follow-up requests mark the instance disconnected."""
    service = AdminService(settings=AdminSettings(ot_dir=tmp_path))
    service.store.upsert(
        DiscoveredInstance(
            identity="mcp-gone",
            short_identity="gone",
            base_url="http://127.0.0.1:9001",
            cwd=str(tmp_path),
            started_at="2026-06-04T00:00:00+00:00",
            api_version=1,
            status="connected",
            display={"message_count": 0},
        ),
        max_instances=service.settings.max_instances,
    )

    async def fake_get(*, base_url: str, path: str, timeout: float = 1.0) -> dict[str, object]:
        del base_url, path, timeout
        raise RuntimeError("gone")

    monkeypatch.setattr(service.direct, "get", fake_get)

    with pytest.raises(RuntimeError, match="gone"):
        await service.proxy_get(identity="mcp-gone", path="/api/admin/display/messages")
    await service.aclose()

    assert service.store.get("mcp-gone").status == "disconnected"  # type: ignore[union-attr]


@pytest.mark.unit
@pytest.mark.core
def test_admin_store_replaces_same_base_url(tmp_path: Path) -> None:
    """Instance store replaces old identities for the same Direct API URL."""
    del tmp_path
    store = AdminInstanceStore()
    older = DiscoveredInstance(
        identity="mcp-old",
        short_identity="old",
        base_url="http://127.0.0.1:9000",
        cwd=".",
        started_at="2026-06-04T00:00:00+00:00",
        api_version=1,
        status="connected",
        display={"message_count": 0},
    )
    newer = DiscoveredInstance(
        identity="mcp-new",
        short_identity="new",
        base_url="http://127.0.0.1:9000",
        cwd=".",
        started_at="2026-06-04T00:01:00+00:00",
        api_version=1,
        status="connected",
        display={"message_count": 0},
    )
    store.upsert(older, max_instances=10)
    store.upsert(newer, max_instances=10)

    identities = [item["identity"] for item in store.list_instances()]
    assert identities == ["mcp-new"]


@pytest.mark.unit
@pytest.mark.core
def test_admin_store_prunes_stale_disconnected(tmp_path: Path) -> None:
    """Instance store drops disconnected entries after the retention window."""
    del tmp_path
    store = AdminInstanceStore()
    stale = DiscoveredInstance(
        identity="mcp-stale",
        short_identity="stale",
        base_url="http://127.0.0.1:9001",
        cwd=".",
        started_at="2026-06-04T00:02:00+00:00",
        api_version=1,
        status="connected",
        display={"message_count": 0},
    )

    store.upsert(stale, max_instances=10)
    store.mark_disconnected("mcp-stale")
    stored = store.get("mcp-stale")
    assert stored is not None
    stored.updated_at = datetime.now(UTC) - timedelta(hours=1)
    store.prune(max_instances=10)

    assert store.list_instances() == []


@pytest.mark.unit
@pytest.mark.core
def test_admin_store_prunes_overflow_preferring_disconnected(tmp_path: Path) -> None:
    """Instance store enforces max size without dropping connected instances first."""
    del tmp_path
    store = AdminInstanceStore()
    connected = DiscoveredInstance(
        identity="mcp-connected",
        short_identity="connected",
        base_url="http://127.0.0.1:9000",
        cwd=".",
        started_at="2026-06-04T00:00:00+00:00",
        api_version=1,
        status="connected",
        display={"message_count": 0},
    )
    disconnected = DiscoveredInstance(
        identity="mcp-disconnected",
        short_identity="disconnected",
        base_url="http://127.0.0.1:9001",
        cwd=".",
        started_at="2026-06-04T00:01:00+00:00",
        api_version=1,
        status="disconnected",
        display={"message_count": 0},
    )

    store.upsert(disconnected, max_instances=10)
    store.upsert(connected, max_instances=1)

    identities = [item["identity"] for item in store.list_instances()]
    assert identities == ["mcp-connected"]
