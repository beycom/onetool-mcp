# Shared LLM Generation

OneTool uses one bounded, backend-aware connection for generation-backed MCP
tools. Ordinary OpenAI-compatible endpoints are the default; CLIProxyAPI is an
explicit option. Both use direct model IDs and the same provider-neutral
request/result boundary.

## OpenAI-Compatible Configuration

Configure an OpenAI-compatible generation route like this:

```yaml
llm:
  base_url: https://api.openai.com/v1
  model: gpt-5.4-nano
```

When omitted, `backend`, `interface`, and `secret_name` default to
`openai_compatible`, `chat_completions`, and `OPENAI_API_KEY`. The complete
defaults also include `model: gpt-5.4-nano` and `max_tokens: 4096`.

For another compatible provider, configure its endpoint and named secret:

```yaml
llm:
  backend: openai_compatible
  interface: chat_completions  # or responses
  base_url: https://openrouter.ai/api/v1
  model: openai/gpt-5.4-nano
  secret_name: OPENROUTER_API_KEY
  timeout: 30
  max_tokens: 4096
```

## CLIProxyAPI Configuration

CLIProxyAPI must be selected explicitly:

```yaml
llm:
  backend: cliproxy
  base_url: http://127.0.0.1:8317/v1
  model: gpt-5.6-luna
  effort: low
  timeout: 30
  max_tokens: 4096
```

This backend always uses `<base_url>/responses` and resolves the fixed
`CLIPROXY_INFERENCE_KEY`. It does not accept `interface`, `secret_name`, or
other unknown fields; strict validation rejects mixed-backend or unknown fields.

Put credentials in the server's `secrets.yaml`:

```yaml
OPENAI_API_KEY: sk-...
OPENROUTER_API_KEY: your-openrouter-key
CLIPROXY_INFERENCE_KEY: your-inference-client-key
```

The standalone code launcher is separate. It reads CLIProxy settings from its
process environment and never reads the MCP server's `llm` or `secrets.yaml`.

## Model and Effort Selection

Model and effort resolve independently in this order:

1. Public call argument
2. Pack configuration
3. Top-level `llm`

Pack overrides remain direct fields:

```yaml
tools:
  ot_image:
    model: gpt-5.6-terra
    effort: low
  knowledge:
    model: gpt-5.6-luna
    effort: medium
```

OneTool sends the selected model string unchanged. It does not restore model
registries, aliases, provider metadata, capability declarations, or discovery.

## Request and Failure Boundary

The shared client supports text, image input, JSON object, and JSON schema
requests through Chat Completions or Responses. Public `max_tokens` becomes
`max_completion_tokens` for Chat Completions and `max_output_tokens` for
Responses.

Each call makes one bounded request. OneTool never retries through another
interface, endpoint, credential, provider, or model. Errors and logs omit secrets,
prompts, content, headers, and raw response bodies.

## Embeddings

Embedding consumers use an independent top-level `embeddings` connection:

```yaml
embeddings:
  backend: openai_compatible
  model: text-embedding-3-small
  base_url: https://api.openai.com/v1
  secret_name: OPENAI_API_KEY
  dimensions: 1536
```

Generation never implies an embedding endpoint. Configure top-level `embeddings`
for any embedding-backed tool, regardless of the generation backend.

## Opt-in Live Verification

```bash
ONETOOL_LIVE_CLIPROXY_LLM=confirmed \
  uv run pytest tests/integration/core/test_generation_routes.py
```

Live tests may consume configured upstream capacity.
