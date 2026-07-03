## MODIFIED Requirements

### Requirement: Secrets Pack Identity Initialisation

The `ot_secrets` pack SHALL provide an `init()` function that generates an age X25519 identity and
stores it in the OS keychain, and SHALL refuse to store it in an insecure keyring backend.

#### Scenario: Generate and store new identity
- **WHEN** `ot_secrets.init(label="macbook-gavin")` is called
- **AND** no existing identity is stored in the keychain
- **AND** the resolved keyring backend is on the secure allow-list
- **THEN** it SHALL generate a new age X25519 identity via `pyrage`
- **AND** store the private key string at keychain service `"onetool"`, key `"age_identity"`
- **AND** store the public key string at keychain service `"onetool"`, key `"age_pubkey"`
- **AND** store the label at keychain service `"onetool"`, key `"age_label"`
- **AND** return `{"pubkey": "age1...", "label": "macbook-gavin", "status": "stored"}`

#### Scenario: Identity already exists
- **WHEN** `ot_secrets.init()` is called
- **AND** an identity already exists in the keychain
- **THEN** it SHALL return an error indicating the identity already exists
- **AND** it SHALL NOT overwrite the existing identity
- **AND** it SHALL instruct the caller to pass `force=True` to overwrite

#### Scenario: Force overwrite
- **WHEN** `ot_secrets.init(force=True)` is called
- **AND** an identity already exists in the keychain
- **THEN** it SHALL overwrite all three keychain entries with a freshly generated identity
- **AND** return `{"pubkey": "age1...", "label": "", "status": "stored"}`

#### Scenario: Default label
- **WHEN** `ot_secrets.init()` is called with no `label` argument
- **THEN** the stored label SHALL be an empty string
- **AND** the function SHALL succeed normally

#### Scenario: Insecure keyring backend rejected at init
- **WHEN** `ot_secrets.init()` is called
- **AND** `keyring.get_keyring()` resolves to a backend that is not on the secure allow-list
  (e.g. `keyring.backends.fail.Keyring`, `keyring.backends.null.Keyring`,
  `keyring.backends.chainer.ChainerBackend`, or any third-party `keyrings.alt` backend)
- **THEN** `init()` SHALL raise/return an error naming the detected backend's fully-qualified
  class name
- **AND** it SHALL NOT call `keyring.set_password` for any of the three identity entries
- **AND** the error SHALL instruct the caller to configure a secure OS keychain

---

### Requirement: Secrets Pack Encryption

The `ot_secrets` pack SHALL provide an `encrypt()` function that encrypts unencrypted values
in-place in a secrets YAML file, atomically, at `0600` permissions, without defaulting to a
persistent plaintext backup.

#### Scenario: Encrypt plain values
- **WHEN** `ot_secrets.encrypt(file="~/.onetool/secrets.yaml")` is called
- **AND** the file contains plain-text values
- **AND** an age identity is stored in the keychain in a secure backend
- **THEN** it SHALL encrypt each plain value with the stored public key
- **AND** replace the value in-file with `age1enc:<base64-ciphertext>`
- **AND** leave already-encrypted values (starting with `age1enc:`) untouched
- **AND** return `{"file": str, "backup": str | null, "encrypted": [...], "skipped": [...], "null_keys": [...], "pubkey_hint": str}`

#### Scenario: Key order preserved on encrypt
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **THEN** the written YAML file SHALL preserve the original key ordering
- **AND** SHALL NOT sort keys alphabetically

#### Scenario: Idempotent on already-encrypted values
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **AND** all values already start with `age1enc:`
- **THEN** it SHALL skip all values
- **AND** return `{"encrypted": [], "skipped": ["KEY1", ...], "null_keys": []}`

#### Scenario: Null values skipped and reported
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **AND** the file contains keys with `null` values
- **THEN** those keys SHALL be skipped (nothing to encrypt)
- **AND** appear in `null_keys` in the return value, not in `encrypted` or `skipped`

#### Scenario: Invalid YAML in encrypt
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **AND** the file contains malformed YAML that cannot be parsed
- **THEN** it SHALL return `{"error": "<parse error>", "status": "invalid_yaml"}`
- **AND** SHALL NOT raise an unhandled exception

#### Scenario: Mixed encrypted and plain values
- **WHEN** a secrets file contains a mix of `age1enc:` and plain values
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **THEN** it SHALL encrypt only the plain values
- **AND** leave `age1enc:` values untouched
- **AND** leave intentional non-secret plain values (non-API-key strings) untouched if already present alongside encrypted values

#### Scenario: Backup default is off
- **WHEN** `ot_secrets.encrypt(file="...")` is called with no explicit `backup` argument
- **THEN** the default `backup` value SHALL be `False`
- **AND** it SHALL NOT create a `<file>.bak` plaintext copy
- **AND** the `backup` field in the return value SHALL be `null`

#### Scenario: Explicit backup at 0600
- **WHEN** `ot_secrets.encrypt(file="...", backup=True)` is called
- **THEN** it SHALL copy the original file to `<file>.bak` before modifying
- **AND** the `.bak` file SHALL be `chmod`'d to `0600`
- **AND** the `backup` field in the return value SHALL be the `.bak` path

#### Scenario: Atomic write
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **THEN** the updated YAML SHALL be written to a temp file in the same directory and then moved
  into place via `os.replace()` (or equivalent atomic rename)
- **AND** if an error occurs before the rename, the original `secrets.yaml` SHALL be left
  unmodified and the temp file SHALL be removed

#### Scenario: 0600 enforced on write
- **WHEN** `ot_secrets.encrypt(file="...")` completes a successful write
- **THEN** the resulting `secrets.yaml` file mode SHALL be `0600` regardless of the process umask

#### Scenario: No identity in keychain
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **AND** no identity exists in the keychain
- **THEN** it SHALL return an error with a message pointing to `ot_secrets.init()`

#### Scenario: Insecure keyring backend rejected before write
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **AND** `keyring.get_keyring()` resolves to a backend not on the secure allow-list
- **THEN** it SHALL return/raise an error naming the detected backend
- **AND** it SHALL NOT read the public key or modify the secrets file

---

### Requirement: Secrets Pack Rotation

The `ot_secrets` pack SHALL provide a `rotate()` function that generates a new identity and
re-encrypts all encrypted values in-place, atomically, verifying every value round-trips under
the new identity before the new identity replaces the old one in the keychain.

#### Scenario: Successful rotation
- **WHEN** `ot_secrets.rotate(file="~/.onetool/secrets.yaml")` is called
- **AND** an identity exists in the keychain in a secure backend
- **THEN** it SHALL decrypt all `age1enc:` values using the old identity
- **AND** generate a new age X25519 identity
- **AND** re-encrypt each decrypted value with the new public key
- **AND** verify each new ciphertext decrypts back to the original plaintext under the new
  identity before writing anything to disk
- **AND** write the updated file in-place atomically
- **AND**, only after the atomic file write succeeds, replace all three keychain entries with the
  new identity
- **AND** return `{"old_pubkey_hint": str, "new_pubkey_hint": str, "file": str, "backup": str | null, "rotated": [...], "skipped": [...], "status": "rotated"}`

#### Scenario: Key order preserved on rotate
- **WHEN** `ot_secrets.rotate(file="...")` is called
- **THEN** the written YAML file SHALL preserve the original key ordering
- **AND** SHALL NOT sort keys alphabetically

#### Scenario: Backup default is off
- **WHEN** `ot_secrets.rotate(file="...")` is called with no explicit `backup` argument
- **THEN** the default `backup` value SHALL be `False`
- **AND** it SHALL NOT create a `<file>.bak` plaintext copy

#### Scenario: Explicit backup at 0600
- **WHEN** `ot_secrets.rotate(file="...", backup=True)` is called
- **THEN** it SHALL write `<file>.bak` before modifying
- **AND** the `.bak` file SHALL be `chmod`'d to `0600`

#### Scenario: Plain values untouched during rotation
- **WHEN** rotating a mixed file
- **THEN** plain (non-`age1enc:`) values SHALL be left unchanged
- **AND** those key names SHALL appear in `skipped` in the return value

#### Scenario: Atomic write and crash-safe ordering
- **WHEN** `ot_secrets.rotate(file="...")` is called
- **THEN** the new-key-ciphertext file SHALL be written to a temp file and moved into place via
  `os.replace()` before any keychain entry is modified
- **AND** if the process crashes or raises after the atomic file write but before the keychain
  update, re-running `rotate()` SHALL fail with a clear decrypt-mismatch error (not silent data
  loss) because the file now holds new-key ciphertext while the keychain still holds the old
  identity
- **AND** if the process crashes or raises before the atomic file write completes, the original
  `secrets.yaml` and the original keychain identity SHALL both remain intact and usable

#### Scenario: 0600 enforced on write
- **WHEN** `ot_secrets.rotate(file="...")` completes a successful write
- **THEN** the resulting `secrets.yaml` file mode SHALL be `0600` regardless of the process umask

#### Scenario: Invalid YAML in rotate
- **WHEN** `ot_secrets.rotate(file="...")` is called
- **AND** the file contains malformed YAML that cannot be parsed
- **THEN** it SHALL return `{"error": "<parse error>", "status": "invalid_yaml"}`
- **AND** SHALL NOT raise an unhandled exception

#### Scenario: No identity in keychain
- **WHEN** `ot_secrets.rotate(file="...")` is called
- **AND** no identity exists in the keychain
- **THEN** it SHALL return an error pointing to `ot_secrets.init()`

#### Scenario: Insecure keyring backend rejected before rotation
- **WHEN** `ot_secrets.rotate(file="...")` is called
- **AND** `keyring.get_keyring()` resolves to a backend not on the secure allow-list
- **THEN** it SHALL return/raise an error naming the detected backend
- **AND** it SHALL NOT read the existing identity or modify the secrets file or keychain

#### Scenario: Strict base64 decoding
- **WHEN** `ot_secrets.rotate(file="...")` decodes an `age1enc:`-prefixed value's base64 payload
- **THEN** it SHALL decode using `base64.b64decode(..., validate=True)`
- **AND** malformed base64 SHALL raise a clear decode error rather than being silently accepted

---

## ADDED Requirements

### Requirement: Secrets Pack Keyring Backend Validation

The `ot_secrets` pack SHALL validate that the resolved OS keyring backend is on an explicit
allow-list of secure backends before performing any keychain read or write, and SHALL reject
(fail loudly, naming the detected backend) any backend not on the allow-list.

#### Scenario: Secure backend allow-list
- **GIVEN** the resolved backend's fully-qualified class name (`module.Qualname`)
- **THEN** the allow-list SHALL include at least: `keyring.backends.macOS.Keyring`,
  `keyring.backends.Windows.WinVaultKeyring`, `keyring.backends.SecretService.Keyring`,
  `keyring.backends.libsecret.Keyring`, `keyring.backends.kwallet.DBusKeyring`,
  `keyring.backends.kwallet.DBusKeyringKWallet4`

#### Scenario: Validation runs before every keychain touch
- **WHEN** any `ot_secrets` operation is about to call `keyring.get_password` or
  `keyring.set_password`
- **THEN** the backend validation SHALL run first
- **AND** if validation fails, no keychain call SHALL be made

#### Scenario: Unknown or third-party backend rejected
- **WHEN** `keyring.get_keyring()` resolves to a backend whose fully-qualified class name is not
  on the allow-list (including `keyring.backends.fail.Keyring`, `keyring.backends.null.Keyring`,
  `keyring.backends.chainer.ChainerBackend`, or any `keyrings.alt.*` backend)
- **THEN** validation SHALL fail with an error naming the exact fully-qualified class name found
- **AND** the error SHALL instruct the caller to configure a secure OS keychain provider

---

### Requirement: Secrets Pack File Path Default Resolution

The `ot_secrets` pack's file-taking operations (`encrypt`, `status`, `rotate`, `audit`, `set`,
`get`) SHALL accept an optional `file` parameter that, when omitted, resolves to the configured
secrets path rather than requiring the caller to know the path.

#### Scenario: Explicit file wins
- **WHEN** any file-taking `ot_secrets` operation is called with an explicit `file=` argument
- **THEN** that path SHALL be used, expanded via `~` expansion

#### Scenario: Falls back to the loaded --secrets path
- **WHEN** a file-taking `ot_secrets` operation is called with `file=None` (or omitted)
- **AND** the running server was started with `--secrets <path>`
- **THEN** it SHALL resolve `file` to that loaded secrets path

#### Scenario: Falls back to the config-dir default
- **WHEN** a file-taking `ot_secrets` operation is called with `file=None` (or omitted)
- **AND** no `--secrets` path was loaded for the running server
- **THEN** it SHALL resolve `file` to `<config dir>/secrets.yaml` (the config directory returned
  by `get_config_dir()`)

---

### Requirement: Secrets Pack Single-Value Set

The `ot_secrets` pack SHALL provide a `set(key, value, file=None)` function that encrypts and
writes a single secret value in place, with round-trip verification, without ever leaving the
plaintext value written to disk unencrypted (when an identity is available).

#### Scenario: Set a new value with an identity present
- **WHEN** `ot_secrets.set(key="BRAVE_API_KEY", value="abc123")` is called
- **AND** an age identity exists in the keychain in a secure backend
- **THEN** it SHALL encrypt `"abc123"` with the stored public key
- **AND** verify the resulting ciphertext decrypts back to `"abc123"` under the same identity
  before writing
- **AND** write `age1enc:<ciphertext>` for key `BRAVE_API_KEY` into the resolved secrets file
- **AND** return a result that does NOT contain the plaintext value `"abc123"` anywhere
- **AND** the write SHALL be atomic and the resulting file mode SHALL be `0600`

#### Scenario: Overwrite an existing key
- **WHEN** `ot_secrets.set(key="BRAVE_API_KEY", value="new-value")` is called
- **AND** `BRAVE_API_KEY` already has a value (plain or `age1enc:`) in the file
- **THEN** the existing value SHALL be replaced with the newly encrypted value
- **AND** all other keys in the file SHALL be left unchanged
- **AND** key ordering SHALL be preserved (new keys appended, existing keys stay in place)

#### Scenario: No identity present
- **WHEN** `ot_secrets.set(key="X", value="y")` is called
- **AND** no age identity exists in the keychain
- **THEN** it SHALL store the plain value
- **AND** the result SHALL include a `warning` field recommending `ot_secrets.init()` followed by
  `ot_secrets.encrypt()`

#### Scenario: Insecure keyring backend rejected before set
- **WHEN** `ot_secrets.set(key="X", value="y")` is called
- **AND** `keyring.get_keyring()` resolves to a backend not on the secure allow-list
- **THEN** it SHALL return/raise an error naming the detected backend
- **AND** it SHALL NOT write the value to the secrets file

#### Scenario: File defaults per the resolution requirement
- **WHEN** `ot_secrets.set(key="X", value="y")` is called with no `file=` argument
- **THEN** the file path SHALL be resolved per the "Secrets Pack File Path Default Resolution"
  requirement

---

### Requirement: Secrets Pack Single-Value Get (No Plaintext Leak)

The `ot_secrets` pack SHALL provide a `get(key, file=None, out_file=None)` function that reports
whether a key exists and whether it is encrypted, and SHALL NEVER include the plaintext (or
ciphertext) value in its return value.

#### Scenario: Get without out_file returns metadata only
- **WHEN** `ot_secrets.get(key="BRAVE_API_KEY")` is called
- **AND** `BRAVE_API_KEY` exists in the resolved secrets file
- **THEN** it SHALL return `{"found": true, "encrypted": bool}` (plus standard `file`/`status`
  fields as used by other ops)
- **AND** the return value SHALL NOT contain a `value` key or the secret's plaintext/ciphertext
  anywhere in the structure

#### Scenario: Get with out_file writes the decrypted value to a file
- **WHEN** `ot_secrets.get(key="BRAVE_API_KEY", out_file="/tmp/secret.txt")` is called
- **AND** `BRAVE_API_KEY` exists and is `age1enc:`-encrypted
- **AND** an age identity exists in the keychain in a secure backend
- **THEN** it SHALL decrypt the value and write it to `/tmp/secret.txt`
- **AND** `chmod` that file to `0600`
- **AND** return `{"found": true, "encrypted": true, "written_to": "/tmp/secret.txt"}`
- **AND** the return value SHALL still NOT contain the plaintext value

#### Scenario: Key not found
- **WHEN** `ot_secrets.get(key="MISSING_KEY")` is called
- **AND** `MISSING_KEY` is not present in the resolved secrets file
- **THEN** it SHALL return `{"found": false, "encrypted": null}` (or equivalent) with no error
  raised for the not-found case

#### Scenario: No escape hatch for including the value in the result
- **GIVEN** any combination of arguments to `ot_secrets.get(...)`
- **THEN** there SHALL NOT exist a parameter that causes the plaintext or ciphertext value to
  appear in the function's return value

---

### Requirement: Secrets Decryption Robustness And Guidance

The transparent decrypt path in `src/ot/config/secrets.py` SHALL decode base64 strictly and SHALL
use guidance text identical to the `ot_secrets` pack's own "no identity" error text.

#### Scenario: Strict base64 decoding on load
- **WHEN** `load_secrets()` decrypts an `age1enc:`-prefixed value
- **THEN** it SHALL decode the base64 payload using `base64.b64decode(..., validate=True)`
- **AND** malformed base64 SHALL raise a clear error rather than being silently accepted

#### Scenario: Consistent "no identity" guidance
- **WHEN** `load_secrets()` finds `age1enc:`-prefixed values but no private key in the keychain
- **AND** `ot_secrets.encrypt()`/`ot_secrets.rotate()` are called with no identity in the keychain
- **THEN** both error messages SHALL use identical canonical guidance text pointing to
  `ot_secrets.init()` as the fix

---

### Requirement: Missing-Secret Error Guidance

The shared `otpack.http` helpers used by key-gated tool packs SHALL, when a required secret is
not configured, name both the missing secret and where/how to set it.

#### Scenario: api_headers names the secret and the setup path
- **WHEN** `otpack.http.api_headers(secret_name="BRAVE_API_KEY")` is called
- **AND** `BRAVE_API_KEY` is not configured
- **THEN** the raised `ValueError`'s message SHALL name `BRAVE_API_KEY`
- **AND** SHALL name at least one concrete setup path (`secrets.yaml`, `ot_secrets.set()`, or the
  guided `onetool init` secrets step)

#### Scenario: require_api_key names the secret and the setup path
- **WHEN** `otpack.http.require_api_key(secret_name="BRAVE_API_KEY")` is called
- **AND** `BRAVE_API_KEY` is not configured
- **THEN** the returned error message SHALL name `BRAVE_API_KEY`
- **AND** SHALL name at least one concrete setup path (`secrets.yaml`, `ot_secrets.set()`, or the
  guided `onetool init` secrets step)

#### Scenario: check_api_key names the secret and the setup path
- **WHEN** `otpack.http.check_api_key(secret_name="BRAVE_API_KEY")` is called
- **AND** `BRAVE_API_KEY` is not configured
- **THEN** the returned error message SHALL name `BRAVE_API_KEY`
- **AND** SHALL name at least one concrete setup path (`secrets.yaml`, `ot_secrets.set()`, or the
  guided `onetool init` secrets step)

---

### Requirement: Secrets Pack Dependency Documentation

The `ot_secrets` pack's reference documentation SHALL list its runtime library dependencies.

#### Scenario: Requires section lists pyrage and keyring
- **GIVEN** `docs/reference/tools/ot_secrets.md`
- **WHEN** its "Requires" section is read
- **THEN** it SHALL list `pyrage` and `keyring` as Python package dependencies, alongside the
  existing OS keychain support note
