# cliproxy-connection Specification

## Purpose

Defines the inference-only boundary used by MCP generation with an independently
managed CLIProxyAPI service.

## Requirements

### Requirement: External inference connection

OneTool SHALL use only CLIProxyAPI's public HTTP inference boundary when the
service is explicitly selected. MCP generation SHALL read its versioned API base
and direct default model from an explicit `llm.backend: cliproxy` connection and
the fixed credential from `secrets.yaml`.

#### Scenario: CLIProxy defaults
- **WHEN** top-level `llm.backend` is `cliproxy` and optional connection fields are omitted
- **THEN** OneTool SHALL use the documented loopback `/v1` base and bounded defaults
- **AND** it SHALL resolve only `CLIPROXY_INFERENCE_KEY` from `secrets.yaml`

#### Scenario: CLIProxy is not selected implicitly
- **WHEN** top-level `llm.backend` is omitted
- **THEN** MCP generation SHALL use the OpenAI-compatible default
- **AND** it SHALL not contact CLIProxyAPI

#### Scenario: No management or file ownership
- **WHEN** the CLIProxyAPI connection is used
- **THEN** OneTool SHALL NOT call management APIs or manage the proxy lifecycle
- **AND** it SHALL NOT read or mutate CLIProxyAPI configuration, OAuth, account, log, or routing files

### Requirement: Generation uses direct configured models

MCP generation SHALL use its configured direct model ID without discovery.

#### Scenario: Direct generation
- **WHEN** MCP generation receives a configured direct model ID
- **THEN** OneTool SHALL send it unchanged without calling `GET /v1/models`

### Requirement: Inference credential safety

CLIProxy generation SHALL use the fixed name `CLIPROXY_INFERENCE_KEY` from its
server secrets boundary.

#### Scenario: MCP secret use
- **WHEN** MCP generation explicitly selects CLIProxyAPI
- **THEN** only the `secrets.yaml` value SHALL be used
- **AND** no configurable generation secret name SHALL be accepted

#### Scenario: Secret redaction
- **WHEN** generation uses its credential
- **THEN** the value SHALL never appear in output, logs, errors, or generated files

#### Scenario: Missing secret
- **WHEN** the credential is absent or empty
- **THEN** generation SHALL fail before network I/O occurs
