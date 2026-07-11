# tool-secrets Specification

## Purpose

Provides agent-callable functions for managing age-encrypted secrets in `secrets.yaml`. The `ot_secrets` pack enables setup and management of encrypted secrets entirely through the OneTool agent interface.

## Requirements

### Requirement: Secrets Pack Identity Initialisation

The `ot_secrets` pack SHALL provide an `init()` function that generates an age X25519 identity and stores it in the OS keychain.

#### Scenario: Generate and store new identity
- **WHEN** `ot_secrets.init(label="macbook-gavin")` is called
- **AND** no existing identity is stored in the keychain
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

---

### Requirement: Secrets Pack Encryption

The `ot_secrets` pack SHALL provide an `encrypt()` function that encrypts unencrypted values in-place in a secrets YAML file.

#### Scenario: Encrypt plain values
- **WHEN** `ot_secrets.encrypt(file="~/.onetool/secrets.yaml")` is called
- **AND** the file contains plain-text values
- **AND** an age identity is stored in the keychain
- **THEN** it SHALL encrypt each plain value with the stored public key
- **AND** replace the value in-file with `age1enc:<base64-ciphertext>`
- **AND** leave already-encrypted values (starting with `age1enc:`) untouched
- **AND** return `{"file": str, "backup": str, "encrypted": [...], "skipped": [...], "null_keys": [...], "pubkey_hint": str}`

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

#### Scenario: Backup on encrypt
- **WHEN** `ot_secrets.encrypt(file="...", backup=True)` is called (default)
- **THEN** it SHALL copy the original file to `<file>.bak` before modifying
- **AND** the `backup` field in the return value SHALL be the `.bak` path

#### Scenario: Skip backup
- **WHEN** `ot_secrets.encrypt(file="...", backup=False)` is called
- **THEN** it SHALL NOT create a `.bak` file
- **AND** the `backup` field in the return value SHALL be `null`

#### Scenario: No identity in keychain
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **AND** no identity exists in the keychain
- **THEN** it SHALL return an error with a message pointing to `ot_secrets.init()`

---

### Requirement: Secrets Pack Status

The `ot_secrets` pack SHALL provide a `status()` function reporting the current secrets configuration.

#### Scenario: Identity found, no file
- **WHEN** `ot_secrets.status()` is called
- **AND** an identity is stored in the keychain
- **THEN** it SHALL return `{"identity": "found", "pubkey_hint": "age1ql3z...c8p", "label": str, "file": null, "values": null}`

#### Scenario: Identity found with file
- **WHEN** `ot_secrets.status(file="~/.onetool/secrets.yaml")` is called
- **THEN** it SHALL parse the YAML and count encrypted vs plain values
- **AND** return `{"identity": "found", "pubkey_hint": str, "label": str, "file": str, "values": {"encrypted": [...], "plain": [...], "null_keys": [...]}}`

#### Scenario: File not found
- **WHEN** `ot_secrets.status(file="...")` is called
- **AND** the path does not exist
- **THEN** it SHALL set `file_error` in the result with a "not found" message
- **AND** `file` and `values` SHALL remain `null`

#### Scenario: File is not a YAML mapping
- **WHEN** `ot_secrets.status(file="...")` is called
- **AND** the file exists but `yaml.safe_load` does not return a dict (e.g. empty or comment-only file)
- **THEN** it SHALL set `file_error` in the result indicating the file must be a YAML mapping
- **AND** `file` and `values` SHALL remain `null`

#### Scenario: Invalid YAML in status
- **WHEN** `ot_secrets.status(file="...")` is called
- **AND** the file contains malformed YAML that cannot be parsed
- **THEN** it SHALL set `file_error` in the result with the parse error message
- **AND** `file` and `values` SHALL remain `null`
- **AND** SHALL NOT raise an unhandled exception

#### Scenario: No identity found
- **WHEN** `ot_secrets.status()` is called
- **AND** no identity is stored in the keychain
- **THEN** `identity` SHALL be `"not found"`
- **AND** the response SHALL suggest running `ot_secrets.init()`

---

### Requirement: Secrets Pack Rotation

The `ot_secrets` pack SHALL provide a `rotate()` function that generates a new identity and re-encrypts all encrypted values in-place.

#### Scenario: Successful rotation
- **WHEN** `ot_secrets.rotate(file="~/.onetool/secrets.yaml")` is called
- **AND** an identity exists in the keychain
- **THEN** it SHALL decrypt all `age1enc:` values using the old identity
- **AND** generate a new age X25519 identity
- **AND** re-encrypt each decrypted value with the new public key
- **AND** write the updated file in-place
- **AND** replace all three keychain entries with the new identity
- **AND** return `{"old_pubkey_hint": str, "new_pubkey_hint": str, "file": str, "rotated": [...], "skipped": [...], "status": "rotated"}`

#### Scenario: Key order preserved on rotate
- **WHEN** `ot_secrets.rotate(file="...")` is called
- **THEN** the written YAML file SHALL preserve the original key ordering
- **AND** SHALL NOT sort keys alphabetically

#### Scenario: Backup on rotate
- **WHEN** `ot_secrets.rotate(file="...", backup=True)` is called (default)
- **THEN** it SHALL write `<file>.bak` before modifying

#### Scenario: Plain values untouched during rotation
- **WHEN** rotating a mixed file
- **THEN** plain (non-`age1enc:`) values SHALL be left unchanged
- **AND** those key names SHALL appear in `skipped` in the return value

#### Scenario: Invalid YAML in rotate
- **WHEN** `ot_secrets.rotate(file="...")` is called
- **AND** the file contains malformed YAML that cannot be parsed
- **THEN** it SHALL return `{"error": "<parse error>", "status": "invalid_yaml"}`
- **AND** SHALL NOT raise an unhandled exception

#### Scenario: No identity in keychain
- **WHEN** `ot_secrets.rotate(file="...")` is called
- **AND** no identity exists in the keychain
- **THEN** it SHALL return an error pointing to `ot_secrets.init()`

---

### Requirement: Secrets Pack Audit

The `ot_secrets` pack SHALL provide an `audit()` function that scans a secrets file for unencrypted values.

#### Scenario: All values encrypted
- **WHEN** `ot_secrets.audit(file="~/.onetool/secrets.yaml")` is called
- **AND** all values start with `age1enc:`
- **THEN** it SHALL return `{"file": str, "safe": true, "plain_keys": [], "encrypted_keys": [...]}`

#### Scenario: Plain values detected
- **WHEN** `ot_secrets.audit(file="...")` is called
- **AND** some values are plain text
- **THEN** `safe` SHALL be `false`
- **AND** `plain_keys` SHALL contain the key names of unencrypted values
- **AND** `plain_keys` SHALL NEVER contain the actual plaintext values
- **AND** the response SHALL include a message: `"Run ot_secrets.encrypt() to secure these values before committing."`

#### Scenario: Audit never exposes values
- **WHEN** `ot_secrets.audit(file="...")` is called
- **THEN** the return value SHALL contain only key names, never secret values

#### Scenario: Empty or comment-only file
- **WHEN** `ot_secrets.audit(file="...")` is called
- **AND** the file is syntactically valid YAML but has no top-level mapping (e.g. all comments)
- **THEN** it SHALL return `{"error": "File must be a YAML mapping", "status": "no_mapping"}`

#### Scenario: Invalid YAML in audit
- **WHEN** `ot_secrets.audit(file="...")` is called
- **AND** the file contains malformed YAML that cannot be parsed
- **THEN** it SHALL return `{"error": "<parse error>", "status": "invalid_yaml"}`
- **AND** SHALL NOT raise an unhandled exception

#### Scenario: Null values tracked separately
- **WHEN** `ot_secrets.audit(file="...")` is called
- **AND** the file contains keys with `null` values
- **THEN** those keys SHALL appear in `null_keys`, not in `plain_keys` or `encrypted_keys`
- **AND** the result SHALL always include a `null_keys` list (empty if none)

---

### Requirement: Secrets Pack Key Removal

The `ot_secrets.unset()` function SHALL remove a single key from the secrets file without exposing its value.

#### Scenario: Remove an existing key
- **WHEN** `ot_secrets.unset(key="OLD_KEY")` is called and the key exists
- **THEN** the key SHALL be removed via an atomic write and the result SHALL be `{"removed": true, "key": "OLD_KEY"}`

#### Scenario: Key not present
- **WHEN** `ot_secrets.unset(key="MISSING")` is called and the key does not exist
- **THEN** it SHALL return `{"removed": false, "key": "MISSING", "status": "not_found"}` without modifying the file

---

### Requirement: Secrets Pack Dependency Declaration

The `ot_secrets` pack SHALL declare its runtime library dependencies.

#### Scenario: Dependency declaration
- **WHEN** `ot_secrets.py` is loaded
- **THEN** it SHALL declare `__ot_requires__ = {"lib": [("pyrage", "pip install pyrage"), ("keyring", "pip install keyring")]}`
- **AND** `onetool check` SHALL surface missing packages with the install hint
