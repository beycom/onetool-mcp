# LLM Tools

**Data in. Structured output. One function.**

LLM-powered data transformation tools. Takes input data and a prompt, uses an LLM to process/transform it.

## Highlights

- Single function for any data transformation
- Configurable model via OpenRouter or OpenAI-compatible API
- Chain with other tools for structured output extraction

## Functions

| Function | Description |
|----------|-------------|
| `llm.transform(input, prompt, ...)` | Transform data using LLM instructions |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `input` | any | Data to transform (converted to string) |
| `prompt` | str | Instructions for transformation |
| `model` | str | AI model to use (uses `transform.model` from config) |

## Requires

Configuration (tool not available until all are set):
- `OPENAI_API_KEY` in secrets.yaml
- `transform.base_url` in onetool.yaml (e.g., `https://openrouter.ai/api/v1`)
- `transform.model` in onetool.yaml (e.g., `openai/gpt-5-mini`)

## Examples

```python
# Extract structured data from search results
llm.transform(
    input=brave.search(query="gold price today"),
    prompt="Extract the current gold price in USD/oz as a single number"
)

# Convert to YAML format
llm.transform(
    input=some_data,
    prompt="Return ONLY valid YAML with fields: name, price, url"
)

# Summarize content
llm.transform(
    input=web.fetch(url="https://example.com/article"),
    prompt="Summarize the main points in 3 bullet points"
)
```

## Configuration

Add to `onetool.yaml`:

```yaml
tools:
  transform:
    base_url: https://openrouter.ai/api/v1
    model: openai/gpt-5-mini
```

## Source

[OpenRouter API](https://openrouter.ai/docs) | [OpenAI API](https://platform.openai.com/docs)
