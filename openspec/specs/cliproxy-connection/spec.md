# cliproxy-connection Specification

## Purpose

Defines OneTool's inference-only connection to an independently installed,
configured, authenticated, and running CLIProxyAPI service.

## Requirements

### Requirement: External inference connection

OneTool SHALL configure only the HTTP inference boundary: base URL, named
inference-client secret, and bounded timeouts.

#### Scenario: Connection defaults
- **WHEN** optional connection fields are omitted
- **THEN** OneTool SHALL use the documented loopback URL, secret name, and bounded
  timeout defaults

#### Scenario: No management ownership
- **WHEN** the connection is used
- **THEN** OneTool SHALL NOT require or call management APIs
- **AND** it SHALL NOT install, configure, start, stop, restart, authenticate, or
  administer CLIProxyAPI

#### Scenario: No CLIProxyAPI file dependency
- **WHEN** OneTool loads or launches code routing
- **THEN** it SHALL NOT require a CLIProxyAPI config path
- **AND** it SHALL NOT read or mutate proxy YAML, OAuth files, accounts, logs,
  retries, routing policy, or process state

### Requirement: Launch and discovery are separate

Normal launch, dry run, status, model listing, and generation SHALL not require
live model discovery.

#### Scenario: Normal launch
- **WHEN** a configured launcher model is selected
- **THEN** OneTool SHALL pass its exact effective id to the process without calling
  `GET /v1/models`

#### Scenario: Generation request
- **WHEN** a configured generation model selects CLIProxyAPI
- **THEN** OneTool SHALL send its configured proxy wire identity without calling
  `GET /v1/models`

#### Scenario: Explicit doctor
- **WHEN** `onetool code doctor` runs with configured proxy routes and secret
- **THEN** it SHALL call `GET /v1/models` exactly once
- **AND** it SHALL compare each configured proxy launcher id exactly against that
  one bounded inventory

#### Scenario: Direct-only doctor
- **WHEN** `onetool code doctor` runs without configured proxy routes
- **THEN** it SHALL not resolve a proxy secret or call `GET /v1/models`

#### Scenario: Diagnostic mismatch
- **WHEN** the inventory omits an id or advertises it more than once
- **THEN** doctor SHALL fail that record with an actionable redacted result
- **AND** it SHALL NOT translate, substitute, or rewrite the id

#### Scenario: Invalid diagnostic response
- **WHEN** discovery times out, exceeds its body limit, or returns an invalid shape
- **THEN** doctor SHALL report a bounded redacted failure

### Requirement: Inference credential safety

The configured inference key SHALL remain within OneTool's named-secret boundary.

#### Scenario: Secret use
- **WHEN** a proxy child invocation, generation call, or doctor requires the secret
- **THEN** only the configured secret name SHALL be resolved
- **AND** its value SHALL never appear in summaries, dry runs, logs, errors, or
  generated files

### Requirement: Shared generation connection

Generation routes that explicitly select the `cliproxy` backend SHALL reuse the
optional `code.proxy` connection fields without coupling launcher models to the
top-level generation registry.

#### Scenario: Generation alias remains generation-only
- **WHEN** a top-level generation model defines `proxy_alias`
- **THEN** generation SHALL use that exact configured value as the proxy-facing
  wire identity
- **AND** the code launcher SHALL ignore the top-level record completely

#### Scenario: Missing proxy connection
- **WHEN** top-level `llm.backend` uses `cliproxy` without `code.proxy`
- **THEN** strict configuration validation SHALL reject the configuration

#### Scenario: Nested route lacks proxy connection
- **WHEN** a complete nested pack or operation selection uses `cliproxy` without
  `code.proxy`
- **THEN** effective-route resolution SHALL fail before network I/O
