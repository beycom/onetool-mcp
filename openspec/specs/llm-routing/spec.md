# llm-routing Specification

## Purpose

Defines provider-neutral generation routing through a shared model registry,
explicit CLIProxyAPI or direct OpenAI-compatible backends, deterministic selection
precedence, capability checks, independent embeddings, and safe route observability.

## Requirements
### Requirement: Shared model registry

OneTool SHALL resolve generation models from one typed top-level `models` registry
used by LLM-backed tools and ignored by the code launcher. Each entry SHALL identify its
shortcut, concrete model id, source, supported generation interfaces, modalities,
supported structured-output modes per interface, supported effort values, and
optional default effort. Structured-output modes SHALL use verified typed values,
including `json_object` and `json_schema`, rather than inferred provider or
model-name behavior.

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

#### Scenario: Structured-output metadata is explicit
- **WHEN** a registry entry declares support for `json_object` or `json_schema`
- **THEN** it SHALL associate that mode with a verified generation interface
- **AND** an omitted mode SHALL be treated as unsupported rather than inferred

### Requirement: Explicit generation backend

Every effective generation route SHALL select either `cliproxy` or
`openai_compatible` and exactly one verified generation `interface`. The initial
interface values SHALL be `responses` and `chat_completions`. A CLIProxyAPI route
SHALL reuse the endpoint and inference client credential supplied by the external
`code.proxy` inference connection. An OpenAI-compatible route SHALL use its
configured base URL and named OneTool secret.

#### Scenario: CLIProxyAPI route uses subscription gateway
- **WHEN** the effective generation backend is `cliproxy`
- **THEN** the request SHALL be sent through the configured CLIProxyAPI inference endpoint with its client credential
- **AND** no provider API key SHALL be required by the calling tool

#### Scenario: Codex subscription uses Responses
- **WHEN** a CLIProxyAPI generation route selects a Codex-subscription-backed model
- **THEN** the complete route SHALL select `interface: responses`
- **AND** the model registry and verified CLIProxyAPI capability fixture SHALL both
  declare Responses support

#### Scenario: Direct route uses named secret
- **WHEN** the effective generation backend is `openai_compatible`
- **THEN** the request SHALL use that route's base URL and named OneTool secret

#### Scenario: Backend-specific values do not cross routes
- **WHEN** a narrower selection changes the backend selected by a broader configuration layer
- **THEN** endpoint and credential fields from the broader backend SHALL NOT be inherited
- **AND** the narrower backend SHALL provide and satisfy its own required configuration at that layer

#### Scenario: Interface is not inferred
- **WHEN** a complete backend omits `interface` or selects an interface not declared
  by the resolved model and backend fixture
- **THEN** configuration or route resolution SHALL fail before network I/O
- **AND** OneTool SHALL not infer an endpoint from model name, source, launcher
  route, SDK default, or error response

### Requirement: Explicit subscription-backed generation

Subscription-backed generation SHALL be used only when an effective generation route
explicitly selects `cliproxy`. OneTool SHALL describe the intended reduction in
separate API spending without guaranteeing terms compliance, subscription
classification, included usage, rate limits, availability, credits, or billing.

#### Scenario: Codex subscription model selected
- **WHEN** the effective CLIProxyAPI route selects a configured Codex
  subscription-backed model such as Luna
- **THEN** the request SHALL use the external proxy inference endpoint without
  requiring a separate OpenAI API key
- **AND** available returned usage metadata SHALL be preserved in the normalized
  result

#### Scenario: Subscription route omitted
- **WHEN** no effective generation route selects `cliproxy`
- **THEN** OneTool SHALL not infer subscription access from launcher configuration,
  installed harness authentication, or model source alone

#### Scenario: No included-usage guarantee
- **WHEN** a subscription-backed route is documented, inspected, or fails
- **THEN** OneTool SHALL not claim that the request is covered by included allowance,
  free of charges, compliant with provider terms, or continuously supported

#### Scenario: No paid fallback
- **WHEN** subscription authentication, allowance, model availability, capability, or
  proxy health prevents generation
- **THEN** the operation SHALL fail through the selected route
- **AND** it SHALL not switch to OpenRouter, a paid API endpoint, another model, or
  another transport

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
behavior, and effort support using configured capability metadata.

#### Scenario: Vision requires image capability
- **WHEN** an image operation selects a text-only model
- **THEN** OneTool SHALL fail before network I/O with an error identifying the missing image capability

#### Scenario: Required interface is unavailable
- **WHEN** a configured model does not support the generation interface required by
  the operation
- **THEN** OneTool SHALL fail before network I/O with an actionable incompatibility
  error

#### Scenario: Required structured-output mode is unavailable
- **WHEN** an operation requires `json_object` or `json_schema` and the selected model does not declare that mode for the effective interface
- **THEN** OneTool SHALL fail before network I/O with an error identifying the unsupported structured-output mode

### Requirement: Bounded CLIProxyAPI inference

OneTool's generation adapter SHALL send bounded requests to the configured
CLIProxyAPI inference interface and normalize response and usage data. Tool callers
SHALL NOT supply arbitrary paths, methods, headers, or credentials.

#### Scenario: Configured model generates
- **WHEN** a CLIProxyAPI generation route resolves to a configured wire model
  identity
- **THEN** OneTool SHALL send that identity directly and normalize returned content
  and available usage metadata
- **AND** it SHALL not require live model discovery

#### Scenario: Generation uses HTTP inference
- **WHEN** any tool generates through CLIProxyAPI
- **THEN** OneTool SHALL call the selected configured HTTP inference interface
  directly
- **AND** it SHALL not spawn Claude Code, Codex, CLIProxyAPI, or another executable
- **AND** it SHALL not read harness settings, profiles, auth files, or terminal output

#### Scenario: Configured metadata is capability proof
- **WHEN** generation resolves a model
- **THEN** its configured interfaces, modalities, structured-output modes, and
  efforts SHALL determine operation compatibility
- **AND** OneTool SHALL not probe with a potentially billable request implicitly

#### Scenario: Proxy is unavailable
- **WHEN** a configured CLIProxyAPI route is unhealthy or unreachable during a tool call
- **THEN** the call SHALL fail with an actionable external-proxy error
- **AND** OneTool SHALL NOT start the proxy or retry through another provider route

#### Scenario: Tool call does not mutate lifecycle
- **WHEN** a tool performs generation through CLIProxyAPI
- **THEN** it SHALL NOT start, stop, restart, or reconfigure the proxy process
- **AND** it SHALL NOT call the CLIProxyAPI management API

#### Scenario: Server startup is discovery-free
- **WHEN** the OneTool server starts with a CLIProxyAPI generation route
- **THEN** startup SHALL not probe the inference endpoint or model inventory
- **AND** unrelated tools SHALL not depend on external proxy readiness

#### Scenario: Bounded request
- **WHEN** the generation adapter sends an HTTP request
- **THEN** it SHALL apply the effective generation-route timeout and finite request
  and response byte limits
- **AND** it SHALL perform no adapter retry

#### Scenario: External correction required
- **WHEN** a CLIProxyAPI generation route is unavailable
- **THEN** the request SHALL fail until the user or CLIProxyAPI corrects the
  external state
- **AND** OneTool SHALL not offer management or lifecycle mutation as part of the
  generation call

#### Scenario: Persistent generation client
- **WHEN** multiple generation requests use the shared generation adapter
- **THEN** OneTool SHALL reuse a lazily-created HTTP client and its connection pool
- **AND** resetting owned runtime state or shutting down the server SHALL close and
  discard that owned client

### Requirement: Native grounding isolation

All `ground` operations SHALL continue to use the native Google GenAI client, a
Gemini model, `GEMINI_API_KEY`, and Google Search grounding. They SHALL NOT use the
shared generation router or CLIProxyAPI.

#### Scenario: Global CLIProxyAPI does not affect ground
- **WHEN** top-level `llm.backend` is `cliproxy` and a `ground` operation is called
- **THEN** the operation SHALL use its native Gemini configuration and `GEMINI_API_KEY`
- **AND** no request SHALL be sent to CLIProxyAPI

#### Scenario: Ground model remains native
- **WHEN** a `ground` operation is configured with a string that also resembles a
  shared model shortcut
- **THEN** OneTool SHALL pass that string only to the native Google client as its
  model selector
- **AND** it SHALL not resolve the string through top-level `models` or route the
  operation to CLIProxyAPI

### Requirement: Safe route observability

Successful generation logs SHALL expose only backend, interface, shortcut, source,
effort, latency, output size, returned token counts, and status. They SHALL omit
full model ids, proxy wire identities, credentials, and user content.

#### Scenario: Generation failure is redacted
- **WHEN** an upstream generation request fails
- **THEN** actionable errors MAY identify the configured endpoint and HTTP status
- **AND** logs and tool errors SHALL omit proxy keys, named secret values, OAuth
  state, account identities, headers, prompts, responses, and raw upstream bodies

#### Scenario: Responsibility boundary is reported
- **WHEN** effective route details or subscription guidance are shown
- **THEN** OneTool SHALL identify itself as the configuration and request adapter
- **AND** it SHALL identify the user as responsible for route choice and CLIProxyAPI
  as responsible for proxy authentication and provider routing
