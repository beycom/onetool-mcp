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

### Requirement: Worker execution preserves the main agent's capabilities

The strict `execution` object SHALL contain exactly absolute current-project
`cwd`, `approval_policy: never`, and a typed `sandbox` object that reproduces the
main agent's effective `read-only`, `workspace-write`, `danger-full-access`, or
`external-sandbox` boundary. The policy SHALL preserve network access, writable
roots, temporary-directory exclusions, and externally managed network mode where
those fields apply. Other values or unrepresentable restrictions SHALL fail
before worker startup.

#### Scenario: Execution policy is supported
- **WHEN** the explicit execution object represents the main agent's effective permissions
- **THEN** the fresh worker SHALL start with those boundaries
- **AND** Codex SHALL load the same project instructions, skills, tools, plugins, and configured MCPs for `cwd`

#### Scenario: Main agent is unrestricted
- **WHEN** the main agent has unrestricted filesystem and network access
- **THEN** the execution object SHALL use `danger-full-access`
- **AND** the worker SHALL NOT substitute a narrower sandbox

#### Scenario: Main agent uses workspace-write
- **WHEN** the main agent has workspace-write access
- **THEN** the execution object SHALL preserve its complete writable-root list, network access, and temporary-directory exclusions

#### Scenario: Execution policy is unsupported
- **WHEN** the execution object is invalid or cannot be represented by the installed app-server
- **THEN** `worker.run` SHALL return `failed` before starting a worker thread
- **AND** it SHALL NOT substitute a broader or narrower policy

### Requirement: worker.run returns one small terminal result

`worker.run` SHALL always return exactly `session_id`, `status`, and `message`.
`status` SHALL be one of `completed`, `needs_input`, `failed`, or `interrupted`.
The worker-authored terminal schema SHALL permit only `completed` or
`needs_input`, one bounded Status message, and optional complete Context. The MCP
SHALL process and remove Context, add the session ID, and map runtime failure or
caller interruption. The final public `message`, including runtime warnings,
SHALL NOT exceed 1024 UTF-8 bytes and SHALL NOT contain a Console body.

#### Scenario: Worker completes
- **WHEN** the worker produces valid terminal status `completed`
- **THEN** `worker.run` SHALL return the same status with a bounded control receipt and session ID
- **AND** substantial user-facing output SHALL remain in Console rather than the result

#### Scenario: Worker needs user input
- **WHEN** the worker produces valid terminal status `needs_input`
- **THEN** `worker.run` SHALL return that status
- **AND** `message` SHALL contain one direct question for the user

#### Scenario: Worker output is invalid
- **WHEN** worker-authored terminal output does not match its strict schema or exceeds the Status limit
- **THEN** `worker.run` SHALL return `failed`
- **AND** the MCP SHALL NOT ask an agent to repair the output shape

#### Scenario: Runtime failure
- **WHEN** preflight, startup, protocol handling, timeout, output validation, or context commit fails
- **THEN** `worker.run` SHALL return `failed` with a diagnostic message

#### Scenario: Caller interruption
- **WHEN** the active turn is explicitly cancelled or reported interrupted
- **THEN** `worker.run` SHALL return `interrupted`

### Requirement: Worker output follows the six-channel boundary

Only the current Chat request and complete committed Context SHALL be supplied
automatically to a fresh worker. Workers SHALL publish substantial user-facing
answers, reports, evidence, previews, and file references through the existing
Console tool. Workers SHALL apply project deliverables through normal project
file operations. Console, History, Status, Local Changes observations, tool
results, source text, and prior worker messages SHALL NOT become automatic worker
or main-agent input.

#### Scenario: Worker produces a substantial answer
- **WHEN** a worker has user-facing content beyond a bounded Status receipt
- **THEN** it SHALL publish that content through Console
- **AND** the public worker result SHALL NOT duplicate the Console body

#### Scenario: Later episode starts
- **WHEN** a fresh worker starts for an existing session
- **THEN** it SHALL receive only the new Chat request and complete committed Context automatically
- **AND** it SHALL NOT receive Console bodies, History, Status, Local Changes observations, tool results, or prior worker messages

### Requirement: Local Changes are observed mechanically

The MCP SHALL compare the project tree immediately before and after each started
episode using the same VCS-independent rules. It SHALL classify regular project
paths as `created`, `modified`, or `deleted`, including further modifications to
files that were already dirty before the episode. It SHALL exclude `.git`,
OneTool runtime state, configured cache roots, and targets reached only through
symlinks outside the project.

The observer SHALL NOT store file contents or diffs, invoke Git, depend on
Localhist, create snapshots, or roll back filesystem effects.

#### Scenario: Worker changes project files
- **WHEN** the final project fingerprint differs from the pre-episode fingerprint
- **THEN** the MCP SHALL produce sorted project-relative path classifications
- **AND** it SHALL NOT copy file content or diffs into History or Status

#### Scenario: File was already dirty before the episode
- **WHEN** a worker further changes an existing dirty file
- **THEN** the path SHALL still be classified as modified for the episode

#### Scenario: Final scan fails
- **WHEN** the MCP cannot complete the final Local Changes observation
- **THEN** known worker, Console, Context, and filesystem outcomes SHALL remain unchanged
- **AND** Status SHALL include a bounded observation warning

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

#### Scenario: Worker requests user input
- **WHEN** a worker returns `needs_input`
- **THEN** the runtime SHALL commit any valid terminal Context and delete that worker thread before returning the question
- **AND** the user's answer SHALL start a fresh episode and distinct fresh thread with the same session ID

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
