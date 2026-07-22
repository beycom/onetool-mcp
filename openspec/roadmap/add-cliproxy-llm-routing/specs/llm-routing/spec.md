## ADDED Requirements

### Requirement: Shared model registry

OneTool SHALL resolve generation models from one typed top-level `models` registry
shared by harness launchers and LLM-backed tools. Each entry SHALL identify its
shortcut, concrete model id, source, supported generation interfaces, modalities,
supported effort values, and optional default effort.

#### Scenario: Shortcut resolves for a tool
- **WHEN** a generation-backed tool selects a configured shortcut such as `sol`, `terra`, or `luna`
- **THEN** OneTool SHALL use the concrete model id and capabilities from that registry entry

#### Scenario: Full model id resolves to the same entry
- **WHEN** a configured concrete model id uniquely matches a registry entry
- **THEN** OneTool SHALL resolve the same model and capabilities as its shortcut

#### Scenario: Unknown or ambiguous model fails
- **WHEN** a model value matches no registry entry or matches more than one entry
- **THEN** OneTool SHALL fail before network I/O with an error naming the unresolved value

#### Scenario: Luma is not a shortcut
- **WHEN** `luma` is supplied but only `luna` is configured
- **THEN** OneTool SHALL reject `luma` as unknown and SHALL NOT treat it as an alias

### Requirement: Explicit generation backend

Every effective generation route SHALL select either `cliproxy` or
`openai_compatible`. A CLIProxyAPI route SHALL reuse the endpoint and inference
client credential supplied by the prerequisite proxy subsystem. An
OpenAI-compatible route SHALL use its configured base URL and named OneTool secret.

#### Scenario: CLIProxyAPI route uses subscription gateway
- **WHEN** the effective generation backend is `cliproxy`
- **THEN** the request SHALL be sent through the configured CLIProxyAPI inference endpoint with its client credential
- **AND** no provider API key SHALL be required by the calling tool

#### Scenario: Direct route uses named secret
- **WHEN** the effective generation backend is `openai_compatible`
- **THEN** the request SHALL use that route's base URL and named OneTool secret

#### Scenario: Backend-specific values do not cross routes
- **WHEN** a narrower selection changes the backend selected by a broader configuration layer
- **THEN** endpoint and credential fields from the broader backend SHALL NOT be inherited
- **AND** the narrower backend SHALL satisfy its own required configuration

### Requirement: Deterministic generation selection

OneTool SHALL resolve generation selections in this order: per-call `model` and
`effort`, operation-specific tool configuration, pack-level tool configuration,
top-level `llm`, then the selected model's default effort. Omitted fields SHALL fall
through independently except that backend-specific fields SHALL remain atomic.

#### Scenario: Per-call values take precedence
- **WHEN** a tool call supplies `model` or `effort`
- **THEN** each supplied value SHALL override the corresponding configured value for that call only

#### Scenario: Operation selection takes precedence
- **WHEN** an operation and its containing pack both configure the same generation field
- **THEN** the operation value SHALL be effective

#### Scenario: Pack selection takes precedence
- **WHEN** a pack and top-level `llm` both configure the same generation field
- **THEN** the pack value SHALL be effective

#### Scenario: Model default supplies omitted effort
- **WHEN** no call, operation, pack, or top-level effort is configured and the selected model declares a default effort
- **THEN** OneTool SHALL use the model's declared default effort

### Requirement: Canonical reasoning effort

The public reasoning-effort values SHALL be exactly `low`, `medium`, and `high`.
OneTool SHALL translate the selected value to the verified wire representation for
the effective backend without changing the resolved model id.

#### Scenario: Supported effort is translated
- **WHEN** a selected model declares the requested `low`, `medium`, or `high` effort as supported
- **THEN** OneTool SHALL send the backend's verified effort field with the corresponding value

#### Scenario: Unsupported effort fails before the request
- **WHEN** the selected model does not support the requested effort
- **THEN** OneTool SHALL fail before network I/O and list the supported values

#### Scenario: Non-canonical effort is rejected
- **WHEN** a caller or configuration supplies `med`, `xhigh`, `max`, or another non-canonical value
- **THEN** OneTool SHALL reject it through normal input or configuration validation

#### Scenario: Omitted effort remains omitted
- **WHEN** no layer and no model metadata supplies an effort
- **THEN** OneTool SHALL omit the effort field from the upstream request

### Requirement: Capability validation

Before a generation request, OneTool SHALL validate the selected model against the
operation's required generation interface, input modalities, structured-output
behavior, and effort support.

#### Scenario: Vision requires image capability
- **WHEN** an image operation selects a text-only model
- **THEN** OneTool SHALL fail before network I/O with an error identifying the missing image capability

#### Scenario: Required interface is unavailable
- **WHEN** a model or live proxy route does not support the generation interface required by the operation
- **THEN** OneTool SHALL fail with an actionable incompatibility error

### Requirement: Bounded CLIProxyAPI inference

The shared CLIProxyAPI service SHALL expose a bounded generation operation that
accepts resolved model and generation options and returns normalized response and
usage data. Tool callers SHALL NOT supply arbitrary paths, methods, headers, or
credentials.

#### Scenario: Healthy discovered model generates
- **WHEN** a CLIProxyAPI route is healthy and its resolved model is available from live discovery
- **THEN** the service SHALL perform the generation request and return normalized content and available usage metadata

#### Scenario: Proxy is unavailable
- **WHEN** a configured CLIProxyAPI route is unhealthy or unreachable during a tool call
- **THEN** the call SHALL fail with an actionable proxy lifecycle error
- **AND** OneTool SHALL NOT retry through a direct provider route

#### Scenario: Tool call does not mutate lifecycle
- **WHEN** a tool performs generation through CLIProxyAPI
- **THEN** it SHALL NOT start, stop, restart, or reconfigure the proxy process

### Requirement: Native grounding isolation

All `ground` operations SHALL continue to use the native Google GenAI client, a
Gemini model, `GEMINI_API_KEY`, and Google Search grounding. They SHALL NOT use the
shared generation router or CLIProxyAPI.

#### Scenario: Global CLIProxyAPI does not affect ground
- **WHEN** top-level `llm.backend` is `cliproxy` and a `ground` operation is called
- **THEN** the operation SHALL use its native Gemini configuration and `GEMINI_API_KEY`
- **AND** no request SHALL be sent to CLIProxyAPI

#### Scenario: Ground rejects proxy model shortcuts
- **WHEN** a `ground` operation is configured with a non-Gemini shared shortcut such as `sol`, `terra`, or `luna`
- **THEN** configuration or tool validation SHALL reject the selection

### Requirement: Safe route observability

Generation route diagnostics SHALL limit exposed request metadata to backend,
shortcut, resolved model, source, effort, latency, and token counts and SHALL redact
credentials and user content.

#### Scenario: Generation failure is redacted
- **WHEN** an upstream generation request fails
- **THEN** logs and tool errors SHALL omit proxy keys, named secret values, OAuth state, account identities, headers, prompts, responses, and raw upstream bodies
