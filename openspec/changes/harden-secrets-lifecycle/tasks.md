## 1. Secrets Lifecycle Contract

- [x] 1.1 Remove forced initialization and rotation from implementation, exports, current specs, tests, references, and discovery inventories.
- [x] 1.2 Add coherent private/public identity validation before every encryption-side mutation.
- [x] 1.3 Make direct encryption backups exact, secure, transactional, and enabled by default while retaining explicit opt-out.

## 2. Guided Setup

- [x] 2.1 Keep entered values in memory and abort identity-reuse decline without changing keys or files.
- [x] 2.2 Stage only verified ciphertext and atomically commit the recovery backup and encrypted target.
- [x] 2.3 Treat returned errors, exceptions, and unsafe audit results as transactional failures.

## 3. Verification and Documentation

- [x] 3.1 Add focused identity inconsistency, encryption backup, filesystem failure-injection, and round-trip tests.
- [x] 3.2 Add focused guided cancellation, reuse, lifecycle failure, residue, and successful recovery tests.
- [x] 3.3 Regenerate tool references and indexes, update recovery guidance and exact tool counts, and validate documentation synchronization.
- [x] 3.4 Strictly validate OpenSpec, run focused secrets and CLI tests, and run `just check`.
