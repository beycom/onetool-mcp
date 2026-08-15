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

The main agent SHALL use `approval_policy: never`, disable worker network access,
and select `read-only` or current-project `workspace-write` without exceeding its
own authority. If it cannot represent the current environment safely, it SHALL
report that the workflow is unsupported rather than invoking the worker.

#### Scenario: First delegated episode
- **WHEN** the orchestrator delegates the first request in its current workflow
- **THEN** it SHALL omit `session_id` and retain the returned value

#### Scenario: Follow-up episode
- **WHEN** the user provides a follow-up request or answer in the same workflow
- **THEN** the orchestrator SHALL call `worker.run` with the retained session ID
- **AND** it SHALL NOT discover or infer a different session

### Requirement: The orchestrator relays terminal results

The main agent SHALL relay a worker's completed result, failure, or interruption
to the user. For `needs_input`, it SHALL ask the worker's single question and use
the user's answer as the next prompt in the same session.

#### Scenario: Worker reaches a terminal outcome
- **WHEN** `worker.run` returns `completed`, `failed`, or `interrupted`
- **THEN** the main agent SHALL report its message to the user

#### Scenario: Worker requires user input
- **WHEN** `worker.run` returns `needs_input`
- **THEN** the main agent SHALL present its question to the user
- **AND** the user's answer SHALL become the next `worker.run` prompt for the same session
