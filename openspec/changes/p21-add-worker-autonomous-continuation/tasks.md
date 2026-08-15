## 1. Confirm Foundation and Configuration

- [ ] 1.1 Confirm `p11-update-episodic-worker-foundation` is implemented, verified,
  and synced into the main specs before integrating this change.
- [ ] 1.2 Add strict `max_turns` and `episode_timeout_seconds` configuration with
  documented defaults, ranges, unknown-field rejection, and validation tests.

## 2. Implement the Internal Continuation Contract

- [ ] 2.1 Add the strict internal-only `continue` terminal variant with bounded
  `next_action` and rejection of Context, questions, public messages, permission
  changes, and unknown fields.
- [ ] 2.2 Extend worker instructions to prefer normal within-turn tool use and emit
  `continue` only for concrete autonomous remaining work.
- [ ] 2.3 Keep public `worker.run` statuses and exact three-field Status shape
  unchanged and prove `continue` is never exposed.

## 3. Add the Bounded Turn Loop

- [ ] 3.1 Reuse the same worker thread and exact execution policy for later turns,
  supplying only the fixed continuation instruction and `next_action` after turn 1.
- [ ] 3.2 Enforce the configured maximum count and one monotonic total deadline,
  mapping limit exhaustion to bounded failure without Context commit or replay.
- [ ] 3.3 Commit Context only on final `completed` or `needs_input`, then run thread
  cleanup, Local Changes observation, History append, and Status once.
- [ ] 3.4 Record actual turn count mechanically and keep continuation instructions,
  same-thread messages, and intermediate output out of durable channels.

## 4. Verify Lifecycle and Isolation

- [ ] 4.1 Test one-turn completion, multiple continuations, invalid continuation,
  maximum turns, deadline expiry, later-turn protocol failure, and interruption.
- [ ] 4.2 Test Context commit timing, preserved side effects without replay, exact
  authority reuse, and absence of repeated Chat or Context input.
- [ ] 4.3 Prove `needs_input` deletes the continued thread and the user's answer
  starts a fresh episode and thread with the same committed Context.

## 5. Promote and Validate

- [ ] 5.1 Verify implementation against the proposal, design, and delta specs.
- [ ] 5.2 Update the program `arch.md` with verified continuation lifecycle and
  channel routing, then remove only `Bounded Autonomous Same-Thread Continuation`
  and its supporting-only text from the program `next.md`.
- [ ] 5.3 Update worker skill/reference documentation and the delivery plan status
  if an execution record or status field has been added.
- [ ] 5.4 Run focused tests, strict OpenSpec validation, and `just check`; resolve
  every failure before syncing or archiving the change.
