# cliproxy-connection Specification

## Purpose

Defines OneTool's inference-only connection to an externally managed CLIProxyAPI,
including bounded model discovery, named-secret handling, capability validation,
and the boundary that excludes proxy lifecycle and management ownership.

## Requirements
### Requirement: External CLIProxyAPI inference connection
OneTool SHALL connect only to an independently installed and configured CLIProxyAPI
inference endpoint.

#### Scenario: Connection configured
- **WHEN** a route uses CLIProxyAPI
- **THEN** OneTool SHALL require a base URL and named inference-client secret
- **AND** it SHALL use configured bounded connection and request timeouts

#### Scenario: No management ownership
- **WHEN** the CLIProxyAPI connection is used
- **THEN** OneTool SHALL not require or call a management endpoint
- **AND** it SHALL not read or mutate proxy configuration, processes, PID state,
  accounts, OAuth files, logs, retries, failover, or session affinity

#### Scenario: Proxy unavailable
- **WHEN** the configured inference endpoint is unavailable
- **THEN** the selected route SHALL fail with an actionable redacted error
- **AND** OneTool SHALL not start the proxy or fall back to another provider

### Requirement: Bounded model discovery
OneTool SHALL validate proxied routes through authenticated live model discovery.

#### Scenario: Selected model available
- **WHEN** `/v1/models` returns a valid bounded response containing the configured
  alias or model id
- **THEN** the route SHALL be eligible for launch

#### Scenario: Selected model absent
- **WHEN** discovery omits both the configured alias and model id
- **THEN** launch SHALL fail before starting the harness

#### Scenario: Invalid response
- **WHEN** model discovery times out or returns an invalid shape
- **THEN** OneTool SHALL report a bounded redacted diagnostic

#### Scenario: Discovery cache
- **WHEN** a valid discovery result is cached
- **THEN** it MAY be reused only within the configured finite TTL
- **AND** stale discovery SHALL not authorize a launch

### Requirement: Inference credential safety
CLIProxyAPI inference credentials SHALL remain within OneTool's named-secret
boundary.

#### Scenario: Secret resolved
- **WHEN** discovery or a child adapter requires the inference client key
- **THEN** only the configured secret SHALL be resolved
- **AND** its value SHALL never appear in terminal summaries, dry runs, logs, errors,
  caches, or generated adapter files

#### Scenario: User-owned config path
- **WHEN** an optional upstream login helper requires a CLIProxyAPI config path
- **THEN** OneTool SHALL pass the configured user-owned path without parsing secrets
  from it or rewriting it

### Requirement: Upstream capability verification
OneTool SHALL reject unsupported CLIProxyAPI behavior rather than guessing.

#### Scenario: Missing proxy capability
- **WHEN** the installed or observed proxy lacks a required inference protocol,
  model-discovery shape, or delegated-command flag
- **THEN** the affected route, check, or delegated command SHALL report the missing
  capability and any evidence-based minimum version
- **AND** OneTool SHALL not require an exact development-fixture version

#### Scenario: No raw request surface
- **WHEN** CLI commands and configuration are inspected
- **THEN** no arbitrary method, path, header, body, or raw YAML passthrough SHALL be
  available

#### Scenario: Ambiguous proxy alias
- **WHEN** live discovery returns duplicate or otherwise ambiguous entries for a
  configured proxy alias
- **THEN** the route SHALL fail before launch with guidance to assign unique
  CLIProxyAPI aliases
- **AND** OneTool SHALL not inspect or rewrite `oauth-model-alias` configuration

#### Scenario: CLIProxyAPI documentation boundary
- **WHEN** OneTool documents external proxy setup
- **THEN** it SHALL link to the upstream configuration options, canonical example
  YAML, and relevant Codex and Claude Code client guides
- **AND** it SHALL not copy an inline inference credential into generated OneTool,
  Codex, or Claude configuration
