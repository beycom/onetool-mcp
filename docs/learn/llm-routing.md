# LLM routing

OneTool routes generation-backed tools through one strict model registry and an
explicit generation backend. Generation can use an externally managed CLIProxyAPI
endpoint or an independent OpenAI-compatible endpoint. Embeddings are configured
separately and never inherit generation settings.

OneTool configures and sends the selected route. It does not guarantee provider
compatibility, terms compliance, model availability, subscription classification,
included usage, rate limits, credits, or billing treatment. You are responsible for
the selected route; CLIProxyAPI owns proxy authentication and provider routing.

## Model registry

Every selectable model has a shortcut, full id, source, modalities, and explicit
generation capabilities:

- `interfaces`: `responses` and/or `chat_completions`
- `structured_outputs`: verified `json_object` and `json_schema` support per interface
- `efforts`: any supported values from `low`, `medium`, and `high`
- `default_effort`: the effort used only when no narrower layer selects one

For example, this registry supports both backend examples below:

```yaml
models:
  luna:
    shortcut: luna
    id: gpt-5.6-luna
    source: codex_subscription
    proxy_alias: gpt-5.6-luna
    modalities: [text]
    interfaces: [responses]
    structured_outputs:
      responses: [json_object, json_schema]
    efforts: [low, medium, high]
    default_effort: low

  glm52:
    shortcut: glm52
    id: z-ai/glm-5.2
    source: openrouter
    modalities: [text]
    interfaces: [chat_completions]
    structured_outputs:
      chat_completions: [json_object, json_schema]
    efforts: [low, medium, high]
```

A shortcut, full id, or unique proxy alias resolves to the same entry. Unknown or
ambiguous identities fail before network I/O. OneTool does not infer interfaces,
modalities, structured output, or effort from a model name.

Generation defaults are configured explicitly in the top-level `llm` selection.
They are not inferred from code launcher routes. The optional `code-routing.yaml`
launcher template does not install this generation registry.

## Backends

### CLIProxyAPI

```yaml
code:
  proxy:
    routes:
      codex_subscription:
        - id: gpt-5.6-luna

llm:
  backend: cliproxy
  interface: responses
  model: luna
  effort: low
  timeout: 30
  max_output_tokens: 4096
```

This backend reuses `code.proxy.base_url` and its named inference-client secret.
The top-level `models` registry and any generation-only `proxy_alias` remain
independent from launcher records in `code.proxy.routes`.
Codex-subscription models require the verified Responses interface. OneTool sends
direct bounded HTTP requests; it does not run Codex, Claude Code, or CLIProxyAPI,
read their auth/config files, manage the proxy, or call management endpoints.

The intended benefit is avoiding a separate provider API charge while applicable
subscription capacity is available. That is not a promise that requests are
included, free, compliant, continuously available, or exempt from credits or other
charges. OneTool never falls back to OpenRouter, a paid API, another model, or
another transport when this route fails.

### Direct OpenAI-compatible

```yaml
llm:
  backend: openai_compatible
  interface: chat_completions
  model: glm52
  base_url: https://openrouter.ai/api/v1
  secret_name: OPENROUTER_API_KEY
  timeout: 30
  max_output_tokens: 4096
```

A direct route owns its base URL and named secret. It does not reuse the
CLIProxyAPI endpoint or credential. Put the exact named value in `secrets.yaml`.

## Selection precedence

Generation fields resolve in this order:

```text
per-call > operation > pack > top-level llm > model default
```

Pack and operation selections may partially override `model`, `effort`, `timeout`,
or `max_output_tokens`. A backend switch is atomic: it must provide a complete
discriminated backend, including the interface and, for a direct route, its base URL
and named secret.

```yaml
tools:
  ot_llm:
    llm:
      model: sol
      effort: medium
  ot_image:
    llm:
      model: terra
  knowledge:
    llm:
      model: luna
    rerank:
      llm:
        effort: low
    ask:
      llm:
        effort: medium
    enrich:
      llm:
        model: sol
```

`model` and `effort` arguments on `ot_llm`, image, context, memory, and knowledge
calls override configured selections. On `knowledge.ask()`, they apply to both
reranking and synthesis.

## Effective-route inspection

Strict configuration validation reports removed keys, incomplete backend switches,
unknown models, and unsupported interface/capability combinations at load or before
network I/O. Server startup does not probe CLIProxyAPI or scan nested pack routes.
Each generation call sends its configured wire model identity directly and reports
an external-route failure only to that call.

After a successful call, the structured `generation.completed` log entry is the
effective-route record. It contains only backend, interface, shortcut, source,
effort, latency, output size, and returned token counts. It omits endpoints, named
secret values, credentials, full model ids, proxy wire identities, headers, prompts,
responses, and raw bodies.

Use finite `timeout` and `max_output_tokens` values. The adapter also caps encoded
requests at 16 MiB and streamed responses at 8 MiB and performs no retries or
provider fallback. Returned usage is observational; upstream capacity and billing
systems remain authoritative.

## Independent embeddings

```yaml
embeddings:
  backend: openai_compatible
  model: text-embedding-3-small
  base_url: https://api.openai.com/v1
  secret_name: OPENAI_API_KEY
  dimensions: 1536
  timeout: 60
  batch_size: 200
  max_tokens: 8191

tools:
  mem:
    embeddings_enabled: true
    embeddings_async: true
```

Memory and knowledge embeddings use only this root. They never use CLIProxyAPI
generation endpoints, generation credentials, model defaults, or pack generation
selections. Removed fields such as `llm.embedding_model`, `tools.mem.model`,
`tools.mem.base_url`, `tools.mem.dimensions`, `tools.knowledge.model`,
`tools.knowledge.base_url`, and `tools.knowledge.enrich_model` are invalid.

The `ground` pack remains isolated: it uses the native Google GenAI client,
`GEMINI_API_KEY`, a Gemini model, and Google Search grounding regardless of `llm`.

## Image summary cache

`ot_image.summary()` resolves a generation route only on a cache miss. A cached
summary is returned without checking a model, effort, endpoint, or secret, and
changing a generation selection does not invalidate it.

## Live verification

The default suite is offline. Live checks require explicit confirmation because
they may consume subscription allowance or incur provider charges:

```bash
ONETOOL_LIVE_CLIPROXY_LLM=confirmed \
  uv run pytest tests/integration/core/test_generation_routes.py \
  -k subscription

ONETOOL_LIVE_DIRECT_LLM=confirmed \
  uv run pytest tests/integration/core/test_generation_routes.py \
  -k direct
```

Protocol provenance is recorded in
`tests/fixtures/llm_routing/cliproxyapi-7.2.95.yaml`; the observed release is not a
runtime pin.

## Upstream references

- [Code harness routing and ownership boundary](code-routing.md)
- [CLIProxyAPI configuration options](https://help.router-for.me/configuration/options)
- [CLIProxyAPI canonical configuration example](https://github.com/router-for-me/CLIProxyAPI/blob/main/config.example.yaml)
- [CLIProxyAPI Codex client guide](https://help.router-for.me/agent-client/codex)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [Codex configuration](https://developers.openai.com/codex/config-basic/)
- [Claude Code settings](https://code.claude.com/docs/en/settings)
