"""OAuth client configuration and secure token storage for MCP proxies."""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import json
import os
import re
import secrets
from collections.abc import AsyncGenerator, Mapping
from typing import TYPE_CHECKING, Any, override
from urllib.parse import urlsplit, urlunsplit

import keyring
from fastmcp.client.auth import OAuth
from filelock import AsyncFileLock
from filelock import Timeout as FileLockTimeout
from key_value.aio._utils.compound import compound_key
from key_value.aio.stores.keyring.store import (
    KeyringStore,
    KeyringV1CollectionSanitizationStrategy,
    KeyringV1KeySanitizationStrategy,
)
from keyring.errors import PasswordDeleteError

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
_WINDOWS_CHUNK_BYTES = 1800
_WINDOWS_MANIFEST_KIND = "onetool-oauth-keyring-chunks"
_WINDOWS_MANIFEST_VERSION = 1
_WINDOWS_SLOT_PATTERN = re.compile(r"[0-9a-f]{16}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class OAuthSecureStorageError(RuntimeError):
    """A secure OAuth credential entry could not be safely read or updated."""


def _use_windows_keyring_chunks() -> bool:
    """Return whether the keyring requires bounded Windows credential values."""
    return os.name == "nt"


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
        if _use_windows_keyring_chunks():
            serialized = self._get_windows_payload(key=key, collection=collection)
            if serialized is None:
                return None
            try:
                return self._serialization_adapter.load_json(json_str=serialized)
            except Exception:
                raise self._corrupt_entry_error() from None
        return await super()._get_managed_entry(key=key, collection=collection)

    @override
    async def _put_managed_entry(
        self, *, key: str, collection: str, managed_entry: ManagedEntry
    ) -> None:
        _assert_secure_keyring_backend(keyring)
        if _use_windows_keyring_chunks():
            serialized = self._serialization_adapter.dump_json(
                entry=managed_entry,
                key=key,
                collection=collection,
            )
            self._put_windows_payload(
                key=key,
                collection=collection,
                serialized=serialized,
            )
            return
        await super()._put_managed_entry(
            key=key,
            collection=collection,
            managed_entry=managed_entry,
        )

    @override
    async def _delete_managed_entry(self, *, key: str, collection: str) -> bool:
        _assert_secure_keyring_backend(keyring)
        if _use_windows_keyring_chunks():
            return self._delete_windows_payload(key=key, collection=collection)
        return await super()._delete_managed_entry(key=key, collection=collection)

    @staticmethod
    def _corrupt_entry_error() -> OAuthSecureStorageError:
        return OAuthSecureStorageError(
            "Stored OAuth credentials are incomplete or corrupt; remove the "
            "OneTool OAuth keyring entry and reauthorize"
        )

    def _entry_username(self, *, key: str, collection: str) -> str:
        sanitized_collection = self._sanitize_collection(collection=collection)
        sanitized_key = self._sanitize_key(key=key)
        return str(compound_key(collection=sanitized_collection, key=sanitized_key))

    @staticmethod
    def _entry_id(username: str) -> str:
        return hashlib.sha256(username.encode()).hexdigest()

    @staticmethod
    def _chunk_username(entry_id: str, slot: str, index: int) -> str:
        return f"onetool-oauth-chunk::{entry_id}::{slot}::{index:06d}"

    def _get_password(self, username: str) -> str | None:
        try:
            return keyring.get_password(
                service_name=self._service_name,
                username=username,
            )
        except Exception:
            raise OAuthSecureStorageError(
                "Could not read OAuth credentials from the secure keyring"
            ) from None

    def _set_password(self, username: str, value: str) -> None:
        try:
            keyring.set_password(
                service_name=self._service_name,
                username=username,
                password=value,
            )
        except Exception:
            raise OAuthSecureStorageError(
                "Could not update OAuth credentials in the secure keyring"
            ) from None

    def _delete_password(self, username: str) -> bool:
        try:
            keyring.delete_password(
                service_name=self._service_name,
                username=username,
            )
        except PasswordDeleteError:
            return False
        except Exception:
            raise OAuthSecureStorageError(
                "Could not delete OAuth credentials from the secure keyring"
            ) from None
        return True

    def _parse_manifest(self, serialized: str) -> dict[str, Any]:
        try:
            manifest = json.loads(serialized)
        except (TypeError, ValueError):
            raise self._corrupt_entry_error() from None
        if (
            not isinstance(manifest, dict)
            or manifest.get("kind") != _WINDOWS_MANIFEST_KIND
            or manifest.get("version") != _WINDOWS_MANIFEST_VERSION
            or not isinstance(manifest.get("slot"), str)
            or _WINDOWS_SLOT_PATTERN.fullmatch(manifest["slot"]) is None
            or type(manifest.get("chunks")) is not int
            or manifest["chunks"] < 1
            or type(manifest.get("length")) is not int
            or manifest["length"] < 0
            or not isinstance(manifest.get("sha256"), str)
            or _SHA256_PATTERN.fullmatch(manifest["sha256"]) is None
        ):
            raise self._corrupt_entry_error()
        return manifest

    def _load_chunked_payload(
        self,
        *,
        entry_id: str,
        manifest: Mapping[str, Any],
    ) -> str:
        payload_parts: list[bytes] = []
        try:
            for index in range(manifest["chunks"]):
                username = self._chunk_username(entry_id, manifest["slot"], index)
                encoded_chunk = self._get_password(username)
                if encoded_chunk is None:
                    raise self._corrupt_entry_error()
                payload_parts.append(
                    base64.b64decode(encoded_chunk.encode("ascii"), validate=True)
                )
            payload = b"".join(payload_parts)
        except (UnicodeEncodeError, binascii.Error):
            raise self._corrupt_entry_error() from None

        if (
            len(payload) != manifest["length"]
            or hashlib.sha256(payload).hexdigest() != manifest["sha256"]
        ):
            raise self._corrupt_entry_error()
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            raise self._corrupt_entry_error() from None

    def _get_windows_payload(self, *, key: str, collection: str) -> str | None:
        manifest_username = self._entry_username(key=key, collection=collection)
        serialized_manifest = self._get_password(manifest_username)
        if serialized_manifest is None:
            return None
        manifest = self._parse_manifest(serialized_manifest)
        entry_id = self._entry_id(manifest_username)
        try:
            return self._load_chunked_payload(
                entry_id=entry_id,
                manifest=manifest,
            )
        except OAuthSecureStorageError:
            current_serialized_manifest = self._get_password(manifest_username)
            if current_serialized_manifest is None:
                return None
            if current_serialized_manifest == serialized_manifest:
                raise
            current_manifest = self._parse_manifest(current_serialized_manifest)
            return self._load_chunked_payload(
                entry_id=entry_id,
                manifest=current_manifest,
            )

    def _delete_chunks(
        self,
        *,
        entry_id: str,
        manifest: Mapping[str, Any],
    ) -> None:
        for index in range(manifest["chunks"]):
            self._delete_password(
                self._chunk_username(entry_id, manifest["slot"], index)
            )

    def _put_windows_payload(
        self,
        *,
        key: str,
        collection: str,
        serialized: str,
    ) -> None:
        manifest_username = self._entry_username(key=key, collection=collection)
        entry_id = self._entry_id(manifest_username)
        old_serialized_manifest = self._get_password(manifest_username)
        old_manifest = (
            self._parse_manifest(old_serialized_manifest)
            if old_serialized_manifest is not None
            else None
        )
        if old_manifest is not None:
            self._load_chunked_payload(entry_id=entry_id, manifest=old_manifest)

        payload = serialized.encode("utf-8")
        raw_chunks = [
            payload[offset : offset + _WINDOWS_CHUNK_BYTES]
            for offset in range(0, len(payload), _WINDOWS_CHUNK_BYTES)
        ] or [b""]
        slot = secrets.token_hex(8)
        manifest = {
            "kind": _WINDOWS_MANIFEST_KIND,
            "version": _WINDOWS_MANIFEST_VERSION,
            "slot": slot,
            "chunks": len(raw_chunks),
            "length": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        switched = False
        try:
            for index, chunk in enumerate(raw_chunks):
                self._set_password(
                    self._chunk_username(entry_id, slot, index),
                    base64.b64encode(chunk).decode("ascii"),
                )
            self._load_chunked_payload(entry_id=entry_id, manifest=manifest)
            self._set_password(
                manifest_username,
                json.dumps(manifest, separators=(",", ":"), sort_keys=True),
            )
            switched = True
            if old_manifest is not None:
                self._delete_chunks(entry_id=entry_id, manifest=old_manifest)
        except Exception:
            if not switched:
                with contextlib.suppress(OAuthSecureStorageError):
                    self._delete_chunks(entry_id=entry_id, manifest=manifest)
            raise

    def _delete_windows_payload(self, *, key: str, collection: str) -> bool:
        manifest_username = self._entry_username(key=key, collection=collection)
        serialized_manifest = self._get_password(manifest_username)
        if serialized_manifest is None:
            return False
        manifest = self._parse_manifest(serialized_manifest)
        entry_id = self._entry_id(manifest_username)
        self._load_chunked_payload(entry_id=entry_id, manifest=manifest)
        deleted = self._delete_password(manifest_username)
        self._delete_chunks(entry_id=entry_id, manifest=manifest)
        return deleted


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
