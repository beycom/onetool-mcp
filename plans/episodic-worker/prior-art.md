# Archived Handoff Prior Art

This file records useful evidence from the removed handoff implementation without
making that implementation part of the current change. It is non-normative. The
proposal, design, delta specifications, and tasks remain the sources of approved
behavior and implementation work.

## Source

- Archived branch:
  `https://github.com/beycom/onetool-mcp/tree/archive/feature/handoff`
- Reviewed commit: `da3f22141744cf14b2e6ab1226b9a5e86dff70b5`
- Initial handoff implementation: `0767aad8`
- Parent-runtime forwarding correction: `33af3e10`
- Removal from the main line: `0407dd5f`

The archive added roughly 3,700 lines across an asynchronous task queue, Codex
app-server adapter, child OneTool runtime, result files, index and search tools,
cleanup, skill instructions, specifications, and tests. It was removed as one
surface after the child-runtime design grew across the CLI, Direct API, tool pack,
storage, and documentation.

The current change solves a narrower problem: one serialized fresh worker per
episode with one small MCP-managed context file. Nothing should be cherry-picked
wholesale. Individual lessons must pass the classification below.

## Selection Rules

An archived idea is useful only when it:

1. directly supports fresh-thread execution or reliable context handoff;
2. remains valid against the installed Codex app-server protocol;
3. does not reintroduce queues, result databases, or a second execution policy;
4. has a clear destination in design, observable specifications, or tasks; and
5. is smaller and clearer than implementing the current contract directly.

Protocol details must be checked against the current Codex version. Official
Codex app-server documentation states that generated TypeScript and JSON schemas
are version-specific:
`https://developers.openai.com/codex/app-server/`.

## Retain

| Lesson | Archive evidence | Destination |
|---|---|---|
| Isolated app-server adapter | `src/ot/handoff/codex_runner.py:55` | Design |
| Required connection handshake | `src/ot/handoff/codex_runner.py:163` | Adapter tests |
| Fresh thread and turn lifecycle | `src/ot/handoff/codex_runner.py:404` | Design and specs |
| Terminal output fallbacks | `src/ot/handoff/codex_runner.py:227` | Tasks and tests |
| Distinct terminal failures | `src/ot/handoff/codex_runner.py:354`, `:516` | Specs and tests |
| Strict configuration | `src/ot/handoff/models.py:41` | Specs and tests |
| Atomic beside-file replacement | `src/ot/handoff/results.py:32` | Context tests |
| High-signal worker output | `src/ot/handoff/default_worker_prompt.md:1` | Skill tasks |
| Fake app-server harness | `tests/ottools/unit/tools/test_handoff.py:120` | Adapter tests |
| Quality and cost comparison | `tests/explore/compare-handoff.md:198` | Evaluation tasks |

## Adapt

### Execution policy

The archive hard-coded `approvalPolicy: "never"` and `sandbox: "read-only"` in
`src/ot/handoff/codex_runner.py:414`. That is incompatible with the current
contract, where a worker may make changes when authorized and must inherit the
user's execution boundaries.

The new adapter must derive effective working directory, approval, sandbox or
permission profile, instructions, skills, tools, and MCP access from the parent.
If it cannot represent the effective policy with the installed protocol, it must
fail before starting the worker rather than silently widening or replacing the
policy.

### Thread lifetime

The archive sent `ephemeral: true` to `thread/start` at
`src/ot/handoff/codex_runner.py:421`. Current official documentation describes
ephemeral creation for `thread/fork`, while generated schemas are tied to the
installed Codex version. The old request shape must not be treated as current.

V1 uses the current `thread/delete` method after capturing the terminal result and
committing or discarding staged context. The adapter verifies that method exists
in the installed app-server schema before starting a worker. Cleanup failure is
reported without changing the episode outcome, and the thread is never resumed.

### MCP access

The archive created a restricted `onetool child` process and forwarded signed
requests to a parent Direct API in `src/ot/handoff/child_proxy.py:58`. That surface
was later removed by `0407dd5f` and must not return.

The new worker uses the normal configured MCP environment inherited through
Codex. Required MCP startup failure should fail clearly rather than silently run
a worker that cannot perform the requested task.

### Context input

The archive interpolated an untyped `context: str` into the worker prompt through
`src/ot/handoff/default_worker_prompt.md:15`. The current design replaces that
with the complete parsed context object, delimited as state data. No raw YAML or
unvalidated prompt fragment is accepted as the context write interface.

### Cancellation and timeout

The archive's `turn/interrupt` and timeout handling are useful protocol examples,
but the surrounding polling and cancellation buckets are not. V1 needs only one
active call, one terminal outcome, discarded staged context after interruption,
and no automatic replay.

### Worker prompt

The archive's compact-output rules are useful, but its instruction not to ask
follow-up questions conflicts with episodic execution. A worker must be able to
return a concise, explicit request for user input when progress genuinely depends
on it.

## Defer

The following archived features are possible follow-ons, not v1 requirements:

| Archived feature | Current deferred destination |
|---|---|
| Result Markdown files and raw event logs | `next.md` session artifact store and console outbox. |
| Local JSONL result index | `next.md` session artifact store. |
| Index substring search | `next.md` selective reads and deterministic search. |
| Submission deduplication | `next.md` retry and recovery policies if a real duplicate-execution problem emerges. |
| Age-based artifact cleanup | `next.md` session artifact lifecycle. |
| Warm app-server readiness caching | `next.md` warm runtime and connection reuse. |
| Raw token and timing capture | `next.md` advanced telemetry. |

These mappings preserve the ideas without copying their old APIs or storage
contracts into the current design.

## Reject

- The public `handoff.submit`, `check`, `cancel`, `clear`, `read_index`, and
  `search_index` surface. The new public entry point is serialized `worker.run`.
- The `onetool child` CLI and signed Direct API forwarding path. It creates a
  second runtime surface and was explicitly removed.
- The queue record, task IDs, dedupe hash, persistent task-state JSON, and restart
  transition to `abandoned`. V1 has one synchronous episode and one context
  revision.
- Automatic fallback to a worker without required MCP tools. Missing required
  capability must be visible before substantive work begins.
- Archived model names, effort defaults, app-server request fields, and config
  key shapes. They are historical values, not current contracts.
- Treating result files or raw logs as hidden continuation context. Only the
  validated context object is supplied automatically to a later worker.

## Reusable Test Evidence

The archived fake app-server approach should inform, but not be copied blindly
into, the future tasks. The useful test inventory is:

1. reject requests before `initialize` and verify the client sends `initialized`;
2. create a distinct thread ID for every `worker.run` and never call
   `thread/resume`;
3. start exactly one turn with the current request and complete parsed context;
4. map `turn/completed` statuses `completed`, `interrupted`, and `failed` into the
   documented worker result;
5. recover the final worker message when completed turn items are absent but
   streamed final-answer events exist;
6. surface startup, malformed response, missing thread ID, missing turn ID,
   process exit, and request timeout errors deterministically;
7. send `turn/interrupt` on cancellation and preserve the last committed context;
8. verify parent working directory, approval, sandbox or permission profile,
   instructions, skills, tools, and MCP availability are preserved;
9. fail before `thread/start` when the parent execution restrictions cannot be
   represented safely;
10. verify completed worker threads follow the selected supported disposal policy;
11. keep invalid or absent context candidates from advancing the revision; and
12. run a small live smoke test separately from deterministic CI tests.

The adapter tests must use schemas and event shapes supported by the installed
Codex version. They should not preserve undocumented archive fields for
compatibility.

## Evaluation Evidence

The archived exploratory comparison correctly evaluated answer quality rather
than assuming delegation was better. A future evaluation should compare direct
and episodic execution on the same tasks and record:

- valid findings and false positives;
- relative recall across confirmed findings;
- evidence quality and missed high-impact issues;
- wall time and time to terminal result;
- model input, cached input, output, and reasoning tokens when available; and
- main-agent coordination overhead.

The core change does not depend on these metrics, so the evaluation belongs in
tasks after the context and worker contracts are implemented.

## Promotion Rules

- Add nothing from this file to `proposal.md` unless it changes the user-facing
  purpose or v1 scope.
- Add something to `design.md` only when it changes a durable architectural
  decision or security boundary.
- Add observable success, failure, permission, and persistence behavior to delta
  specifications.
- Add protocol calls, archive file references, fake-server cases, and evaluation
  mechanics to tasks.
- Keep deferred product concepts in `next.md` and detailed historical evidence in
  this file.
