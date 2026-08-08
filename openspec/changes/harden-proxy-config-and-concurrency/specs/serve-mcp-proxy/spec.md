## MODIFIED Requirements

### Requirement: Async Proxy Execution

The system SHALL handle async proxy calls within the executor using bounded per-server capacity and one absolute operation deadline.

#### Scenario: Async tool call
- **GIVEN** a proxied tool is async
- **WHEN** run() calls it from sync code
- **THEN** it SHALL properly await the result

#### Scenario: Safe calls overlap
- **GIVEN** multiple calls to one server have no interactive request owner
- **WHEN** shared capacity is available
- **THEN** the calls SHALL be allowed to execute concurrently on the downstream session
- **AND** concurrency SHALL remain bounded

#### Scenario: Interactive call has exclusive ownership
- **GIVEN** a proxied call has an originating root request that may receive elicitation
- **WHEN** it acquires server capacity
- **THEN** no other call SHALL execute on that server until the interactive call completes
- **AND** its elicitation handler SHALL be bound only to that root request

#### Scenario: Timeout handling
- **GIVEN** a proxied tool call exceeds timeout
- **WHEN** timeout is reached before or after capacity acquisition
- **THEN** it SHALL return an error with timeout details
- **AND** the same absolute deadline SHALL include waiting for per-server call capacity
- **AND** the operation SHALL be cancelled
- **AND** cancellation SHALL release only that call's capacity and ownership
- **AND** timed-out lifecycle work SHALL NOT publish connection state later

### Requirement: Portable proxy elicitation forwarding

During a proxied tool call, the system SHALL forward standard MCP form and URL elicitation to the client that owns the active `run` request when that client supports the requested mode. The system SHALL preserve standard accept, decline, and cancel outcomes and SHALL NOT synthesize user answers.

#### Scenario: Form elicitation is forwarded
- **GIVEN** an active proxied call requests form elicitation
- **AND** the invoking client supports form elicitation
- **WHEN** the client responds with accept, decline, or cancel
- **THEN** the proxied server SHALL receive the same action
- **AND** accepted form content SHALL be returned unchanged

#### Scenario: URL elicitation is forwarded
- **GIVEN** an active proxied call requests URL elicitation
- **AND** the invoking client supports URL elicitation
- **WHEN** OneTool forwards the request
- **THEN** the client SHALL receive the upstream URL and elicitation identifier unchanged
- **AND** the proxied server SHALL receive the client's action unchanged

#### Scenario: Unsupported interaction completes promptly
- **GIVEN** the invoking client does not support the requested elicitation mode or cannot interact
- **WHEN** a proxied server requests elicitation
- **THEN** the proxied server SHALL receive a standard cancel outcome without indefinite waiting
- **AND** if the proxied operation cannot continue, the root MCP error SHALL advise retrying with explicit tool arguments

#### Scenario: Concurrent callers remain isolated
- **GIVEN** multiple proxied calls could request elicitation
- **WHEN** OneTool cannot correlate a downstream elicitation to its originating tool request
- **THEN** interactive calls SHALL execute serially with exclusive ownership
- **AND** detached calls SHALL NOT execute alongside an interactive call or borrow its context
- **AND** no caller SHALL observe another caller's elicitation or response

#### Scenario: Expired request cannot elicit
- **GIVEN** a proxy operation continues after its enclosing `run` request has completed
- **WHEN** the operation requests elicitation
- **THEN** OneTool SHALL NOT initiate elicitation through the expired client context
- **AND** the upstream elicitation request SHALL receive a cancel outcome promptly
- **AND** the upstream tool MAY stop or continue according to that standard outcome

#### Scenario: Headless explicit arguments remain supported
- **GIVEN** a headless client cannot participate in elicitation
- **WHEN** it supplies all required proxied tool arguments explicitly
- **THEN** the proxied workflow SHALL be able to complete without elicitation
