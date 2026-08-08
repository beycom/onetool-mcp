# llm-routing Specification

## Purpose

Defines one lean backend-aware generation connection with direct model selection,
bounded Chat Completions and Responses adapters, an independent embedding
connection, and strict no-fallback behavior.
## Requirements
### Requirement: Backend-aware generation connection

OneTool SHALL provide one strict top-level `llm` connection for shared MCP
generation. An omitted backend SHALL resolve to `openai_compatible`; CLIProxyAPI
SHALL require explicit `backend: cliproxy`.

#### Scenario: OpenAI-compatible configuration
- **GIVEN** `llm` contains `base_url: https://api.openai.com/v1` and `model: gpt-5.4-nano`
- **WHEN** OneTool loads the configuration and starts MCP
- **THEN** validation and the MCP initialization handshake SHALL complete
- **AND** generation SHALL default to Chat Completions and `OPENAI_API_KEY`

#### Scenario: Fully omitted connection uses compatible defaults
- **WHEN** the top-level `llm` section is omitted
- **THEN** OneTool SHALL use the published OpenAI-compatible generation model, endpoint, token limit, interface, and credential defaults
- **AND** startup SHALL perform no network request

#### Scenario: Explicit compatible Responses route
- **WHEN** an OpenAI-compatible connection selects `interface: responses`
- **THEN** generation SHALL use that endpoint, interface, model, and named secret exactly once

#### Scenario: Explicit CLIProxy route
- **WHEN** `llm.backend` is `cliproxy`
- **THEN** generation SHALL use Responses and `CLIPROXY_INFERENCE_KEY`
- **AND** configuration SHALL reject explicit interface or secret-name fields

### Requirement: Deterministic direct-model selection

OneTool SHALL resolve direct `model` and optional `effort` independently in call,
pack, then root order. Backend, interface, endpoint, credential, timeout, and
output bounds SHALL come only from top-level `llm`.

#### Scenario: Call values take precedence
- **WHEN** a tool call supplies model or effort
- **THEN** each supplied value SHALL override pack and root for that call

#### Scenario: Pack values take precedence
- **WHEN** pack and root both configure model or effort
- **THEN** each pack value SHALL apply to that pack

#### Scenario: Root values provide defaults
- **WHEN** call and pack omit a value
- **THEN** top-level `llm` SHALL provide it

#### Scenario: Direct model remains unchanged
- **WHEN** any scope selects a non-empty model
- **THEN** OneTool SHALL send that exact string without registry, alias, source, route, provider, discovery, or capability resolution

### Requirement: Canonical reasoning effort

The optional effort values SHALL be exactly `low`, `medium`, and `high`. OneTool
SHALL forward a selected effort in the chosen interface's field and SHALL not
maintain model-specific support metadata.

#### Scenario: Selected effort is forwarded
- **WHEN** any scope selects a canonical effort
- **THEN** Responses SHALL receive it in `reasoning.effort`
- **AND** Chat Completions SHALL receive it in `reasoning_effort`

#### Scenario: Unsupported effort
- **WHEN** upstream rejects the selected effort
- **THEN** OneTool SHALL return the redacted upstream error without trying another value or interface

#### Scenario: Effort omitted
- **WHEN** every scope omits effort
- **THEN** the reasoning effort field SHALL be omitted upstream

### Requirement: Bounded generation adapters

The shared client SHALL encode Chat Completions and Responses requests, normalize
returned content and usage, enforce finite request, response, and timeout bounds,
and perform no routing fallback. Tool callers SHALL not supply arbitrary paths,
methods, headers, endpoints, or credentials.

#### Scenario: Request shapes
- **WHEN** an operation supplies text, images, JSON object, JSON schema, or effort
- **THEN** OneTool SHALL encode those values for the selected interface
- **AND** it SHALL not consult a capability registry or perform a probe

#### Scenario: Interface-specific output limit
- **WHEN** `llm.max_tokens` is configured
- **THEN** Chat Completions SHALL receive `max_completion_tokens`
- **AND** Responses SHALL receive `max_output_tokens`

#### Scenario: No fallback
- **WHEN** authentication, transport, HTTP status, parsing, or request support fails
- **THEN** generation SHALL fail through the selected route
- **AND** it SHALL not change interface, endpoint, credential, provider, or model

#### Scenario: Connection reuse and reset
- **WHEN** multiple generation calls run
- **THEN** they SHALL reuse one shared HTTP connection pool
- **AND** reset or shutdown SHALL close that pool

### Requirement: Independent embedding connection

Embedding consumers SHALL use only an explicit top-level `embeddings`
connection. Generation configuration SHALL not imply an embedding route.

#### Scenario: Explicit embeddings route
- **GIVEN** top-level `embeddings` is configured
- **WHEN** an embedding consumer resolves its connection
- **THEN** it SHALL use that connection's model, endpoint, named secret,
  dimensions, batching, timeout, and token limit

#### Scenario: No implicit embeddings
- **GIVEN** top-level `embeddings` is omitted
- **WHEN** an embedding consumer resolves its connection
- **THEN** no embedding route SHALL be available
- **AND** it SHALL not derive one from any generation backend or field

### Requirement: Native grounding isolation

All `ground` operations SHALL continue using the native Google GenAI client,
Gemini model, `GEMINI_API_KEY`, and Google Search grounding.

#### Scenario: Shared generation does not affect ground
- **WHEN** top-level `llm` is configured and a ground operation runs
- **THEN** it SHALL not send a request through the shared generation connection

### Requirement: Safe generation observability

Generation logs SHALL expose only backend, interface, direct model ID, optional
effort, latency, output size, returned usage, and status.

#### Scenario: Failure is redacted
- **WHEN** an upstream generation request fails
- **THEN** errors MAY identify backend, interface, model, endpoint, secret name, and status
- **AND** logs and errors SHALL omit credentials, prompts, content, headers, and raw bodies

#### Scenario: Responsibility boundary
- **WHEN** generation configuration or guidance is shown
- **THEN** OneTool SHALL identify itself as the bounded request client
- **AND** each configured external service SHALL remain responsible for provider routing and availability
