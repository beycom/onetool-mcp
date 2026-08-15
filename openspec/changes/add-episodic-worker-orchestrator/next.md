# Deferred Episodic Worker Extensions

This file preserves follow-on ideas removed from v1. It is non-normative: none
of these features is required by the current proposal, design, or future delta
specifications unless promoted through a separate OpenSpec change.

The adoption rule is evidence first. A feature should move into scope only after
real episodic-worker use demonstrates that the simple whole-context design is
insufficient and the added behavior can be specified and tested independently.

## Session Artifact Store

### Opportunity

Workers may produce research notes, captured evidence, generated reports, or
large intermediate results that should outlive one episode but do not belong in
the small context file or as normal project deliverables.

### Possible Design

- Add `episodic-context/<session-id>/artifacts/` beside `context.yaml`.
- Give artifact metadata a small stable identifier, relative path, media type or
  kind, status, summary, and relevance to current work.
- Require artifact paths to remain within the session artifact root and use
  atomic writes for MCP-created metadata.
- Keep artifact content out of worker startup. Context would carry only compact
  metadata, and workers would open a referenced artifact deliberately.
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

## Human-Facing Console Outbox

### Opportunity

A worker may generate progress details, warnings, evidence, and user-facing
results that are too large for the main agent's bounded terminal relay but still
need to be inspectable.

### Possible Design

- Add an append-oriented `console.md` or structured event log beside the context.
- Separate durable user output from worker context; never inject the console into
  later workers automatically.
- Record episode and revision identifiers so users can correlate messages with a
  worker result.
- Define whether writes stream during execution or publish atomically at the end.
  If streaming is allowed, incomplete-episode markers and crash recovery are
  required.
- Expose bounded terminal metadata telling the main agent where detailed output
  is available.

### Why Deferred

The worker's normal terminal result is sufficient to prove the episode model.
An outbox creates another persistence contract and must not become hidden context
or an unbounded transcript by another name.

### Adoption Criteria

- Real terminal results are routinely truncated or too large to relay usefully.
- Users need durable episode output independent of project deliverables.

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

Whole-object replacement may become inefficient if context grows, multiple
writers are introduced, or independent components need to update state without
resubmitting unrelated fields.

### Possible Design

- Introduce stable item IDs only for sections that demonstrably need independent
  mutation.
- Support typed whole-item `upsert` and `remove`; continue rejecting arbitrary
  YAML paths and partial unvalidated objects.
- Require an expected base revision and apply a batch atomically.
- Define conflicts explicitly rather than silently merging concurrent updates.
- Keep runtime-managed schema and revision fields unavailable to callers.

### Why Deferred

V1 has one worker and one small file. IDs, patch ordering, conflict rules, and
merge semantics solve a concurrency and scale problem that does not yet exist.

### Adoption Criteria

- Whole-context submissions cause measured latency or repeated omission errors,
  or a separately approved change introduces concurrent writers.
- Mutation semantics can remain smaller and clearer than replacing the file.

## Semantic Compaction or Summarization

### Opportunity

Over long sessions, workers may repeatedly preserve facts that are valid but no
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

- Representative long sessions hit the KB limit despite concise worker
  submissions.
- An evaluation set can detect loss of goals, constraints, decisions, blockers,
  and essential references after compaction.

## Scheduling, Concurrency, and Worker Trees

### Opportunity

Independent subtasks could run concurrently, and some episodes might benefit
from delegated research or background execution.

### Possible Design

- Add a bounded queue with explicit task ownership and terminal states.
- Give concurrent work isolated context branches or an explicit merge protocol;
  never let workers race on one YAML file.
- Preserve inherited sandbox and approval policy for every child.
- Reject unbounded recursion and enforce depth, fan-out, and resource limits.
- Require user-visible cancellation and status semantics for background jobs.

### Why Deferred

Concurrency changes the context model from a single current truth into branchable
state and introduces conflict resolution, scheduling, cancellation, and resource
governance. It should not be hidden inside the initial context proof.

### Adoption Criteria

- Serialized episodes are a demonstrated throughput bottleneck.
- A separate proposal defines branch ownership, merge behavior, resource limits,
  approvals, and failure recovery.

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
or reuse knowledge across orchestrator sessions.

### Possible Design

- Build transcript storage, full-text search, semantic retrieval, or durable
  cross-session memory as separate capabilities with explicit user controls.
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

- Users demonstrably need discarded or cross-session information that cannot be
  represented as current knowledge or a project-file reference.
- A separate proposal defines ownership, retrieval, security, and deletion.
