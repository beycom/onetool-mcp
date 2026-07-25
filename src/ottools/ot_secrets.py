"""Secrets management tool pack for OneTool.

Provides agent-callable functions to manage age-encrypted secrets in secrets.yaml.
Values prefixed with `age1enc:` are encrypted with an age X25519 identity stored
in the OS keychain.
"""

from __future__ import annotations

import base64
import contextlib
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ot.config.keyring import (
    _NO_IDENTITY_MSG as _NO_IDENTITY_MSG,
)
from ot.config.keyring import (
    _SECURE_BACKENDS as _SECURE_BACKENDS,
)
from ot.config.keyring import (
    _assert_secure_keyring_backend as _assert_secure_keyring_backend,
)
from ot.config.keyring import (
    _InsecureKeyringError as _InsecureKeyringError,
)
from otpack import LogSpan

# Pack for dot notation: ot_secrets.init(), ot_secrets.encrypt(), etc.
pack = "ot_secrets"
pack_aliases = ("sec",)

__all__ = ["audit", "encrypt", "get", "init", "set", "status", "unset"]

__ot_requires__ = {
    "lib": [
        ("pyrage", "pip install pyrage"),
        ("keyring", "pip install keyring"),
    ]
}

_SERVICE = "onetool"
_KEY_IDENTITY = "age_identity"
_KEY_PUBKEY = "age_pubkey"
_KEY_LABEL = "age_label"
_PREFIX = "age1enc:"

# These keyring definitions live in the core configuration package so core code
# does not depend on a leaf tool pack.


def _resolve_secrets_file(file: str | None) -> Path:
    """Resolve the secrets-file path, defaulting to the configured location.

    Explicit ``file`` wins; else the loaded ``--secrets`` path; else
    ``<config dir>/secrets.yaml``.
    """
    if file is not None:
        return Path(file).expanduser()
    from ot.config.loader import get_loaded_secrets_path

    loaded = get_loaded_secrets_path()
    if loaded is not None:
        return Path(loaded).expanduser()
    from ot.paths import get_config_dir

    return get_config_dir() / "secrets.yaml"


def _yaml_bytes(data: dict[str, Any]) -> bytes:
    """Serialize a secrets mapping deterministically without touching disk."""
    return yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).encode()


def _secure_atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically replace ``path`` with ``data`` at mode 0600."""
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_")
    descriptor_open = True
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            descriptor_open = False
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temp_path).replace(path)
    except BaseException:
        if descriptor_open:
            os.close(fd)
        with contextlib.suppress(OSError):
            Path(temp_path).unlink()
        raise


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write ``data`` to ``path`` atomically at mode 0600."""
    _secure_atomic_write_bytes(path, _yaml_bytes(data))


def _commit_with_backup(
    path: Path,
    target_bytes: bytes,
    *,
    backup_bytes: bytes | None,
) -> str | None:
    """Commit a secure target and optional backup, restoring backup on failure."""
    if backup_bytes is None:
        _secure_atomic_write_bytes(path, target_bytes)
        return None

    backup_path = Path(f"{path}.bak")
    previous_backup = backup_path.read_bytes() if backup_path.exists() else None
    _secure_atomic_write_bytes(backup_path, backup_bytes)
    try:
        _secure_atomic_write_bytes(path, target_bytes)
    except BaseException:
        if previous_backup is None:
            backup_path.unlink(missing_ok=True)
        else:
            _secure_atomic_write_bytes(backup_path, previous_backup)
        raise
    return str(backup_path)


def _secure_staging_file(path: Path, data: bytes) -> Path:
    """Create a mode-0600 sibling staging file containing only encrypted data."""
    fd, stage_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".secrets_stage_", suffix=".yaml"
    )
    descriptor_open = True
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            descriptor_open = False
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if descriptor_open:
            os.close(fd)
        with contextlib.suppress(OSError):
            Path(stage_name).unlink()
        raise
    return Path(stage_name)


def _require_keyring() -> Any:
    try:
        import keyring

        return keyring
    except ImportError as e:
        raise ImportError("keyring is not installed. Run: pip install keyring") from e


def _require_pyrage() -> Any:
    try:
        import pyrage  # type: ignore[import-untyped]

        return pyrage
    except ImportError as e:
        raise ImportError("pyrage is not installed. Run: pip install pyrage") from e


def _pubkey_hint(pubkey: str) -> str:
    """Return a truncated public key hint for safe display."""
    if len(pubkey) <= 12:
        return pubkey
    return pubkey[:8] + "..." + pubkey[-3:]


def init(*, label: str = "") -> dict[str, Any]:
    """Generate an age X25519 identity and store it in the OS keychain.

    Args:
        label: Optional label to identify this identity (e.g., "macbook-gavin").

    Returns:
        Dict with pubkey, label, and status.
    """
    with LogSpan(span="ot_secrets.init") as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()

        _assert_secure_keyring_backend(keyring)

        existing_private = keyring.get_password(_SERVICE, _KEY_IDENTITY)
        existing_public = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        if existing_private or existing_public:
            s.add(status="exists")
            return {
                "error": (
                    "Identity state already exists in keychain. Keep the original "
                    "identity to decrypt existing ciphertext."
                ),
                "status": "exists",
            }

        identity = pyrage.x25519.Identity.generate()
        private_key = str(identity)
        public_key = str(identity.to_public())

        keyring.set_password(_SERVICE, _KEY_IDENTITY, private_key)
        keyring.set_password(_SERVICE, _KEY_PUBKEY, public_key)
        keyring.set_password(_SERVICE, _KEY_LABEL, label)

        s.add(status="stored")
        return {
            "pubkey": public_key,
            "label": label,
            "status": "stored",
        }


def unset(*, key: str, file: str | None = None) -> dict[str, Any]:
    """Remove a single key from a secrets YAML file.

    Args:
        key: Secret key name to remove.
        file: Path to secrets YAML file. Defaults to the configured secrets path.

    Returns:
        Dict with ``removed`` flag and key name. Never contains the value.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.unset", file=str(path), key=key) as s:
        data, err = _load_secrets_mapping(path, s)
        if err:
            return err
        if key not in data:
            s.add(removed=False)
            return {"removed": False, "key": key, "status": "not_found"}
        del data[key]
        _atomic_write_yaml(path, data)
        s.add(removed=True)
        return {"removed": True, "key": key}


def _load_secrets_mapping(
    path: Path, s: Any
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Load a secrets YAML mapping. Returns (data, None) or ({}, error_dict)."""
    if not path.exists():
        s.add(status="file_not_found")
        return {}, {"error": f"File not found: {path}", "status": "file_not_found"}
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        s.add(status="invalid_yaml")
        return {}, {"error": str(exc), "status": "invalid_yaml"}
    if not isinstance(data, dict):
        s.add(status="invalid_yaml")
        return {}, {"error": "File must be a YAML mapping", "status": "invalid_yaml"}
    return data, None


def _load_secrets_snapshot(
    path: Path, s: Any
) -> tuple[dict[str, Any], bytes, dict[str, Any] | None]:
    """Load one exact byte snapshot for both parsing and recovery backup."""
    if not path.exists():
        s.add(status="file_not_found")
        return (
            {},
            b"",
            {
                "error": f"File not found: {path}",
                "status": "file_not_found",
            },
        )
    source = path.read_bytes()
    try:
        data = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        s.add(status="invalid_yaml")
        return {}, source, {"error": str(exc), "status": "invalid_yaml"}
    if not isinstance(data, dict):
        s.add(status="invalid_yaml")
        return (
            {},
            source,
            {
                "error": "File must be a YAML mapping",
                "status": "invalid_yaml",
            },
        )
    return data, source, None


def _identity_error(s: Any, message: str) -> dict[str, Any]:
    s.add(status="identity_inconsistent")
    return {"error": message, "status": "identity_inconsistent"}


def _validated_identity(
    keyring: Any, pyrage: Any, s: Any
) -> tuple[tuple[str, Any, Any] | None, dict[str, Any] | None]:
    """Return a parsed, matching, operational private/public identity pair."""
    private_key = keyring.get_password(_SERVICE, _KEY_IDENTITY)
    public_key = keyring.get_password(_SERVICE, _KEY_PUBKEY)
    if not private_key or not public_key:
        return None, _identity_error(
            s,
            "Age identity is incomplete. Both private and public keychain entries "
            "are required; keep the original identity for existing ciphertext.",
        )

    try:
        identity = pyrage.x25519.Identity.from_str(private_key)
        recipient = pyrage.x25519.Recipient.from_str(public_key)
        derived_public = str(identity.to_public())
    except Exception as exc:
        return None, _identity_error(s, f"Stored age identity is invalid: {exc}")

    if derived_public != str(recipient):
        return None, _identity_error(
            s,
            "Stored age private and public identity entries do not match.",
        )

    representative = b"onetool-age-identity-check"
    try:
        ciphertext = pyrage.encrypt(representative, [recipient])
        decrypted = pyrage.decrypt(ciphertext, [identity])
    except Exception as exc:
        return None, _identity_error(
            s, f"Stored age identity failed operational verification: {exc}"
        )
    if decrypted != representative:
        return None, _identity_error(
            s, "Stored age identity failed operational verification."
        )
    return (public_key, recipient, identity), None


def _prepare_encrypted_mapping(
    data: dict[str, Any],
    *,
    pyrage: Any,
    recipient: Any,
    identity: Any,
    s: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Encrypt and verify a mapping entirely in memory."""
    encrypted_keys: list[str] = []
    skipped_keys: list[str] = []
    null_keys: list[str] = []
    updated = dict(data)

    for key, value in data.items():
        if value is None:
            null_keys.append(key)
            continue
        plaintext = str(value).encode()
        if plaintext.startswith(_PREFIX.encode()):
            skipped_keys.append(key)
            continue
        try:
            ciphertext = pyrage.encrypt(plaintext, [recipient])
            verified = pyrage.decrypt(ciphertext, [identity])
        except Exception as exc:
            s.add(status="verify_failed", key=key)
            return None, {
                "error": (
                    f"Round-trip verification failed for '{key}': {exc}. "
                    "Nothing written."
                ),
                "status": "verify_failed",
            }
        if verified != plaintext:
            s.add(status="verify_failed", key=key)
            return None, {
                "error": (
                    f"Round-trip verification failed for '{key}'. Nothing written."
                ),
                "status": "verify_failed",
            }
        updated[key] = _PREFIX + base64.b64encode(ciphertext).decode()
        encrypted_keys.append(key)

    return updated, {
        "encrypted": encrypted_keys,
        "skipped": skipped_keys,
        "null_keys": null_keys,
    }


def _prepare_guided_encryption(
    data: dict[str, Any],
) -> tuple[bytes | None, dict[str, Any]]:
    """Prepare guided ciphertext in memory using the same encryption boundary."""
    with LogSpan(span="ot_secrets.guided_prepare") as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()
        _assert_secure_keyring_backend(keyring)
        validated, error = _validated_identity(keyring, pyrage, s)
        if error:
            return None, error
        assert validated is not None
        public_key, recipient, identity = validated
        updated, result = _prepare_encrypted_mapping(
            data,
            pyrage=pyrage,
            recipient=recipient,
            identity=identity,
            s=s,
        )
        if updated is None:
            return None, result
        result["pubkey_hint"] = _pubkey_hint(public_key)
        return _yaml_bytes(updated), result


def encrypt(*, file: str | None = None, backup: bool = True) -> dict[str, Any]:
    """Encrypt plain values in a secrets YAML file in-place.

    Skips values already prefixed with `age1enc:`. Writes atomically at mode 0600.

    Args:
        file: Path to secrets YAML file. Defaults to the configured secrets path.
        backup: Create an exact plaintext .bak recovery copy at mode 0600.
            Defaults to True.

    Returns:
        Dict with encryption summary including encrypted, skipped, and plain key lists.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.encrypt", file=str(path)) as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()

        _assert_secure_keyring_backend(keyring)

        validated, error = _validated_identity(keyring, pyrage, s)
        if error:
            return error
        assert validated is not None
        pubkey_str, recipient, identity = validated

        data, original_bytes, err = _load_secrets_snapshot(path, s)
        if err:
            return err
        updated, result = _prepare_encrypted_mapping(
            data,
            pyrage=pyrage,
            recipient=recipient,
            identity=identity,
            s=s,
        )
        if updated is None:
            return result
        backup_path = _commit_with_backup(
            path,
            _yaml_bytes(updated),
            backup_bytes=original_bytes if backup else None,
        )

        encrypted_keys = result["encrypted"]
        skipped_keys = result["skipped"]
        s.add(encryptedCount=len(encrypted_keys), skippedCount=len(skipped_keys))
        return {
            "file": str(path),
            "backup": backup_path,
            "encrypted": encrypted_keys,
            "skipped": skipped_keys,
            "null_keys": result["null_keys"],
            "pubkey_hint": _pubkey_hint(pubkey_str),
        }


def status(*, file: str | None = None) -> dict[str, Any]:
    """Check secrets identity status and optionally inspect a secrets file.

    Args:
        file: Optional path to secrets YAML file to count encrypted vs plain values.

    Returns:
        Dict with identity status and optional value counts.
    """
    with LogSpan(span="ot_secrets.status", file=file) as s:
        keyring = _require_keyring()

        pubkey_str = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        label = keyring.get_password(_SERVICE, _KEY_LABEL) or ""

        if not pubkey_str:
            s.add(identity="not_found")
            return {
                "identity": "not found",
                "pubkey_hint": None,
                "label": None,
                "file": None,
                "values": None,
                "hint": "Run ot_secrets.init() to generate an identity.",
            }

        result: dict[str, Any] = {
            "identity": "found",
            "pubkey_hint": _pubkey_hint(pubkey_str),
            "label": label,
            "file": None,
            "values": None,
        }

        # Resolve the secrets file to inspect: explicit file, else the configured
        # default (best-effort — an identity-only status() still works with no file).
        resolved: Path | None = None
        if file is not None:
            resolved = Path(file).expanduser()
        else:
            with contextlib.suppress(Exception):
                resolved = _resolve_secrets_file(None)

        if resolved is not None and (file is not None or resolved.exists()):
            path = resolved
            if not path.exists():
                result["file_error"] = f"File not found: {path}"
            else:
                try:
                    with path.open() as f:
                        data = yaml.safe_load(f)
                except yaml.YAMLError as exc:
                    result["file_error"] = str(exc)
                    s.add(identity="found", file_error="invalid_yaml")
                    return result
                if not isinstance(data, dict):
                    result["file_error"] = "File must be a YAML mapping"
                else:
                    encrypted = []
                    plain = []
                    nulls = []
                    # Falsy non-None values (e.g. empty string) are treated as plain,
                    # not null — they are present but unencrypted.
                    for k, v in data.items():
                        if v is None:
                            nulls.append(k)
                        elif str(v).startswith(_PREFIX):
                            encrypted.append(k)
                        else:
                            plain.append(k)
                    result["file"] = str(path)
                    result["values"] = {
                        "encrypted": encrypted,
                        "plain": plain,
                        "null_keys": nulls,
                    }

        s.add(identity="found")
        return result


def audit(*, file: str | None = None) -> dict[str, Any]:
    """Scan a secrets YAML file for unencrypted values.

    Returns key names only — never exposes actual values.

    Args:
        file: Path to secrets YAML file. Defaults to the configured secrets path.

    Returns:
        Dict with safe status, plain_keys, and encrypted_keys.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.audit", file=str(path)) as s:
        if not path.exists():
            s.add(status="file_not_found")
            return {"error": f"File not found: {path}", "status": "file_not_found"}

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            s.add(status="invalid_yaml")
            return {"error": str(exc), "status": "invalid_yaml"}

        if not isinstance(data, dict):
            s.add(status="no_mapping")
            return {"error": "File must be a YAML mapping", "status": "no_mapping"}

        encrypted_keys: list[str] = []
        plain_keys: list[str] = []
        null_keys: list[str] = []

        for key, value in data.items():
            if value is None:
                null_keys.append(key)
            elif str(value).startswith(_PREFIX):
                encrypted_keys.append(key)
            else:
                plain_keys.append(key)

        safe = len(plain_keys) == 0
        s.add(
            safe=safe, plain_count=len(plain_keys), encrypted_count=len(encrypted_keys)
        )
        result: dict[str, Any] = {
            "file": str(path),
            "safe": safe,
            "plain_keys": plain_keys,
            "encrypted_keys": encrypted_keys,
            "null_keys": null_keys,
        }
        if not safe:
            result["message"] = (
                "Run ot_secrets.encrypt() to secure these values before committing."
            )
        return result


def set(*, key: str, value: str, file: str | None = None) -> dict[str, Any]:
    """Set a single secret, encrypting it in place if an identity exists.

    Encrypts ``value`` in memory (never touching disk in plaintext) and round-trip
    verifies before the atomic 0600 write. If no identity is present, the value is
    stored in plaintext and a ``warning`` is returned.

    Args:
        key: Secret name.
        value: Secret value (encrypted in place when an identity exists).
        file: Path to secrets YAML file. Defaults to the configured secrets path.

    Returns:
        Dict summarising the write. Never contains the plaintext value.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.set", file=str(path), key=key) as s:
        keyring = _require_keyring()

        data: dict[str, Any] = {}
        if path.exists():
            try:
                with path.open() as f:
                    loaded = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                s.add(status="invalid_yaml")
                return {"error": str(exc), "status": "invalid_yaml"}
            if loaded is not None:
                if not isinstance(loaded, dict):
                    s.add(status="invalid_yaml")
                    return {
                        "error": "File must be a YAML mapping",
                        "status": "invalid_yaml",
                    }
                data = loaded

        pubkey_str = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        encrypted = False
        warning: str | None = None

        if pubkey_str:
            _assert_secure_keyring_backend(keyring)
            private_key = keyring.get_password(_SERVICE, _KEY_IDENTITY)
            if not private_key:
                # Keychain has the pubkey but lost the identity (e.g. keychain
                # entry deleted out-of-band) — fail with the canonical guidance
                # instead of an unhandled TypeError from Identity.from_str(None).
                s.add(status="no_identity")
                return {"error": _NO_IDENTITY_MSG, "status": "no_identity"}
            pyrage = _require_pyrage()
            recipient = pyrage.x25519.Recipient.from_str(pubkey_str)
            ciphertext = pyrage.encrypt(value.encode(), [recipient])
            encoded = base64.b64encode(ciphertext).decode()
            # Round-trip verify before writing anything.
            identity = pyrage.x25519.Identity.from_str(private_key)
            if pyrage.decrypt(ciphertext, [identity]).decode() != value:
                s.add(status="verify_failed")
                return {
                    "error": (
                        f"Round-trip verification failed for '{key}'. Nothing written."
                    ),
                    "status": "verify_failed",
                }
            data[key] = _PREFIX + encoded
            encrypted = True
        else:
            data[key] = value
            warning = (
                "No age identity found — value stored in plaintext. Run "
                "ot_secrets.init() then ot_secrets.encrypt() to secure it."
            )

        _atomic_write_yaml(path, data)
        s.add(encrypted=encrypted)
        result: dict[str, Any] = {
            "file": str(path),
            "key": key,
            "encrypted": encrypted,
            "status": "set",
        }
        if warning:
            result["warning"] = warning
        return result


def get(
    *, key: str, file: str | None = None, out_file: str | None = None
) -> dict[str, Any]:
    """Look up a secret's existence/metadata, never returning its plaintext value.

    The plaintext value is *never* placed in the returned dict, a log line, or the
    LogSpan — there is intentionally no escape hatch. To obtain the value, pass
    ``out_file`` and the decrypted value is written to that 0600 file.

    Args:
        key: Secret name.
        file: Path to secrets YAML file. Defaults to the configured secrets path.
        out_file: If given, decrypt/pass-through the value into this 0600 file.

    Returns:
        Dict with ``found``/``encrypted`` (and ``written_to`` when ``out_file`` is
        used). Never contains the value itself.
    """
    path = _resolve_secrets_file(file)
    with LogSpan(span="ot_secrets.get", file=str(path), key=key) as s:
        if not path.exists():
            s.add(found=False)
            return {"found": False, "encrypted": None}

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            s.add(status="invalid_yaml")
            return {"error": str(exc), "status": "invalid_yaml"}

        if not isinstance(data, dict) or key not in data:
            s.add(found=False)
            return {"found": False, "encrypted": None}

        raw = data[key]
        raw_str = "" if raw is None else str(raw)
        is_encrypted = raw_str.startswith(_PREFIX)
        result: dict[str, Any] = {"found": True, "encrypted": is_encrypted}

        if out_file is not None:
            if is_encrypted:
                keyring = _require_keyring()
                _assert_secure_keyring_backend(keyring)
                private_key = keyring.get_password(_SERVICE, _KEY_IDENTITY)
                if not private_key:
                    s.add(status="no_identity")
                    return {"error": _NO_IDENTITY_MSG, "status": "no_identity"}
                pyrage = _require_pyrage()
                identity = pyrage.x25519.Identity.from_str(private_key)
                try:
                    ciphertext = base64.b64decode(
                        raw_str[len(_PREFIX) :], validate=True
                    )
                    plaintext = pyrage.decrypt(ciphertext, [identity]).decode()
                except (ValueError, pyrage.DecryptError) as exc:
                    s.add(status="decrypt_failed")
                    return {
                        "error": (
                            "Cannot decrypt value — it is corrupted or was encrypted "
                            f"with a different key ({exc})."
                        ),
                        "status": "decrypt_failed",
                    }
            else:
                plaintext = raw_str
            out_path = Path(out_file).expanduser()
            fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(plaintext)
            out_path.chmod(0o600)
            result["written_to"] = str(out_path)

        s.add(found=True, encrypted=is_encrypted)
        return result
