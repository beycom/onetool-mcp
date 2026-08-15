## Why

Long-running agent conversations become more expensive and less reliable as old
tool output, superseded plans, and stale assumptions remain in model context. A
larger context window delays this problem but does not keep the working state
focused.

This change replaces accumulated worker conversation with a small structured
record of current operational truth. Each fresh worker receives that record,
does one episode of substantive work, and leaves a validated replacement for the
next worker without carrying prior worker messages forward.

## What Changes

- Add an explicitly invoked `episodic-orchestrator` Codex skill. The main agent
  remains the user's conversational coordinator and delegates substantive work
  through `worker.run`; it does not inspect the project or execute work itself.
- Add a `worker` tool pack whose sole entry point starts one new Codex app thread
  per episode. The caller supplies a small non-interactive execution object; the
  worker loads normal Codex instructions, skills, tools, and configured MCPs for
  that working directory, but never a previous worker conversation.
- Give every worker the complete current context at startup. Context is small
  enough to read as one object, so v1 has no context search, selective-read, or
  partial-update protocol.
- Let a worker include one complete typed replacement for the next episode in its
  strict terminal output. The worker supplies structured content, not YAML and
  not formatting or repair instructions.
- Make the MCP runtime solely responsible for deterministic normalization,
  mechanical repair, strict schema validation, canonical YAML rendering, file
  size enforcement, revision management, and atomic persistence. Ambiguous or
  semantic corrections are rejected rather than guessed.
- Store the current state as one human-inspectable `context.yaml` in OneTool's
  project-state area. Its compact schema covers the goal, current work, durable
  knowledge, unresolved questions, and references to relevant project files.
- Replace token accounting and compaction thresholds with one configurable
  `tools.worker.context_max_kb` setting, defaulting to 16 KB, measured from the
  canonical UTF-8 file.
- Preserve the last valid context after cancellation, worker failure, invalid
  input, oversized input, or interrupted writes. A potentially side-effecting
  worker episode is never retried automatically.

## Capabilities

### New Capabilities

- `episodic-context`: Small structured current-state storage, whole-context worker
  handoff, deterministic MCP-owned processing, a simple KB file-size guard, and
  atomic last-valid-state persistence.
- `tool-worker`: Serialized fresh-thread worker execution through the sole
  `worker.run` tool, explicit fail-closed execution boundaries, terminal
  whole-context submission, and failure handling without automatic replay.
- `skill-episodic-orchestrator`: Explicit main-conversation coordination that
  delegates substantive work to fresh workers.

### Modified Capabilities

- `serve-configuration`: Add strict worker model, effort, and context file-size
  settings through the existing configuration path.
- `serve-skills`: Distribute the episodic orchestrator through the existing skill
  layout with explicit invocation.

## Impact

- Affected systems: a new worker pack, the Codex app-server thread adapter,
  episodic context persistence, worker configuration, skill distribution, tests,
  and user documentation.
- V1 workers accept only non-interactive `never` approval policy, disabled network
  access, and read-only or current-project workspace-write sandboxing. Unsupported
  execution policies fail before startup.
- V1 is deliberately serialized and small: no recursion, scheduling, context
  search, semantic compaction, session artifact store, console outbox, transcript
  database, advanced telemetry, compatibility aliases, or migration path.
- Deferred extensions and their adoption criteria are recorded in `next.md`.
