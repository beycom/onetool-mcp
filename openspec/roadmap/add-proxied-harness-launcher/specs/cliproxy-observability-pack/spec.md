## ADDED Requirements

### Requirement: cliproxy pack registration
The system SHALL provide a base MCP pack named `cliproxy` for read-only gateway and
harness-route observation.

#### Scenario: Pack discoverable
- **WHEN** OneTool discovers bundled base packs
- **THEN** `cliproxy` SHALL appear with a real description and valid help URL

#### Scenario: Public tools exposed
- **WHEN** the pack is loaded
- **THEN** it SHALL expose `status`, `models`, `providers`, `routes`, `activity`, and
  `errors` as synchronous keyword-only tools

#### Scenario: Shared semantics
- **WHEN** pack and CLI status surfaces observe the same gateway
- **THEN** they SHALL use the same typed service, redaction, capability detection,
  and route resolution

### Requirement: Gateway status observation
`cliproxy.status()` SHALL return structured, redacted gateway and current-route
state.

#### Scenario: Managed gateway running
- **WHEN** the managed gateway is healthy
- **THEN** status SHALL include mode, process state, endpoint health, version,
  management availability, config freshness, and model readiness

#### Scenario: Current launched route
- **GIVEN** the OneTool MCP process inherited non-secret launcher markers
- **WHEN** status is called
- **THEN** it SHALL include harness, configured model, source, route id, and
  permission mode

#### Scenario: Pack does not mutate state
- **WHEN** status finds an unhealthy or stopped proxy
- **THEN** it SHALL report the state and recommended CLI command
- **AND** it SHALL not start or restart the proxy

### Requirement: Model and route observation
The pack SHALL expose configured and live proxy model compatibility without
launching a harness.

#### Scenario: Filter models
- **WHEN** `cliproxy.models()` is called with optional harness or source filters
- **THEN** it SHALL return matching configured models with shortcut, model id,
  source, proxy alias, context, capabilities, configured harnesses, and live
  availability

#### Scenario: Inspect route
- **WHEN** `cliproxy.routes()` is called for a harness/model pair
- **THEN** it SHALL return the redacted resolved route, warnings, capability state,
  and incompatibility reason without starting a process

#### Scenario: Live discovery unavailable
- **WHEN** configured models are readable but live model discovery is unavailable
- **THEN** results SHALL distinguish configured state from unverified live state
- **AND** they SHALL not report a model as live merely because it is configured

### Requirement: Provider readiness observation
`cliproxy.providers()` SHALL report provider/source readiness without exposing
account or credential identities.

#### Scenario: Provider ready
- **WHEN** CLIProxyAPI reports usable Claude, ChatGPT/Codex, or OpenRouter auth
  state
- **THEN** the result SHALL report source, readiness, compatible model count, and
  safe capability metadata

#### Scenario: Provider missing auth
- **WHEN** a configured source lacks usable authentication
- **THEN** the result SHALL report `not_authenticated` with the relevant
  `onetool code login` or secret-configuration command

#### Scenario: Identity redaction
- **WHEN** upstream provider state includes filenames, emails, account ids, token
  fields, keys, or authorization headers
- **THEN** those values SHALL be omitted rather than returned or partially masked

### Requirement: Bounded activity observation
`cliproxy.activity()` SHALL expose bounded operational request metadata only when
the installed management API supports it.

#### Scenario: Recent activity available
- **WHEN** safe recent request metadata is available
- **THEN** the tool SHALL return bounded entries containing only timestamp,
  route/session identifier when available, harness, requested/resolved model,
  source, status, latency, and upstream-provided token counts

#### Scenario: Content is excluded
- **WHEN** activity is returned
- **THEN** prompts, response bodies, tool arguments/results, raw headers, and full
  request/response payloads SHALL never be included

#### Scenario: Activity unsupported
- **WHEN** the required management endpoint is absent or disabled
- **THEN** the tool SHALL return a structured `unsupported` or `disabled` result
  with an actionable hint
- **AND** it SHALL not parse arbitrary raw log lines as a fallback

#### Scenario: Usage queue is not consumed
- **WHEN** activity is requested
- **THEN** the tool SHALL not read a destructive CLIProxyAPI usage queue

### Requirement: Sanitized error observation
`cliproxy.errors()` SHALL return bounded, sanitized diagnostic summaries.

#### Scenario: Recent errors available
- **WHEN** safe management error metadata is available
- **THEN** the tool SHALL return timestamp, model/source when known, status/error
  class, bounded message, and correlation id when safe

#### Scenario: Secret-shaped error
- **WHEN** an upstream error contains a token, API key, credentialed URL, auth
  filename, email, account id, request body, or response body
- **THEN** the returned summary SHALL omit or redact the sensitive value

#### Scenario: Limit validation
- **WHEN** an invalid or excessive result limit is requested
- **THEN** the tool SHALL reject or clamp it according to a documented finite
  maximum

### Requirement: Read-only pack boundary
The `cliproxy` pack SHALL not expose state-changing or interactive gateway
operations.

#### Scenario: No lifecycle tools
- **WHEN** pack metadata is inspected
- **THEN** no start, stop, restart, install, update, or clear-log tool SHALL be
  exported

#### Scenario: No authentication tools
- **WHEN** pack metadata is inspected
- **THEN** no login, OAuth callback, auth upload/download/delete, or credential
  mutation tool SHALL be exported

#### Scenario: No generic management request
- **WHEN** pack metadata is inspected
- **THEN** no function SHALL accept an arbitrary management method, path, body, or
  header

#### Scenario: Mutation guidance
- **WHEN** an observed state requires user action
- **THEN** the result SHALL identify the explicit `onetool code` CLI command rather
  than performing the action

### Requirement: Pack configuration and secret safety
The pack SHALL consume the shared typed harness configuration and OneTool secret
boundary.

#### Scenario: No duplicate pack config
- **WHEN** the pack is called
- **THEN** it SHALL use the effective top-level `harness` configuration
- **AND** users SHALL not maintain a second `tools.cliproxy` route configuration

#### Scenario: Management key missing
- **WHEN** a management-only tool is called without a configured management key
- **THEN** it SHALL return a redacted configuration error and setup hint
- **AND** inference client keys SHALL not be tried as management credentials

#### Scenario: Returned data is native
- **WHEN** a pack tool succeeds
- **THEN** it SHALL return native Python dictionaries/lists or a plain error string
- **AND** it SHALL not pre-serialize JSON
