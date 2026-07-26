# OT LLM

LLM-powered data transformation tools. Takes input data and a prompt, uses an LLM to process/transform it.

Short alias: `llm`

## Highlights

- Single function for any data transformation
- Configurable model via OpenRouter or OpenAI-compatible API
- Chain with other tools for structured output extraction

## Functions

| Function | Description |
|----------|-------------|
| `ot_llm.transform(data, prompt, ...)` | Transform data using LLM instructions |
| `ot_llm.transform_file(prompt, in_file, out_file, ...)` | Transform file content and write to output |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | any | Data to transform (converted to string) |
| `prompt` | str | Instructions for transformation |
| `in_file` | str | Input file path (for transform_file) |
| `out_file` | str | Output file path (for transform_file) |
| `model` | str | AI model to use (uses `ot_llm.model` from config) |
| `json_mode` | bool | If True, request JSON output format (default: False) |

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `core`.

| Kind | Requirement | Purpose | Availability |
|---|---|---|---|
| `lib` | `openai` (import `openai`, OneTool `core`) | Call OpenAI-compatible language model APIs | Required |
| `secret` | `OPENAI_API_KEY` | Authenticate model requests | Required |
| `config` | `model` | Select the language model used by transform | Required |

Use `ot.help(query='<pack>', topic='setup')` for current readiness and non-mutating setup guidance.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Examples

```python
# Extract structured data from search results
ot_llm.transform(
    data=brave.search(query="gold price today"),
    prompt="Extract the current gold price in USD/oz as a single number"
)

# Convert to YAML format
ot_llm.transform(
    data=some_data,
    prompt="Return ONLY valid YAML with fields: name, price, url"
)

# Summarize content
ot_llm.transform(
    data=webfetch.fetch(url="https://docs.python.org/3/library/json.html"),
    prompt="Summarize the main points in 3 bullet points"
)

# Get JSON output with json_mode
ot_llm.transform(
    data=raw_data,
    prompt="Extract name and email fields",
    json_mode=True
)

# Transform a file
ot_llm.transform_file(
    prompt="Convert this markdown to reStructuredText format",
    in_file="README.md",
    out_file="README.rst"
)
```

## Configuration

### Required

- `OPENAI_API_KEY` must be set in `secrets.yaml`.
- `base_url` and `model` must be configured via top-level `llm:` or `tools.ot_llm.*`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ot_llm.base_url` | string | `""` | Overrides `llm.base_url` for this tool only. |
| `tools.ot_llm.model` | string | `""` | Overrides `llm.model` for this tool only. |
| `tools.ot_llm.timeout` | int | `30` | API timeout in seconds. |
| `tools.ot_llm.max_tokens` | int \| null | `null` | Max response tokens. `null` means no limit. |

Configure `base_url` and `model` once at the top level for all LLM-using tools (`ot_llm`, `ot_image`, `mem`, `knowledge`, `ctx`):

```yaml
llm:
  base_url: https://openrouter.ai/api/v1
  model: google/gemini-2-flash-preview
  embedding_model: text-embedding-3-small  # for mem and knowledge

# Per-tool override (optional)
tools:
  ot_llm:
    timeout: 30
    max_tokens: null
```

### Defaults

- `timeout` defaults to `30`.
- `max_tokens` defaults to `null`.
- `base_url` and `model` fall back to the top-level `llm:` block; the tool is not usable if neither is set.
