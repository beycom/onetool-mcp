## MODIFIED Requirements

### Requirement: CLI Entry Point

The base distribution SHALL provide a lightweight `onetool` CLI facade. When the
MCP component is installed, the facade SHALL provide an explicit `serve` runtime
command for root MCP server startup. `onetool serve` SHALL default to stdio
transport and SHALL support Streamable HTTP root mode through `--transport http`.
When the Skill component is installed, the facade SHALL provide the `skill`
subcommand group without requiring the MCP component.

#### Scenario: Explicit stdio root invocation

- **GIVEN** the MCP component is installed
- **WHEN** `onetool serve --config /path/to/onetool.yaml` is executed
- **THEN** it SHALL start the MCP server over stdio

#### Scenario: Explicit HTTP root invocation

- **GIVEN** the MCP component is installed
- **WHEN** `onetool serve --transport http --config /path/to/onetool.yaml` is
  executed with optional host, port, and path options
- **THEN** it SHALL start the same OneTool MCP server over Streamable HTTP
- **AND** the public transport value `http` SHALL map internally to FastMCP's
  `streamable-http` transport
- **AND** it SHALL use the same config, secrets, lifespan, proxy startup, Direct
  API startup, stats, telemetry, and shutdown behavior as stdio root mode

#### Scenario: Transport short option

- **GIVEN** the MCP component is installed
- **WHEN** `onetool serve -t http -c /path/to/onetool.yaml` is executed
- **THEN** it SHALL behave the same as `--transport http --config
  /path/to/onetool.yaml`

#### Scenario: HTTP root defaults

- **GIVEN** the MCP component is installed
- **WHEN** `onetool serve --transport http` is started without host, port, or
  path overrides
- **THEN** the bind host SHALL default to loopback
- **AND** the bind port SHALL default to `8767`
- **AND** the MCP endpoint path SHALL default to `/mcp`

#### Scenario: HTTP root explicit broad bind

- **GIVEN** the MCP component is installed
- **WHEN** Streamable HTTP root mode is started with `--host 0.0.0.0`
- **THEN** the server SHALL bind to `0.0.0.0`
- **AND** startup logs SHALL include an explicit warning that the bind address is
  not loopback

#### Scenario: Root callback compatibility warning

- **GIVEN** the MCP component is installed
- **WHEN** `onetool --config /path/to/onetool.yaml` starts stdio root mode
- **THEN** it SHALL continue to start the MCP server over stdio
- **AND** it SHALL print a warning recommending `onetool serve --config
  /path/to/onetool.yaml`

#### Scenario: Root invocation without MCP component

- **GIVEN** the MCP component is not installed
- **WHEN** `onetool` is executed without a subcommand
- **THEN** it SHALL display facade help instead of attempting MCP startup
- **AND** it SHALL show the command for installing `onetool-mcp[mcp]`

#### Scenario: Missing MCP command

- **GIVEN** the MCP component is not installed
- **WHEN** an MCP-only command such as `onetool serve` is requested
- **THEN** the CLI SHALL fail without importing an MCP runtime module
- **AND** it SHALL show `uv tool install 'onetool-mcp[mcp]'` as the corrective
  installation

#### Scenario: Skill command with Skill-only installation

- **GIVEN** only the Skill component is installed
- **WHEN** `onetool skill --help` is executed
- **THEN** Skill commands SHALL be displayed
- **AND** no MCP initialization or configuration SHALL be required

#### Scenario: Removed serve-http command

- **GIVEN** the MCP component is installed
- **WHEN** `onetool serve-http` is executed
- **THEN** the CLI SHALL fail through normal unknown-command handling

#### Scenario: Startup config validation failure

- **GIVEN** the MCP component is installed
- **AND** `onetool --config /path/to/onetool.yaml` is launched by an MCP client
- **AND** config loading fails before the MCP handshake
- **WHEN** the process exits
- **THEN** stderr SHALL include a compact config error diagnostic
- **AND** `<config-dir>/runtime/logs/serve.log` SHALL record the config path and
  error message

#### Scenario: Startup failure when --secrets file does not exist

- **GIVEN** the MCP component is installed
- **AND** `onetool serve --config /path/to/onetool.yaml --secrets
  /path/to/missing-secrets.yaml` is executed, or the equivalent root invocation
- **AND** `/path/to/missing-secrets.yaml` does not exist on disk
- **WHEN** the process starts
- **THEN** it SHALL exit with a non-zero status before the MCP handshake
- **AND** stderr SHALL print an actionable message that names the missing secrets
  path and points at `onetool init`
- **AND** `<config-dir>/runtime/logs/serve.log` SHALL record the same error
- **AND** omitting `--secrets` SHALL continue to start the server with no secrets
  loaded and no error

#### Scenario: Termination signal

- **GIVEN** the stdio or HTTP MCP server process receives SIGINT or SIGTERM
- **WHEN** the signal is handled
- **THEN** the process SHALL unwind through normal server shutdown
- **AND** FastMCP lifespan cleanup SHALL be able to close proxied transports
- **AND** the Direct API sidecar SHALL be stopped if it is running

#### Scenario: Facade help output

- **GIVEN** `onetool --help` is executed
- **WHEN** help is displayed
- **THEN** it SHALL list facade options and installed component subcommands with
  descriptions
- **AND** MCP subcommands SHALL be grouped under `CLI`, `Runtime`, `Direct`,
  `Configuration`, and `Knowledge Base` panels only when the MCP component is
  installed
- **AND** the Skill group SHALL be listed under a `Skill` panel only when the Skill
  component is installed
- **AND** absent components SHALL be summarized with their installation extras

#### Scenario: Version flag

- **GIVEN** `onetool --version` is executed
- **WHEN** executed
- **THEN** it SHALL display the facade package version
- **AND** installed component diagnostics SHALL report component versions from
  their package metadata
