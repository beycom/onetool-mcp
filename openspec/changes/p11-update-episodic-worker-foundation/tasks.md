Sections 1–6 record the verified session-based precursor already implemented on
this branch. The revised named-Context contract in sections 7 onward supersedes
that public behavior; checked precursor tasks are historical implementation
evidence, not permission to retain session aliases or fallbacks.

## 1. Freeze the Precursor Data and Configuration Contracts

- [x] 1.1 Add strict typed models for worker-maintained context, committed context,
  internal terminal output, execution policy, and the precursor public result.
- [x] 1.2 Add strict worker model, effort, and positive context-size configuration.
- [x] 1.3 Add deterministic normalization and canonical rendering for the
  precursor complete Context schema.

## 2. Implement the Precursor Context Store

- [x] 2.1 Add project-local Context storage with safe opaque precursor identities.
- [x] 2.2 Add startup validation, reference containment, canonical rewrite, and
  byte-limit enforcement.
- [x] 2.3 Add loaded-revision checks and beside-file atomic commits.

## 3. Implement the Codex App-Server Adapter

- [x] 3.1 Build the focused adapter with capability preflight, one fresh thread,
  one turn, strict output, interruption, and thread deletion.
- [x] 3.2 Validate and forward the precursor explicit execution envelope.
- [x] 3.3 Normalize completion, required input, failure, timeout, malformed output,
  process exit, and interruption.
- [x] 3.4 Delete finished threads and preserve known outcomes on cleanup warnings.

## 4. Add the Precursor Worker Surface

- [x] 4.1 Add the precursor session-based `worker.run` operation.
- [x] 4.2 Enforce one active call, reject recursion and concurrency, and never retry.

## 5. Distribute the Explicit Orchestrator Skill

- [x] 5.1 Add the precursor session-coordinator skill and authority forwarding.
- [x] 5.2 Add standard skill discovery metadata with implicit invocation disabled.

## 6. Verify the Precursor Slice

- [x] 6.1 Add integration coverage for fresh threads and complete Context handoff.
- [x] 6.2 Prove the precursor exposed only `worker.run`.
- [x] 6.3 Document the precursor worker and Context behavior.
- [x] 6.4 Run focused tests, strict OpenSpec validation, and `just check`.

## 7. Replace Session Identity With Named Context Files

- [x] 7.1 Replace the opaque session store with
  `.onetool/state/worker/contexts/<context>.md`, strict slug validation, reserved
  `default`, frontmatter schema, Markdown body, stable listing, and project-local
  containment tests.
- [x] 7.2 Remove `session_id`, session directories, session discovery, and every
  public or internal compatibility alias or legacy read path.
- [x] 7.3 Add atomic automatic creation for missing active names used by run,
  select, or metadata update; reject archived-name reuse and invalid names.
- [x] 7.4 Add strict frontmatter parsing that rejects malformed YAML, aliases,
  unknown fields, invalid values, invalid encoding, and oversized complete files.

## 8. Implement Context Metadata and Archival Operations

- [x] 8.1 Add `worker.select` with create-or-select behavior and bounded name and
  creation receipt; keep Chat selection coordinator-owned rather than process-global.
- [x] 8.2 Add `worker.list_contexts` with stable metadata-only results, active or
  archived filtering, and no semantic body or inferred summary.
- [x] 8.3 Add `worker.update_context` upsert with omitted-versus-empty semantics,
  complete tag replacement, metadata bounds, atomic revision increment, and
  semantic-body preservation.
- [x] 8.4 Add `worker.archive_context` with default protection, active-only
  transition, body/metadata preservation, archived-use rejection, and no delete,
  move, restore, or implicit reactivation path.

## 9. Replace the Worker Run Contract

- [x] 9.1 Change `worker.run` to accept prompt, optional named Context, model, and
  effort; remove the public execution object and derive the current project and
  effective authority without broadening it.
- [x] 9.2 Replace the public session result with exact `context`, `status`, and
  bounded `message`; update terminal processing without exposing Context bodies.
- [x] 9.3 Supply only the current request and selected complete Context body to a
  fresh thread; prove a newly named review Context sees the project but not the
  implementation Context.
- [x] 9.4 Bind worker replacements and manual metadata edits to loaded revision
  and digest; preserve the last valid file on conflict, failure, interruption,
  invalid body, invalid reference, or oversize.

## 10. Update Orchestration and Worker Instructions

- [x] 10.1 Revise the orchestrator to initialize each invoked Chat to `default`,
  retain one selected name, pass it explicitly to run, and avoid process-global
  or project-global selection.
- [x] 10.2 Teach explicit run Contexts as one-episode overrides that do not change
  Chat selection; route required-input answers to the same effective Context in a
  fresh episode.
- [x] 10.3 Revise worker instructions for complete untrusted Markdown Context,
  Console publication, full body replacement, metadata isolation, and prohibition
  on direct OneTool state modification.
- [x] 10.4 Remove session terminology and execution-envelope plumbing from skill,
  references, examples, result models, and tests without compatibility aliases.

## 11. Reconcile the Six Channels

- [x] 11.1 Enforce a 1024-byte bounded Status and substantial-output publication
  through Console without returning Console bodies to the main agent.
- [x] 11.2 Implement VCS-independent pre/post project-tree fingerprints with the
  specified exclusions, containment, stable ordering, and classifications.
- [x] 11.3 Implement project-scoped strict `history.jsonl` with selected Context
  name, canonical append, flush and `fsync`, valid-prefix recovery, and body and
  metadata exclusions.
- [x] 11.4 Implement deterministic terminal ordering for Context handling, thread
  deletion, final scan, History append, bounded warnings, and Status return.

## 12. Reconcile Dependent Worker Changes

- [x] 12.1 Update `p21` to carry one named Context through bounded same-thread
  continuation without session terminology.
- [x] 12.2 Update `p22` from session-owned artifacts to named-Context ownership,
  including archive retention and active-only artifact creation.
- [x] 12.3 Update `p23` lifecycle wording so runtime reuse never reuses Context or
  thread state and required-input follow-up uses the same name.
- [x] 12.4 Update `p24` to retain Context size/revision metrics while excluding
  names, descriptions, tags, and reconstructable Context identity.
- [x] 12.5 Update `p31` compaction selection, evidence, approval binding, and
  archived-state failure from session ID to named Context.

## 13. Verify and Promote the Named-Context Foundation

- [x] 13.1 Add unit tests for names, frontmatter, creation, metadata upsert,
  listing, archival, revision/digest conflicts, size, privacy, and result shapes.
- [x] 13.2 Add integration tests for default selection, Chat switching, one-episode
  override, fresh review isolation, required input, fresh threads, Console,
  History, Local Changes, authority, interruption, and cleanup.
- [x] 13.3 Update the program documents in `plans/episodic-worker/`, worker
  references, and skill docs to describe only the final named-Context contract.
- [x] 13.4 Verify implementation against every delta requirement, run focused
  worker and Console tests, strict OpenSpec validation, and `just check`.
- [x] 13.5 Sync the verified named-Context delta specs into main specs before any
  dependent implementation is integrated; keep `p11` open as program owner.
