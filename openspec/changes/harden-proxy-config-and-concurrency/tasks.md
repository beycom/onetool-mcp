## 1. Configuration Validation

- [x] 1.1 Add strict auth-type validation and deterministic OAuth scope normalization.
- [x] 1.2 Add transport-specific server field, URL, command, and positive-timeout validation.
- [x] 1.3 Reject reserved and Python-safe-colliding server names at the root configuration model.
- [x] 1.4 Cover valid and invalid shapes through YAML configuration loading, including environment-backed bearer tokens.

## 2. Safe Proxy Concurrency

- [x] 2.1 Replace the singular call lock with a bounded shared/exclusive per-server capacity gate.
- [x] 2.2 Allow detached calls to overlap while interactive calls retain exclusive elicitation ownership.
- [x] 2.3 Preserve absolute-deadline, cancellation, detached-call, and lifecycle cleanup behavior.
- [x] 2.4 Add unit and protocol-level tests for overlap, isolation, reversed completion, capacity timeouts, and cleanup.

## 3. Verification

- [x] 3.1 Run focused configuration, proxy manager, elicitation, namespace, and integration tests.
- [x] 3.2 Run p-review-py and `just check`, resolve findings, and confirm implementation matches the delta specs.
