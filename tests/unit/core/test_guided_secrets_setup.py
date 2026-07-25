"""Transactional tests for ``onetool.cli._guided_secrets_setup``."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml


class _FakeSecureBackend:
    """Stand-in for an allow-listed OS keyring backend."""


_FakeSecureBackend.__module__ = "keyring.backends.macOS"
_FakeSecureBackend.__qualname__ = "Keyring"


def _keyring(store: dict[tuple[str, str], str]) -> MagicMock:
    keyring = MagicMock()
    keyring.get_keyring.return_value = _FakeSecureBackend()
    keyring.get_password.side_effect = lambda service, key: store.get((service, key))
    keyring.set_password.side_effect = lambda service, key, value: store.__setitem__(
        (service, key), value
    )
    return keyring


def _identity_store(pyrage: Any) -> tuple[Any, dict[tuple[str, str], str]]:
    identity = pyrage.x25519.Identity.generate()
    return identity, {
        ("onetool", "age_identity"): str(identity),
        ("onetool", "age_pubkey"): str(identity.to_public()),
        ("onetool", "age_label"): "original",
    }


def _prompt(
    monkeypatch: pytest.MonkeyPatch,
    *,
    confirmations: list[bool | None],
    keys: list[str | None],
    values: list[str | None],
) -> None:
    import questionary

    from ot import _tui

    confirm_answers = iter(confirmations)
    monkeypatch.setattr(
        questionary,
        "confirm",
        lambda *_args, **_kwargs: MagicMock(ask=lambda: next(confirm_answers)),
    )
    monkeypatch.setattr(_tui, "ask_text_sync", MagicMock(side_effect=keys))
    monkeypatch.setattr(_tui, "ask_password_sync", MagicMock(side_effect=values))


def _assert_no_residue(directory: Path) -> None:
    assert not list(directory.glob(".secrets_stage_*"))
    assert not list(directory.glob(".tmp_*"))


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.parametrize(
    ("keys", "values"),
    [
        ([None], []),
        (["ONE", None], ["secret-one"]),
        (["ONE"], [None]),
        (["ONE", "TWO", None], ["secret-one", "secret-two"]),
    ],
)
def test_cancellation_never_creates_target_backup_or_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    keys: list[str | None],
    values: list[str | None],
) -> None:
    from onetool.cli import _guided_secrets_setup

    target = tmp_path / "secrets.yaml"
    _prompt(
        monkeypatch,
        confirmations=[True],
        keys=keys,
        values=values,
    )

    _guided_secrets_setup(target)

    assert not target.exists()
    assert not Path(f"{target}.bak").exists()
    _assert_no_residue(tmp_path)


@pytest.mark.unit
@pytest.mark.core
def test_cancellation_preserves_existing_target_and_backup_exactly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from onetool.cli import _guided_secrets_setup

    target = tmp_path / "secrets.yaml"
    backup = Path(f"{target}.bak")
    target_bytes = b"EXISTING: 'age1enc:YWJj'\n"
    backup_bytes = b"OLD-RECOVERY: exact\n"
    target.write_bytes(target_bytes)
    backup.write_bytes(backup_bytes)
    _prompt(
        monkeypatch,
        confirmations=[True],
        keys=["ONE", "TWO", None],
        values=["secret-one", "secret-two"],
    )

    _guided_secrets_setup(target)

    assert target.read_bytes() == target_bytes
    assert backup.read_bytes() == backup_bytes
    _assert_no_residue(tmp_path)


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.parametrize("reuse_answer", [False, None])
def test_declining_or_cancelling_reuse_preserves_global_identity_and_ciphertext(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reuse_answer: bool | None,
) -> None:
    pyrage = pytest.importorskip("pyrage")
    from onetool.cli import _guided_secrets_setup
    from ottools import ot_secrets

    identity, store = _identity_store(pyrage)
    original_store = dict(store)
    other_file = tmp_path / "other.yaml"
    other_plaintext = b"still-readable"
    ciphertext = pyrage.encrypt(other_plaintext, [identity.to_public()])
    other_bytes = (
        "OTHER: 'age1enc:" + base64.b64encode(ciphertext).decode() + "'\n"
    ).encode()
    other_file.write_bytes(other_bytes)
    target = tmp_path / "secrets.yaml"
    _prompt(
        monkeypatch,
        confirmations=[True, reuse_answer],
        keys=["NEW", ""],
        values=["new-value"],
    )
    monkeypatch.setattr(ot_secrets, "_require_keyring", lambda: _keyring(store))

    _guided_secrets_setup(target)

    assert store == original_store
    assert other_file.read_bytes() == other_bytes
    loaded = yaml.safe_load(other_file.read_text())
    encrypted = base64.b64decode(loaded["OTHER"][len("age1enc:") :], validate=True)
    assert pyrage.decrypt(encrypted, [identity]) == other_plaintext
    assert not target.exists()
    assert not Path(f"{target}.bak").exists()
    _assert_no_residue(tmp_path)


@pytest.mark.unit
@pytest.mark.core
def test_reuse_success_preserves_identity_and_writes_verified_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyrage = pytest.importorskip("pyrage")
    from onetool.cli import _guided_secrets_setup
    from ottools import ot_secrets

    identity, store = _identity_store(pyrage)
    original_store = dict(store)
    target = tmp_path / "secrets.yaml"
    _prompt(
        monkeypatch,
        confirmations=[True, True],
        keys=["NEW_SECRET", ""],
        values=["new-value"],
    )
    monkeypatch.setattr(ot_secrets, "_require_keyring", lambda: _keyring(store))

    _guided_secrets_setup(target)

    assert store == original_store
    target_data = yaml.safe_load(target.read_text())
    encoded = target_data["NEW_SECRET"]
    assert encoded.startswith("age1enc:")
    ciphertext = base64.b64decode(encoded[len("age1enc:") :], validate=True)
    assert pyrage.decrypt(ciphertext, [identity]) == b"new-value"
    backup = Path(f"{target}.bak")
    assert backup.read_bytes() == b"NEW_SECRET: new-value\n"
    assert (target.stat().st_mode & 0o777) == 0o600
    assert (backup.stat().st_mode & 0o777) == 0o600
    _assert_no_residue(tmp_path)


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.parametrize(
    "failure",
    [
        "init_return",
        "init_raise",
        "encrypt_return",
        "encrypt_raise",
        "audit_return",
        "audit_raise",
        "audit_unsafe",
        "commit_raise",
    ],
)
def test_lifecycle_failures_preserve_existing_files_and_leave_no_plaintext(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    pyrage = pytest.importorskip("pyrage")
    from onetool.cli import _guided_secrets_setup
    from ottools import ot_secrets

    _, store = _identity_store(pyrage)
    target = tmp_path / "secrets.yaml"
    backup = Path(f"{target}.bak")
    target_bytes = b"EXISTING: 'age1enc:YWJj'\n"
    backup_bytes = b"EXISTING: old-recovery\n"
    target.write_bytes(target_bytes)
    backup.write_bytes(backup_bytes)
    _prompt(
        monkeypatch,
        confirmations=[True, True],
        keys=["NEW", ""],
        values=["never-write-this"],
    )
    monkeypatch.setattr(ot_secrets, "_require_keyring", lambda: _keyring(store))

    if failure == "init_return":
        monkeypatch.setattr(
            ot_secrets,
            "init",
            MagicMock(return_value={"error": "init failed", "status": "failed"}),
        )
    elif failure == "init_raise":
        monkeypatch.setattr(
            ot_secrets, "init", MagicMock(side_effect=RuntimeError("init failed"))
        )
    elif failure == "encrypt_return":
        monkeypatch.setattr(
            ot_secrets,
            "encrypt",
            MagicMock(return_value={"error": "encrypt failed", "status": "failed"}),
        )
    elif failure == "encrypt_raise":
        monkeypatch.setattr(
            ot_secrets, "encrypt", MagicMock(side_effect=RuntimeError("encrypt failed"))
        )
    elif failure == "audit_return":
        monkeypatch.setattr(
            ot_secrets,
            "audit",
            MagicMock(return_value={"error": "audit failed", "status": "failed"}),
        )
    elif failure == "audit_raise":
        monkeypatch.setattr(
            ot_secrets, "audit", MagicMock(side_effect=RuntimeError("audit failed"))
        )
    elif failure == "audit_unsafe":
        monkeypatch.setattr(
            ot_secrets,
            "audit",
            MagicMock(return_value={"safe": False, "plain_keys": ["NEW"]}),
        )
    else:
        monkeypatch.setattr(
            ot_secrets,
            "_commit_with_backup",
            MagicMock(side_effect=RuntimeError("commit failed")),
        )

    with pytest.raises(RuntimeError):
        _guided_secrets_setup(target)

    assert target.read_bytes() == target_bytes
    assert backup.read_bytes() == backup_bytes
    for file_path in tmp_path.iterdir():
        assert b"never-write-this" not in file_path.read_bytes()
    _assert_no_residue(tmp_path)
