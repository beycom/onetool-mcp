"""Bounded read-only diagnostics for the CLIProxyAPI harness launcher."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import webbrowser
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from onetool.code.adapters import (
    BASE_URL_ENV,
    DEFAULT_PROXY_ORIGIN,
    INFERENCE_KEY_ENV,
    normalize_proxy_origin,
)
from onetool.code.proxy import ModelDiscovery, ProxyDiscoveryError

_CONNECT_TIMEOUT = 2.0
_REQUEST_TIMEOUT = 5.0
_VERSION_TIMEOUT = 2.0
_MAX_VERSION_BYTES = 4096


@dataclass(frozen=True, slots=True)
class ExecutableStatus:
    """One optional executable probe result."""

    name: str
    path: str | None
    version: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class CodeStatus:
    """A complete read-only launcher readiness snapshot."""

    proxy_origin: str | None
    origin_source: str
    origin_error: str | None
    credential_present: bool
    models: tuple[str, ...]
    inventory_error: str | None
    management_url: str | None
    management_reachable: bool
    management_error: str | None
    executables: tuple[ExecutableStatus, ...]

    @property
    def ready(self) -> bool:
        """Return whether required inference launch inputs are ready."""
        return (
            self.proxy_origin is not None
            and self.credential_present
            and self.inventory_error is None
        )


def collect_code_status(
    *,
    environment: Mapping[str, str] | None = None,
    client: httpx.Client | None = None,
) -> CodeStatus:
    """Collect independent, sanitized launcher readiness checks."""
    values = os.environ if environment is None else environment
    origin_source = "environment" if BASE_URL_ENV in values else "default"
    raw_origin = values.get(BASE_URL_ENV, DEFAULT_PROXY_ORIGIN)
    credential = values.get(INFERENCE_KEY_ENV)

    try:
        origin = normalize_proxy_origin(raw_origin)
        origin_error = None
    except ValueError as exc:
        origin = None
        origin_error = str(exc)

    models: tuple[str, ...] = ()
    if origin is None:
        inventory_error = origin_error
    elif not credential:
        inventory_error = f"{INFERENCE_KEY_ENV} is required"
    else:
        try:
            models = ModelDiscovery(
                proxy_origin=origin,
                credential=credential,
                client=client,
            ).models()
            inventory_error = None
        except ProxyDiscoveryError as exc:
            inventory_error = str(exc)

    management_url = f"{origin}/management.html" if origin is not None else None
    if management_url is None:
        management_reachable = False
        management_error = origin_error
    else:
        try:
            management_reachable = _page_reachable(
                url=management_url,
                client=client,
            )
            management_error = (
                None
                if management_reachable
                else "management page returned an unsuccessful HTTP status"
            )
        except httpx.HTTPError:
            management_reachable = False
            management_error = "management page is unavailable"

    executables = tuple(
        _probe_executable(name=name, arguments=arguments)
        for name, arguments in (
            ("cliproxyapi", ("--help",)),
            ("claude", ("--version",)),
            ("codex", ("--version",)),
        )
    )
    return CodeStatus(
        proxy_origin=origin,
        origin_source=origin_source,
        origin_error=origin_error,
        credential_present=bool(credential),
        models=models,
        inventory_error=inventory_error,
        management_url=management_url,
        management_reachable=management_reachable,
        management_error=management_error,
        executables=executables,
    )


def _page_reachable(*, url: str, client: httpx.Client | None) -> bool:
    timeout = httpx.Timeout(
        connect=_CONNECT_TIMEOUT,
        read=_REQUEST_TIMEOUT,
        write=_REQUEST_TIMEOUT,
        pool=_CONNECT_TIMEOUT,
    )
    if client is not None:
        with client.stream("GET", url, timeout=timeout) as response:
            return response.status_code < 400
    with (
        httpx.Client(timeout=timeout) as owned_client,
        owned_client.stream("GET", url, timeout=timeout) as response,
    ):
        return response.status_code < 400


def _probe_executable(
    *,
    name: str,
    arguments: tuple[str, ...],
) -> ExecutableStatus:
    path = shutil.which(name)
    if path is None:
        return ExecutableStatus(
            name=name,
            path=None,
            version=None,
            error="not installed or not on PATH",
        )
    try:
        with tempfile.TemporaryFile() as output:
            subprocess.run(
                (path, *arguments),
                check=False,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=_VERSION_TIMEOUT,
            )
            output.seek(0)
            content = output.read(_MAX_VERSION_BYTES + 1)
    except (OSError, subprocess.TimeoutExpired):
        return ExecutableStatus(
            name=name,
            path=path,
            version=None,
            error="version probe failed",
        )
    if len(content) > _MAX_VERSION_BYTES:
        return ExecutableStatus(
            name=name,
            path=path,
            version=None,
            error="version probe output exceeded the 4 KiB limit",
        )
    lines = [line.strip() for line in content.decode(errors="replace").splitlines() if line.strip()]
    if not lines:
        return ExecutableStatus(
            name=name,
            path=path,
            version=None,
            error="version probe returned no output",
        )
    return ExecutableStatus(
        name=name,
        path=path,
        version=lines[0][:500],
        error=None,
    )


def open_management_url(url: str) -> bool:
    """Ask the platform browser to open one normalized management URL."""
    try:
        return webbrowser.open(url, new=2)
    except (OSError, webbrowser.Error):
        return False


__all__ = [
    "CodeStatus",
    "ExecutableStatus",
    "collect_code_status",
    "open_management_url",
]
