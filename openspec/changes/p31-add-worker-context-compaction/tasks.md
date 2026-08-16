## 1. Enforce the Evidence Entry Gate

- [ ] 1.1 Confirm named-Context `p11` and privacy-bounded `p24` are verified and
  collect identity-free evidence where concise active Context files reach 75%.
- [ ] 1.2 Create a versioned evaluation set marking essential goals, criteria,
  constraints, decisions, blockers, questions, and references.
- [ ] 1.3 Prove complete validity, perfect essential retention, no inventions, and
  20% median byte reduction or defer implementation without behavior change.

## 2. Implement Explicit Named-Context Compaction

- [ ] 2.1 Add strict Context-name input and bounded body/frontmatter-free results.
- [ ] 2.2 Require an existing active Context and invoke a tool-free proposer with
  only its semantic body and fixed instructions.
- [ ] 2.3 Compare proposal/base semantics, classify removals, evaluate, and return
  unchanged when no meaningful reduction exists.

## 3. Add Approval and Atomic Commit

- [ ] 3.1 Create expiring single-use tokens bound to Context name, active status,
  base revision/digest, proposal digest, removals, and evaluation version.
- [ ] 3.2 Require approval for protected removals and reject expired, reused,
  archived, stale, or mismatched tokens without changing Context.
- [ ] 3.3 Reuse named-Context encoding, reference, size, revision/digest, metadata-
  preservation, and atomic-commit validation.
- [ ] 3.4 Preserve the last valid file on every model, validation, evaluation,
  concurrency, archival, approval, or write failure.

## 4. Verify Evaluation and Channel Isolation

- [ ] 4.1 Test evidence rejection, safe direct compaction, material approval,
  token failures, archived Context, manual edits, unchanged proposals, and all
  preservation paths.
- [ ] 4.2 Run representative and holdout evaluation under `p24` privacy without
  names, descriptions, tags, or bodies in telemetry.
- [ ] 4.3 Prove no project/Console/artifact/external tools and only bounded History metadata.

## 5. Promote and Validate

- [ ] 5.1 Verify implementation and evaluation thresholds against all artifacts.
- [ ] 5.2 Update `plans/episodic-worker/epic-worker-arch.md` and remove
  `plans/episodic-worker/next/context-compaction.md` after verification.
- [ ] 5.3 Update worker skill/reference documentation for named selection.
- [ ] 5.4 Run focused tests, strict OpenSpec validation, and `just check` before
  syncing or archiving.
