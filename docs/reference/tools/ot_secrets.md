# OT Secrets

Age-encrypted secrets management using an identity stored in your OS keychain.

Short alias: `sec`

## Highlights

- Generate and store an age X25519 identity in your OS keychain
- Encrypt plaintext values in `secrets.yaml` in place
- Create an exact mode-`0600` plaintext recovery backup by default
- Audit files for remaining plaintext secrets

## Functions

| Function | Description |
|----------|-------------|
| `ot_secrets.init(label)` | Create/store a keypair when no identity exists |
| `ot_secrets.set(key, value, file)` | Encrypt and store a single value in place (round-trip verified) |
| `ot_secrets.get(key, file, out_file)` | Report a key's existence/encryption; write the value to a `0600` `out_file` only (never returned) |
| `ot_secrets.encrypt(file, backup)` | Encrypt plaintext values in a secrets YAML file |
| `ot_secrets.status(file)` | Show identity status and encrypted/plain counts |
| `ot_secrets.audit(file)` | Report plaintext vs encrypted keys in a secrets file |

`file` defaults to the configured secrets path (the loaded `--secrets` file, else `<config dir>/secrets.yaml`) for `set`, `get`, `encrypt`, `status`, and `audit`.

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | str | Path to secrets YAML file (defaults to the configured secrets path) |
| `label` | str | Human-readable key label for keychain identity |
| `backup` | bool | Create an exact plaintext `.bak` recovery backup at mode `0600` before modifying the file (default: `True`) |

## Requires

- OS keychain support (macOS Keychain, Windows Credential Locker, or compatible Linux keyring)
- Python packages: `pyrage` (age encryption) and `keyring` (OS keychain access) — both are core dependencies, no extra required

## Configuration

### Required

- No required `tools.ot_secrets` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.ot_secrets`.

### Defaults

- OneTool uses the built-in defaults for OS keychain integration and encrypted value handling.

## Examples

```python
# 1) Create key identity (once per machine)
ot_secrets.init(label="work-mac")

# 2) Encrypt a secrets file in place
ot_secrets.encrypt(file="~/.onetool/secrets.yaml")

# 3) Check identity and file status
ot_secrets.status(file="~/.onetool/secrets.yaml")

# 4) Audit a file for plaintext values
ot_secrets.audit(file="~/.onetool/secrets.yaml")
```

## Notes

- Values prefixed with `age1enc:` are treated as encrypted.
- Every non-null plaintext value is encrypted by `encrypt()`.
- Decryption occurs in memory when OneTool loads secrets.
- The default `.bak` file is intentionally plaintext for recovery. Keep it
  private and out of version control; pass `backup=False` only when accepting
  the loss of that recovery copy.
- The original OS-keychain identity is required to decrypt existing ciphertext.
  `init()` never replaces identity state, and v3 provides no replacement path.
