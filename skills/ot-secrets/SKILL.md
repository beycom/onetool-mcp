---
name: ot-secrets
description: Use when initializing OneTool's age identity, encrypting or auditing secrets, adding a secret, checking encryption status, rotating identity, or writing a decrypted value to a protected file. Never return secret plaintext in conversation.
user-invocable: false
---

# OneTool Secrets

Use `ot_secrets` for age-encrypted OneTool secrets backed by the OS keychain.

## Availability

Check `__ot ot.packs(pattern='ot_secrets', info='min')`. If the pack, `age`, identity, or keychain
support is missing, stop and offer installation or configuration guidance; never install,
initialize, or add credentials without a separate explicit request.

## Workflow

1. Inspect status and audit before mutation.
2. Initialize an identity only with explicit intent.
3. Set or encrypt the requested value without echoing plaintext.
4. Verify status and audit after mutation.
5. Retrieve plaintext only to an explicitly requested protected file.

Treat force, rotation, overwrite, and plaintext backups as high impact. Confirm the effective
secrets path and never force reinitialization as automatic recovery.
