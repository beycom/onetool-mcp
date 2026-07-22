## Context

The prerequisite `add-proxied-harness-launcher` change introduces typed
CLIProxyAPI configuration, a managed or external proxy lifecycle, named inference
and management secrets, live model discovery, model shortcuts, and redacted route
observation. Its initial model registry is owned by `harness`, and its inference
client is limited to health and model discovery.

OneTool's generation consumers currently construct OpenAI-compatible clients in
several packs. `ot_llm` requires `OPENAI_API_KEY`; image vision inherits the global
LLM base URL and model but resolves keys separately; knowledge constructs separate
clients for enrichment, reranking, and synthesis; `ctx.ask` and `mem.ask` delegate
to the registered transform service. Embedding settings are mixed into the global
`llm` block and the `mem` and `knowledge` pack configs. Native grounded search is a
different protocol: `ground` uses the Google GenAI client, Gemini models, and the
Google Search grounding tool.

This change is applied only after `add-proxied-harness-launcher`. It reuses that
change's proxy process, generated configuration, client key, model discovery, and
redaction rather than introducing a second gateway or OAuth boundary.

## Goals / Non-Goals

**Goals:**

- Let generation-backed tools explicitly use managed CLIProxyAPI routes and
  subscription-authenticated models without a provider API key.
- Use one authoritative model registry for harness and tool resolution.
- Provide deterministic global, pack, operation, and per-call model and effort
  selection.
- Make `low`, `medium`, and `high` the only OneTool effort values and validate them
  against model capabilities.
- Separate embedding provider configuration from generation configuration.
- Preserve direct OpenAI-compatible generation and embedding support as explicit
  typed backends with named secrets.
- Keep native Gemini grounded search isolated from the shared generation router.
- Reuse proxy health, discovery, authentication, redaction, and warning behavior.

**Non-Goals:**

- No CLIProxyAPI embeddings route unless a future verified upstream capability adds
  one.
- No CLIProxyAPI route for `ground.search`, `ground.search_batch`, `ground.dev`,
  `ground.docs`, or `ground.reddit`.
- No replacement for Brave, Tavily, or other search-provider APIs.
- No automatic model substitution, effort rounding, provider fallback, or legacy
  configuration aliases.
- No `xhigh`, `max`, token-budget, or provider-specific effort value in the v1
  public contract.
- No model-name decoration such as `model(high)` to express effort.
- No OAuth token parsing or direct access by tool packs.

## Decisions

### Decision: Make model metadata shared configuration

Move the authoritative registry from `harness.models` to a typed top-level
`models` mapping. Each key is the unique shortcut, such as `sol`, `terra`, or
`luna`; entries retain model id, source, proxy alias, label, context, modalities,
harness compatibility, and other verified metadata while adding generation
interfaces, supported effort values, and a default effort where applicable.

Harness launch resolution and tool generation resolution consume the same typed
entry. A configured full model id resolves to the same entry as its shortcut.
Unknown and ambiguous shortcuts, ids, or aliases fail validation. There are no
hidden packaged runtime models and no `luma` alias for `luna`.

Alternative considered: duplicate a smaller tool model registry under `llm`.
Rejected because aliases, sources, proxy ids, modalities, and capability metadata
would drift between launcher and tool routes.

### Decision: Separate generation and embedding roots

Use top-level `llm` exclusively for generation and top-level `embeddings`
exclusively for vector generation. Both are strict discriminated configurations,
but they do not inherit from one another.

The generation configuration contains backend, default model shortcut, default
effort, timeout, and output limits. `backend: cliproxy` obtains its endpoint and
client credential from the prerequisite CLIProxyAPI configuration. An explicit
`openai_compatible` backend contains a base URL and named secret reference.

The embedding configuration contains its own backend, model, base URL, named secret,
dimensions, timeout, batching, and token limits. Removing `llm.embedding_model` and
the embedding interpretation of pack-level `model` and `base_url` is a clean
contract change: old keys fail normal strict validation and no legacy detector or
fallback is added.

Alternative considered: keep embeddings nested under `llm` but forbid CLIProxyAPI.
Rejected because it preserves the false implication that completion and embedding
providers share credentials, endpoints, and model resolution.

### Decision: Use reusable partial generation selections per operation

Generation-capable packs accept a typed `llm` selection at the narrowest useful
scope. Packs with one generation purpose use `tools.<pack>.llm`; packs with multiple
purposes use operation blocks such as `tools.knowledge.ask.llm` and
`tools.knowledge.enrich.llm`. Each selection may override backend, model, effort,
timeout, and output limit.

Resolution precedence is:

1. Per-call `model` and `effort` arguments.
2. Operation-specific tool selection.
3. Pack-level tool selection.
4. Top-level `llm` defaults.
5. The selected model's declared default effort.

Changing a nested selection's backend is atomic: all backend-required fields must
be valid for that backend after resolution. Backend-specific credentials or URLs
are never inherited across backend types. Resolved selections are immutable typed
values passed to shared clients; packs do not parse YAML independently.

Alternative considered: named generation profiles referenced by tools. Rejected for
v1 because model shortcuts plus layered typed selections cover the required cases
without a second user-defined naming system.

### Decision: Keep effort provider-neutral and capability-gated

The public enum is exactly `low`, `medium`, and `high`. The shared adapter converts
it to the verified wire shape for the selected protocol, such as
`reasoning_effort` for OpenAI Chat Completions. Effort never changes the resolved
model id or proxy alias.

Model metadata declares whether reasoning effort is supported and which public
levels are valid. An explicit unsupported effort fails before network I/O. When
effort is omitted, resolution uses the operation, pack, global, then model default;
if no default exists the wire field is omitted. OneTool does not round levels or map
`high` to provider-specific `xhigh` or `max`.

### Decision: Extend the shared CLIProxyAPI boundary for generation

Add an explicit, bounded Chat Completions inference method to the shared
CLIProxyAPI service. It accepts a resolved model and generation options, authenticates
with the inference client key, validates health and live model availability, and
returns the normalized response and usage metadata required by tool packs. It never
accepts an arbitrary method, path, headers, or raw credential.

Tool calls do not start, stop, restart, or reconfigure CLIProxyAPI. Managed
auto-start may be ensured during OneTool server startup when explicitly configured;
a proxy that becomes unavailable during a call produces an actionable error with
the existing lifecycle command. There is no direct-provider fallback.

Alternative considered: let every pack construct an OpenAI client pointed at the
proxy. Rejected because it duplicates secret resolution, capability checks,
redaction, health behavior, and failure semantics.

### Decision: Route each generation consumer explicitly

- `ot_llm.transform` and `transform_file` use `tools.ot_llm.llm` and accept
  per-call model and effort.
- `image.ask` and `image.summary` use `tools.ot_image.llm`, require image-input
  capability, and accept per-call model and effort where a network call occurs.
- `ctx.ask` and `mem.ask` use their ask selections and accept model and effort.
- Knowledge reranking, synthesis, and enrichment use operation-specific selections;
  `knowledge.ask` accepts model and effort for both generation stages unless a more
  specific configured rerank selection exists.
- Embedding-backed memory and knowledge operations use only the effective
  `embeddings` selection and their embedding-specific enablement, dimension, and
  batching settings.

Public results remain compatible except for new optional arguments and clearer
configuration or routing failures.

### Decision: Keep grounded search outside generation routing

The `ground` pack continues to require `google-genai`, `GEMINI_API_KEY`, a Gemini
model, and the native Google Search grounding tool. It does not read top-level
`llm`, does not accept a CLIProxyAPI backend, and does not resolve `sol`, `terra`,
or `luna`. This preserves real grounded-search provenance instead of treating
generic model generation as web search.

### Decision: Preserve redaction and subscription warnings

Logs and tool errors may include backend, shortcut, resolved model, source, effort,
latency, and token counts. They omit proxy keys, named secret values, OAuth state,
account identities, headers, prompts, responses, and raw upstream bodies. The
subscription and billing warnings from the prerequisite change apply to tool routes
as well as harness routes; OneTool does not describe them as guaranteed included
subscription usage.

## Risks / Trade-offs

- [Risk] CLIProxyAPI protocol and effort translation changes across releases. ->
  Mitigation: prerequisite version/capability detection, verified fixtures, strict
  response parsing, and no guessed fallback fields.
- [Risk] A shared shortcut may be harness-compatible but unsuitable for a tool. ->
  Mitigation: validate generation interface, modality, JSON, and effort capabilities
  for the requested operation before network I/O.
- [Risk] Layered configuration can produce surprising selections. -> Mitigation:
  fixed precedence, typed effective-route inspection, and tests for every layer.
- [Risk] Moving the registry and embedding keys breaks current version 2 configs. ->
  Mitigation: document the new shape and fail old keys through strict validation;
  do not add compatibility aliases or silent migration.
- [Risk] Subscription-backed traffic may be charged, restricted, or rejected by an
  upstream provider. -> Mitigation: explicit opt-in, inherited warnings, no billing
  claim, actionable failures, and retained explicit direct backends.
- [Risk] A proxy outage disables configured generation tools. -> Mitigation: startup
  readiness, per-call health/model validation, lifecycle diagnostics, and no
  ambiguous direct fallback.

## Migration Plan

1. Complete and verify `add-proxied-harness-launcher`, including its model registry,
   CLIProxyAPI service, generated config, lifecycle, discovery, and redaction.
2. Move model registry ownership to top-level `models` and update launcher consumers
   before enabling tool routing.
3. Add strict `llm` generation and `embeddings` configuration and update templates;
   remove `llm.embedding_model` and superseded pack embedding fields cleanly.
4. Add shared generation selection, effort validation, and explicit CLIProxyAPI and
   direct OpenAI-compatible adapters.
5. Migrate `ot_llm`, image, context, memory, and knowledge generation consumers.
6. Update embedding consumers to use only the independent embedding configuration.
7. Add startup readiness, observability, documentation, and opt-in integration tests.

Rollback restores the previous tool clients and configuration schema together. It
does not retain new keys as aliases, and it does not alter CLIProxyAPI OAuth state or
the prerequisite's generated runtime files.

## Open Questions

None. Current model ids, supported modalities, effort levels, JSON behavior, and
CLIProxyAPI wire translation must be verified during implementation and captured as
capability fixtures rather than inferred at runtime.
