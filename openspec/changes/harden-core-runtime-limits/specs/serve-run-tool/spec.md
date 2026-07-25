## MODIFIED Requirements

### Requirement: Per-Tool Execution Timeout

The `run` tool SHALL enforce a soft caller timeout on user code, so that a hung
or excessively slow tool call returns a clean failure instead of holding that
caller indefinitely. Reaching the timeout SHALL stop waiting for the result but
SHALL NOT claim to terminate the underlying in-process Python thread. The
underlying execution MAY continue performing side effects after the timeout and
SHALL remain admitted and accounted for until it actually finishes.

#### Scenario: Execution exceeding the timeout fails cleanly

- **GIVEN** a command whose execution exceeds the per-tool timeout
- **WHEN** the timeout is reached
- **THEN** `run()` SHALL raise `ToolError` with a message indicating the caller timed out
- **AND** the message SHALL state that underlying in-process work may continue
- **AND** the underlying job SHALL remain admitted until its thread finishes

#### Scenario: Post-timeout side effect remains possible

- **GIVEN** a command blocks past its caller timeout and then performs a side effect
- **WHEN** the caller receives the timeout failure and the blocked command is released
- **THEN** the side effect MAY occur
- **AND** completion SHALL release the job's admission slot

#### Scenario: Execution within the timeout is unaffected

- **GIVEN** a command whose execution completes well within the per-tool timeout
- **WHEN** `run()` executes the command
- **THEN** it SHALL complete and return its result normally, with no timeout-related error

## ADDED Requirements

### Requirement: Bounded In-Process Execution Admission

OneTool SHALL admit at most eight in-process execution jobs per process. The
bound SHALL include running and queued underlying work across all callers and
event loops. A caller timeout or cancellation SHALL NOT release a slot; only
actual underlying thread completion SHALL release it. When all eight slots are
occupied, the next request SHALL fail immediately with an execution-capacity
error and SHALL NOT submit additional underlying work.

#### Scenario: Timed-out work fills capacity

- **GIVEN** eight admitted jobs have timed out for their callers but their underlying threads remain blocked
- **WHEN** a ninth execution request arrives
- **THEN** it SHALL fail immediately with an execution-capacity error
- **AND** no ninth underlying job SHALL be submitted or queued

#### Scenario: Underlying completion restores capacity

- **GIVEN** all eight slots are occupied by underlying jobs
- **WHEN** one underlying thread actually finishes
- **THEN** its slot SHALL be released
- **AND** a subsequent request SHALL be eligible for admission

#### Scenario: Caller cancellation does not release capacity

- **GIVEN** an admitted job is still running
- **WHEN** its awaiting caller is cancelled
- **THEN** the underlying job SHALL continue and remain counted
- **AND** overflow admission behavior SHALL remain unchanged until that job finishes

### Requirement: In-Process Execution Shutdown

MCP server shutdown SHALL stop accepting new in-process execution jobs and SHALL
wait for every admitted job, including work detached by caller timeout or
cancellation, to actually finish before dependent runtime resources are closed.
The runtime SHALL NOT claim hard termination of Python threads.

#### Scenario: Shutdown drains detached work

- **GIVEN** a caller has timed out while its admitted thread remains blocked
- **WHEN** MCP server shutdown begins
- **THEN** new execution admission SHALL be rejected
- **AND** shutdown SHALL remain pending until the blocked thread is released and finishes
- **AND** the admitted-work count SHALL then reach zero

#### Scenario: Startup reopens clean admission

- **GIVEN** a prior server lifespan completed shutdown with no admitted work
- **WHEN** a new MCP server lifespan starts in the same process
- **THEN** execution admission SHALL reopen with capacity eight
