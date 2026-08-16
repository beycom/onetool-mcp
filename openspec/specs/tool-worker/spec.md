# tool-worker Specification

## Purpose

Defines the named-Context worker tool surface, fresh-thread execution boundary,
channel routing, project change observation, cleanup, and terminal results.

## Requirements

### Requirement: The worker pack exposes named-Context operations

The `worker` tool pack SHALL expose exactly `run`, `ctx_select`, `ctx_list`,
`ctx_update`, `ctx_archive`, `asset_create`, `asset_open`, `asset_list`, and
`asset_delete`.

`worker.run` SHALL require nonblank `prompt`, MAY accept a Context name and direct
model or effort override, and SHALL NOT accept project, session, thread, or public
execution-policy parameters. An omitted Context SHALL resolve to `default` for a
direct call; the orchestrator SHALL supply its selected Context explicitly.

The removed names `select`, `list_contexts`, `update_context`, `archive_context`,
`artifact_create`, `artifact_open`, `artifact_list`, and `artifact_delete` SHALL
NOT be exported, aliased, or resolved as worker tools.

#### Scenario: Direct run omits Context
- **WHEN** `worker.run` is invoked without an orchestrator selection or explicit Context
- **THEN** it SHALL use named Context `default`

#### Scenario: Explicit run overrides Chat selection
- **GIVEN** the orchestrator has selected `feature-x`
- **WHEN** one run explicitly names `review-feature-x`
- **THEN** that episode SHALL use `review-feature-x`
- **AND** the orchestrator selection SHALL remain `feature-x`

#### Scenario: Removed operation name is requested
- **WHEN** a caller requests any removed Context or artifact operation name
- **THEN** normal tool discovery or attribute lookup SHALL reject the name
- **AND** the runtime SHALL NOT forward it to a renamed operation

### Requirement: Context operation results are bounded metadata

`worker.ctx_select` SHALL return Context name and whether it created the file.
`worker.ctx_list` SHALL return bounded validated frontmatter metadata and MAY
filter by active or archived status. `worker.ctx_update` SHALL return name,
creation indicator, description, tags, status, and revision.
`worker.ctx_archive` SHALL return name and archived status.

`worker.ctx_select` SHALL NOT persist a project-global or process-global
selection. The orchestrator SHALL retain the returned name as Chat-local
coordinator state; a direct caller SHALL pass that name explicitly on later runs.

No Context operation SHALL return a semantic body, infer tags or description from
a prompt, or silently substitute another Context.

#### Scenario: Missing Context is selected
- **WHEN** `ctx_select` names a valid missing Context
- **THEN** it SHALL create it and return `created: true`

#### Scenario: Contexts are listed
- **WHEN** `ctx_list` is called without a status filter
- **THEN** it SHALL return active and archived Context metadata in stable name order

### Requirement: Management operation diagnostics follow public names

Worker management operation log spans SHALL use `worker.ctx_*` or
`worker.asset_*` names. A failed management operation SHALL return the matching
`ctx_*_failed` or `asset_*_failed` status classifier while preserving the
operation's existing bounded error shape.

#### Scenario: Asset open fails validation
- **WHEN** `worker.asset_open` receives an invalid artifact identifier
- **THEN** it SHALL return status `asset_open_failed`
- **AND** its log span SHALL identify `worker.asset_open`

### Requirement: Every episode uses a fresh worker thread

Each `worker.run` SHALL create one fresh Codex app-server thread and SHALL NOT
resume or supply messages from a prior worker thread. Only one worker call SHALL
be active at a time. A marked worker environment SHALL reject recursive worker
operations.

#### Scenario: Same Context runs another episode
- **WHEN** `worker.run` is called again with the same named Context
- **THEN** it SHALL create a distinct thread
- **AND** it SHALL supply the current request and complete committed Context rather than prior messages

#### Scenario: Concurrent call
- **GIVEN** one worker call is active
- **WHEN** another worker call attempts to start
- **THEN** the second call SHALL fail rather than queue or run concurrently

### Requirement: Worker authority derives from the current project environment

The worker SHALL start in the effective project CWD with non-interactive approval
and SHALL load the same project instructions, skills, tools, plugins, and
configured MCP servers. Its filesystem and network authority SHALL be inherited
from and remain bounded by the calling environment.

The runtime SHALL fail before thread startup when it cannot ensure that the child
cannot broaden the effective authority. It SHALL NOT ask callers to reproduce the
authority through a public `execution` object or silently substitute a broader or
narrower project boundary.

#### Scenario: Effective environment is supported
- **WHEN** the runtime can start a child inside the current enforced boundary
- **THEN** the worker SHALL receive that same effective authority and project CWD

#### Scenario: Effective environment is unrepresentable
- **WHEN** the runtime cannot prove the child remains within the effective authority
- **THEN** the operation SHALL fail before starting a worker thread

### Requirement: worker.run returns one small terminal result

`worker.run` SHALL return exactly `context`, `status`, and `message`. Context SHALL
be the effective Context name. Status SHALL be `completed`, `needs_input`,
`failed`, or `interrupted`. Final message, including runtime warnings, SHALL NOT
exceed 1024 UTF-8 bytes and SHALL NOT contain a Console or Context body.

The worker-authored terminal schema SHALL permit only `completed` or
`needs_input`, one bounded Status message, and an optional complete Context body
replacement. The runtime SHALL process and remove the replacement, add the
effective name, and map runtime failure or interruption.

#### Scenario: Worker completes
- **WHEN** a worker produces valid terminal status `completed`
- **THEN** run SHALL return a bounded control receipt and effective Context name
- **AND** substantial output SHALL remain in Console

#### Scenario: Worker needs input
- **WHEN** a worker produces valid terminal status `needs_input`
- **THEN** run SHALL return one direct bounded question
- **AND** the answer SHALL be sent to a fresh episode using the same Context name

#### Scenario: Worker output is invalid
- **WHEN** terminal output violates its strict schema or Status limit
- **THEN** run SHALL fail without asking an agent to repair the shape

### Requirement: Worker output follows the six-channel boundary

Only the current Chat request and complete selected Context body SHALL be supplied
automatically to a fresh worker. Workers SHALL publish substantial user-facing
answers, reports, evidence, previews, and file references through the existing
Console publisher and apply project deliverables through normal file operations.

Console, History, Status, Local Changes observations, tool results, source text,
and prior worker messages SHALL NOT become automatic worker or main-agent input.

#### Scenario: Worker produces substantial output
- **WHEN** user-facing content exceeds a bounded Status receipt
- **THEN** the worker SHALL publish it through Console
- **AND** run SHALL NOT duplicate the Console body

#### Scenario: Later episode starts
- **WHEN** a fresh worker starts with an existing named Context
- **THEN** it SHALL receive only the new request and complete selected Context automatically
- **AND** it SHALL not receive another Context or non-input channel

### Requirement: Local Changes are observed mechanically

The runtime SHALL compare the effective project tree immediately before and after
each started episode using the same VCS-independent rules. It SHALL classify
regular project paths as created, modified, or deleted, including further changes
to files already dirty before the episode. It SHALL exclude `.git`, OneTool state,
configured cache roots, and targets reached only through symlinks outside the
project.

The observer SHALL NOT store file contents or diffs, invoke Git, depend on
Localhist, create snapshots, or roll back filesystem effects.

#### Scenario: Worker changes project files
- **WHEN** the final project fingerprint differs from the baseline
- **THEN** History SHALL receive sorted project-relative path classifications
- **AND** no file content or diff SHALL enter History or Status

#### Scenario: Final scan fails
- **WHEN** final Local Changes observation cannot complete
- **THEN** known worker, Console, Context, and filesystem outcomes SHALL remain unchanged
- **AND** Status SHALL include a bounded observation warning

### Requirement: Completed worker threads are disposed

After terminal and Context handling, the runtime SHALL delete the worker thread
and SHALL never reuse it. The runtime SHALL confirm deletion support before
starting a worker.

#### Scenario: Worker requests input
- **WHEN** a worker returns `needs_input`
- **THEN** the runtime SHALL process Context and delete that thread before returning
- **AND** the answer SHALL start a distinct thread with the same Context name

#### Scenario: Thread deletion fails
- **WHEN** cleanup fails after worker and Context outcomes are known
- **THEN** those outcomes SHALL remain unchanged
- **AND** Status SHALL include one bounded cleanup warning

### Requirement: Failed episodes are not replayed automatically

The runtime SHALL NOT automatically retry a failed, interrupted, or potentially
side-effecting worker episode.

#### Scenario: Episode fails after starting
- **WHEN** an active worker episode fails
- **THEN** run SHALL return the failure once
- **AND** the runtime SHALL NOT start a replacement episode automatically
