## ADDED Requirements

### Requirement: CLIProxyAPI is required
OneTool harness launch support SHALL require an installed or explicitly configured
CLIProxyAPI service.

#### Scenario: Managed executable detected
- **WHEN** managed setup runs and `cliproxyapi` is available on `PATH`
- **THEN** OneTool SHALL report its resolved executable and version

#### Scenario: Managed executable missing on macOS
- **WHEN** managed setup runs on macOS and the executable is missing
- **THEN** OneTool SHALL offer or print the verified official Homebrew installation
  command
- **AND** it SHALL not install anything without interactive confirmation

#### Scenario: Unsupported proxy version
- **WHEN** the installed version lacks a required command, config field, protocol,
  or management endpoint
- **THEN** setup or doctor SHALL report the missing capability and required version
- **AND** launch SHALL not guess an alternate flag or schema

### Requirement: Generated proxy configuration
OneTool SHALL generate CLIProxyAPI configuration from the effective typed OneTool
harness configuration.

#### Scenario: Generated config written privately
- **WHEN** setup or a configuration change regenerates the proxy config
- **THEN** it SHALL be written atomically under `{OT_DIR}/runtime/code/cliproxy/`
- **AND** the file mode SHALL be `0600`

#### Scenario: Single source of truth
- **WHEN** generated CLIProxyAPI configuration differs from prior generated state
- **THEN** the effective OneTool configuration SHALL remain authoritative
- **AND** users SHALL not be required to edit or reconcile the generated file

#### Scenario: Secrets resolved only when needed
- **WHEN** generation requires a proxy client key, management key, or OpenRouter key
- **THEN** OneTool SHALL resolve the named secret through its existing secret/env
  boundary
- **AND** it SHALL never render the resolved value in status, dry-run, errors, or
  logs

#### Scenario: Existing independent proxy config
- **WHEN** an unrelated CLIProxyAPI configuration exists outside `{OT_DIR}`
- **THEN** managed setup SHALL not import, rewrite, or silently reuse it

### Requirement: OAuth delegation
OneTool SHALL delegate Claude and Codex subscription authentication to the official
CLIProxyAPI OAuth flows.

#### Scenario: Claude login
- **WHEN** `onetool code login claude` is executed
- **THEN** OneTool SHALL invoke CLIProxyAPI's current Claude OAuth login mode with
  the generated config and OneTool-owned auth directory

#### Scenario: Codex login
- **WHEN** `onetool code login codex` is executed
- **THEN** OneTool SHALL invoke CLIProxyAPI's current Codex OAuth login mode with
  the generated config and OneTool-owned auth directory

#### Scenario: OAuth ownership
- **WHEN** login or token refresh occurs
- **THEN** CLIProxyAPI SHALL own the protocol and credential files
- **AND** OneTool SHALL not parse, copy, refresh, or display OAuth token values

#### Scenario: Claude login warning
- **WHEN** Claude subscription OAuth login starts
- **THEN** OneTool SHALL warn that proxied usage may be classified as extra usage
  and may incur additional charges

### Requirement: Managed process lifecycle
OneTool SHALL provide bounded local CLIProxyAPI process management.

#### Scenario: Start managed proxy
- **WHEN** a managed proxy is started
- **THEN** OneTool SHALL start it as a detached process using the generated config
- **AND** redirect output to the config-relative proxy log
- **AND** record a validated PID under config-relative runtime state

#### Scenario: Auto-start before launch
- **GIVEN** managed mode and `auto_start` are enabled
- **WHEN** any harness route is selected and the proxy is unhealthy
- **THEN** OneTool SHALL start the proxy and wait a bounded time for health before
  launching the harness

#### Scenario: Auto-start disabled
- **GIVEN** managed mode and `auto_start` are disabled
- **WHEN** a harness route is selected and the proxy is unhealthy
- **THEN** OneTool SHALL fail with the explicit start command

#### Scenario: Stop managed proxy
- **WHEN** proxy stop is requested for a validated live managed PID
- **THEN** OneTool SHALL send a graceful termination signal and wait a bounded time
  before escalation
- **AND** remove its PID state after verified shutdown

#### Scenario: Stale PID
- **WHEN** PID state is malformed, dead, or does not identify the managed process
- **THEN** OneTool SHALL not signal an unrelated process
- **AND** it SHALL safely remove or report the stale state

### Requirement: External proxy mode
OneTool SHALL support an explicitly configured externally managed CLIProxyAPI
endpoint.

#### Scenario: Healthy external proxy
- **WHEN** external mode is configured and health/model checks succeed
- **THEN** OneTool SHALL use the endpoint for harness launches
- **AND** it SHALL not create PID state or start a local process

#### Scenario: Lifecycle mutation rejected
- **WHEN** start, stop, or restart is requested in external mode
- **THEN** OneTool SHALL reject the operation and identify the endpoint as
  externally managed

#### Scenario: Remote management is explicit
- **WHEN** a non-loopback management endpoint is configured
- **THEN** OneTool SHALL require explicit opt-in and authenticated TLS
- **AND** doctor SHALL warn about the expanded exposure surface

### Requirement: Health and model discovery
OneTool SHALL validate gateway health and live model availability before launching
a harness.

#### Scenario: Health succeeds
- **WHEN** the CLIProxyAPI health endpoint returns the expected success response
- **THEN** status SHALL report the proxy as healthy with bounded latency metadata

#### Scenario: Models succeed
- **WHEN** authenticated model discovery returns a valid model list
- **THEN** OneTool SHALL validate configured aliases and full model ids against it
- **AND** cache successful results only for the configured bounded TTL

#### Scenario: Invalid model response
- **WHEN** model discovery returns an invalid shape or omits the selected alias/id
- **THEN** launch SHALL fail with an actionable, redacted diagnostic

#### Scenario: Discovery cache cannot authorize launch indefinitely
- **WHEN** cached model discovery is stale beyond its configured TTL
- **THEN** OneTool SHALL refresh it before launch or fail if a fresh result cannot
  be obtained

### Requirement: Management diagnostics
OneTool SHALL provide redacted CLIProxyAPI status, doctor, model, provider, log, and
version diagnostics.

#### Scenario: Concise status
- **WHEN** `onetool code status` is executed
- **THEN** it SHALL report harness installation, effective config path, proxy mode,
  process/endpoint health, proxy version, credential presence, and model readiness
  without network-expensive deep checks

#### Scenario: Detailed doctor
- **WHEN** `onetool code doctor` is executed
- **THEN** it SHALL run version/capability, config generation, path permission,
  endpoint, management authentication, OAuth readiness, model compatibility, and
  harness checks
- **AND** every failure SHALL include an actionable next command

#### Scenario: Logs view
- **WHEN** managed proxy logs are requested through the CLI
- **THEN** output SHALL be bounded by default and pass through secret redaction
- **AND** the CLI SHALL require explicit options for a larger tail

#### Scenario: Management API disabled
- **WHEN** inference health works but the management API is disabled or unavailable
- **THEN** launches SHALL continue if their required route is healthy
- **AND** management-only diagnostics SHALL report `unsupported` or `disabled`
  rather than exposing an authentication error body

### Requirement: No durable analytics ownership
This change SHALL not silently consume or persist CLIProxyAPI usage streams.

#### Scenario: Destructive usage queue
- **WHEN** the installed CLIProxyAPI exposes a queue whose read operation removes
  records
- **THEN** OneTool SHALL not consume it as part of status, doctor, or pack calls

#### Scenario: Persistent usage requested
- **WHEN** users need durable token/cost history or quota tracking
- **THEN** this capability SHALL report that persistent analytics is not provided
  by this change
- **AND** it SHALL not synthesize missing usage data from request bodies
