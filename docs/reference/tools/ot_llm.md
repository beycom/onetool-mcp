# OT LLM

LLM-powered data transformation through the shared backend-aware generation client.

Short alias: `llm`

## Functions

| Function | Description |
|----------|-------------|
| `ot_llm.transform(data, prompt, ...)` | Transform data using LLM instructions |
| `ot_llm.transform_file(prompt, in_file, out_file, ...)` | Transform UTF-8 file content and write the output |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | any | Data to transform; converted to text and treated as untrusted content |
| `prompt` | str | Transformation instructions |
| `in_file` | str | UTF-8 input path for `transform_file()` |
| `out_file` | str | Output path for `transform_file()` |
| `model` | str \| null | Direct model ID override |
| `effort` | str \| null | `low`, `medium`, or `high` |
| `json_mode` | bool | Request a JSON object through the selected interface |

## Requires

- Top-level `llm` defaults or overrides in `onetool.yaml`
- The resolved connection secret in the server's `secrets.yaml`

## Configuration

```yaml
llm:
  backend: cliproxy
  base_url: http://127.0.0.1:8317/v1
  model: gpt-5.6-luna
  effort: low
  timeout: 30
  max_tokens: 4096

tools:
  ot_llm:
    model: gpt-5.6-luna
    effort: medium
```

The model and effort precedence is call, pack, then root. Model IDs are sent
unchanged, without aliases or capability lookup. The configured service or model
returns the authoritative error for unsupported structured output or effort.
There is no model, endpoint, provider, interface, or paid-route fallback.

See [Shared LLM generation](../../learn/llm-routing.md).

## Examples

```python
ot_llm.transform(
    data=raw_data,
    prompt="Extract name and email",
    json_mode=True,
)

ot_llm.transform(
    data=report,
    prompt="Summarise in three bullets",
    model="gpt-5.6-luna",
    effort="medium",
)

ot_llm.transform_file(
    prompt="Convert this Markdown to reStructuredText",
    in_file="README.md",
    out_file="README.rst",
)
```
