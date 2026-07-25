"""Unit tests for ot_secrets tool pack.

Tests init(), encrypt(), status(), and audit().
Uses mocked keyring and pyrage to avoid external dependencies.
"""

from __future__ import annotations

import base64
import inspect
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeSecureBackend:
    """Stand-in whose type resolves to an allow-listed secure keyring backend."""


_FakeSecureBackend.__module__ = "keyring.backends.macOS"
_FakeSecureBackend.__qualname__ = "Keyring"


class _FakeInsecureBackend:
    """Stand-in whose type resolves to a rejected (plaintext-fallback) backend."""


_FakeInsecureBackend.__module__ = "keyring.backends.fail"
_FakeInsecureBackend.__qualname__ = "Keyring"


def _make_keyring_mock(
    store: dict | None = None,
    *,
    secure: bool = True,
    complete_identity: bool = True,
) -> MagicMock:
    """Return a keyring mock backed by an in-memory store.

    By default resolves to a secure backend so backend validation passes; set
    ``secure=False`` to exercise the insecure-backend rejection path.
    """
    if store is None:
        store = {}
    if (
        complete_identity
        and ("onetool", "age_pubkey") in store
        and ("onetool", "age_identity") not in store
    ):
        store[("onetool", "age_identity")] = "AGE-SECRET-KEY-fake"
    kr = MagicMock()
    kr.get_password.side_effect = lambda s, k: store.get((s, k))
    kr.set_password.side_effect = lambda s, k, v: store.update({(s, k): v})
    kr.get_keyring.return_value = (
        _FakeSecureBackend() if secure else _FakeInsecureBackend()
    )
    return kr


def _make_pyrage_mock(
    private_key: str = "AGE-SECRET-KEY-fake",
    public_key: str = "age1fakepubkey1234567890abcdef",
    ciphertext: bytes = b"fake_ciphertext",
    plaintext: bytes = b"decrypted_value",
) -> MagicMock:
    """Return a pyrage mock with sensible defaults."""
    pr = MagicMock()

    # Identity.generate()
    identity = MagicMock()
    identity.__str__ = MagicMock(return_value=private_key)
    recipient = MagicMock()
    recipient.__str__ = MagicMock(return_value=public_key)
    identity.to_public.return_value = recipient
    pr.x25519.Identity.generate.return_value = identity

    # Identity.from_str() and Recipient.from_str() form a matching pair.
    loaded_identity = MagicMock()
    loaded_identity.__str__ = MagicMock(return_value=private_key)
    pr.x25519.Identity.from_str.return_value = loaded_identity

    def parse_recipient(value: str) -> MagicMock:
        parsed = MagicMock()
        parsed.__str__ = MagicMock(return_value=value)
        loaded_identity.to_public.return_value = parsed
        return parsed

    pr.x25519.Recipient.from_str.side_effect = parse_recipient

    # Keep operational identity validation reversible while preserving explicit
    # ciphertext/plaintext controls for value-level tests.
    identity_probe = b"onetool-age-identity-check"
    probe_ciphertext = b"identity-check:" + identity_probe
    last_plaintext: list[bytes | None] = [None]

    def encrypt_value(value: bytes, _recipients: list[object]) -> bytes:
        if value == identity_probe:
            return probe_ciphertext
        last_plaintext[0] = value
        return ciphertext

    def decrypt_value(value: bytes, _identities: list[object]) -> bytes:
        if value == probe_ciphertext:
            return identity_probe
        return last_plaintext[0] if last_plaintext[0] is not None else plaintext

    pr.encrypt.side_effect = encrypt_value
    pr.decrypt.side_effect = decrypt_value

    return pr


# ---------------------------------------------------------------------------
# Module structure tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_pack_name() -> None:
    from ottools.ot_secrets import pack

    assert pack == "ot_secrets"


@pytest.mark.unit
@pytest.mark.tools
def test_all_exports() -> None:
    from ottools.ot_secrets import __all__

    assert set(__all__) == {"init", "encrypt", "status", "audit", "set", "get", "unset"}


@pytest.mark.unit
@pytest.mark.tools
def test_removed_identity_replacement_interfaces_are_absent() -> None:
    from ottools import ot_secrets

    assert not hasattr(ot_secrets, "rotate")
    assert "force" not in inspect.signature(ot_secrets.init).parameters


@pytest.mark.unit
@pytest.mark.tools
def test_ot_requires() -> None:
    from ottools.ot_secrets import __ot_requires__

    lib_names = [name for name, _ in __ot_requires__["lib"]]
    assert "pyrage" in lib_names
    assert "keyring" in lib_names


# ---------------------------------------------------------------------------
# init() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_init_stores_new_identity() -> None:
    """New identity is generated and stored in keychain."""
    store: dict = {}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock(
        private_key="AGE-SECRET-KEY-test",
        public_key="age1testpubkey1234567890abcdef01",
    )

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import init

        result = init(label="macbook-gavin")

    assert result["status"] == "stored"
    assert result["pubkey"] == "age1testpubkey1234567890abcdef01"
    assert result["label"] == "macbook-gavin"
    assert store[("onetool", "age_identity")] == "AGE-SECRET-KEY-test"
    assert store[("onetool", "age_pubkey")] == "age1testpubkey1234567890abcdef01"
    assert store[("onetool", "age_label")] == "macbook-gavin"


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.parametrize("existing_key", ["age_identity", "age_pubkey"])
def test_init_error_on_existing_identity(existing_key: str) -> None:
    """Error returned when any identity state already exists."""
    store = {("onetool", existing_key): "existing"}
    kr = _make_keyring_mock(store, complete_identity=False)
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import init

        result = init()

    assert result["status"] == "exists"
    assert "error" in result
    assert "original identity" in result["error"]
    assert store == {("onetool", existing_key): "existing"}
    pr.x25519.Identity.generate.assert_not_called()


@pytest.mark.unit
@pytest.mark.tools
def test_init_default_label_empty_string() -> None:
    """Default label is empty string."""
    store: dict = {}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import init

        result = init()

    assert result["label"] == ""
    assert store[("onetool", "age_label")] == ""


# ---------------------------------------------------------------------------
# encrypt() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_plain_values(tmp_path: Path) -> None:
    """Plain values are encrypted; return value lists encrypted keys."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("API_KEY: mykey\nOTHER: value\n")

    fake_cipher = b"CIPHER"
    expected_encoded = base64.b64encode(fake_cipher).decode()

    store = {("onetool", "age_pubkey"): "age1fakepub"}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock(ciphertext=fake_cipher)

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file), backup=False)

    assert result["encrypted"] == ["API_KEY", "OTHER"] or set(result["encrypted"]) == {
        "API_KEY",
        "OTHER",
    }
    assert result["skipped"] == []
    assert result["backup"] is None

    data = yaml.safe_load(secrets_file.read_text())
    assert data["API_KEY"] == f"age1enc:{expected_encoded}"
    assert data["OTHER"] == f"age1enc:{expected_encoded}"


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_skips_already_encrypted(tmp_path: Path) -> None:
    """Values already prefixed age1enc: are skipped."""
    existing = "age1enc:ALREADYENCODED"
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text(f"KEY: '{existing}'\n")

    store = {("onetool", "age_pubkey"): "age1fakepub"}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file), backup=False)

    assert result["encrypted"] == []
    assert "KEY" in result["skipped"]
    pr.encrypt.assert_called_once()


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_creates_backup(tmp_path: Path) -> None:
    """backup=True creates a .bak copy of the original file."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("KEY: value\n")

    store = {("onetool", "age_pubkey"): "age1fakepub"}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file), backup=True)

    backup_path = Path(str(secrets_file) + ".bak")
    assert backup_path.exists()
    assert result["backup"] == str(backup_path)


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_no_identity_returns_error(tmp_path: Path) -> None:
    """Error returned when no identity is in keychain."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("KEY: value\n")

    store: dict = {}  # no pubkey
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file))

    assert "error" in result
    assert result["status"] == "identity_inconsistent"


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_idempotent_on_all_encrypted(tmp_path: Path) -> None:
    """File with all age1enc: values → no changes, empty encrypted list."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("KEY: 'age1enc:ENCODED'\n")

    store = {("onetool", "age_pubkey"): "age1fakepub"}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file), backup=False)

    assert result["encrypted"] == []
    assert "KEY" in result["skipped"]


# ---------------------------------------------------------------------------
# status() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_status_identity_found_no_file(tmp_path: Path) -> None:
    """Identity found, no resolvable secrets file: returns identity with no values."""
    store = {
        ("onetool", "age_pubkey"): "age1longpubkey1234567890abcdefgh",
        ("onetool", "age_label"): "my-machine",
    }
    kr = _make_keyring_mock(store)

    # status() now resolves a default secrets file; point that default at a path
    # that does not exist so this test still exercises the identity-only branch.
    missing = tmp_path / "no-secrets.yaml"
    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._resolve_secrets_file", return_value=missing),
    ):
        from ottools.ot_secrets import status

        result = status()

    assert result["identity"] == "found"
    assert result["label"] == "my-machine"
    assert result["file"] is None
    assert result["values"] is None
    assert "pubkey_hint" in result
    # Hint should be truncated, not full key
    assert result["pubkey_hint"] != "age1longpubkey1234567890abcdefgh"


@pytest.mark.unit
@pytest.mark.tools
def test_status_identity_found_with_file(tmp_path: Path) -> None:
    """Identity found with file: returns encrypted/plain value counts."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("KEY1: 'age1enc:ENCODED'\nKEY2: plaintext\n")

    store = {("onetool", "age_pubkey"): "age1fakepubkey1234567890abcdef01"}
    kr = _make_keyring_mock(store)

    with patch("ottools.ot_secrets._require_keyring", return_value=kr):
        from ottools.ot_secrets import status

        result = status(file=str(secrets_file))

    assert result["identity"] == "found"
    assert result["file"] == str(secrets_file)
    assert "KEY1" in result["values"]["encrypted"]
    assert "KEY2" in result["values"]["plain"]


@pytest.mark.unit
@pytest.mark.tools
def test_status_no_identity() -> None:
    """No identity found: returns not found with hint."""
    store: dict = {}
    kr = _make_keyring_mock(store)

    with patch("ottools.ot_secrets._require_keyring", return_value=kr):
        from ottools.ot_secrets import status

        result = status()

    assert result["identity"] == "not found"
    assert "hint" in result
    assert "ot_secrets.init()" in result["hint"]


@pytest.mark.unit
@pytest.mark.tools
def test_status_file_not_found() -> None:
    """File not found: file_error set, file/values remain null."""
    store = {("onetool", "age_pubkey"): "age1fakepubkey1234567890abcdef01"}
    kr = _make_keyring_mock(store)

    with patch("ottools.ot_secrets._require_keyring", return_value=kr):
        from ottools.ot_secrets import status

        result = status(file="/nonexistent/path/secrets.yaml")

    assert result["identity"] == "found"
    assert "file_error" in result
    assert "not found" in result["file_error"].lower()
    assert result["file"] is None
    assert result["values"] is None


@pytest.mark.unit
@pytest.mark.tools
def test_status_file_empty_yaml(tmp_path: Path) -> None:
    """File exists but has no YAML mapping: file_error set."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("# only comments\n")

    store = {("onetool", "age_pubkey"): "age1fakepubkey1234567890abcdef01"}
    kr = _make_keyring_mock(store)

    with patch("ottools.ot_secrets._require_keyring", return_value=kr):
        from ottools.ot_secrets import status

        result = status(file=str(secrets_file))

    assert result["identity"] == "found"
    assert "file_error" in result
    assert result["file"] is None
    assert result["values"] is None


# ---------------------------------------------------------------------------
# audit() tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_audit_all_encrypted(tmp_path: Path) -> None:
    """All encrypted values → safe=True, empty plain_keys."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("KEY1: 'age1enc:ABC'\nKEY2: 'age1enc:XYZ'\n")

    from ottools.ot_secrets import audit

    result = audit(file=str(secrets_file))

    assert result["safe"] is True
    assert result["plain_keys"] == []
    assert set(result["encrypted_keys"]) == {"KEY1", "KEY2"}


@pytest.mark.unit
@pytest.mark.tools
def test_audit_plain_values_detected(tmp_path: Path) -> None:
    """Plain values detected → safe=False, plain_keys listed, values never exposed."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("SECRET_KEY: my_secret_value\nKEY2: 'age1enc:ENC'\n")

    from ottools.ot_secrets import audit

    result = audit(file=str(secrets_file))

    assert result["safe"] is False
    assert "SECRET_KEY" in result["plain_keys"]
    assert "message" in result
    assert "ot_secrets.encrypt()" in result["message"]


@pytest.mark.unit
@pytest.mark.tools
def test_audit_never_exposes_values(tmp_path: Path) -> None:
    """Return value contains only key names, never actual secret values."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("SENSITIVE: super_secret_api_key_12345\n")

    from ottools.ot_secrets import audit

    result = audit(file=str(secrets_file))

    # Ensure the actual value does not appear anywhere in the result
    result_str = str(result)
    assert "super_secret_api_key_12345" not in result_str
    assert "SENSITIVE" in result["plain_keys"]


@pytest.mark.unit
@pytest.mark.tools
def test_audit_safe_true_no_message(tmp_path: Path) -> None:
    """All encrypted → no warning message returned."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("KEY: 'age1enc:ABC'\n")

    from ottools.ot_secrets import audit

    result = audit(file=str(secrets_file))

    assert result["safe"] is True
    assert "message" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_audit_empty_yaml_returns_no_mapping(tmp_path: Path) -> None:
    """Comment-only or empty YAML → status 'no_mapping', not 'invalid_yaml'."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("# only comments\n")

    from ottools.ot_secrets import audit

    result = audit(file=str(secrets_file))

    assert result["status"] == "no_mapping"
    assert "error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_audit_null_values_tracked(tmp_path: Path) -> None:
    """Keys with null values appear in null_keys, not plain_keys or encrypted_keys."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("API_KEY: null\nOTHER: ~\nSET: plaintext\n")

    from ottools.ot_secrets import audit

    result = audit(file=str(secrets_file))

    assert set(result["null_keys"]) == {"API_KEY", "OTHER"}
    assert result["plain_keys"] == ["SET"]
    assert result["encrypted_keys"] == []
    assert result["safe"] is False


@pytest.mark.unit
@pytest.mark.tools
def test_audit_all_null_safe_false(tmp_path: Path) -> None:
    """All-null file: safe=False is NOT reported (no plain values), null_keys listed."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("API_KEY: null\nOTHER: ~\n")

    from ottools.ot_secrets import audit

    result = audit(file=str(secrets_file))

    assert result["safe"] is True  # no plain-text values to expose
    assert set(result["null_keys"]) == {"API_KEY", "OTHER"}
    assert result["plain_keys"] == []


# ---------------------------------------------------------------------------
# encrypt() key-order preservation tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Invalid YAML handling tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_audit_invalid_yaml_returns_error(tmp_path: Path) -> None:
    """Malformed YAML → status 'invalid_yaml', no exception raised."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("not: a: valid: yaml: - bad\n")

    from ottools.ot_secrets import audit

    result = audit(file=str(secrets_file))

    assert result["status"] == "invalid_yaml"
    assert "error" in result


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_invalid_yaml_returns_error(tmp_path: Path) -> None:
    """Malformed YAML in encrypt → status 'invalid_yaml', no exception raised."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("not: a: valid: yaml: - bad\n")

    store = {("onetool", "age_pubkey"): "age1fakepub"}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file), backup=False)

    assert result["status"] == "invalid_yaml"
    assert "error" in result


# ---------------------------------------------------------------------------
# Null key reporting tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_reports_null_keys(tmp_path: Path) -> None:
    """Null-valued keys appear in null_keys, not encrypted or skipped."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("API_KEY: realvalue\nOPTIONAL: null\nOTHER: ~\n")

    store = {("onetool", "age_pubkey"): "age1fakepub"}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock(ciphertext=b"CIPHER")

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file), backup=False)

    assert result["encrypted"] == ["API_KEY"]
    assert result["skipped"] == []
    assert set(result["null_keys"]) == {"OPTIONAL", "OTHER"}


@pytest.mark.unit
@pytest.mark.tools
def test_status_reports_null_keys(tmp_path: Path) -> None:
    """status() includes null_keys in values dict."""
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text(
        "KEY1: 'age1enc:ENCODED'\nKEY2: plaintext\nOPTIONAL: null\n"
    )

    store = {("onetool", "age_pubkey"): "age1fakepubkey1234567890abcdef01"}
    kr = _make_keyring_mock(store)

    with patch("ottools.ot_secrets._require_keyring", return_value=kr):
        from ottools.ot_secrets import status

        result = status(file=str(secrets_file))

    assert result["identity"] == "found"
    assert "KEY1" in result["values"]["encrypted"]
    assert "KEY2" in result["values"]["plain"]
    assert "OPTIONAL" in result["values"]["null_keys"]


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_preserves_key_order(tmp_path: Path) -> None:
    """encrypt() preserves original key ordering in the written file."""
    secrets_file = tmp_path / "secrets.yaml"
    # Deliberately non-alphabetical order: Z, A, M
    secrets_file.write_text("ZEBRA: value1\nAPPLE: value2\nMIDDLE: value3\n")

    store = {("onetool", "age_pubkey"): "age1fakepub"}
    kr = _make_keyring_mock(store)
    pr = _make_pyrage_mock(ciphertext=b"CIPHER")

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        encrypt(file=str(secrets_file), backup=False)

    content = secrets_file.read_text()
    zebra_pos = content.index("ZEBRA")
    apple_pos = content.index("APPLE")
    middle_pos = content.index("MIDDLE")
    assert zebra_pos < apple_pos < middle_pos, "Key order not preserved after encrypt()"


# ---------------------------------------------------------------------------
# p14: keyring backend validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_insecure_backend_rejected_by_init_and_encrypt(tmp_path: Path) -> None:
    """init and encrypt reject an insecure backend before touching the keychain."""
    from ottools import ot_secrets

    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("A: plain\n")

    for fn, kwargs in (
        (ot_secrets.init, {}),
        (ot_secrets.encrypt, {"file": str(secrets_file)}),
    ):
        kr = _make_keyring_mock(
            {("onetool", "age_pubkey"): "age1pub", ("onetool", "age_identity"): "id"},
            secure=False,
        )
        with (
            patch("ottools.ot_secrets._require_keyring", return_value=kr),
            pytest.raises(RuntimeError, match=r"keyring\.backends\.fail"),
        ):
            fn(**kwargs)
        # No keychain read/write happened after rejection.
        kr.set_password.assert_not_called()


@pytest.mark.unit
@pytest.mark.tools
def test_secure_backend_allows_init() -> None:
    """A secure backend does not trip the allow-list (happy-path regression guard)."""
    from ottools.ot_secrets import init

    kr = _make_keyring_mock(secure=True)
    pr = _make_pyrage_mock()
    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        result = init()
    assert result["status"] == "stored"


# ---------------------------------------------------------------------------
# p14: atomic write + 0600
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_atomic_write_failure_leaves_original(tmp_path: Path) -> None:
    """A mid-write failure leaves the original file intact and no temp behind."""
    from ottools.ot_secrets import _atomic_write_yaml

    target = tmp_path / "secrets.yaml"
    target.write_text("ORIGINAL: value\n")

    with (
        patch("ottools.ot_secrets.yaml.dump", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        _atomic_write_yaml(target, {"NEW": "data"})

    assert target.read_text() == "ORIGINAL: value\n"
    assert not list(tmp_path.glob(".tmp_*"))


@pytest.mark.unit
@pytest.mark.tools
def test_atomic_write_is_0600_under_permissive_umask(tmp_path: Path) -> None:
    """The written file is 0600 even with a permissive umask."""
    from ottools.ot_secrets import _atomic_write_yaml

    target = tmp_path / "secrets.yaml"
    old = os.umask(0o022)
    try:
        _atomic_write_yaml(target, {"K": "v"})
    finally:
        os.umask(old)
    assert (target.stat().st_mode & 0o777) == 0o600


# ---------------------------------------------------------------------------
# encrypt backup default + 0600
# ---------------------------------------------------------------------------


def _encrypt_ready(tmp_path: Path) -> tuple[Path, MagicMock, MagicMock]:
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("API: sk-plain\n")
    kr = _make_keyring_mock({("onetool", "age_pubkey"): "age1pub"})
    pr = _make_pyrage_mock()
    return secrets_file, kr, pr


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_creates_exact_backup_by_default(tmp_path: Path) -> None:
    secrets_file, kr, pr = _encrypt_ready(tmp_path)
    original = secrets_file.read_bytes()
    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file))
    backup_path = Path(str(secrets_file) + ".bak")
    assert result["backup"] == str(backup_path)
    assert backup_path.read_bytes() == original
    assert (backup_path.stat().st_mode & 0o777) == 0o600
    assert (secrets_file.stat().st_mode & 0o777) == 0o600


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_backup_false_creates_none(tmp_path: Path) -> None:
    secrets_file, kr, pr = _encrypt_ready(tmp_path)
    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file), backup=False)
    bak = Path(str(secrets_file) + ".bak")
    assert result["backup"] is None
    assert not bak.exists()


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.parametrize(
    ("store", "failure"),
    [
        ({("onetool", "age_pubkey"): "age1pub"}, "public-only"),
        ({("onetool", "age_identity"): "private"}, "private-only"),
    ],
)
def test_encrypt_incomplete_identity_preserves_file_and_metadata(
    tmp_path: Path,
    store: dict[tuple[str, str], str],
    failure: str,
) -> None:
    secrets_file = tmp_path / "secrets.yaml"
    original = b"API: plaintext\n"
    secrets_file.write_bytes(original)
    secrets_file.chmod(0o640)
    before = secrets_file.stat()
    kr = _make_keyring_mock(store, complete_identity=False)
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file))

    after = secrets_file.stat()
    assert result["status"] == "identity_inconsistent", failure
    assert secrets_file.read_bytes() == original
    assert (after.st_mode, after.st_mtime_ns, after.st_ino) == (
        before.st_mode,
        before.st_mtime_ns,
        before.st_ino,
    )
    assert not Path(f"{secrets_file}.bak").exists()


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.parametrize("invalid_half", ["private", "public"])
def test_encrypt_malformed_identity_preserves_source(
    tmp_path: Path, invalid_half: str
) -> None:
    secrets_file, kr, pr = _encrypt_ready(tmp_path)
    original = secrets_file.read_bytes()
    parser = (
        pr.x25519.Identity.from_str
        if invalid_half == "private"
        else pr.x25519.Recipient.from_str
    )
    parser.side_effect = ValueError(f"malformed {invalid_half}")

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file))

    assert result["status"] == "identity_inconsistent"
    assert secrets_file.read_bytes() == original
    assert not Path(f"{secrets_file}.bak").exists()


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_mismatched_identity_preserves_source(tmp_path: Path) -> None:
    secrets_file, kr, pr = _encrypt_ready(tmp_path)
    original = secrets_file.read_bytes()
    mismatched = MagicMock()
    mismatched.__str__ = MagicMock(return_value="age1different")
    recipient = MagicMock()
    recipient.__str__ = MagicMock(return_value="age1pub")
    pr.x25519.Recipient.from_str.side_effect = None
    pr.x25519.Recipient.from_str.return_value = recipient
    pr.x25519.Identity.from_str.return_value.to_public.return_value = mismatched

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file))

    assert result["status"] == "identity_inconsistent"
    assert secrets_file.read_bytes() == original
    assert not Path(f"{secrets_file}.bak").exists()


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_identity_probe_failure_preserves_source(tmp_path: Path) -> None:
    secrets_file, kr, pr = _encrypt_ready(tmp_path)
    original = secrets_file.read_bytes()
    pr.decrypt.side_effect = RuntimeError("key cannot decrypt")

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file))

    assert result["status"] == "identity_inconsistent"
    assert secrets_file.read_bytes() == original
    assert not Path(f"{secrets_file}.bak").exists()


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_value_verification_exception_preserves_source(tmp_path: Path) -> None:
    secrets_file, kr, pr = _encrypt_ready(tmp_path)
    original = secrets_file.read_bytes()
    pr.decrypt.side_effect = [
        b"onetool-age-identity-check",
        RuntimeError("value cannot decrypt"),
    ]

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file))

    assert result["status"] == "verify_failed"
    assert secrets_file.read_bytes() == original
    assert not Path(f"{secrets_file}.bak").exists()


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.parametrize("failure_point", ["create", "chmod", "replace"])
def test_encrypt_backup_failure_preserves_exact_source(
    tmp_path: Path,
    failure_point: str,
) -> None:
    secrets_file, kr, pr = _encrypt_ready(tmp_path)
    original = secrets_file.read_bytes()
    before = secrets_file.stat()
    patch_target = {
        "create": "ottools.ot_secrets.tempfile.mkstemp",
        "chmod": "ottools.ot_secrets.os.fchmod",
        "replace": "ottools.ot_secrets.Path.replace",
    }[failure_point]

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
        patch(patch_target, side_effect=OSError(failure_point)),
        pytest.raises(OSError, match=failure_point),
    ):
        from ottools.ot_secrets import encrypt

        encrypt(file=str(secrets_file))

    after = secrets_file.stat()
    assert secrets_file.read_bytes() == original
    assert (after.st_mode, after.st_mtime_ns, after.st_ino) == (
        before.st_mode,
        before.st_mtime_ns,
        before.st_ino,
    )
    assert not Path(f"{secrets_file}.bak").exists()
    assert not list(tmp_path.glob(".tmp_*"))


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_target_failure_restores_previous_backup(tmp_path: Path) -> None:
    secrets_file, kr, pr = _encrypt_ready(tmp_path)
    source = secrets_file.read_bytes()
    backup_path = Path(f"{secrets_file}.bak")
    previous_backup = b"PREVIOUS-BACKUP\n"
    backup_path.write_bytes(previous_backup)

    real_replace = os.replace
    calls = 0

    def fail_target_replace(source_path: str, destination: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("target replace")
        real_replace(source_path, destination)

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
        patch(
            "ottools.ot_secrets.Path.replace",
            autospec=True,
            side_effect=fail_target_replace,
        ),
        pytest.raises(OSError, match="target replace"),
    ):
        from ottools.ot_secrets import encrypt

        encrypt(file=str(secrets_file))

    assert secrets_file.read_bytes() == source
    assert backup_path.read_bytes() == previous_backup
    assert not list(tmp_path.glob(".tmp_*"))


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_real_identity_round_trip_and_backup(tmp_path: Path) -> None:
    pyrage = pytest.importorskip("pyrage")
    identity = pyrage.x25519.Identity.generate()
    store = {
        ("onetool", "age_identity"): str(identity),
        ("onetool", "age_pubkey"): str(identity.to_public()),
    }
    kr = _make_keyring_mock(store)
    secrets_file = tmp_path / "secrets.yaml"
    original = b"API: exact-secret\n"
    secrets_file.write_bytes(original)

    with patch("ottools.ot_secrets._require_keyring", return_value=kr):
        from ottools.ot_secrets import encrypt

        result = encrypt(file=str(secrets_file))

    written = yaml.safe_load(secrets_file.read_text())
    ciphertext = base64.b64decode(written["API"][len("age1enc:") :], validate=True)
    assert pyrage.decrypt(ciphertext, [identity]) == b"exact-secret"
    backup_path = Path(result["backup"])
    assert backup_path.read_bytes() == original
    assert (backup_path.stat().st_mode & 0o777) == 0o600


# ---------------------------------------------------------------------------
# p14: file= default resolution
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_encrypt_defaults_to_loaded_secrets_path(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("API: plain\n")
    kr = _make_keyring_mock({("onetool", "age_pubkey"): "age1pub"})
    pr = _make_pyrage_mock()
    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
        patch(
            "ot.config.loader.get_loaded_secrets_path", return_value=str(secrets_file)
        ),
    ):
        from ottools.ot_secrets import encrypt

        result = encrypt()
    assert result["file"] == str(secrets_file)


# ---------------------------------------------------------------------------
# p14: set()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_set_encrypts_and_never_leaks_value(tmp_path: Path) -> None:
    import json

    secrets_file = tmp_path / "secrets.yaml"
    kr = _make_keyring_mock(
        {("onetool", "age_pubkey"): "age1pub", ("onetool", "age_identity"): "id"}
    )
    pr = _make_pyrage_mock(plaintext=b"secret123")
    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import set as set_secret

        result = set_secret(key="X", value="secret123", file=str(secrets_file))

    assert result["encrypted"] is True
    assert "secret123" not in json.dumps(result)
    written = yaml.safe_load(secrets_file.read_text())
    assert written["X"].startswith("age1enc:")
    assert "secret123" not in secrets_file.read_text()
    assert (secrets_file.stat().st_mode & 0o777) == 0o600


@pytest.mark.unit
@pytest.mark.tools
def test_set_preserves_other_keys(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("KEEP: keep_val\nX: old\n")
    kr = _make_keyring_mock(
        {("onetool", "age_pubkey"): "age1pub", ("onetool", "age_identity"): "id"}
    )
    pr = _make_pyrage_mock(plaintext=b"newval")
    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import set as set_secret

        set_secret(key="X", value="newval", file=str(secrets_file))
    written = yaml.safe_load(secrets_file.read_text())
    assert written["KEEP"] == "keep_val"
    assert list(written.keys()) == ["KEEP", "X"]


@pytest.mark.unit
@pytest.mark.tools
def test_set_no_identity_stores_plain_with_warning(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.yaml"
    kr = _make_keyring_mock({})  # no pubkey
    with patch("ottools.ot_secrets._require_keyring", return_value=kr):
        from ottools.ot_secrets import set as set_secret

        result = set_secret(key="X", value="plainval", file=str(secrets_file))
    assert result["encrypted"] is False
    assert "warning" in result
    assert yaml.safe_load(secrets_file.read_text())["X"] == "plainval"


@pytest.mark.unit
@pytest.mark.tools
def test_set_pubkey_present_identity_missing_clean_error(tmp_path: Path) -> None:
    """FIX-E: pubkey present but identity lost from keychain -> clean no-identity
    error, not an unhandled TypeError from Identity.from_str(None)."""
    secrets_file = tmp_path / "secrets.yaml"
    kr = _make_keyring_mock(
        {("onetool", "age_pubkey"): "age1pub"}, complete_identity=False
    )
    pr = _make_pyrage_mock()

    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import set as set_secret

        result = set_secret(key="X", value="v", file=str(secrets_file))

    assert result["status"] == "no_identity"
    assert "ot_secrets.init()" in result["error"]
    pr.x25519.Identity.from_str.assert_not_called()
    assert not secrets_file.exists()


@pytest.mark.unit
@pytest.mark.tools
def test_set_insecure_backend_rejected_before_write(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.yaml"
    kr = _make_keyring_mock(
        {("onetool", "age_pubkey"): "age1pub", ("onetool", "age_identity"): "id"},
        secure=False,
    )
    with patch("ottools.ot_secrets._require_keyring", return_value=kr):
        from ottools.ot_secrets import set as set_secret

        with pytest.raises(RuntimeError, match=r"keyring\.backends\.fail"):
            set_secret(key="X", value="v", file=str(secrets_file))
    assert not secrets_file.exists()


# ---------------------------------------------------------------------------
# p14: get()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
def test_get_metadata_only_no_value(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("X: 'age1enc:" + base64.b64encode(b"ct").decode() + "'\n")
    from ottools.ot_secrets import get as get_secret

    result = get_secret(key="X", file=str(secrets_file))
    assert result == {"found": True, "encrypted": True}
    assert "value" not in result


@pytest.mark.unit
@pytest.mark.tools
def test_get_out_file_writes_0600_no_value_in_result(tmp_path: Path) -> None:
    import json

    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("X: 'age1enc:" + base64.b64encode(b"ct").decode() + "'\n")
    out = tmp_path / "out.txt"
    kr = _make_keyring_mock({("onetool", "age_identity"): "id"})
    pr = _make_pyrage_mock(plaintext=b"the_secret")
    with (
        patch("ottools.ot_secrets._require_keyring", return_value=kr),
        patch("ottools.ot_secrets._require_pyrage", return_value=pr),
    ):
        from ottools.ot_secrets import get as get_secret

        result = get_secret(key="X", file=str(secrets_file), out_file=str(out))
    assert out.read_text() == "the_secret"
    assert (out.stat().st_mode & 0o777) == 0o600
    assert result["written_to"] == str(out)
    assert "the_secret" not in json.dumps(result)


@pytest.mark.unit
@pytest.mark.tools
def test_get_missing_key(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.yaml"
    secrets_file.write_text("X: v\n")
    from ottools.ot_secrets import get as get_secret

    assert get_secret(key="MISSING", file=str(secrets_file)) == {
        "found": False,
        "encrypted": None,
    }


@pytest.mark.unit
@pytest.mark.tools
def test_get_has_no_value_escape_hatch() -> None:
    import inspect

    from ottools.ot_secrets import get as get_secret

    params = inspect.signature(get_secret).parameters
    assert "include_value" not in params
    assert "reveal" not in params
