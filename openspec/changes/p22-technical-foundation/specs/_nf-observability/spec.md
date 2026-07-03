## MODIFIED Requirements

### Requirement: Sensitive Data Protection

Observability output SHALL avoid exposing secrets or unbounded user data by
default.

#### Scenario: Credential masking
- **GIVEN** a logged value contains URL credentials or secret-like values known to OneTool
- **WHEN** the log record is rendered
- **THEN** credentials SHALL be masked or omitted

#### Scenario: Bounded default logging
- **GIVEN** a log field contains a large command, response, path, URL, or query
- **WHEN** default logging renders the field
- **THEN** the value SHALL be truncated or summarized

#### Scenario: Verbose opt-in
- **GIVEN** a user explicitly enables verbose logging
- **WHEN** log records are rendered
- **THEN** truncation MAY be disabled for diagnostic fields
- **AND** secret masking SHALL still apply

#### Scenario: Secret-shaped literal masking in any field
- **GIVEN** a logged field of any name (including `command`, `preparedCode`, or `error`) contains a
  secret-shaped literal — an API key (`sk-...`), a GitHub token (`ghp_...`/`gho_...`/
  `github_pat_...`), a Slack token (`xoxb-...`/`xoxp-...`), an AWS access key (`AKIA...`), a
  `password=`/`token=`/`secret=`/`api_key=` style assignment, or a credentialed connection string
  (`postgres://user:pass@host`, etc.)
- **WHEN** the log record is rendered, regardless of whether the value passes through a span-based log
  (`LogSpan`) or a direct `logger.debug(LogEntry(...))` call
- **THEN** the secret-shaped literal SHALL be replaced with a `[REDACTED:<kind>]` marker
- **AND** this masking SHALL apply even though the field name does not contain "url" and the value
  does not start with `http://`/`https://`

#### Scenario: Redaction applies to both LogSpan and direct LogEntry logging paths
- **GIVEN** `runner.py`'s `LogSpan(span="runner.execute", command=..., ...)` block and its nested
  `logger.debug(LogEntry(event="runner.execute.prepared", preparedCode=..., ...))` call, where the
  command or prepared code contains an inlined secret literal (e.g. `token="sk-abc123..."` instead of
  a `${VAR}` reference)
- **WHEN** either log record is emitted
- **THEN** the secret literal SHALL be redacted in both the `LogSpan`-produced record and the
  directly-logged `LogEntry` record — there SHALL NOT be a logging path that bypasses redaction
