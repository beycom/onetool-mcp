---
name: ot-secrets
description: Use when initializing OneTool's age identity, encrypting or auditing secrets, adding a secret, checking encryption status, rotating identity, or writing a decrypted value to a protected file. Never return secret plaintext in conversation.
user-invocable: false
---

# OneTool Secrets

Use `ot_secrets` for age-encrypted OneTool secrets backed by the OS keychain.

## Capability boundary

Check `__ot ot.packs(pattern='ot_secrets', info='min')`. If the pack, `age`, identity, or keychain
support is missing, stop and offer installation or configuration guidance; never install,
initialize, or add credentials without a separate explicit request.

Use the exact lifecycle: `status`/`audit` inspect, `init` creates the age identity, `set`/`unset`
mutate named values, `encrypt` protects plaintext storage, `get` retrieves only for an explicitly
authorized sink, and `rotate` changes identity/encryption. Inspect live signatures before any
mutation because force and backup behavior are consequential.

## Workflow

1. Inspect status and audit before mutation.
2. Confirm the effective secrets path, backend/keyring readiness, requested name, and desired
   lifecycle operation.
3. Initialize or rotate an identity only with explicit approval; preserve/review backup behavior.
4. Set, unset, or encrypt only the requested value without echoing plaintext.
5. Verify status/audit and a presence-based round trip without returning the secret.

## Safety and side effects

Secret mutation writes encrypted storage and keyring state. `force`, overwrite, plaintext backup,
rotation, and protected-output retrieval are high impact. Never print or include decrypted values
in logs, chat, tests, diffs, or error messages. Standalone `otpack` mode does not provide the full
encrypted secret backend.

## Verification and recovery

Run `status` and `audit`, confirm only secret names and set/encrypted state, and verify the intended
backend. If keyring or age access fails, stop and hand the exact host prerequisite to `ot-setup`;
never auto-reinitialize or rotate as recovery.

<!-- BEGIN GENERATED:CATALOG_COVERAGE -->
## Catalog coverage

**Role:** `capability-owner`

| Pack | Extra | Help topics | Docs |
|---|---|---|---|
| `ot_secrets` | `core` | `overview`, `workflow`, `setup`, `config` | [reference](https://onetool.beycom.online/reference/tools/ot_secrets/) |

For a missing pack, dependency, secret, or config field, inspect `ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.
<!-- END GENERATED:CATALOG_COVERAGE -->
