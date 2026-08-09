"""Bounded inference-only CLIProxyAPI model discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from onetool.code.adapters import normalize_proxy_origin

_MAX_DISCOVERY_BYTES = 1_048_576
_MAX_MODELS = 10_000
_CONNECT_TIMEOUT = 2.0
_REQUEST_TIMEOUT = 5.0


class ProxyDiscoveryError(RuntimeError):
    """A bounded, redacted external inference discovery failure."""


@dataclass(frozen=True, slots=True)
class DiscoveredModel:
    """One direct model ID with optional provider metadata."""

    id: str
    provider: str | None


def _contains_control_characters(value: str) -> bool:
    """Return whether text contains terminal-unsafe control characters."""
    return any(
        ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F for character in value
    )


@dataclass(slots=True)
class ModelDiscovery:
    """Authenticated one-request discovery for the explicit models command."""

    proxy_origin: str
    credential: str
    client: httpx.Client | None = None

    def _read_response(
        self,
        client: httpx.Client,
        url: str,
        timeout: httpx.Timeout,
    ) -> tuple[int, bytes]:
        """Stream one response while enforcing the body limit."""
        headers = {
            "Authorization": f"Bearer {self.credential}",
            "Accept": "application/json",
        }
        with client.stream("GET", url, headers=headers, timeout=timeout) as response:
            declared = response.headers.get("Content-Length")
            if (
                declared is not None
                and declared.isdigit()
                and int(declared) > _MAX_DISCOVERY_BYTES
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
        """Issue the one supported authenticated inventory request."""
        origin = normalize_proxy_origin(self.proxy_origin)
        timeout = httpx.Timeout(
            connect=_CONNECT_TIMEOUT,
            read=_REQUEST_TIMEOUT,
            write=_REQUEST_TIMEOUT,
            pool=_CONNECT_TIMEOUT,
        )
        try:
            if self.client is not None:
                return self._read_response(
                    self.client,
                    f"{origin}/v1/models",
                    timeout,
                )
            with httpx.Client(timeout=timeout) as client:
                return self._read_response(client, f"{origin}/v1/models", timeout)
        except ProxyDiscoveryError:
            raise
        except httpx.HTTPError as exc:
            raise ProxyDiscoveryError(
                f"CLIProxyAPI inference endpoint is unavailable at {origin}"
            ) from exc

    def models(self) -> tuple[DiscoveredModel, ...]:
        """Return sorted direct models from one fresh bounded inventory."""
        status_code, content = self._request()
        if status_code != 200:
            raise ProxyDiscoveryError(
                f"CLIProxyAPI model discovery failed with HTTP {status_code}"
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

        models: list[DiscoveredModel] = []
        for index, item in enumerate(data):
            model_id = item.get("id") if isinstance(item, dict) else None
            if (
                not isinstance(model_id, str)
                or not model_id.strip()
                or _contains_control_characters(model_id)
            ):
                raise ProxyDiscoveryError(
                    f"CLIProxyAPI model entry {index} has an invalid id"
                )
            raw_provider = item.get("owned_by")
            provider = raw_provider.strip() if isinstance(raw_provider, str) else None
            if not provider or _contains_control_characters(provider):
                provider = None
            models.append(DiscoveredModel(id=model_id, provider=provider))
        return tuple(sorted(models, key=lambda model: (model.id.casefold(), model.id)))


__all__ = ["DiscoveredModel", "ModelDiscovery", "ProxyDiscoveryError"]
