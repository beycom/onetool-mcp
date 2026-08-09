# cliproxy-connection Specification

## Purpose

Defines the separate, inference-only boundaries used by standalone harness
launchers and MCP generation with an independently managed CLIProxyAPI service.
## Requirements
### Requirement: External inference connection

OneTool SHALL use only CLIProxyAPI's public HTTP inference boundary when the
service is explicitly selected. Standalone launchers SHALL read the proxy origin
and inference credential only from their process environment. MCP generation
SHALL read its versioned API base and direct default model from an explicit
`llm.backend: cliproxy` connection and the fixed credential from `secrets.yaml`.

#### Scenario: Launcher defaults
- **WHEN** `CLIPROXY_BASE_URL` is omitted from a launcher process
- **THEN** OneTool SHALL use `http://127.0.0.1:8317`
- **AND** it SHALL require `CLIPROXY_INFERENCE_KEY` from that process environment

#### Scenario: MCP CLIProxy defaults
- **WHEN** top-level `llm.backend` is `cliproxy` and optional connection fields are omitted
- **THEN** OneTool SHALL use the documented loopback `/v1` base and bounded defaults
- **AND** it SHALL resolve only `CLIPROXY_INFERENCE_KEY` from `secrets.yaml`

#### Scenario: MCP does not select CLIProxy implicitly
- **WHEN** top-level `llm.backend` is omitted
- **THEN** MCP generation SHALL use the OpenAI-compatible default
- **AND** it SHALL not contact CLIProxyAPI

#### Scenario: Configuration boundaries remain separate
- **WHEN** a standalone launcher runs
- **THEN** it SHALL not load `onetool.yaml` or `secrets.yaml`
- **AND** MCP generation SHALL not read the launcher's environment configuration

#### Scenario: No management or file ownership
- **WHEN** either CLIProxyAPI connection is used
- **THEN** OneTool SHALL NOT call management APIs or manage the proxy lifecycle
- **AND** it SHALL NOT read or mutate CLIProxyAPI configuration, OAuth, account, log, or routing files

### Requirement: Launcher discovery and generation are separate

Standalone harness launches SHALL resolve their required model query against one
fresh bounded inference inventory. MCP generation SHALL use its configured direct
model ID without discovery.

#### Scenario: Launcher live selection
- **WHEN** a standalone harness launch receives a model query
- **THEN** OneTool SHALL call `GET /v1/models` exactly once using the environment
  credential
- **AND** it SHALL fail before starting the child unless the query resolves to one
  inventory ID

#### Scenario: Direct generation
- **WHEN** MCP generation receives a configured direct model ID
- **THEN** OneTool SHALL send it unchanged without calling `GET /v1/models`

#### Scenario: Explicit model listing
- **WHEN** `onetool code models` runs with a valid environment credential
- **THEN** it SHALL call `GET /v1/models` exactly once
- **AND** it SHALL return the direct IDs and optional `owned_by` provider values
  from that bounded inventory
- **AND** it SHALL not require a management credential or read CLIProxyAPI files

#### Scenario: Invalid discovery response
- **WHEN** discovery times out, exceeds its body limit, or returns an invalid shape
- **THEN** OneTool SHALL report a bounded redacted failure

### Requirement: Inference credential safety

Both CLIProxy consumers SHALL use the fixed name `CLIPROXY_INFERENCE_KEY` through
their separate configuration boundaries.

#### Scenario: Launcher secret use
- **WHEN** a launcher or launcher inventory request requires authentication
- **THEN** only the process environment value SHALL be used

#### Scenario: MCP secret use
- **WHEN** MCP generation explicitly selects CLIProxyAPI
- **THEN** only the `secrets.yaml` value SHALL be used
- **AND** no configurable generation secret name SHALL be accepted

#### Scenario: Secret redaction
- **WHEN** either consumer uses its credential
- **THEN** the value SHALL never appear in argv, output, logs, errors, or generated files

#### Scenario: Missing secret
- **WHEN** the applicable credential is absent or empty
- **THEN** the operation SHALL fail before a child starts or network I/O occurs
