# Episodic Worker Delivery Plan

## Purpose

This is the standalone delivery plan for promoting the episodic-worker
architecture and selected extensions into six OpenSpec changes. It is intended
to be sufficient context for a new chat session: read this file first, then
inspect the referenced architecture and backlog before creating or changing any
OpenSpec artifacts.

The target architecture is always one main agent delegating to one worker:

```text
User <-> Main -> Worker
```

It is never `Main -> Many Workers`, and a worker cannot create another worker.

## Source documents

Until this program closes, these files are the program-level source documents:

- `arch.md` — the implemented architecture, including channel ownership and
  isolation.
- `next.md` — ideas that are still deferred and non-normative.
- `plan.md` — sequencing, dependency, and completion rules for this program.

Normative behavior belongs in each change's proposal, design, delta specs, and
tasks. `arch.md` must describe only behavior that has been implemented and
verified; `next.md` must describe only behavior that remains deferred.

## Non-negotiable architecture

Every change in this plan must preserve all of these constraints:

1. There is one main conversation, one worker per call, and at most one active
   `worker.run` call. There is no worker fan-out, worker tree, recursion, or
   multi-worker coordination.
2. A worker has the main agent's effective project instructions, skills, tools,
   configured MCP servers, and execution permissions.
3. Only Chat and committed Context are supplied automatically to a fresh worker.
4. Context is selected by project-local name for each episode. Its semantic body
   is shared only between workers using that name and is not exposed to the main
   agent; bounded frontmatter metadata is explicitly discoverable.
5. Console is user-facing output. Console bodies do not enter Context, History,
   worker startup, Status, or the main conversation.
6. Status is a bounded control result for the main agent and user; it does not
   duplicate substantial Console output.
7. History is a small, structured, MCP-authored mechanical record. Agents do not
   compose it, and it contains no prompts, narrative summaries, file contents,
   diffs, Console bodies, or tool results.
8. Local Changes remain ordinary project filesystem updates. Pre/post observation
   is VCS-independent and must not depend on Localhist.
9. Tool output, source text, intermediate reasoning, and same-thread messages are
   ephemeral working state unless explicitly written to an appropriate channel.
10. `needs_input` always terminates the current episode and deletes its worker
    thread. The user's answer starts a fresh episode and fresh worker thread with
    the same named Context.
11. Autonomous continuation may reuse a thread only when no user input is
    required and only within the same bounded `worker.run` episode.
12. No change may add backward-compatibility aliases, legacy modes, or transitional
    fallbacks unless the user explicitly requests them.

## Naming and waves

OpenSpec change IDs use this form:

```text
p<x><y>-<change-name>
```

`x` is the dependency wave and `y` is the recommended priority within that
wave; both are one-based digits in this plan. Priority defines the order in
which changes should be prepared and integrated; it is not a severity label.
The requested `dd-worker-warm-runtime` name is treated as a typo and corrected
to `add-worker-warm-runtime`.

| Wave | Priority | OpenSpec change ID | Depends on | Initial status | Outcome |
|---:|---:|---|---|---|---|
| 1 | 1 | `p11-update-episodic-worker-foundation` | Existing implementation | Planned | Replace session continuation with the named-Context channel foundation |
| 2 | 1 | `p21-add-worker-autonomous-continuation` | `p11` | Planned | Permit bounded same-thread turns without user input |
| 2 | 2 | `p22-add-worker-artifact-store` | `p11` | Planned | Add named-Context-owned non-project artifacts with explicit access |
| 2 | 3 | `p23-add-worker-warm-runtime` | `p11` | Planned | Reuse process/transport infrastructure without reusing a worker thread |
| 2 | 4 | `p24-add-worker-advanced-telemetry` | `p11` | Planned | Add privacy-bounded measurements separate from History |
| 3 | 1 | `p31-add-worker-context-compaction` | `p11`, `p24` | Planned | Add evaluated, explicit semantic Context compaction |

Dependency shape:

```text
                              +-> p21 autonomous continuation
                              +-> p22 artifact store
p11 named-Context foundation +-> p23 warm runtime
                              +-> p24 advanced telemetry -> p31 context compaction
```

Wave 2 changes are contractually separate. They may be prepared in isolation,
but their priority order is the default integration order. This independence is
about change management and never permits runtime multi-worker behavior.

## Foundation change archival

`p11-update-episodic-worker-foundation` is an update of the existing active
`add-episodic-worker-orchestrator` change, not a second competing foundation.
At the start of the new session:

1. Confirm the existing change and implementation are present and record the
   current Git state without modifying unrelated work.
2. Rename the existing change directory to
   `p11-update-episodic-worker-foundation`; do not leave an alias directory.
3. Update exact internal references to the old change path.
4. Preserve the existing artifacts and completed task evidence, then append the
   foundation-update work needed to reconcile proposal, design, delta specs,
   tasks, tests, code, `arch.md`, and `next.md`.
5. After `p11` is implemented and verified, sync its delta specs to the main
   specs so later changes have a normative baseline.
6. Archive `p11` after its exit gate passes and its delta specs are synced.
   Follow-on changes depend on the main normative specs, not an active foundation
   change directory.

The program documents originally lived inside the foundation change. Moving
them to the tracked `plans/episodic-worker/` directory makes that directory the
stable program owner and lets each completed OpenSpec change follow the normal
sync-and-archive lifecycle. It also avoids two active changes defining the same
base contract.

## Documentation promotion rule

Every change's `tasks.md` must include this completion sequence:

1. Implement the approved change and its tests.
2. Verify the implementation against the proposal, design, and delta specs.
3. Update the program `arch.md` to describe the verified behavior, channel
   routing, lifecycle, configuration, and failure semantics as implemented.
4. Remove the promoted extension section from the program `next.md`. Remove only
   that idea and any text that exists solely to support it; preserve every other
   deferred idea.
5. Update this plan's status if a status field or execution record has been added
   during delivery.
6. Run strict OpenSpec validation and the relevant project checks.

Do not remove an idea from `next.md` when its proposal is created or when coding
starts. Remove it only after implementation and verification succeed. If a
change is abandoned or deferred again, its idea remains in or returns to
`next.md`; `arch.md` must not claim it exists.

The section-to-change mapping is exact:

| Change | `next.md` section removed at completion |
|---|---|
| `p11-update-episodic-worker-foundation` | None; reconcile the current channel foundation and leave deferred sections intact |
| `p21-add-worker-autonomous-continuation` | `Bounded Autonomous Same-Thread Continuation` |
| `p22-add-worker-artifact-store` | `Named-Context Artifact Store` |
| `p23-add-worker-warm-runtime` | `Warm Runtime and Connection Reuse` |
| `p24-add-worker-advanced-telemetry` | `Advanced Telemetry` |
| `p31-add-worker-context-compaction` | `Semantic Compaction or Summarization` |

## Wave 1 — Foundation

### `p11-update-episodic-worker-foundation`

**Goal:** Replace the precursor session contract with named project-local Context
files and make implementation, normative artifacts, tests, and architecture agree
on the channel model before adding extensions.

**Required scope:**

- Define Chat, Context, Console, Local Changes, Status, and History with explicit
  writers, readers, storage, and automatic-input rules.
- Keep worker working state ephemeral and out of durable channels by default.
- Route substantial user-facing worker output through the existing Console
  mechanism and return only a bounded receipt/control Status.
- Start each invoked Chat on `default`, keep its selected Context name in the
  orchestrator, and permit explicit one-episode named overrides.
- Store each named Context as one bounded project-local Markdown file with strict
  discoverable frontmatter and a private complete semantic body.
- Add select, metadata listing/upsert, and archive operations; remove session IDs,
  contextless operation, project selection, and the public execution object.
- Append MCP-owned History as versioned JSONL after terminal handling and the
  post-episode file scan.
- Observe Local Changes mechanically with project-root pre/post comparison,
  without file contents, diffs, Git dependence, or Localhist.
- Teach the main-agent skill and worker instructions how to select the correct
  channel without making agents responsible for mechanical History.
- Make `needs_input` a terminal result whose answer always creates a fresh
  episode.
- Specify ordering and warnings for Context commit, Console publication,
  thread cleanup, change scanning, and History append failures.
- Reconcile all existing tests and reference documentation with the same rules.

**Out of scope:** autonomous additional turns, managed artifacts, warm runtime,
advanced telemetry, semantic compaction, indexed History, durable Console
replay, selective Context queries, partial Context updates, retries, transcripts,
and long-term memory.

**Exit gate:** The code and all artifacts express the same six-channel contract;
the main agent never receives Context or Console bodies; user-input continuation
is demonstrably a fresh thread; mechanical History and Local Changes observation
are tested; strict OpenSpec validation and relevant project checks pass; the
delta specs are synced for dependent work.

## Wave 2 — Independent extensions

### `p21-add-worker-autonomous-continuation`

**Goal:** Let one worker perform more than one model turn inside one synchronous
episode when it can continue without user input.

**Required scope:**

- Add an internal worker-authored continuation outcome that is not a public
  `worker.run` terminal status.
- Keep the same worker thread and execution policy for bounded autonomous turns.
- Supply Chat and Context only on the first turn; later turns receive a fixed
  continuation instruction through ephemeral same-thread state.
- Add a strict maximum turn count and one total episode deadline.
- Commit Context only on terminal `completed` or `needs_input`.
- Define later-turn failure, interruption, cleanup, and non-replay behavior.
- Record mechanical turn count in History and expose only bounded terminal
  Status.
- Prove that `needs_input` deletes the thread and that the user's response starts
  a fresh episode.

**Out of scope:** public continue/resume APIs, user-driven thread resumption,
automatic retries, parallel workers, worker recursion, Context checkpoints after
each turn, and authority escalation.

**Exit gate:** Tests cover one-turn completion, bounded continuation, max-turn
and deadline termination, later-turn failure, Context commit timing, and fresh
episodes after user input. Update `arch.md`, remove the mapped `next.md` section,
validate, and run relevant checks.

### `p22-add-worker-artifact-store`

**Goal:** Preserve worker-created, named-Context-scoped evidence or intermediate
files that should outlive an episode but are neither semantic Context nor project
deliverables.

**Required scope:**

- Add a project-scoped artifact root owned by a named Context with stable IDs and
  bounded typed metadata.
- Define explicit create/open/list or equivalent access; artifacts are never
  injected automatically into worker startup.
- Enforce path containment, symlink safety, atomic metadata updates, media/kind
  validation, size limits, and collision behavior.
- Define retention, deletion, orphan recovery, and Context archival behavior.
- Keep compact references in Context only when operationally needed.
- Keep project deliverables in Local Changes and user-facing bodies in Console.
- Keep artifact contents and summaries out of mechanical History.

**Out of scope:** copying project files into the artifact store, using artifacts
as automatic memory, semantic indexing, long-term cross-Context storage, durable
Console replay, and storing artifact bodies in Context or History.

**Exit gate:** Lifecycle, containment, cleanup, crash recovery, and channel
isolation are tested. Update `arch.md`, remove the mapped `next.md` section,
validate, and run relevant checks.

### `p23-add-worker-warm-runtime`

**Goal:** Reduce episode startup latency by reusing safe process and transport
infrastructure while retaining a fresh worker thread for every episode.

**Required scope:**

- Measure and document the cold-start baseline before selecting reusable state.
- Reuse only app-server process and eligible MCP transport/connection state.
- Create and delete a fresh Codex thread for every episode, including after
  `needs_input`.
- Add health checks, idle expiry, shutdown, reconnect, and stale-process recovery.
- Partition reusable state by project and effective execution/security envelope.
- Ensure credentials, permissions, cached state, and MCP sessions cannot broaden
  authority or cross project boundaries.
- Measure cold and warm startup separately.

**Out of scope:** thread pooling, transcript reuse, preloaded Context shared
between sessions, concurrent workers, changed permission semantics, and hiding
lifecycle failures with automatic work replay.

**Exit gate:** Isolation, project switching, policy switching, expiry, crash,
reconnect, and shutdown tests pass, and measurements show a material benefit.
Update `arch.md`, remove the mapped `next.md` section, validate, and run relevant
checks.

### `p24-add-worker-advanced-telemetry`

**Goal:** Add measurements needed to evaluate episodic execution, continuation,
warm-runtime performance, and future compaction without creating another memory
channel.

**Required scope:**

- Define each metric, unit, source, aggregation, consumer, retention, and privacy
  classification before implementation.
- Where providers expose reliable data, measure input/output/cached tokens,
  first-event latency, total duration, turn count, terminal status, Context bytes
  and revisions, validation failures, and rejected sizes.
- Separate cold/warm runtime and per-turn/whole-episode measurements.
- Keep telemetry storage and APIs distinct from History, Context, Console, and
  Chat; it is never automatic worker or main-agent input.
- Default to excluding prompts, Console bodies, file contents, diffs, tool
  results, secrets, and high-cardinality sensitive labels.
- State explicitly when a measurement is unavailable or estimated; do not treat
  Context size as total model input.

**Out of scope:** transcript capture, semantic memory, full prompt logging,
Console retention, agent-authored History, and using telemetry to silently alter
worker behavior.

**Exit gate:** Metric semantics, privacy/retention controls, unavailable-data
behavior, and channel isolation are tested. Update `arch.md`, remove the mapped
`next.md` section, validate, and run relevant checks. The resulting evidence
contract must be sufficient for `p31` evaluations.

## Wave 3 — Evidence-gated context behavior

### `p31-add-worker-context-compaction`

**Goal:** Explicitly compact Context when evidence shows long-lived named
Contexts cannot remain within the bounded whole-state model without losing
continuation quality.

**Entry gate:** Do not create or implement this change merely because `p24` is
complete. First collect representative evidence that concise worker-authored
replacements still approach or exceed the Context limit, and create an
evaluation set that detects loss of goals, constraints, decisions, blockers,
unresolved questions, and essential file references.

**Required scope:**

- Treat compaction as an explicit semantic operation, never as validation,
  deterministic normalization, repair, or silent truncation.
- Define the trigger, initiator, model/runtime boundary, and whether approval is
  required for material removals.
- Compare proposed compact Context with the last valid revision and expose
  important removals through bounded audit metadata without copying Context into
  History or Status.
- Validate the complete compacted Markdown body through the named-Context
  revision/digest and atomic-commit path while preserving frontmatter metadata.
- Preserve the last valid Context on timeout, model failure, invalid output,
  oversize output, or failed evaluation.
- Measure continuation quality as well as bytes and tokens.

**Out of scope:** automatic truncation, embeddings, semantic retrieval,
cross-Context memory, transcript summarization, indexed History, and injecting
removed material into future workers.

**Exit gate:** The evaluation demonstrates acceptable retention and a measured
benefit on representative long-lived Contexts; all failure paths preserve the last
valid Context; channel isolation remains intact. Update `arch.md`, remove the
mapped `next.md` section, validate, and run relevant checks.

## OpenSpec workflow for each change

For each change, the new session must:

1. Read `AGENTS.md`, `dev/index.md`, the relevant linked development guidance,
   this plan, `arch.md`, `next.md`, and the latest normative specs.
2. Confirm prerequisites and inspect existing work before editing. Preserve
   unrelated or user-owned worktree changes.
3. Use the OpenSpec workflow to create or continue exactly one named change.
4. Write a focused proposal explaining evidence, scope, dependencies, affected
   capabilities, and explicit non-goals.
5. Write a design that specifies lifecycle, channel routing, data ownership,
   validation, limits, failure ordering, cleanup, and security boundaries.
6. Write delta specs with testable `SHALL` requirements and scenarios. Do not
   rely on `arch.md` or `next.md` as normative contracts.
7. Write ordered implementation tasks that include tests, docs promotion,
   `next.md` removal, strict validation, and project checks.
8. Review and approve the artifacts before applying implementation work.
9. Implement only the approved scope, verify it against the artifacts, and
   perform the documentation promotion rule.
10. Sync/archive according to dependencies. Do not begin a dependent wave until
    its required specs are available in the main normative spec set.

## Program completion

The program is complete when:

- all six named changes have passed their individual exit gates;
- the normative specs and implementation agree;
- `arch.md` describes all six delivered capabilities and no deferred behavior;
- the five promoted sections are absent from `next.md`, while unrelated deferred
  extensions remain intact;
- no architecture or test permits `Main -> Many Workers`;
- user input always starts a fresh episode;
- channel-isolation tests prevent Console, History, Local Changes observations,
  telemetry, artifacts, and ephemeral working state from becoming implicit agent
  context;
- the final strict OpenSpec validation and relevant project checks pass; and
- every completed change has synced its delta specs and been archived.
