"""Admin App data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

InstanceStatus = Literal["connected", "disconnected"]


@dataclass
class AdminSettings:
    """Runtime settings for the shared Admin App."""

    ot_dir: Path
    host: str = "127.0.0.1"
    port: int = 8760
    max_instances: int = 100


@dataclass
class DiscoveredInstance:
    """One signed MCP Direct API instance discovered by the Admin App."""

    identity: str
    short_identity: str
    base_url: str
    cwd: str
    started_at: str
    api_version: int
    status: InstanceStatus
    display: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    heartbeat_seconds: float = 15.0
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_browser_dict(self) -> dict[str, Any]:
        """Return browser-safe instance metadata."""
        return {
            "identity": self.identity,
            "short_identity": self.short_identity,
            "base_url": self.base_url,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "api_version": self.api_version,
            "status": self.status,
            "display": self.display,
            "meta": self.meta,
            "heartbeat_seconds": self.heartbeat_seconds,
            "discovered_at": self.discovered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
