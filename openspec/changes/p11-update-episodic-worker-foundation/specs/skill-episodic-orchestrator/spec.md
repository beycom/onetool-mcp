## ADDED Requirements

### Requirement: The orchestrator is an explicit coordinator

The `episodic-orchestrator` skill SHALL activate only when explicitly invoked.
While active, the main agent SHALL coordinate the user conversation and delegate
substantive inspection, planning, editing, execution, and verification through
`worker.run` rather than performing that work itself.

#### Scenario: Skill is not invoked
- **WHEN** the user has not explicitly invoked `episodic-orchestrator`
- **THEN** the skill SHALL NOT change the main agent's normal behavior

#### Scenario: Skill is invoked
- **WHEN** the user explicitly invokes `episodic-orchestrator`
- **THEN** the main agent SHALL pass the current request and supported execution policy to `worker.run`
- **AND** substantive project work SHALL remain the worker's responsibility

### Requirement: The orchestrator maintains only the session handle

For an invoked workflow, the main agent SHALL omit `session_id` on its first
`worker.run` call, retain the returned ID as its only episodic session state, and
supply that same ID on later calls in the same main conversation.

The main agent SHALL use `approval_policy: never` and reproduce its effective
read-only, workspace-write, danger-full-access, or external sandbox in the typed
`sandbox` object, including network access, writable roots, and temporary-directory
exclusions where applicable. The worker SHALL use the same project instructions,
skills, tools, plugins, and configured MCPs as the main agent. If the main agent
cannot represent its current environment exactly, it SHALL report that the
workflow is unsupported rather than invoking the worker with different authority.

#### Scenario: First delegated episode
- **WHEN** the orchestrator delegates the first request in its current workflow
- **THEN** it SHALL omit `session_id` and retain the returned value

#### Scenario: Follow-up episode
- **WHEN** the user provides a follow-up request or answer in the same workflow
- **THEN** the orchestrator SHALL call `worker.run` with the retained session ID
- **AND** it SHALL NOT discover or infer a different session

### Requirement: The orchestrator relays only bounded Status

The main agent SHALL relay only the bounded `worker.run` Status receipt,
diagnostic, or question. It SHALL NOT request, read, reproduce, or summarize
Context or Console bodies. Substantial completed output SHALL reach the user
through Console. For `needs_input`, the main agent SHALL ask the single returned
question and use the user's answer as the next Chat prompt in the same session.

#### Scenario: Worker reaches a terminal outcome
- **WHEN** `worker.run` returns `completed`, `failed`, or `interrupted`
- **THEN** the main agent SHALL report its bounded Status message
- **AND** it SHALL NOT copy Console or Context into the main conversation

#### Scenario: Worker requires user input
- **WHEN** `worker.run` returns `needs_input`
- **THEN** the main agent SHALL present its question to the user
- **AND** the user's answer SHALL become the next `worker.run` prompt for the same session
- **AND** that call SHALL start a fresh worker episode rather than resume the prior thread
