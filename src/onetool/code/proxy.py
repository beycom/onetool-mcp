"""Bounded inference-only CLIProxyAPI model discovery."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from ot.config.routing import CLIProxyConnectionConfig

_MAX_DISCOVERY_BYTES = 1_048_576
_MAX_MODELS = 10_000


class ProxyDiscoveryError(RuntimeError):
    """A bounded, redacted external inference discovery failure."""


@dataclass(slots=True)
class ModelDiscovery:
    """Authenticated model discovery with finite in-memory freshness."""

    config: CLIProxyConnectionConfig
    secret: str
    client: httpx.Client | None = None
    _cached_at: float | None = field(default=None, init=False)
    _cached_ids: tuple[str, ...] = field(default=(), init=False)

    def _read_response(
        self,
        client: httpx.Client,
        url: str,
        timeout: httpx.Timeout,
    ) -> tuple[int, bytes]:
        """Stream one response while enforcing the body limit during download."""
        headers = {
            "Authorization": f"Bearer {self.secret}",
            "Accept": "application/json",
        }
        with client.stream("GET", url, headers=headers, timeout=timeout) as response:
            declared_length = response.headers.get("Content-Length")
            if (
                declared_length is not None
                and declared_length.isdigit()
                and int(declared_length) > _MAX_DISCOVERY_BYTES
            ):
                raise ProxyDiscoveryError(
                    "CLIProxyAPI model discovery response exceeded the 1 MiB limit"
                )
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > _MAX_DISCOVERY_BYTES:
                    raise ProxyDiscoveryError(
                        "CLIProxyAPI model discovery response exceeded the 1 MiB limit"
                    )
            return response.status_code, bytes(content)

    def _request(self) -> tuple[int, bytes]:
        """Issue and boundedly read the one supported inference request."""
        timeout = httpx.Timeout(
            connect=self.config.connect_timeout,
            read=self.config.request_timeout,
            write=self.config.request_timeout,
            pool=self.config.connect_timeout,
        )
        url = f"{self.config.base_url}/v1/models"
        try:
            if self.client is not None:
                return self._read_response(self.client, url, timeout)
            with httpx.Client(timeout=timeout) as client:
                return self._read_response(client, url, timeout)
        except httpx.HTTPError as exc:
            raise ProxyDiscoveryError(
                f"CLIProxyAPI inference endpoint is unavailable at "
                f"{self.config.base_url}; check the external service and route"
            ) from exc

    def models(self, *, force: bool = False) -> tuple[str, ...]:
        """Return a fresh bounded model id list."""
        now = time.monotonic()
        if (
            not force
            and self._cached_at is not None
            and now - self._cached_at <= self.config.model_cache_ttl
        ):
            return self._cached_ids

        status_code, content = self._request()
        if status_code != 200:
            raise ProxyDiscoveryError(
                f"CLIProxyAPI model discovery failed with HTTP "
                f"{status_code} at {self.config.base_url}; check the "
                "inference client secret and external service"
            )
        try:
            payload: Any = httpx.Response(200, content=content).json()
        except ValueError as exc:
            raise ProxyDiscoveryError(
                "CLIProxyAPI model discovery returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ProxyDiscoveryError(
                "CLIProxyAPI model discovery must return an object with a data list"
            )
        data = payload["data"]
        if len(data) > _MAX_MODELS:
            raise ProxyDiscoveryError(
                "CLIProxyAPI model discovery returned too many model entries"
            )

        ids: list[str] = []
        for index, item in enumerate(data):
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("id"), str)
                or not item["id"]
            ):
                raise ProxyDiscoveryError(
                    f"CLIProxyAPI model entry {index} has an invalid id"
                )
            ids.append(item["id"])

        self._cached_ids = tuple(ids)
        self._cached_at = now
        return self._cached_ids

    def validate(self, *identities: str) -> str:
        """Return the unique advertised identity or fail without fallback."""
        available = self.models()
        for identity in identities:
            count = available.count(identity)
            if count > 1:
                raise ProxyDiscoveryError(
                    f"CLIProxyAPI advertises ambiguous model identity {identity!r}; "
                    "configure unique proxy aliases"
                )
            if count == 1:
                return identity
        wanted = " or ".join(repr(identity) for identity in identities)
        raise ProxyDiscoveryError(
            f"CLIProxyAPI at {self.config.base_url} does not advertise {wanted}; "
            "check the external model alias configuration"
        )


__all__ = ["ModelDiscovery", "ProxyDiscoveryError"]
