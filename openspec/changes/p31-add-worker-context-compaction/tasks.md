## 1. Enforce the Evidence Entry Gate

- [ ] 1.1 Confirm verified `p11` and `p24` specs/implementations are available and
  collect representative sessions where concise Context reaches at least 75% of
  its configured limit.
- [ ] 1.2 Create and approve a versioned evaluation set marking essential goals,
  criteria, constraints, decisions, blockers, questions, and file references.
- [ ] 1.3 Measure the proposed evaluator against 100% essential retention, zero
  invented facts/references, complete validity, and 20% median byte reduction;
  defer implementation without changing Context if any entry gate fails.

## 2. Implement the Explicit Compaction Proposal

- [ ] 2.1 Add strict `context_compact` input and bounded body-free result models
  with exact statuses, sizes, revisions, removal metadata, and optional token.
- [ ] 2.2 Implement a tool-free semantic proposer receiving only the current
  complete Context and fixed instructions with one bounded deadline.
- [ ] 2.3 Compare proposal/base semantics, classify material removal, run the
  versioned evaluation, and return `unchanged` when no meaningful reduction exists.

## 3. Add Approval and Atomic Commit

- [ ] 3.1 Create 30-minute single-use approval tokens bound to session, base
  revision, proposal digest, removal metadata, and evaluation version.
- [ ] 3.2 Require approval for removal or weakening of any protected category and
  reject expired, reused, stale, or mismatched tokens without changing Context.
- [ ] 3.3 Reuse complete schema/reference/size validation, expected-revision checks,
  canonical rendering, and atomic commit for approved or safe proposals.
- [ ] 3.4 Preserve the last valid Context on timeout, model/protocol failure,
  invalid/oversized output, hallucination, retention failure, stale revision,
  invalid approval, or write failure.

## 4. Verify Evaluation and Channel Isolation

- [ ] 4.1 Test evidence-gate rejection, safe direct compaction, material approval,
  token expiry/reuse/mismatch, unchanged proposals, and every preservation path.
- [ ] 4.2 Run the representative and holdout evaluation, recording continuation
  retention, hallucination rate, bytes, latency, and benefit under `p24` privacy.
- [ ] 4.3 Prove the compactor has no project/Console/artifact/external side-effect
  tools and audit channels contain only bounded metadata, never Context or removals.

## 5. Promote and Validate

- [ ] 5.1 Verify the implementation, evaluation thresholds, and measured benefit
  against the proposal, design, and delta specs.
- [ ] 5.2 Update program `arch.md` with only verified compaction behavior, then
  remove only `Semantic Compaction or Summarization` and supporting-only text from
  program `next.md`.
- [ ] 5.3 Update worker skill/reference documentation and the delivery plan status
  if an execution record or status field has been added.
- [ ] 5.4 Run focused compaction/evaluation tests, strict OpenSpec validation, and
  `just check`; resolve every failure before syncing or archiving the change.
