"""OAuth client configuration and secure token storage for MCP proxies."""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING, override

import keyring
from key_value.aio.stores.keyring.store import (
    KeyringStore,
    KeyringV1CollectionSanitizationStrategy,
    KeyringV1KeySanitizationStrategy,
)

from ot.config.keyring import _assert_secure_keyring_backend
from ot.paths import get_config_dir

if TYPE_CHECKING:
    from pathlib import Path

    from key_value.aio._utils.managed_entry import ManagedEntry
    from key_value.aio.protocols import AsyncKeyValue

_OAUTH_KEYRING_SERVICE_PREFIX = "onetool-mcp.oauth"


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
