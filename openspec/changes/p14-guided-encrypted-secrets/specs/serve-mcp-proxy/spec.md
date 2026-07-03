## MODIFIED Requirements

### Requirement: Proxy Server Lifecycle

The system SHALL manage proxy MCP server connections through the server lifecycle, and SHALL
sanitize connect-error strings before they are stored or surfaced to the agent or logs.

#### Scenario: Startup connection
- **GIVEN** servers configured in onetool.yaml
- **WHEN** the OneTool server starts
- **THEN** it SHALL begin connecting to all enabled MCP servers
- **AND** readiness/status surfaces SHALL distinguish proxy servers that are connected, connecting, or failed

#### Scenario: Startup connection failure
- **GIVEN** an MCP server that fails to connect
- **WHEN** the OneTool server starts
- **THEN** it SHALL log a warning and continue without that server
- **AND** other MCP servers SHALL still be available

#### Scenario: Shutdown cleanup
- **GIVEN** connected proxy MCP servers
- **WHEN** the OneTool server shuts down
- **THEN** it SHALL disconnect all MCP servers cleanly
- **AND** terminate any stdio subprocesses

#### Scenario: Parallel connection
- **GIVEN** multiple MCP servers configured
- **WHEN** the OneTool server starts
- **THEN** connections SHALL be established independently so one slow server does not delay unrelated servers
- **AND** failures SHALL be recorded per server without failing unrelated connections

#### Scenario: Connect-error strings sanitized before surfacing
- **GIVEN** an MCP server connection attempt fails with an exception whose string representation
  could contain an `Authorization`/`Bearer`/`Basic`-style credential fragment (e.g. built from a
  decrypted secret used as a bearer token for an HTTP-transport server)
- **WHEN** the error is stored in `self._errors[name]` (`src/ot/proxy/manager.py:489,733`) for
  later surfacing via `ot.servers()`/status output
- **THEN** the stored string SHALL have any `Authorization:`/`Bearer `/`Basic `-prefixed credential
  fragments stripped or redacted before storage
- **AND** the sanitized string SHALL still identify the failure reason (e.g. connection
  refused/timeout/DNS failure) so the error remains diagnosable
