## Why

OneTool's LLM-backed tools currently require separately configured API credentials and
resolve models inconsistently across global and pack-specific settings. Users who opt
into the managed CLIProxyAPI subsystem need those generation calls to use the same
subscription-backed gateway, model registry, and explicit reasoning effort without
coupling embeddings or native Gemini grounding to that route.

This change depends on `openspec/roadmap/add-proxied-harness-launcher`; its shared
CLIProxyAPI configuration, lifecycle, authentication, model discovery, and redaction
contracts must be implemented first.

## What Changes

- Add a shared generation-routing contract with explicit `cliproxy` and
  `openai_compatible` backends, named model resolution, capability validation, and
  canonical `low`, `medium`, and `high` effort values.
- Move the authoritative model registry out of harness-only ownership so launcher and
  tool routes share shortcuts such as `sol`, `terra`, and `luna` without aliases or
  hidden model definitions.
- **BREAKING**: Separate top-level embedding configuration from `llm` generation configuration;
  embedding clients, models, dimensions, and credentials never inherit from a
  CLIProxyAPI generation route. Remove `llm.embedding_model` and the embedding
  interpretation of pack-level `model`/`base_url` fields without compatibility
  aliases or legacy-key handling.
- Add pack- and operation-specific LLM route configuration for transforms, image
  analysis, context and memory Q&A, and knowledge enrichment, reranking, and
  synthesis.
- Add per-call `model` and `effort` overrides to generation-backed tool operations,
  with deterministic precedence and actionable unsupported-combination errors.
- Keep `ground.search` and related grounded-search operations exclusively on the
  native Gemini client and `GEMINI_API_KEY`; global or tool CLIProxyAPI routes do not
  affect them.
- Remove hard-coded `OPENAI_API_KEY` availability requirements from generation tools
  when their effective backend is CLIProxyAPI. Direct OpenAI-compatible routes remain
  explicit and use named OneTool secrets.
- Prohibit silent direct-provider fallback when a configured CLIProxyAPI route is
  unhealthy, unavailable, or incompatible.

## Capabilities

### New Capabilities

- `llm-routing`: Shared model registry, generation backend selection, model and effort
  resolution, CLIProxyAPI inference routing, capability validation, and failure
  behavior for LLM-backed tools.

### Modified Capabilities

- `serve-configuration`: Separate models, generation, and embedding configuration and
  validate reusable global, pack, and operation-level route selections.
- `ottools/tool-llm`: Route transforms through the effective generation backend and
  expose model and effort overrides without a mandatory provider API key.
- `ottools/tool-image`: Route vision analysis through a capability-compatible backend
  with model and effort controls.
- `ctx`: Route `ctx.ask` through its effective generation selection and expose effort
  control alongside model control.
- `ottools/tool-mem`: Separate embedding settings from `mem.ask` generation routing
  and expose model and effort controls for Q&A.
- `knowledge-pack`: Separate embedding configuration from enrichment, reranking, and
  synthesis generation routes and expose operation-specific model and effort control.

## Impact

- Depends on the `add-proxied-harness-launcher` roadmap change and its CLIProxyAPI
  management/runtime services.
- Affects typed configuration models and templates, shared inference resolution,
  generation clients, service registration, tool pack configuration, and MCP tool
  signatures.
- Affects `ot_llm`, `ot_image`, `ctx`, `mem`, and `knowledge`; `ground`, Brave, and
  Tavily provider behavior remains unchanged.
- Requires strict offline tests for precedence, backend isolation, shortcut and effort
  validation, capability gating, secret redaction, proxy failure, and the absence of
  direct fallback.
- Requires user-facing configuration and tool documentation updates. Subscription
  routing remains explicit third-party behavior and carries the warnings defined by
  the prerequisite launcher change.
