# OT Secrets

Age-encrypted secrets management using an identity stored in your OS keychain.

Short alias: `sec`

## Highlights

- Generate and store an age X25519 identity in your OS keychain
- Encrypt plaintext values in `secrets.yaml` in place
- Rotate to a new identity and re-encrypt all values
- Audit files for remaining plaintext secrets

## Functions

| Function | Description |
|----------|-------------|
| `ot_secrets.init(label, force)` | Create/store keypair in OS keychain |
| `ot_secrets.set(key, value, file)` | Encrypt and store a single value in place (round-trip verified) |
| `ot_secrets.get(key, file, out_file)` | Report a key's existence/encryption; write the value to a `0600` `out_file` only (never returned) |
| `ot_secrets.encrypt(file, backup)` | Encrypt plaintext values in a secrets YAML file |
| `ot_secrets.status(file)` | Show identity status and encrypted/plain counts |
| `ot_secrets.rotate(file, backup)` | Generate new keypair and re-encrypt encrypted values |
| `ot_secrets.audit(file)` | Report plaintext vs encrypted keys in a secrets file |

`file` defaults to the configured secrets path (the loaded `--secrets` file, else `<config dir>/secrets.yaml`) for `set`, `get`, `encrypt`, `status`, `rotate`, and `audit`.

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | str | Path to secrets YAML file (defaults to the configured secrets path) |
| `label` | str | Human-readable key label for keychain identity |
| `backup` | bool | Create a plaintext `.bak` backup (mode `0600`) before modifying file (default: `False`) |
| `force` | bool | Overwrite existing keychain identity when initializing |

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

# 4) Rotate to a new key and re-encrypt values
ot_secrets.rotate(file="~/.onetool/secrets.yaml")

# 5) Audit a file for plaintext values
ot_secrets.audit(file="~/.onetool/secrets.yaml")
```

## Notes

- Values prefixed with `age1enc:` are treated as encrypted.
- Plain and encrypted values can coexist in the same file.
- Decryption occurs in memory when OneTool loads secrets.
