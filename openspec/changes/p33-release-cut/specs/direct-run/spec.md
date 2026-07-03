## MODIFIED Requirements

### Requirement: authenticated direct API client

`onetool direct run` SHALL connect only to `127.0.0.1:PORT` and use the
HMAC key from `OT_DIR/auth/mcp-direct.key`. The client-side OT_DIR SHALL come
from `--ot-dir`, defaulting to `~/.onetool`.

`--ot-dir` SHALL be an explicit absolute directory selector after `~`
expansion. It SHALL NOT load OneTool config and SHALL NOT resolve relative to
cwd or `.onetool`. Relative `--ot-dir` values SHALL fail with a clear argument
error.

Before `/run`, the client SHALL perform signed `/health` and `/ready` checks.
The client SHALL verify signed responses before printing or trusting response
content.

#### Scenario: Unreachable selected port

- **WHEN** no service is listening on the selected port
- **THEN** the command SHALL fail clearly

#### Scenario: Non-OneTool or unauthenticated service

- **WHEN** a service is listening but signed health/readiness fails
- **THEN** the command SHALL fail clearly as an authentication or protocol error
- **AND** no command SHALL be sent without valid authentication

#### Scenario: Protocol mismatch

- **WHEN** `/health` or `/run` returns a different direct protocol version
- **THEN** the command SHALL fail clearly with a protocol mismatch
- **AND** `/ready` SHALL still be signed and parseable before it is trusted

#### Scenario: Execution failure

- **WHEN** `/run` returns `{"protocol_version":1,"success":false,"result":"..."}`
- **THEN** the result SHALL be printed
- **AND** the CLI SHALL exit with code `1`
