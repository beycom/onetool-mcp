## ADDED Requirements

### Requirement: Warm reuse requires measured benefit

The project SHALL record a repeatable cold-start baseline and a target for warm
startup before warm runtime is enabled by default. Measurements SHALL distinguish
process initialization, first protocol event, thread start, and total pre-turn
duration without recording prompt or Context content.

#### Scenario: Reuse is evaluated
- **WHEN** cold and warm behavior are compared on representative projects
- **THEN** the evidence SHALL report each startup phase separately
- **AND** default enablement SHALL require a documented material benefit

### Requirement: Reusable state is partitioned by the complete isolation key

A warm runtime SHALL be reusable only for the same canonical project root,
effective approval/sandbox/network/writable-root envelope, and effective MCP
server and credential identities. Partition keys SHALL not contain secret values.

#### Scenario: Project or authority changes
- **WHEN** a later episode has a different project, permission boundary, network mode, writable roots, MCP configuration, or credential identity
- **THEN** it SHALL NOT lease the earlier runtime or transport sessions

#### Scenario: Isolation key matches
- **GIVEN** warm runtime is enabled
- **WHEN** a healthy idle runtime has the exact effective isolation key
- **THEN** the next serialized episode SHALL reuse its process and eligible transports

### Requirement: Every episode still uses a fresh thread

Warm reuse SHALL preserve one new Codex thread for every episode and SHALL delete
that thread during terminal handling. Reusable state SHALL NOT retain thread IDs,
messages, Chat, Context, developer input, tool results, or worker reasoning.

#### Scenario: Two warm episodes share a process
- **WHEN** two serialized episodes reuse one healthy app-server process
- **THEN** they SHALL use distinct thread IDs
- **AND** the first thread SHALL be deleted before the runtime becomes idle

#### Scenario: User answers needs_input
- **WHEN** an answer starts the next episode with the same named Context
- **THEN** any eligible process reuse SHALL still start a fresh thread

### Requirement: Runtime health and idle expiry are explicit

The runtime SHALL perform a bounded health check before each warm lease. An
unhealthy, exited, desynchronized, expired, or stale runtime SHALL be closed and
SHALL NOT execute a worker turn. Idle expiry SHALL use the configured monotonic
duration.

#### Scenario: Health check fails before execution
- **WHEN** an idle runtime fails its pre-lease health check
- **THEN** it SHALL be discarded
- **AND** the runtime SHALL create at most one cold replacement before substantive execution

#### Scenario: Runtime expires while idle
- **WHEN** idle duration reaches the configured expiry
- **THEN** transports and the child process SHALL be closed without affecting any committed Context file

### Requirement: Active work is never replayed on warm-runtime failure

A process or transport failure after substantive execution starts SHALL use the
normal failed/interrupted lifecycle. The runtime SHALL NOT automatically start a
replacement episode or replay work.

#### Scenario: Warm process exits during a turn
- **WHEN** the leased process exits after the turn starts
- **THEN** `worker.run` SHALL report the failure once
- **AND** project, Console, Context, and History handling SHALL follow the foundation failure contract

### Requirement: Shutdown closes only owned warm resources

Server shutdown SHALL close eligible transports and the owned app-server process
within a bounded grace period. Forced termination SHALL target only the resolved
owned child process.

#### Scenario: Server shuts down with an idle runtime
- **WHEN** OneTool begins shutdown
- **THEN** the runtime SHALL stop accepting leases and close all owned warm resources

### Requirement: Cold and warm startup remain distinguishable

Every episode SHALL classify runtime startup as `cold` or `warm` and expose
bounded operational duration measurements without prompts, Context, Console
bodies, file contents, diffs, tool results, or secrets.

#### Scenario: Warm runtime is leased
- **WHEN** an episode reuses a healthy process
- **THEN** its operational measurement SHALL use `warm`
- **AND** cold initialization time SHALL not be attributed to that episode
