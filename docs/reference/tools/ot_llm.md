# OT LLM

Provider-neutral LLM-powered data transformation through the shared generation route.

Short alias: `llm`

## Highlights

- Transform arbitrary values or UTF-8 files
- Select a configured model and `low`, `medium`, or `high` reasoning effort
- Request capability-checked JSON output
- Use explicit CLIProxyAPI or direct OpenAI-compatible generation

## Functions

| Function | Description |
|----------|-------------|
| `ot_llm.transform(data, prompt, ...)` | Transform data using LLM instructions |
| `ot_llm.transform_file(prompt, in_file, out_file, ...)` | Transform file content and write the output |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | any | Data to transform; converted to text |
| `prompt` | str | Transformation instructions |
| `in_file` | str | UTF-8 input path for `transform_file()` |
| `out_file` | str | Output path for `transform_file()` |
| `model` | str \| null | Exact per-call shortcut, full model id, or unique proxy alias |
| `effort` | str \| null | `low`, `medium`, or `high` |
| `json_mode` | bool | Require the selected route to support `json_object` |

## Requires

- An effective top-level or `tools.ot_llm.llm` generation route
- A matching entry in the top-level generation `models` registry
- The named secret required by that route; CLIProxyAPI routes use the
  `code.proxy` inference-client secret and do not require `OPENAI_API_KEY`

## Configuration

### Required

- Configure the selected model in top-level `models`.
- Configure a complete top-level `llm`, or a complete `tools.ot_llm.llm`.
- For CLIProxyAPI, configure `code.proxy` and its named secret.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ot_llm.llm` | generation selection \| null | `null` | Pack model/effort/timeout/output overrides, or a complete backend switch |

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

tools:
  ot_llm:
    llm:
      model: luna
      effort: medium
```

Put the matching `CLIPROXY_INFERENCE_KEY` value in `secrets.yaml`. Model identity
matching is exact; ambiguous shortcuts, ids, or proxy aliases are rejected.

### Defaults

- Selection precedence is call, pack, top-level, then model default.
- A complete pack backend switch must include every backend-specific field.
- There is no provider or paid-route fallback.

See [LLM routing](../../learn/llm-routing.md) for model metadata, backend schemas,
embedding separation, and responsibility boundaries.

## Examples

```python
# Extract structured data through a JSON-capable route
ot_llm.transform(
    data=raw_data,
    prompt="Extract name and email",
    json_mode=True,
)

# Use a configured model and effort for one call
ot_llm.transform(
    data=report,
    prompt="Summarise in three bullets",
    model="sol",
    effort="medium",
)

# Transform a UTF-8 file
ot_llm.transform_file(
    prompt="Convert this Markdown to reStructuredText",
    in_file="README.md",
    out_file="README.rst",
)
```
