"""Unit tests for onetool.cli._guided_secrets_setup (FIX-G).

Covers: (a) the plaintext interim write is always chmod 0600 regardless of
whether a prior template-copy chmod ran, and (b) a failure in ot_secrets
init()/encrypt() never leaves plaintext secrets on disk — the file is
restored to its pre-merge content (if that content was already fully
encrypted) or deleted outright otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def _mock_confirm_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    import questionary

    monkeypatch.setattr(
        questionary, "confirm", lambda *a, **k: MagicMock(ask=lambda: True)
    )


def _mock_one_pair_entry(
    monkeypatch: pytest.MonkeyPatch, key: str = "MY_KEY", value: str = "my_value"
) -> None:
    """Simulate entering exactly one key/value pair, then finishing normally."""
    import ot._tui as tui

    monkeypatch.setattr(tui, "ask_text_sync", MagicMock(side_effect=[key, ""]))
    monkeypatch.setattr(tui, "ask_password_sync", MagicMock(side_effect=[value]))


@pytest.mark.unit
@pytest.mark.core
def test_write_is_chmod_0600_even_without_prior_template_chmod(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The interim plaintext write is chmod 0600 unconditionally (FIX-G part a),
    not relying on a prior template-copy chmod that may have been skipped."""
    from onetool.cli import _guided_secrets_setup
    from ottools import ot_secrets

    secrets_path = tmp_path / "secrets.yaml"
    _mock_confirm_yes(monkeypatch)
    _mock_one_pair_entry(monkeypatch)

    monkeypatch.setattr(
        ot_secrets, "init", MagicMock(return_value={"status": "stored"})
    )
    monkeypatch.setattr(ot_secrets, "encrypt", MagicMock(return_value={}))
    monkeypatch.setattr(
        ot_secrets, "audit", MagicMock(return_value={"safe": True, "plain_keys": []})
    )

    _guided_secrets_setup(secrets_path)

    assert secrets_path.exists()
    assert (secrets_path.stat().st_mode & 0o777) == 0o600


@pytest.mark.unit
@pytest.mark.core
def test_failure_unlinks_when_file_did_not_pre_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No pre-existing file + init()/encrypt() failure -> plaintext is deleted,
    not left on disk (FIX-G part b)."""
    from onetool.cli import _guided_secrets_setup
    from ottools import ot_secrets

    secrets_path = tmp_path / "secrets.yaml"
    assert not secrets_path.exists()

    _mock_confirm_yes(monkeypatch)
    _mock_one_pair_entry(monkeypatch)

    monkeypatch.setattr(
        ot_secrets, "init", MagicMock(side_effect=RuntimeError("keychain exploded"))
    )

    with pytest.raises(RuntimeError, match="keychain exploded"):
        _guided_secrets_setup(secrets_path)

    assert not secrets_path.exists()


@pytest.mark.unit
@pytest.mark.core
def test_failure_restores_pre_merge_content_when_already_encrypted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-existing file whose content was already fully encrypted -> on failure,
    restore that exact pre-merge content rather than leaving the newly-merged
    plaintext value on disk."""
    from onetool.cli import _guided_secrets_setup
    from ottools import ot_secrets

    secrets_path = tmp_path / "secrets.yaml"
    original = "EXISTING: 'age1enc:ZmFrZQ=='\n"
    secrets_path.write_text(original)

    _mock_confirm_yes(monkeypatch)
    _mock_one_pair_entry(monkeypatch)

    monkeypatch.setattr(
        ot_secrets, "init", MagicMock(side_effect=RuntimeError("encrypt failed"))
    )

    with pytest.raises(RuntimeError, match="encrypt failed"):
        _guided_secrets_setup(secrets_path)

    assert secrets_path.exists()
    assert secrets_path.read_text() == original
    assert "my_value" not in secrets_path.read_text()
    assert (secrets_path.stat().st_mode & 0o777) == 0o600


@pytest.mark.unit
@pytest.mark.core
def test_failure_unlinks_when_pre_existing_content_had_plaintext(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-existing file already contained an unencrypted value of its own ->
    on failure, delete rather than restore (restoring would still leave
    plaintext of the pre-existing key on disk)."""
    from onetool.cli import _guided_secrets_setup
    from ottools import ot_secrets

    secrets_path = tmp_path / "secrets.yaml"
    secrets_path.write_text("EXISTING: plain_value\n")

    _mock_confirm_yes(monkeypatch)
    _mock_one_pair_entry(monkeypatch)

    monkeypatch.setattr(
        ot_secrets, "init", MagicMock(side_effect=RuntimeError("encrypt failed"))
    )

    with pytest.raises(RuntimeError, match="encrypt failed"):
        _guided_secrets_setup(secrets_path)

    assert not secrets_path.exists()


@pytest.mark.unit
@pytest.mark.core
def test_encrypt_failure_also_scrubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure in encrypt() (after init() succeeds) also scrubs the plaintext."""
    from onetool.cli import _guided_secrets_setup
    from ottools import ot_secrets

    secrets_path = tmp_path / "secrets.yaml"

    _mock_confirm_yes(monkeypatch)
    _mock_one_pair_entry(monkeypatch)

    monkeypatch.setattr(
        ot_secrets, "init", MagicMock(return_value={"status": "stored"})
    )
    monkeypatch.setattr(
        ot_secrets, "encrypt", MagicMock(side_effect=RuntimeError("disk full"))
    )

    with pytest.raises(RuntimeError, match="disk full"):
        _guided_secrets_setup(secrets_path)

    assert not secrets_path.exists()
