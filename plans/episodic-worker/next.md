# Deferred Episodic Worker Extensions

This file preserves follow-on ideas removed from v1. It is non-normative: none
of these features is required by the current proposal, design, or future delta
specifications unless promoted through a separate OpenSpec change.

The adoption rule is evidence first. A feature should move into scope only after
real episodic-worker use demonstrates that the current serialized channel design
is insufficient and the added behavior can be specified and tested
independently.

Every extension must preserve the channel boundary defined in `arch.md`. Only the
current Chat request and committed Context may enter a fresh worker
automatically. Console bodies, mechanical History, prior worker messages, and
tool observations must never become implicit worker or main-agent context.

## Named-Context Artifact Store

### Opportunity

Workers may produce research notes, captured evidence, generated reports, or
large intermediate results that should outlive one episode but do not belong in
the small context file or as normal project deliverables.

### Possible Design

- Add `.onetool/state/worker/artifacts/<context>/` under the effective project.
- Give artifact metadata a small stable identifier, relative path, media type or
  kind, status, summary, and relevance to current work.
- Require artifact paths to remain within the owning Context artifact root and use
  atomic writes for MCP-created metadata.
- Keep artifact content out of worker startup. Context would carry only compact
  metadata, and workers would open a referenced artifact deliberately.
- Keep normal project deliverables in the Local Changes channel. An artifact
  store must not copy or replace files that already belong in the project tree.
- Define retention and cleanup independently from context revisioning so deleting
  an old artifact cannot silently corrupt current state.

### Why Deferred

V1 can reference ordinary existing project files. A managed artifact lifecycle
adds storage ownership, cleanup, naming, path-security, and orphan-handling rules
before there is evidence that normal files are inadequate.

### Adoption Criteria

- Repeated tasks create useful non-deliverable files that users do not want in
  the project tree.
- The lifecycle, security boundary, retention behavior, and recovery story can be
  specified without expanding the core context schema substantially.

## Durable Console Retention and Replay

### Opportunity

The existing Console outbox keeps user-facing worker content out of the main
agent's conversational history, but its message bodies are scoped to one runtime
instance. Users may eventually need to reconnect, replay, or retain selected
Console results across runtime restarts.

### Possible Design

- Extend the existing Console protocol and body store rather than adding a
  `console.md`, event log, or second Console transport.
- Associate retained messages with Context and episode identifiers using
  runtime-owned metadata; keep bodies out of `history.jsonl`.
- Add explicit retention, deletion, reconnect, and replay controls for users.
- Preserve bounded receipts for agents and never inject a retained Console body
  into later workers or the main agent automatically.
- If streaming is added, define incomplete-message markers and crash recovery
  without changing terminal Status semantics.

### Why Deferred

The existing Console channel is sufficient for live user delivery. Persistence
across runtime instances adds ownership, retention, deletion, replay, and stale
reference rules that are independent of the initial channel boundary.

### Adoption Criteria

- Users demonstrably need Console results after their producing runtime exits.
- Retention and deletion can be specified without turning Console into History,
  Context, or long-term memory.

## Indexed History and Rich Queries

### Opportunity

The MCP-owned `history.jsonl` journal is sufficient for serialized append and
bounded inspection. Large numbers of Contexts or user-facing filtering may
eventually require indexed queries by episode, status, time, Console message, or
changed path.

### Possible Design

- Introduce a purpose-built project-scoped relational store or derived index for
  the strict mechanical History schema. Do not reuse the agent-facing `mem`
  schema, semantic retrieval, embeddings, relevance, or mutable-memory history.
- Keep the MCP as the sole writer and preserve append-oriented episode records.
- Index only bounded mechanical fields. Never store prompts, Console bodies,
  tool results, file contents, diffs, or agent-authored narrative.
- Keep Local Changes observation VCS-independent and do not depend on Localhist.
- Define pagination, retention, deletion, corruption recovery, and schema
  evolution before replacing or indexing the structured journal.

### Why Deferred

One serialized writer and one compact JSON record per episode do not initially
need a database, migration system, query planner, or secondary indexes.

### Adoption Criteria

- Measurements show JSONL inspection or filtering is a material usability or
  performance problem.
- Required queries and retention behavior are stable enough to justify a
  purpose-built schema without weakening channel isolation.

## Selective Context Reads and Deterministic Search

### Opportunity

A future context schema may grow enough that always injecting the complete state
becomes measurably wasteful, or workers may need to find one known item without
reading unrelated state.

### Possible Design

- Start with exact deterministic selectors over named sections or stable IDs.
- If text search is needed, define literal or normalized substring matching with
  stable ordering and explicit result limits.
- Return revision and match metadata with every response.
- Treat unknown selectors as errors, not empty successful reads.
- Keep semantic similarity, embeddings, and model-selected retrieval out of this
  layer unless evaluated as a separate memory capability.

### Why Deferred

The 16 KB whole-context file is intentionally small. Search would add indexes,
tool calls, result bounds, and missing-context risk while encouraging the store
to grow beyond its purpose.

### Adoption Criteria

- Measurements show whole-state injection is a material cost or reliability
  problem at the configured size.
- Exact retrieval can preserve a worker's ability to discover all state relevant
  to its task.

## Partial Updates and Rich Item Identity

### Opportunity

Whole-object replacement may become inefficient if context grows or independent
sections need to be updated without resubmitting unrelated fields.

### Possible Design

- Introduce stable item IDs only for sections that demonstrably need independent
  mutation.
- Support typed whole-item `upsert` and `remove`; continue rejecting arbitrary
  YAML paths and partial unvalidated objects.
- Require an expected base revision and apply a batch atomically.
- Keep runtime-managed schema and revision fields unavailable to callers.

### Why Deferred

V1 has one worker and one small file. IDs, patch ordering, and item-level
mutation solve a scale problem that does not yet exist.

### Adoption Criteria

- Whole-context submissions cause measured latency or repeated omission errors.
- Mutation semantics can remain smaller and clearer than replacing the file.

## Semantic Compaction or Summarization

### Opportunity

Over long-lived Contexts, workers may repeatedly preserve facts that are valid but no
longer useful. Mechanical MCP normalization cannot determine relevance,
supersession, or the smallest adequate explanation.

### Possible Design

- Treat compaction as an explicit semantic operation, never as deterministic
  validation or repair.
- Compare a proposed compact state with the prior state and surface removals for
  audit or approval when important durable knowledge is affected.
- Consider a dedicated model call only if evaluations show that the normal worker
  cannot keep whole-state replacements concise.
- Preserve the last valid context on compaction failure and prohibit silent
  truncation.
- Measure continuation quality, not only output size.

### Why Deferred

Calling semantic model judgment "automatic cleanup" obscures responsibility and
makes failure difficult to test. V1 instead asks each worker to author current
truth and lets the MCP perform only deterministic mechanical repair.

### Adoption Criteria

- Representative long-lived Contexts hit the KB limit despite concise worker
  submissions.
- An evaluation set can detect loss of goals, constraints, decisions, blockers,
  and essential references after compaction.

## Bounded Autonomous Same-Thread Continuation

### Opportunity

A Codex app-server turn already permits multiple sequential tool calls before the
worker returns its terminal result. Some tasks may nevertheless benefit from an
additional model turn on the same worker thread when work can continue without
user input.

### Possible Design

- Keep one `worker.run` call as one synchronous episode with one worker thread,
  but allow that thread to execute a bounded number of sequential turns.
- Add an internal worker-authored `continue` outcome indicating that another turn
  can proceed without user input. Never expose `continue` as a public
  `worker.run` status.
- Supply the request and complete episodic context only to the first turn. Start
  later turns with a fixed continuation instruction and the ephemeral
  same-thread conversation.
- Prefer completing tool use within the current turn. Continuation is not a
  replacement for ordinary tool calls.
- Apply one total episode deadline and a strict maximum turn count so the worker
  cannot continue indefinitely.
- Preserve the same execution policy for every turn and never introduce an
  approval or authority-escalation bridge.
- Commit context only on the final `completed` or `needs_input` outcome.
- Treat `needs_input` as a mandatory episode boundary: commit any valid returned
  context, delete the worker thread, and return the question to the main agent.
  The user's answer starts a fresh episode and fresh thread with the same named
  Context, never by resuming the prior worker thread.
- If a later turn fails or is interrupted, do not replay earlier turns or assume
  their project or external side effects can be reversed.

### Why Deferred

The current single-turn worker already supports multi-step tool execution.
Additional turns introduce a continuation signal, loop limits, cumulative timeout
rules, later-turn failure handling, and ambiguity about when context becomes
committed.

### Adoption Criteria

- Representative workers demonstrably stop before completing work even though no
  user input is required and ordinary within-turn tool use is available.
- Evaluations show bounded continuation improves completion without increasing
  repeated work, uncontrolled loops, or unclear side-effect recovery.

## Retry and Recovery Policies

### Opportunity

Transient app-server or MCP failures may occur before a worker performs any
external side effect.

### Possible Design

- Classify failures into provably pre-execution transport failures and
  potentially side-effecting failures.
- Permit bounded retry only for the former, with a new thread ID and the same
  committed revision.
- Never infer idempotency from missing output; require runtime evidence that the
  worker did not start substantive execution.
- Record retry reason and attempt count in the terminal result.

### Why Deferred

The safe v1 rule is simple: never replay an episode automatically. Reliable
side-effect classification requires app-server lifecycle evidence not needed for
the core context system.

### Adoption Criteria

- Transport-only failures are frequent enough to harm usability.
- The runtime can prove that a retry cannot duplicate project or external state.

## Warm Runtime and Connection Reuse

### Opportunity

Keeping the Codex app-server process and MCP connections warm between episodes
could reduce startup time while still creating a fresh thread each time.

### Possible Design

- Reuse only process and transport infrastructure; never reuse thread messages or
  worker-local conversational state.
- Add health checks, idle expiry, clean shutdown, and reconnection behavior.
- Ensure cached credentials and MCP sessions do not broaden authority between
  workers or projects.
- Measure cold and warm startup separately.

### Why Deferred

Process lifetime optimization is independent of the context contract and can
hide lifecycle bugs during the initial proof.

### Adoption Criteria

- Cold startup is a measured, material share of episode latency.
- Reuse preserves thread isolation and project security boundaries under tests.

## Advanced Telemetry

### Opportunity

Detailed measurements could help evaluate whether episodic execution reduces
cost and context drift and identify where latency occurs.

### Possible Design

- Record input, output, and cached tokens when the provider exposes them.
- Separate fixed bootstrap input, persisted context bytes, project content read,
  and worker-produced output where the runtime can measure them accurately.
- Track time to first event, total duration, terminal status, context revisions,
  validation failures, and rejected file sizes.
- Keep telemetry distinct from the bounded mechanical History journal; neither
  channel may become implicit agent input.
- Avoid claims that the context file size equals total model input.
- Define retention and privacy rules before storing prompts, paths, or errors.

### Why Deferred

Basic operational logging is enough for v1. A large telemetry surface can become
a second deliverable and may record sensitive task details.

### Adoption Criteria

- Specific product or performance questions require measurements unavailable
  from existing logging.
- Every metric has a clear definition, consumer, retention policy, and test.

## Transcript and Long-Term Memory

### Opportunity

Users may eventually want to recover discarded discussion, search prior episodes,
or reuse knowledge across named Contexts or projects.

### Possible Design

- Build transcript storage, full-text search, semantic retrieval, or durable
  cross-Context memory as a separate capability with explicit user controls.
- Treat transcripts as conversation records, not as the MCP-authored mechanical
  History journal, and never derive one by copying the other.
- Keep retrieved history distinct from trusted current context and label its
  source and age.
- Define retention, deletion, privacy, prompt-injection handling, and project
  boundaries before automatic retrieval.
- Never make long-term memory a fallback that silently expands every worker's
  bootstrap.

### Why Deferred

The current change deliberately replaces conversation history with present task
state. Long-term memory has different trust, privacy, scale, and relevance
requirements and would blur the central experiment.

### Adoption Criteria

- Users demonstrably need discarded or cross-Context information that cannot be
  represented as current knowledge or a project-file reference.
- A separate proposal defines ownership, retrieval, security, and deletion.
