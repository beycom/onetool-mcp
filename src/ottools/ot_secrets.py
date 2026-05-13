"""Secrets management tool pack for OneTool.

Provides agent-callable functions to manage age-encrypted secrets in secrets.yaml.
Values prefixed with `age1enc:` are encrypted with an age X25519 identity stored
in the OS keychain.
"""

from __future__ import annotations

import base64
import shutil
from pathlib import Path
from typing import Any

import yaml
from otpack import LogSpan

# Pack for dot notation: ot_secrets.init(), ot_secrets.encrypt(), etc.
pack = "ot_secrets"
pack_aliases = ("sec",)

__all__ = ["audit", "encrypt", "init", "rotate", "status"]

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


def _require_keyring() -> Any:
    try:
        import keyring

        return keyring
    except ImportError as e:
        raise ImportError(
            "keyring is not installed. Run: pip install keyring"
        ) from e


def _require_pyrage() -> Any:
    try:
        import pyrage  # type: ignore[import-not-found]

        return pyrage
    except ImportError as e:
        raise ImportError(
            "pyrage is not installed. Run: pip install pyrage"
        ) from e


def _pubkey_hint(pubkey: str) -> str:
    """Return a truncated public key hint for safe display."""
    if len(pubkey) <= 12:
        return pubkey
    return pubkey[:8] + "..." + pubkey[-3:]


def init(*, label: str = "", force: bool = False) -> dict[str, Any]:
    """Generate an age X25519 identity and store it in the OS keychain.

    Args:
        label: Optional label to identify this identity (e.g., "macbook-gavin").
        force: If True, overwrite existing identity.

    Returns:
        Dict with pubkey, label, and status.
    """
    with LogSpan(span="ot_secrets.init") as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()

        existing = keyring.get_password(_SERVICE, _KEY_IDENTITY)
        if existing and not force:
            s.add(status="exists")
            return {
                "error": "Identity already exists in keychain. Pass force=True to overwrite.",
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


def encrypt(*, file: str, backup: bool = True) -> dict[str, Any]:
    """Encrypt plain values in a secrets YAML file in-place.

    Skips values already prefixed with `age1enc:`. Creates a .bak copy by default.

    Args:
        file: Path to secrets YAML file.
        backup: If True (default), create a .bak copy before modifying.

    Returns:
        Dict with encryption summary including encrypted, skipped, and plain key lists.
    """
    with LogSpan(span="ot_secrets.encrypt", file=file) as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()

        pubkey_str = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        if not pubkey_str:
            s.add(status="no_identity")
            return {
                "error": "No identity found in keychain. Run ot_secrets.init() first.",
                "status": "no_identity",
            }

        path = Path(file).expanduser()
        if not path.exists():
            s.add(status="file_not_found")
            return {"error": f"File not found: {file}", "status": "file_not_found"}

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            s.add(status="invalid_yaml")
            return {"error": str(exc), "status": "invalid_yaml"}

        if not isinstance(data, dict):
            s.add(status="invalid_yaml")
            return {"error": "File must be a YAML mapping", "status": "invalid_yaml"}

        recipient = pyrage.x25519.Recipient.from_str(pubkey_str)

        backup_path: str | None = None
        if backup:
            backup_path = str(path) + ".bak"
            shutil.copy2(path, backup_path)

        encrypted_keys: list[str] = []
        skipped_keys: list[str] = []
        null_keys: list[str] = []
        updated = dict(data)

        for key, value in data.items():
            if value is None:
                null_keys.append(key)
                continue
            str_val = str(value)
            if str_val.startswith(_PREFIX):
                skipped_keys.append(key)
            else:
                ciphertext = pyrage.encrypt(str_val.encode(), [recipient])
                encoded = base64.b64encode(ciphertext).decode()
                updated[key] = _PREFIX + encoded
                encrypted_keys.append(key)

        with path.open("w") as f:
            yaml.dump(updated, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        s.add(encryptedCount=len(encrypted_keys), skippedCount=len(skipped_keys))
        return {
            "file": str(path),
            "backup": backup_path,
            "encrypted": encrypted_keys,
            "skipped": skipped_keys,
            "null_keys": null_keys,
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

        if file is not None:
            path = Path(file).expanduser()
            if not path.exists():
                result["file_error"] = f"File not found: {file}"
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
                    result["values"] = {"encrypted": encrypted, "plain": plain, "null_keys": nulls}

        s.add(identity="found")
        return result


def rotate(*, file: str, backup: bool = True) -> dict[str, Any]:
    """Generate a new identity and re-encrypt all encrypted values in-place.

    Plain (non-`age1enc:`) values are left unchanged.

    Args:
        file: Path to secrets YAML file.
        backup: If True (default), create a .bak copy before modifying.

    Returns:
        Dict with rotation summary.
    """
    with LogSpan(span="ot_secrets.rotate", file=file) as s:
        keyring = _require_keyring()
        pyrage = _require_pyrage()

        old_private = keyring.get_password(_SERVICE, _KEY_IDENTITY)
        old_pubkey = keyring.get_password(_SERVICE, _KEY_PUBKEY)
        label = keyring.get_password(_SERVICE, _KEY_LABEL) or ""

        if not old_private:
            s.add(status="no_identity")
            return {
                "error": "No identity found in keychain. Run ot_secrets.init() first.",
                "status": "no_identity",
            }

        path = Path(file).expanduser()
        if not path.exists():
            s.add(status="file_not_found")
            return {"error": f"File not found: {file}", "status": "file_not_found"}

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            s.add(status="invalid_yaml")
            return {"error": str(exc), "status": "invalid_yaml"}

        if not isinstance(data, dict):
            s.add(status="invalid_yaml")
            return {"error": "File must be a YAML mapping", "status": "invalid_yaml"}

        backup_path: str | None = None
        if backup:
            backup_path = str(path) + ".bak"
            shutil.copy2(path, backup_path)

        old_identity = pyrage.x25519.Identity.from_str(old_private)

        new_identity = pyrage.x25519.Identity.generate()
        new_private = str(new_identity)
        new_pubkey = str(new_identity.to_public())
        new_recipient = pyrage.x25519.Recipient.from_str(new_pubkey)

        rotated_keys: list[str] = []
        skipped_keys: list[str] = []
        updated = dict(data)

        for key, value in data.items():
            if value is None:
                continue
            str_val = str(value)
            if str_val.startswith(_PREFIX):
                encoded = str_val[len(_PREFIX):]
                ciphertext = base64.b64decode(encoded)
                plaintext = pyrage.decrypt(ciphertext, [old_identity])
                new_ciphertext = pyrage.encrypt(plaintext, [new_recipient])
                new_encoded = base64.b64encode(new_ciphertext).decode()
                updated[key] = _PREFIX + new_encoded
                rotated_keys.append(key)
            else:
                skipped_keys.append(key)

        with path.open("w") as f:
            yaml.dump(updated, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        keyring.set_password(_SERVICE, _KEY_IDENTITY, new_private)
        keyring.set_password(_SERVICE, _KEY_PUBKEY, new_pubkey)
        keyring.set_password(_SERVICE, _KEY_LABEL, label)

        s.add(rotatedCount=len(rotated_keys), status="rotated")
        return {
            "old_pubkey_hint": _pubkey_hint(old_pubkey) if old_pubkey else None,
            "new_pubkey_hint": _pubkey_hint(new_pubkey),
            "file": str(path),
            "backup": backup_path,
            "rotated": rotated_keys,
            "skipped": skipped_keys,
            "status": "rotated",
        }


def audit(*, file: str) -> dict[str, Any]:
    """Scan a secrets YAML file for unencrypted values.

    Returns key names only — never exposes actual values.

    Args:
        file: Path to secrets YAML file.

    Returns:
        Dict with safe status, plain_keys, and encrypted_keys.
    """
    with LogSpan(span="ot_secrets.audit", file=file) as s:
        path = Path(file).expanduser()
        if not path.exists():
            s.add(status="file_not_found")
            return {"error": f"File not found: {file}", "status": "file_not_found"}

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
        s.add(safe=safe, plain_count=len(plain_keys), encrypted_count=len(encrypted_keys))
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
