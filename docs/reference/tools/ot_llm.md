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
| `model` | str \| null | Per-call shortcut or full model id |
| `effort` | str \| null | `low`, `medium`, or `high` |
| `json_mode` | bool | Require the selected route to support `json_object` |

## Requires

- An effective top-level or `tools.ot_llm.llm` generation route
- The named secret required by that route; CLIProxyAPI routes use the
  `code.cliproxy` inference-client secret and do not require `OPENAI_API_KEY`

## Configuration

### Required

- Configure a complete top-level `llm`, or a complete `tools.ot_llm.llm`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ot_llm.llm` | generation selection \| null | `null` | Pack model/effort/timeout/output overrides, or a complete backend switch |

```yaml
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
      model: sol
      effort: medium
```

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
