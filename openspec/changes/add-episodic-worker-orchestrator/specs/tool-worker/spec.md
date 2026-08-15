## ADDED Requirements

### Requirement: worker.run uses explicit session continuation

The `worker` tool pack SHALL expose only `worker.run`, with required `prompt` and
`execution` plus optional `session_id`, `model`, and `effort`. The first call for
a main conversation SHALL omit `session_id`; the MCP SHALL create and return an
opaque session ID under the current project-state root.

#### Scenario: Start a new episodic session
- **WHEN** `worker.run` is called without `session_id`
- **THEN** the MCP SHALL create a new opaque session under the current project-state root
- **AND** the result SHALL return its session ID

#### Scenario: Continue an episodic session
- **GIVEN** a session ID exists under the current project-state root
- **WHEN** `worker.run` is called with that ID
- **THEN** the call SHALL use that session's committed context

#### Scenario: Supplied session is unavailable
- **WHEN** `worker.run` receives a session ID that does not exist under the current project-state root
- **THEN** it SHALL return `failed` rather than create, guess, or find another session

### Requirement: Every episode uses a fresh worker thread

Each `worker.run` call SHALL create one fresh Codex app-server thread and one
turn. It SHALL NOT resume or provide messages from a previous worker thread.
Only one worker call SHALL be active at a time. `worker.run` SHALL reject calls
from the marked worker environment, so a worker cannot recurse.

#### Scenario: Same session runs another episode
- **WHEN** `worker.run` is called again with an existing session ID
- **THEN** it SHALL create a distinct new thread
- **AND** it SHALL supply the current request and complete committed context instead of earlier worker messages

#### Scenario: Concurrent call
- **GIVEN** one `worker.run` call is active
- **WHEN** another call attempts to start
- **THEN** the second call SHALL be rejected rather than queued or run concurrently

#### Scenario: Recursive call
- **WHEN** an active worker attempts to call `worker.run`
- **THEN** the MCP SHALL reject the call without starting another worker

### Requirement: Worker execution uses a small fail-closed policy

The strict `execution` object SHALL contain exactly absolute current-project
`cwd`, `approval_policy: never`, and `sandbox` set to `read-only` or
`workspace-write`. Network access SHALL be disabled; workspace writes SHALL be
limited to `cwd`. Other values or unrepresentable restrictions SHALL fail before
worker startup.

#### Scenario: Execution policy is supported
- **WHEN** the explicit execution object matches the supported v1 policy
- **THEN** the fresh worker SHALL start with those boundaries
- **AND** Codex SHALL load normal instructions, skills, tools, and configured MCPs for `cwd`

#### Scenario: Execution policy is unsupported
- **WHEN** the execution object is invalid or cannot be represented by the installed app-server
- **THEN** `worker.run` SHALL return `failed` before starting a worker thread
- **AND** it SHALL NOT substitute a broader policy

### Requirement: worker.run returns one small terminal result

`worker.run` SHALL always return exactly `session_id`, `status`, and `message`.
`status` SHALL be one of `completed`, `needs_input`, `failed`, or `interrupted`.
The worker-authored terminal schema SHALL permit only `completed` or
`needs_input`, one message, and optional complete context. The MCP SHALL process
and remove context, add the session ID, and map runtime failure or caller
interruption.

#### Scenario: Worker completes
- **WHEN** the worker produces valid terminal status `completed`
- **THEN** `worker.run` SHALL return the same status with its message and session ID

#### Scenario: Worker needs user input
- **WHEN** the worker produces valid terminal status `needs_input`
- **THEN** `worker.run` SHALL return that status
- **AND** `message` SHALL contain one direct question for the user

#### Scenario: Worker output is invalid
- **WHEN** worker-authored terminal output does not match its strict schema
- **THEN** `worker.run` SHALL return `failed`
- **AND** the MCP SHALL NOT ask an agent to repair the output shape

#### Scenario: Runtime failure
- **WHEN** preflight, startup, protocol handling, timeout, output validation, or context commit fails
- **THEN** `worker.run` SHALL return `failed` with a diagnostic message

#### Scenario: Caller interruption
- **WHEN** the active turn is explicitly cancelled or reported interrupted
- **THEN** `worker.run` SHALL return `interrupted`

### Requirement: Completed worker threads are disposed

After capturing the terminal result and committing or preserving context,
the runtime SHALL call the installed app-server's `thread/delete` operation and
SHALL never reuse that thread. The runtime SHALL confirm that operation is
available before starting a worker.

#### Scenario: Thread deletion is unsupported
- **WHEN** the installed generated app-server schema lacks `thread/delete`
- **THEN** `worker.run` SHALL return `failed` before starting a worker

#### Scenario: Thread deletion succeeds
- **WHEN** terminal handling and context handling finish
- **THEN** the runtime SHALL delete the worker thread
- **AND** no later episode SHALL resume it

#### Scenario: Thread deletion fails
- **WHEN** cleanup fails after the episode outcome and context outcome are known
- **THEN** the runtime SHALL keep those outcomes unchanged
- **AND** it SHALL append one cleanup warning to `message`
- **AND** it SHALL never reuse the thread

### Requirement: Failed episodes are not replayed automatically

The runtime SHALL NOT automatically retry a failed, interrupted, or potentially
side-effecting worker episode.

#### Scenario: Episode fails after starting
- **WHEN** an active worker episode fails
- **THEN** `worker.run` SHALL return the failure once
- **AND** the runtime SHALL NOT start a replacement episode automatically
