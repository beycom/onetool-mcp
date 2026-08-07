"""OAuth client configuration and secure token storage for MCP proxies."""

from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncGenerator, Mapping
from typing import TYPE_CHECKING, Any, override
from urllib.parse import urlsplit, urlunsplit

import keyring
from fastmcp.client.auth import OAuth
from filelock import AsyncFileLock
from filelock import Timeout as FileLockTimeout
from key_value.aio.stores.keyring.store import (
    KeyringStore,
    KeyringV1CollectionSanitizationStrategy,
    KeyringV1KeySanitizationStrategy,
)

from ot.config.keyring import _assert_secure_keyring_backend
from ot.paths import RUNTIME_SUBDIR, get_config_dir

if TYPE_CHECKING:
    from pathlib import Path

    import httpx
    from key_value.aio._utils.managed_entry import ManagedEntry
    from key_value.aio.protocols import AsyncKeyValue

_OAUTH_KEYRING_SERVICE_PREFIX = "onetool-mcp.oauth"
_OAUTH_IDENTITY_COLLECTION = "onetool-oauth-identity-v1"
_PUBLIC_CLIENT_AUTH_METHOD = "none"
_OAUTH_LOCK_TIMEOUT_SECONDS = 30.0


def normalize_oauth_endpoint(endpoint: str) -> str:
    """Normalize an MCP endpoint without incorporating callback identity."""
    parsed = urlsplit(endpoint.strip())
    host = (parsed.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    if port is not None and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), host, path, parsed.query, ""))


def canonical_oauth_scopes(scopes: str | list[str] | None) -> tuple[str, ...]:
    """Return a stable, deduplicated scope identity."""
    values = scopes.split() if isinstance(scopes, str) else (scopes or [])
    return tuple(sorted({scope.strip() for scope in values if scope.strip()}))


def oauth_lock_path(endpoint: str, *, config_dir: Path | None = None) -> Path:
    """Return an endpoint-specific lock path containing no endpoint text."""
    runtime_dir = (config_dir or get_config_dir()).resolve() / RUNTIME_SUBDIR / "oauth"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    endpoint_digest = hashlib.sha256(
        normalize_oauth_endpoint(endpoint).encode()
    ).hexdigest()
    return runtime_dir / f"{endpoint_digest}.lock"


class SecureOAuthTokenStore(KeyringStore):
    """Keyring store that revalidates the secure backend for every operation."""

    @override
    def _warn_about_stability(self) -> None:
        """Suppress the upstream warning for OneTool's version-pinned adapter."""
        pass

    @override
    async def _get_managed_entry(
        self, *, key: str, collection: str
    ) -> ManagedEntry | None:
        _assert_secure_keyring_backend(keyring)
        return await super()._get_managed_entry(key=key, collection=collection)

    @override
    async def _put_managed_entry(
        self, *, key: str, collection: str, managed_entry: ManagedEntry
    ) -> None:
        _assert_secure_keyring_backend(keyring)
        await super()._put_managed_entry(
            key=key,
            collection=collection,
            managed_entry=managed_entry,
        )

    @override
    async def _delete_managed_entry(self, *, key: str, collection: str) -> bool:
        _assert_secure_keyring_backend(keyring)
        return await super()._delete_managed_entry(key=key, collection=collection)


class OneToolOAuth(OAuth):
    """FastMCP OAuth provider with OneTool-owned authorization identity checks."""

    def __init__(
        self,
        *,
        mcp_url: str,
        scopes: str | list[str] | None,
        token_storage: AsyncKeyValue,
        callback_port: int | None = None,
        lock_path: Path | None = None,
        lock_timeout: float = _OAUTH_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self._identity_store = token_storage
        self._identity_endpoint = normalize_oauth_endpoint(mcp_url)
        self._identity_scopes = canonical_oauth_scopes(scopes)
        self._state_lock = AsyncFileLock(lock_path or oauth_lock_path(mcp_url))
        self._lock_timeout = lock_timeout
        super().__init__(
            mcp_url=mcp_url,
            scopes=list(self._identity_scopes),
            client_name="OneTool",
            token_storage=token_storage,
            callback_port=callback_port,
            additional_client_metadata={
                "token_endpoint_auth_method": _PUBLIC_CLIENT_AUTH_METHOD
            },
        )

    def _identity_key(self) -> str:
        return f"{self._identity_endpoint}/identity"

    def _identity_record(self) -> dict[str, Any]:
        return {
            "version": 1,
            "endpoint": self._identity_endpoint,
            "scopes": list(self._identity_scopes),
            "token_endpoint_auth_method": _PUBLIC_CLIENT_AUTH_METHOD,
            "redirect_uris": [
                str(uri) for uri in self.context.client_metadata.redirect_uris or []
            ],
        }

    async def _delete_client_info(self) -> None:
        await self._identity_store.delete(
            key=f"{self.mcp_url}/client_info",
            collection="mcp-oauth-client-info",
        )

    def _identity_matches(self, stored_identity: Any) -> bool:
        if not isinstance(stored_identity, Mapping):
            return False
        current_identity = self._identity_record()
        return (
            stored_identity.get("version") == current_identity["version"]
            and stored_identity.get("endpoint") == current_identity["endpoint"]
            and tuple(stored_identity.get("scopes", ())) == self._identity_scopes
            and stored_identity.get("token_endpoint_auth_method")
            == _PUBLIC_CLIENT_AUTH_METHOD
        )

    def _registration_matches_callback(self) -> bool:
        stored_client = self.context.client_info
        if stored_client is None:
            return True
        current_redirects = {
            str(uri) for uri in self.context.client_metadata.redirect_uris or []
        }
        stored_redirects = {str(uri) for uri in stored_client.redirect_uris or []}
        return current_redirects.issubset(stored_redirects)

    async def _discard_incompatible_registration(self) -> None:
        if self._registration_matches_callback():
            return
        await self._delete_client_info()
        self.context.client_info = None

    async def _acquire_state_lock(self) -> None:
        try:
            await self._state_lock.acquire(timeout=self._lock_timeout)
        except FileLockTimeout:
            raise TimeoutError(
                "Timed out waiting for exclusive OAuth credential update"
            ) from None

    async def _reload_persisted_state(self) -> None:
        self._initialized = False
        await self._initialize()

    @override
    async def _initialize(self) -> None:
        stored_identity = await self._identity_store.get(
            key=self._identity_key(), collection=_OAUTH_IDENTITY_COLLECTION
        )
        current_identity = self._identity_record()
        if not self._identity_matches(stored_identity):
            await self.token_storage_adapter.clear()

        await self._identity_store.put(
            key=self._identity_key(),
            value=current_identity,
            collection=_OAUTH_IDENTITY_COLLECTION,
        )
        await super()._initialize()

        if not self.context.is_token_valid() and not self.context.can_refresh_token():
            await self._discard_incompatible_registration()

    @override
    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """Serialize complete OAuth state transitions across processes."""
        lock_held = False
        flow: AsyncGenerator[httpx.Request, httpx.Response] | None = None
        yielded_request: httpx.Request | None = None
        try:
            if not self._initialized or not self.context.is_token_valid():
                await self._acquire_state_lock()
                lock_held = True
                await self._reload_persisted_state()
                if self.context.is_token_valid():
                    await self._state_lock.release()
                    lock_held = False

            flow = super().async_auth_flow(request)
            response: httpx.Response | None = None
            while True:
                if response is not None and response.status_code == 401:
                    if not lock_held:
                        failed_access_token = (
                            self.context.current_tokens.access_token
                            if self.context.current_tokens is not None
                            else None
                        )
                        await self._acquire_state_lock()
                        lock_held = True
                        await self._reload_persisted_state()
                        current_tokens = self.context.current_tokens
                        if (
                            current_tokens is not None
                            and current_tokens.access_token != failed_access_token
                            and self.context.is_token_valid()
                            and yielded_request is not None
                        ):
                            self._add_auth_header(yielded_request)
                            response = yield yielded_request
                            if response.status_code != 401:
                                await self._state_lock.release()
                                lock_held = False
                                continue
                    await self._discard_incompatible_registration()
                try:
                    yielded_request = await flow.asend(
                        response  # type: ignore[arg-type]
                    )
                except StopAsyncIteration:
                    return
                response = yield yielded_request
        finally:
            try:
                if flow is not None:
                    await flow.aclose()
            finally:
                if lock_held:
                    await self._state_lock.release()


def _oauth_keyring_service_name(config_dir: Path | None = None) -> str:
    """Return a stable, non-identifying keyring service scoped to OneTool dir."""
    resolved_dir = (config_dir or get_config_dir()).resolve()
    directory_digest = hashlib.sha256(os.fsencode(resolved_dir)).hexdigest()[:16]
    return f"{_OAUTH_KEYRING_SERVICE_PREFIX}.{directory_digest}"


def create_oauth_token_storage() -> AsyncKeyValue:
    """Create secure persistent storage for proxy OAuth credentials and tokens."""
    _assert_secure_keyring_backend(keyring)
    return SecureOAuthTokenStore(
        service_name=_oauth_keyring_service_name(),
        key_sanitization_strategy=KeyringV1KeySanitizationStrategy(),
        collection_sanitization_strategy=KeyringV1CollectionSanitizationStrategy(),
    )


def create_oauth_provider(
    *,
    mcp_url: str,
    scopes: str | list[str] | None,
    callback_port: int | None = None,
) -> OneToolOAuth:
    """Create a public PKCE OAuth provider with persistent identity checks."""
    return OneToolOAuth(
        mcp_url=mcp_url,
        scopes=scopes,
        token_storage=create_oauth_token_storage(),
        callback_port=callback_port,
    )
