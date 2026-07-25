## Why

The secrets lifecycle can currently strand ciphertext by replacing its identity,
accept incomplete or mismatched key material, and expose plaintext during guided
setup or backup creation. These data-loss and disclosure paths must be removed
before the v3 release.

## What Changes

- **BREAKING** Remove `ot_secrets.rotate()` and remove the `force` parameter from
  `ot_secrets.init()` so an existing identity can never be replaced through the
  public secrets pack.
- Require a complete, parseable, matching, and operational private/public
  identity before `ot_secrets.encrypt()` mutates a secrets file or its backup.
- Make encryption backups secure, exact, transactional, and enabled by default;
  retain explicit backup opt-out.
- Keep guided secret values in memory until they are encrypted, preserve the
  original target and backup on cancellation or failure, and require explicit
  reuse of an existing identity.
- Align current specifications, generated references, tool inventories, and
  recovery guidance with the smaller and safer public contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ottools/tool-secrets`: Remove identity replacement and rotation, and define
  coherent-identity validation plus secure transactional encryption backups.
- `onetool-cli`: Define cancellation, identity-reuse, failure, and commit
  guarantees for guided encrypted-secrets setup.

## Impact

Affected surfaces include `src/ottools/ot_secrets.py`, the guided initialization
flow in `src/onetool/cli.py`, secrets tests, current OpenSpec requirements,
generated tool references and indexes, tool-count assertions, and recovery
documentation. Existing callers of `rotate()` or `init(force=True)` must stop
using those removed interfaces.
