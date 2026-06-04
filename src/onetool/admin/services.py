"""Services for scanning and proxying MCP Direct API instances."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx

from onetool.admin.models import AdminSettings, DiscoveredInstance
from ot.direct_api import PROTOCOL_VERSION
from ot.direct_auth import HEALTH_PATH, READY_PATH, signed_headers, verify_response

BOOTSTRAP_PATH = "/api/admin/bootstrap"
DISPLAY_PREFIX = "/api/admin/display"
DISCONNECTED_RETENTION = timedelta(minutes=30)


class AdminInstanceStore:
    """In-memory snapshot of discovered MCP instances."""

    def __init__(self) -> None:
        self._instances: dict[str, DiscoveredInstance] = {}

    def list_instances(self) -> list[dict[str, Any]]:
        """Return all known instances in browser-safe form."""
        return [instance.to_browser_dict() for instance in self._instances.values()]

    def get(self, identity: str) -> DiscoveredInstance | None:
        """Return one discovered instance by identity."""
        return self._instances.get(identity)

    def upsert(self, instance: DiscoveredInstance, *, max_instances: int) -> None:
        """Insert or update an instance snapshot."""
        existing = self._instances.get(instance.identity)
        if existing is not None:
            instance.discovered_at = existing.discovered_at
        instance.updated_at = datetime.now(UTC)
        for identity, known in list(self._instances.items()):
            if identity != instance.identity and known.base_url == instance.base_url:
                del self._instances[identity]
        self._instances[instance.identity] = instance
        self.prune(max_instances=max_instances)

    def mark_disconnected(self, identity: str) -> None:
        """Mark one known instance disconnected."""
        instance = self._instances.get(identity)
        if instance is not None:
            instance.status = "disconnected"
            instance.updated_at = datetime.now(UTC)

    def prune(self, *, max_instances: int) -> None:
        """Drop stale or excessive disconnected instances."""
        now = datetime.now(UTC)
        for identity, instance in list(self._instances.items()):
            if instance.status == "disconnected" and now - instance.updated_at > DISCONNECTED_RETENTION:
                del self._instances[identity]
        overflow = len(self._instances) - max_instances
        if overflow <= 0:
            return
        for identity, _instance in sorted(
            self._instances.items(),
            key=lambda item: (item[1].status == "connected", item[1].updated_at),
        )[:overflow]:
            del self._instances[identity]


class DirectApiClient:
    """Signed HTTP client for MCP Direct API routes."""

    def __init__(self, *, settings: AdminSettings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient()

    async def get(self, *, base_url: str, path: str, timeout: float = 1.0) -> dict[str, Any]:
        """GET a signed JSON Direct API route."""
        body = b""
        sign_path = _sign_path(path)
        headers = signed_headers(
            method="GET",
            path=sign_path,
            body=body,
            base_dir=self._settings.ot_dir,
        )
        response = await self._client.get(f"{base_url}{path}", headers=headers, timeout=timeout)
        verify_response(
            path=sign_path,
            body=response.content,
            headers=dict(response.headers),
            status_code=response.status_code,
            base_dir=self._settings.ot_dir,
        )
        response.raise_for_status()
        return dict(response.json())

    async def post(
        self,
        *,
        base_url: str,
        path: str,
        payload: dict[str, Any],
        timeout: float = 2.0,
    ) -> dict[str, Any]:
        """POST a signed JSON Direct API route."""
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sign_path = _sign_path(path)
        headers = {
            "content-type": "application/json",
            **signed_headers(
                method="POST",
                path=sign_path,
                body=body,
                base_dir=self._settings.ot_dir,
            ),
        }
        response = await self._client.post(f"{base_url}{path}", content=body, headers=headers, timeout=timeout)
        verify_response(
            path=sign_path,
            body=response.content,
            headers=dict(response.headers),
            status_code=response.status_code,
            base_dir=self._settings.ot_dir,
        )
        response.raise_for_status()
        return dict(response.json())

    async def get_bytes(
        self, *, base_url: str, path: str, timeout: float = 2.0
    ) -> tuple[bytes, str]:
        """GET a signed binary Direct API route."""
        body = b""
        sign_path = _sign_path(path)
        headers = signed_headers(
            method="GET",
            path=sign_path,
            body=body,
            base_dir=self._settings.ot_dir,
        )
        response = await self._client.get(f"{base_url}{path}", headers=headers, timeout=timeout)
        verify_response(
            path=sign_path,
            body=response.content,
            headers=dict(response.headers),
            status_code=response.status_code,
            base_dir=self._settings.ot_dir,
        )
        response.raise_for_status()
        return response.content, response.headers.get("content-type", "application/octet-stream")

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


class AdminService:
    """High-level scan, store, and proxy operations."""

    def __init__(self, *, settings: AdminSettings) -> None:
        self.settings = settings
        self.store = AdminInstanceStore()
        self.direct = DirectApiClient(settings=settings)

    async def scan(self) -> list[dict[str, Any]]:
        """Scan configured Direct API candidate ports and update the snapshot."""
        ports = range(
            self.settings.direct_start_port,
            self.settings.direct_start_port + self.settings.scan_max,
        )
        instances = await asyncio.gather(
            *(self._probe(base_url=f"http://127.0.0.1:{port}") for port in ports)
        )
        for instance in instances:
            if instance is not None:
                self.store.upsert(instance, max_instances=self.settings.max_instances)
        self.store.prune(max_instances=self.settings.max_instances)
        return self.store.list_instances()

    async def refresh_displays(self) -> list[dict[str, Any]]:
        """Refresh display status for all connected instances."""
        for instance in list(self.store._instances.values()):
            if instance.status != "connected":
                continue
            try:
                status = await self.direct.get(
                    base_url=instance.base_url,
                    path=f"{DISPLAY_PREFIX}/status",
                )
            except Exception:
                self.store.mark_disconnected(instance.identity)
                continue
            instance.display = status
            instance.updated_at = datetime.now(UTC)
        self.store.prune(max_instances=self.settings.max_instances)
        return self.store.list_instances()

    async def proxy_get(self, *, identity: str, path: str) -> dict[str, Any]:
        """Proxy a browser GET through a signed MCP Direct API call."""
        instance = self._connected_instance(identity)
        try:
            return await self.direct.get(base_url=instance.base_url, path=path)
        except Exception:
            self.store.mark_disconnected(identity)
            raise

    async def proxy_post(
        self, *, identity: str, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Proxy a browser POST through a signed MCP Direct API call."""
        instance = self._connected_instance(identity)
        try:
            return await self.direct.post(
                base_url=instance.base_url,
                path=path,
                payload=payload,
            )
        except Exception:
            self.store.mark_disconnected(identity)
            raise

    async def proxy_asset(self, *, identity: str, path: str) -> tuple[bytes, str]:
        """Proxy a browser asset GET through signed MCP Direct API."""
        instance = self._connected_instance(identity)
        try:
            return await self.direct.get_bytes(base_url=instance.base_url, path=path)
        except Exception:
            self.store.mark_disconnected(identity)
            raise

    async def aclose(self) -> None:
        """Close service-owned network resources."""
        await self.direct.aclose()

    async def _probe(self, *, base_url: str) -> DiscoveredInstance | None:
        try:
            health = await self.direct.get(base_url=base_url, path=HEALTH_PATH)
            if health.get("protocol_version") != PROTOCOL_VERSION:
                return None
            await self.direct.get(base_url=base_url, path=READY_PATH)
            bootstrap = await self.direct.get(base_url=base_url, path=BOOTSTRAP_PATH)
        except Exception:
            return None
        identity = bootstrap.get("identity")
        if not isinstance(identity, str):
            return None
        return DiscoveredInstance(
            identity=identity,
            short_identity=str(bootstrap.get("short_identity", "")),
            base_url=str(bootstrap.get("base_url", base_url)),
            cwd=str(bootstrap.get("cwd", "")),
            started_at=str(bootstrap.get("started_at", "")),
            api_version=int(bootstrap.get("api_version", 0)),
            status="connected",
            display=dict(bootstrap.get("display", {})),
        )

    def _connected_instance(self, identity: str) -> DiscoveredInstance:
        instance = self.store.get(identity)
        if instance is None:
            raise KeyError(f"unknown MCP instance: {identity}")
        if instance.status != "connected":
            raise RuntimeError(f"MCP instance is disconnected: {identity}")
        return instance


def _sign_path(path: str) -> str:
    """Return the URL path component used by Direct API signatures."""
    return urlsplit(path).path
