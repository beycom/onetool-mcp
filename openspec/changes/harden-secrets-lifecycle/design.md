## Context

One global age identity protects every secrets file. The current replacement
operations (`init(force=True)` and `rotate()`) treat that global identity as if it
belonged to one selected file, so either operation can orphan ciphertext
elsewhere. Encryption also trusts partial keychain state and creates its optional
backup with a copy-then-chmod sequence. Guided setup writes entered plaintext to
the target before identity and encryption have succeeded.

The implementation must preserve exact prior file bytes on every failure, never
persist newly entered plaintext except in the intentional final recovery backup,
and expose no compatibility path for removed identity replacement.

## Goals / Non-Goals

**Goals:**

- Make one non-replaceable global identity the v3 lifecycle model.
- Validate both stored identity halves for parsing, equality, and an operational
  encrypt/decrypt round trip before any encryption-side mutation.
- Commit a secure exact recovery backup before replacing a target, with rollback
  of the backup if target replacement fails.
- Make guided setup transactional across identity reuse, encryption, audit,
  backup, and target replacement.

**Non-Goals:**

- Designing multi-file key rotation or automated identity recovery.
- Retaining aliases, stubs, flags, or migration branches for removed operations.
- Changing the ciphertext marker or YAML data model.

## Decisions

### Delete every in-process identity replacement path

`init()` retains only first-time creation and refuses whenever a private or
public identity entry already exists. `rotate()` is deleted from implementation,
exports, discovery, tests, current specs, and current references. This is safer
than trying to order global keyring and file writes because a file-scoped
operation cannot atomically account for every file protected by the global key.

### Centralize coherent-identity validation

A shared internal validator reads both keychain entries, parses both values,
compares the private identity's derived recipient with the stored recipient, and
round-trips fixed representative bytes. It returns a clear error result for
missing, malformed, mismatched, or unusable state. Public encryption invokes it
before reading or mutating the target or backup.

Comparing only strings without the operational round trip was rejected because
it would not detect a broken encryption/decryption implementation. Checking only
entry presence was rejected because it preserves the current data-loss path.

### Use secure atomic byte writes

A common writer creates a sibling temporary file, applies mode `0600` to the
open descriptor before writing any bytes, flushes and fsyncs, and replaces the
destination atomically. YAML writes serialize in memory before invoking this
writer. This removes the permissive copy-then-chmod window and keeps failed
serialization away from the filesystem.

### Treat backup and target as one recoverable transaction

Encryption captures the target's exact source bytes, prepares and verifies all
ciphertext in memory, then atomically installs the exact bytes at `<file>.bak`
before atomically replacing the target. If target replacement fails after the
backup commit, the previous backup is restored byte-for-byte or the newly
created backup is removed. Explicit `backup=False` bypasses only the recovery
artifact, not validation or ciphertext verification.

### Keep guided plaintext in memory

The guided flow collects values without writing them. After confirmation and
identity creation/reuse, shared encryption preparation produces an encrypted
mapping in memory and writes only ciphertext to a secure sibling staging file.
The public `encrypt(..., backup=False)` and `audit()` paths validate that staged
artifact; their error dictionaries and exceptions are failures. The final
transaction installs a deterministic plaintext recovery serialization at
`<file>.bak` and the verified encrypted stage at the target, then removes the
stage. Cancellation, declined reuse, or any failure occurs before the final pair
commit and preserves the prior target and backup exactly.

An encrypted staging file is used because the existing public audit API is
file-based. A plaintext staging file was rejected because it violates the
security invariant.

## Risks / Trade-offs

- [A successful default operation intentionally leaves plaintext in `.bak`] →
  create it at `0600`, document the recovery/security trade-off, and allow
  explicit backup opt-out for direct encryption.
- [Two filesystem paths cannot be committed with one operating-system rename] →
  commit backup first, preserve its prior state, and roll it back if the target
  replacement fails.
- [A process crash between backup and target replacement can leave a new backup
  beside the old target] → both contain the same recoverable plaintext for
  direct encryption; guided setup writes the backup securely first, and normal
  exception paths remain fully transactional.
- [Existing callers may depend on replacement operations] → fail through normal
  signature/discovery behavior; provide no compatibility shim.

## Migration Plan

1. Strictly validate this change before implementation.
2. Remove replacement interfaces and update current contract artifacts.
3. Introduce coherent identity validation and transactional secure writes.
4. Convert guided setup to in-memory encryption plus encrypted staging.
5. Regenerate references and indexes, then verify focused and repository-wide
   checks.

Rollback is the normal version-control rollback. Users must retain the original
identity for any existing ciphertext; deleting it is not a safe migration.

## Open Questions

None.
