## MODIFIED Requirements

### Requirement: Secrets Pack Identity Initialisation

The `ot_secrets` pack SHALL provide an `init()` function that generates an age
X25519 identity and stores it in the OS keychain only when no identity state
already exists.

#### Scenario: Generate and store new identity
- **WHEN** `ot_secrets.init(label="macbook-gavin")` is called
- **AND** no private or public identity is stored in the keychain
- **THEN** it SHALL generate a new age X25519 identity via `pyrage`
- **AND** store the private key string at keychain service `"onetool"`, key `"age_identity"`
- **AND** store the public key string at keychain service `"onetool"`, key `"age_pubkey"`
- **AND** store the label at keychain service `"onetool"`, key `"age_label"`
- **AND** return `{"pubkey": "age1...", "label": "macbook-gavin", "status": "stored"}`

#### Scenario: Any identity state already exists
- **WHEN** `ot_secrets.init()` is called
- **AND** a private or public identity entry already exists in the keychain
- **THEN** it SHALL return an error indicating the identity already exists
- **AND** it SHALL NOT generate or overwrite any identity or label entry
- **AND** no public force or replacement parameter SHALL exist

#### Scenario: Default label
- **WHEN** `ot_secrets.init()` is called with no `label` argument
- **THEN** the stored label SHALL be an empty string
- **AND** the function SHALL succeed normally when no identity state exists

### Requirement: Secrets Pack Encryption

The `ot_secrets` pack SHALL provide an `encrypt()` function that verifies the
stored identity and encrypts every non-null, unencrypted value in place in a
secrets YAML file.

#### Scenario: Encrypt plain values with a coherent identity
- **WHEN** `ot_secrets.encrypt(file="~/.onetool/secrets.yaml")` is called
- **AND** the file contains plain-text values
- **AND** matching private and public age identity entries are stored
- **AND** the entries parse and pass a representative encrypt/decrypt round trip
- **THEN** it SHALL encrypt every non-null value not starting with `age1enc:` using the stored public key
- **AND** verify every new ciphertext with the stored private identity
- **AND** replace each value with `age1enc:<base64-ciphertext>`
- **AND** leave already-encrypted values untouched
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
- **THEN** those keys SHALL be skipped
- **AND** appear in `null_keys`, not in `encrypted` or `skipped`

#### Scenario: Invalid YAML in encrypt
- **WHEN** `ot_secrets.encrypt(file="...")` is called with a coherent identity
- **AND** the file contains malformed YAML that cannot be parsed
- **THEN** it SHALL return `{"error": "<parse error>", "status": "invalid_yaml"}`
- **AND** SHALL NOT raise an unhandled exception
- **AND** SHALL NOT change the target or backup

#### Scenario: Mixed encrypted and plain values
- **WHEN** a secrets file contains a mix of `age1enc:`, plain, and null values
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **THEN** it SHALL encrypt every plain non-null value
- **AND** leave `age1enc:` and null values untouched

#### Scenario: Secure exact backup by default
- **WHEN** `ot_secrets.encrypt(file="...")` is called without a `backup` argument
- **THEN** it SHALL atomically create or replace `<file>.bak` at mode `0600` before target replacement
- **AND** the backup SHALL contain the exact pre-encryption target bytes
- **AND** the `backup` response field SHALL contain the backup path
- **AND** backup creation, permission, or replacement failure SHALL leave the target byte-identical and prevent target replacement

#### Scenario: Explicitly skip backup
- **WHEN** `ot_secrets.encrypt(file="...", backup=False)` is called
- **THEN** it SHALL NOT create or replace a `.bak` file
- **AND** the `backup` response field SHALL be `null`

#### Scenario: Incomplete or invalid identity
- **WHEN** `ot_secrets.encrypt(file="...")` is called
- **AND** either identity entry is missing, either entry is malformed, the pair does not match, or representative decryption fails
- **THEN** it SHALL return a clear identity inconsistency error
- **AND** it SHALL do so before backup, encryption, or target mutation
- **AND** target bytes and metadata SHALL remain exact
- **AND** no new backup SHALL be created

#### Scenario: Ciphertext verification failure
- **WHEN** encryption of any value cannot be decrypted exactly with the stored private identity
- **THEN** it SHALL return a verification error
- **AND** it SHALL NOT replace the target or backup

## REMOVED Requirements

### Requirement: Secrets Pack Rotation

**Reason**: A file-scoped operation cannot safely replace the one global identity
that may protect other secrets files, and interruption can orphan ciphertext.

**Migration**: Continue using the original initialized identity for existing
ciphertext. V3 provides no in-process identity replacement or rotation path.
