"""Shared OS-keyring backend policy for secrets handling.

Hoisted out of ``ottools.ot_secrets`` so that ``ot.config.secrets`` (core) does
not need to import a leaf pack's private symbols to enforce the same
fail-closed backend check during transparent decryption. This module is the
single source of truth for the secure-backend allow-list, the canonical
"no identity" message, and the backend assertion helper.

Keep this module free of any other ``ot.*`` imports — it is imported from
``ot.config.secrets`` (core) and must not introduce a layering inversion.
"""

from __future__ import annotations

from typing import Any

# Canonical "no identity" guidance, shared between ot_secrets and ot.config.secrets.
_NO_IDENTITY_MSG = (
    "No age identity found in the OS keychain. Run ot_secrets.init() to generate one."
)

# Allow-list of secure OS keyring backends. Anything not listed here (fail/null/
# chainer/third-party keyrings.alt plaintext backends) is refused — third-party
# plaintext backends cannot be enumerated, so this must be an allow-list, not a
# deny-list.
_SECURE_BACKENDS = {
    "keyring.backends.macOS.Keyring",
    "keyring.backends.Windows.WinVaultKeyring",
    "keyring.backends.SecretService.Keyring",
    "keyring.backends.libsecret.Keyring",
    "keyring.backends.kwallet.DBusKeyring",
    "keyring.backends.kwallet.DBusKeyringKWallet4",
}


class _InsecureKeyringError(RuntimeError):
    """Raised when the resolved OS keyring backend is not allow-listed as secure."""


def _assert_secure_keyring_backend(kr: Any) -> None:
    """Refuse to touch the keychain unless a secure backend is active.

    Fail-closed: a headless host can silently resolve a plaintext ``keyrings.alt``
    backend and store the private age identity in cleartext. Verify the backend
    before every keychain read or write, not just after init() — the backend can
    differ between the process that ran init() and a later reader.
    """
    backend = kr.get_keyring()
    qualname = f"{type(backend).__module__}.{type(backend).__qualname__}"
    if qualname not in _SECURE_BACKENDS:
        raise _InsecureKeyringError(
            f"Insecure or unavailable OS keyring backend detected: {qualname}. "
            "OneTool refuses to store the age private key in this backend "
            "(it may be a plaintext fallback). Configure a secure OS keychain "
            "(macOS Keychain, Windows Credential Locker, or a Secret "
            "Service/KWallet/libsecret provider on Linux) and retry."
        )
