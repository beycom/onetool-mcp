## 1. Confirm Foundation and Measure Cold Startup

- [ ] 1.1 Confirm the verified `p11` specs are synced before integrating runtime
  reuse and preserve serialized fresh-thread behavior.
- [ ] 1.2 Build a repeatable cold-start benchmark separating initialization,
  first protocol event, thread start, and total pre-turn duration.
- [ ] 1.3 Record the representative baseline, target material improvement, and
  eligible/ineligible reusable state before enabling warm mode by default.

## 2. Add Configuration and Isolation Keys

- [ ] 2.1 Add strict disabled-by-default warm-runtime and bounded idle-expiry
  configuration with defaults, range validation, and unknown-field tests.
- [ ] 2.2 Build deterministic isolation keys from canonical project, exact
  execution envelope, and effective MCP/credential identities without secrets.
- [ ] 2.3 Test project, policy, network, writable-root, MCP, and credential changes
  cannot lease earlier reusable state.

## 3. Implement the Runtime Lifecycle

- [ ] 3.1 Add explicit starting, ready, leased, idle, unhealthy, and closed states
  around owned app-server processes and eligible transports.
- [ ] 3.2 Reuse initialization only for a healthy matching key while creating and
  deleting a distinct thread for every episode, including after `needs_input`.
- [ ] 3.3 Implement bounded pre-lease health checks, idle expiry, reconnect,
  stale-process recovery, and one cold replacement only before execution begins.
- [ ] 3.4 Implement graceful server shutdown and targeted force termination for
  resolved owned child processes after the grace period.

## 4. Verify Failure and Measurement Boundaries

- [ ] 4.1 Test cold/disabled and warm paths, fresh thread IDs, thread deletion,
  cache state exclusion, eligible transport reuse, and ineligible reconnects.
- [ ] 4.2 Test health failure, expiry, project/policy switching, process crash,
  protocol desynchronization, reconnect, active failure, and shutdown.
- [ ] 4.3 Prove active work is never replayed and emit body-free cold/warm startup
  classification and phase measurements.

## 5. Promote and Validate

- [ ] 5.1 Verify implementation and measured material benefit against the
  proposal, design, delta specs, and cold baseline.
- [ ] 5.2 Update program `arch.md` with verified reusable-state boundaries, then
  remove only `Warm Runtime and Connection Reuse` and supporting-only text from
  program `next.md`.
- [ ] 5.3 Update worker/reference documentation and the delivery plan status if an
  execution record or status field has been added.
- [ ] 5.4 Run focused lifecycle/benchmark tests, strict OpenSpec validation, and
  `just check`; resolve every failure before syncing or archiving the change.
