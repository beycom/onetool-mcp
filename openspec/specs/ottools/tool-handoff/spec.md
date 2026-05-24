# ottools/tool-handoff Specification

## Purpose

Defines the `handoff` tool pack for submitting focused Codex worker tasks,
checking results, and managing local handoff runtime artifacts.

---

## Requirements

### Requirement: Submit Codex Worker Task
The `handoff` pack SHALL expose `handoff.submit(task=..., context="", model=None, reasoning_effort=None, timeout=None)` to submit exactly one focused Codex worker task and return immediately with task metadata.

#### Scenario: Submit accepted task
- **WHEN** `handoff.submit(task="Inspect auth flow")` is called while queue capacity is available
- **THEN** the result SHALL include a handoff id, `status: "submitted"`, `deduped: false`, `remaining_count`, and `queue_empty`

#### Scenario: Resolve submit defaults
- **WHEN** `handoff.submit()` omits model, reasoning effort, or timeout
- **THEN** the task SHALL use configured defaults from the `handoff.defaults` config section

#### Scenario: Single task only
- **WHEN** handoff submission is used
- **THEN** the public API SHALL accept one `task` string per call
- **AND** it SHALL NOT support a `tasks=[...]` batch submission API in v1

#### Scenario: Reject empty task
- **WHEN** `handoff.submit(task="")` is called
- **THEN** the result SHALL report a clear validation error
- **AND** no worker task SHALL be submitted

#### Scenario: Reject queue full
- **WHEN** `handoff.submit()` is called while the configured `max_queue_depth` is reached
- **THEN** the result SHALL report a clear queue-full error
- **AND** no worker task SHALL be submitted

#### Scenario: Deduplicate outstanding task
- **WHEN** `handoff.submit()` receives a task, context, model, and reasoning effort matching an outstanding task inside `dedupe_window_seconds`
- **THEN** the result SHALL return the existing handoff id
- **AND** the result SHALL include `deduped: true`

### Requirement: Check Worker Results
The `handoff` pack SHALL expose `handoff.check(ids=None, wait=False, timeout=None)` to return completed worker results and outstanding queue state.

#### Scenario: Non-blocking check
- **WHEN** `handoff.check(wait=False)` is called
- **THEN** the result SHALL return immediately with `ready`, `completed_count`, `remaining_count`, `remaining_ids`, `index_path`, `queue_empty`, and `timed_out`

#### Scenario: Timed check returns completed results
- **WHEN** `handoff.check(wait=True, timeout=N)` is called and a matching task completes before the timeout
- **THEN** the result SHALL include that task in `ready`
- **AND** the ready item SHALL include id, status, task, summary, result path, timing data when available, model, and raw log path when available

#### Scenario: Timed check returns partial results on timeout
- **WHEN** `handoff.check(wait=True, timeout=N)` times out after some matching tasks complete
- **THEN** the result SHALL include completed tasks in `ready`
- **AND** the result SHALL include outstanding task state
- **AND** the result SHALL include `timed_out: true`

#### Scenario: Check returns file pointers
- **WHEN** a completed result is returned by `handoff.check()`
- **THEN** the result SHALL include result file pointers and short summaries by default
- **AND** the full result body SHALL NOT be returned by default
- **AND** returned runtime paths SHALL be OneTool-resolved paths that the main agent can open directly

#### Scenario: Completed task no longer outstanding
- **WHEN** a completed task has been returned by `handoff.check()`
- **THEN** later queue state SHALL NOT report that task as outstanding

### Requirement: Read Task Result Index
The `handoff` pack SHALL expose `handoff.read_index(status=None, limit=50)` to inspect recent task/result index entries from `index.jsonl`.

#### Scenario: Read recent index entries
- **WHEN** `handoff.read_index()` is called and index entries exist
- **THEN** the result SHALL include `index_path` and recent entries
- **AND** entries SHALL be capped by `limit`

#### Scenario: Filter index entries by status
- **WHEN** `handoff.read_index(status="completed")` is called
- **THEN** returned entries SHALL only include matching status values

#### Scenario: Missing index is empty
- **WHEN** `handoff.read_index()` is called before `index.jsonl` exists
- **THEN** the result SHALL treat the index as empty
- **AND** the call SHALL NOT start the Codex app-server

### Requirement: Search Task Result Index
The `handoff` pack SHALL expose `handoff.search_index(query=..., status=None, limit=20)` to search task, summary, status, id, and result path fields in `index.jsonl`.

#### Scenario: Search index entries
- **WHEN** `handoff.search_index(query="auth")` is called
- **THEN** the result SHALL include matching entries and `index_path`
- **AND** matching SHALL use case-insensitive substring matching

#### Scenario: Search index with status filter
- **WHEN** `handoff.search_index(query="auth", status="completed")` is called
- **THEN** returned matches SHALL satisfy both the query and status filter

#### Scenario: Search uses local index only
- **WHEN** `handoff.search_index()` is called
- **THEN** the implementation SHALL use local file parsing only
- **AND** it SHALL NOT require a database, separate search index, or Codex app-server startup

### Requirement: Cancel Worker Tasks
The `handoff` pack SHALL expose `handoff.cancel(ids=None)` to request best-effort cancellation for outstanding tasks.

#### Scenario: Cancel outstanding tasks
- **WHEN** `handoff.cancel(ids=[...])` is called for outstanding task ids
- **THEN** the implementation SHALL attempt app-server turn interruption when available
- **AND** the result SHALL report ids in `cancel_requested`, `cancelled`, or `cancel_unknown`

#### Scenario: Cancel all outstanding tasks
- **WHEN** `handoff.cancel(ids=None)` is called
- **THEN** the implementation SHALL target all outstanding tasks

#### Scenario: Cancel already finished task
- **WHEN** `handoff.cancel()` is called for a task that already completed
- **THEN** the result SHALL report the task as already finished
- **AND** it SHALL NOT mark the task cancelled

#### Scenario: Cancel unknown task id
- **WHEN** `handoff.cancel(ids=["missing"])` is called
- **THEN** the result SHALL report the id in `not_found`
- **AND** the call SHALL NOT raise a user-facing exception

#### Scenario: Cancellation does not restart healthy runner
- **WHEN** cancellation cannot be confirmed quickly and the runner is otherwise healthy
- **THEN** the result SHALL report `cancel_unknown`
- **AND** the implementation SHALL NOT restart the app-server as normal cancellation behavior

### Requirement: Clear Handoff Runtime State
The `handoff` pack SHALL expose `handoff.clear(include_logs=False)` to clear in-memory queue state and optionally delete runtime artifacts.

#### Scenario: Clear keeps logs by default
- **WHEN** `handoff.clear()` is called
- **THEN** outstanding tasks SHALL be cancelled or marked cleared
- **AND** in-memory registries SHALL be cleared
- **AND** result files, `index.jsonl`, `state.json`, and raw logs SHALL be kept

#### Scenario: Clear includes logs
- **WHEN** `handoff.clear(include_logs=True)` is called
- **THEN** result files, `index.jsonl`, `state.json`, and raw logs SHALL be deleted
- **AND** the result SHALL report cleared counts and `queue_empty`

#### Scenario: Clear avoids unnecessary app-server startup
- **WHEN** `handoff.clear(include_logs=True)` can complete from local state and files
- **THEN** the call SHALL NOT start the Codex app-server

### Requirement: Run Embedded Codex App Server Lazily
The handoff runtime SHALL use one embedded `codex app-server --listen stdio://` process owned by the root OneTool MCP process and SHALL start it lazily only when a handoff call needs the runner.

#### Scenario: Normal startup does not start app-server
- **WHEN** normal OneTool MCP startup completes
- **THEN** the handoff app-server SHALL NOT be started only because the pack is available

#### Scenario: Submit starts app-server lazily
- **WHEN** `handoff.submit()` is called and the app-server is not running
- **THEN** the handoff runtime SHALL start `codex app-server --listen stdio://`

#### Scenario: Read-only index helpers do not start app-server
- **WHEN** `handoff.read_index()` or `handoff.search_index()` is called
- **THEN** the handoff runtime SHALL NOT start the app-server

#### Scenario: Readiness cache used
- **WHEN** app-server or direct API readiness has been checked recently
- **THEN** subsequent handoff calls SHALL reuse cached readiness until `ready_check_cache_seconds` expires or a failure invalidates it

#### Scenario: Websocket transport not used
- **WHEN** the handoff runtime starts the Codex runner
- **THEN** it SHALL use stdio transport
- **AND** it SHALL NOT use websocket transport

### Requirement: Run Focused Workers
The handoff runtime SHALL submit focused Codex worker turns against the current project working directory.

#### Scenario: Worker task uses current project cwd
- **WHEN** a worker task is submitted
- **THEN** the worker turn SHALL run against the current project working directory

#### Scenario: Worker prompt delegates one focused task
- **WHEN** a worker prompt is rendered in v1
- **THEN** the prompt SHALL delegate one focused task
- **AND** worker inspection or edit behavior SHALL be determined by the delegated task

### Requirement: Bound Runtime Resources
The handoff runtime SHALL enforce configured resource limits to protect main OneTool latency and memory use.

#### Scenario: Enforce queue and concurrency limits
- **WHEN** handoff tasks are submitted
- **THEN** the runtime SHALL enforce `max_queue_depth` and `max_workers`

#### Scenario: Cap timed check wait
- **WHEN** `handoff.check(wait=True, timeout=N)` is called with a timeout above `max_check_wait_seconds`
- **THEN** the effective wait SHALL be capped by `max_check_wait_seconds`

#### Scenario: Cap returned outstanding ids
- **WHEN** more outstanding task ids exist than `max_remaining_ids_returned`
- **THEN** returned `remaining_ids` SHALL be capped
- **AND** `remaining_count` SHALL remain authoritative

#### Scenario: Bound raw logs
- **WHEN** raw app-server events are captured
- **THEN** raw logs and in-memory raw event buffers SHALL be bounded by `max_raw_log_bytes`
- **AND** raw logs SHALL be flushed on completion by default rather than every streamed event

### Requirement: Handoff Worker Pool Configuration
The handoff tool SHALL expose a `tools.handoff.limits.max_workers` config key that limits how many queued tasks can be picked up by workers at the same time.

#### Scenario: Worker limit reached
- **WHEN** the number of running handoff workers equals `tools.handoff.limits.max_workers`
- **THEN** newly submitted tasks SHALL remain queued until a worker finishes

#### Scenario: Queue depth remains separate
- **WHEN** submitted handoff tasks exceed `tools.handoff.limits.max_queue_depth`
- **THEN** handoff SHALL reject the submission as queue-full independently of worker count

### Requirement: Write Result Files and Index
The handoff runtime SHALL write each terminal task result to one Markdown file with YAML frontmatter and maintain an atomic JSONL index of task status, summaries, and result paths.

#### Scenario: Completed task writes result file
- **WHEN** a task reaches a terminal result with output
- **THEN** the runtime SHALL write one Markdown result file under the configured result directory
- **AND** frontmatter SHALL include task id, status, original task request, summary, model, timestamps when available, duration when available, and raw log path when available

#### Scenario: Index updated after result file
- **WHEN** a terminal task result is persisted
- **THEN** the result file SHALL be written atomically before `index.jsonl` points to it
- **AND** `index.jsonl` SHALL be rewritten atomically

#### Scenario: Running task represented in index
- **WHEN** a task is outstanding
- **THEN** `index.jsonl` SHALL be able to represent its id, status, task, summary, result path, and timestamps when available

### Requirement: Recover State After Restart
The handoff runtime SHALL preserve terminal inspection artifacts and mark non-terminal prior tasks as abandoned after root OneTool restart.

#### Scenario: Restart abandons non-terminal tasks
- **WHEN** the root OneTool process restarts with non-terminal task state present
- **THEN** those tasks SHALL be marked `abandoned`
- **AND** the implementation SHALL NOT attempt app-server task resumption

#### Scenario: Terminal artifacts remain inspectable
- **WHEN** the root OneTool process restarts
- **THEN** existing terminal result files and `index.jsonl` entries SHALL remain inspectable

### Requirement: Clean Up Old Runtime Files
The handoff runtime SHALL support simple age-based cleanup of old terminal runtime artifacts when the handoff runtime initializes.

#### Scenario: Cleanup removes old terminal artifacts
- **WHEN** cleanup is enabled and old terminal result artifacts exceed `cleanup.max_age_days`
- **THEN** terminal result files, raw logs, stale index rows, and stale terminal state entries SHALL be removed

#### Scenario: Cleanup preserves active tasks
- **WHEN** cleanup runs while outstanding or running task state exists
- **THEN** outstanding and running task state SHALL be preserved

#### Scenario: Cleanup preserves retained raw logs
- **WHEN** cleanup retains a result file that references a raw log
- **THEN** that raw log SHALL be preserved

### Requirement: Configure Handoff Runtime
The `handoff` pack SHALL define a Pydantic configuration model loaded from the `tools.handoff` section using `get_tool_config()`.

#### Scenario: Load handoff config
- **WHEN** handoff tools are called
- **THEN** config SHALL be read from `tools.handoff` using `get_tool_config()`
- **AND** runtime paths SHALL be resolved with `resolve_ot_path()`

#### Scenario: Unknown config rejected
- **WHEN** unsupported handoff config values are provided
- **THEN** config validation SHALL fail clearly
- **AND** no legacy aliases or compatibility shims SHALL be accepted

#### Scenario: Config fields are bounded
- **WHEN** numeric handoff config values are loaded
- **THEN** configured limits, timeouts, and cleanup age values SHALL be validated with explicit bounds

#### Scenario: Worker prompt configurable
- **WHEN** `defaults.worker_prompt` is configured
- **THEN** worker task prompts SHALL be rendered from that single template
- **AND** the template SHALL support at least `{task}` and `{context}` placeholders

#### Scenario: Lazy startup not configurable
- **WHEN** handoff config is loaded
- **THEN** app-server startup timing SHALL remain fixed lazy behavior
- **AND** no v1 config knob SHALL start the app-server during normal OneTool MCP startup

### Requirement: Handoff Worker Defaults
The handoff tool SHALL keep worker execution defaults under `tools.handoff.defaults`, including model, reasoning effort, timeout, and worker prompt.

#### Scenario: Worker reasoning effort override
- **WHEN** `tools.handoff.defaults.reasoning_effort` is configured
- **THEN** handoff SHALL use that value as the default reasoning effort for delegated workers

### Requirement: Optional Worker MCP Access
The handoff tool SHALL treat MCP server setup for workers as optional.

#### Scenario: MCP setup unavailable
- **WHEN** a worker can start but MCP server setup is unavailable
- **THEN** handoff SHALL start the worker without MCP servers
- **AND** the submit result SHALL include a warning that MCP tools could not be enabled

### Requirement: Provide Child OneTool Access
The handoff runtime SHALL give delegated Codex tasks lean OneTool tool access through a child MCP process that forwards to the root OneTool direct API.

#### Scenario: Worker receives child OneTool access
- **WHEN** a worker task is submitted
- **THEN** worker configuration SHALL expose only the normal OneTool `run` surface through MCP server `onetool`, tool `run`
- **AND** the child MCP server SHALL be launched as `onetool child --url <parent-url> --ot-dir <parent-ot-dir>`

#### Scenario: Recursive handoff disabled for workers
- **WHEN** child OneTool access is configured
- **THEN** recursive access to the `handoff` pack SHALL be disabled

#### Scenario: Child runtime unavailable
- **WHEN** child runtime setup is unavailable but the Codex worker can start
- **THEN** `handoff.submit()` SHALL launch the worker without MCP servers
- **AND** the submit result SHALL include a warning that MCP tools could not be enabled

### Requirement: Return Structured Runtime Errors
The handoff public tools SHALL return plain error strings or structured error results for expected runtime failures.

#### Scenario: Missing Codex CLI
- **WHEN** Codex app-server startup fails because the local Codex CLI is unavailable or unauthenticated
- **THEN** the handoff tool result SHALL contain a clear startup error
- **AND** the public tool function SHALL NOT raise an unhandled user-facing exception

#### Scenario: Unknown id
- **WHEN** a public handoff tool receives an unknown task id
- **THEN** the result SHALL report the unknown id in a structured way
- **AND** the public tool function SHALL NOT raise an unhandled user-facing exception

#### Scenario: Native return types
- **WHEN** a handoff public tool returns a structured result
- **THEN** the result SHALL be returned as a native Python mapping or sequence
- **AND** the public tool SHALL NOT manually serialize the result to JSON text

### Requirement: Declare Codex CLI Requirement
The handoff pack SHALL declare its external `codex` CLI dependency using standard OneTool tool requirement metadata.

#### Scenario: Dependency metadata available
- **WHEN** the handoff pack is inspected by OneTool tooling
- **THEN** the pack metadata SHALL include the external `codex` CLI requirement
- **AND** the requirement SHALL include an actionable install or authentication hint

### Requirement: Report Performance Timings
The handoff runtime SHALL record useful timing fields for task and check performance when available.

#### Scenario: Task timing fields returned
- **WHEN** a task result is completed
- **THEN** persisted metadata or result metadata SHALL include submitted time, started time, completed time, submit-to-start duration, and run duration when available

#### Scenario: Check timing fields recorded
- **WHEN** completed work is returned by `handoff.check()`
- **THEN** completed-to-checked delay and check duration SHALL be recorded when available

### Requirement: Document Handoff Tool Reference
The implementation SHALL add user-facing handoff tool reference documentation following the standard OneTool tool reference structure.

#### Scenario: Reference document created
- **WHEN** the handoff pack is implemented
- **THEN** `docs/reference/tools/handoff.md` SHALL document the pack
- **AND** it SHALL include Highlights, Functions, Key Parameters, Requires, Configuration, and Examples sections

#### Scenario: No CLI section
- **WHEN** the handoff reference document is created
- **THEN** it SHALL NOT include a CLI section because v1 does not ship `onetool handoff` subcommands
