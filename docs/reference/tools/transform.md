# Transform

**Data in. Structured output. One function.**

LLM-powered data transformation. Takes input data and a prompt, uses an LLM to process/transform it.

| Function                        | Description                          |
|---------------------------------|--------------------------------------|
| `transform(input, prompt, ...)` | Transform data using LLM instructions |

**Key Parameters:**
- `input`: Data to transform (any type, converted to string)
- `prompt`: Instructions for transformation
- `model`: AI model to use (uses `transform.model` from config)

**Requires configuration (tool not available until all are set):**
- `OPENAI_API_KEY` in secrets.yaml
- `transform.base_url` in ot-serve.yaml (e.g., `https://openrouter.ai/api/v1`)
- `transform.model` in ot-serve.yaml (e.g., `openai/gpt-5-mini`)

**Example:**

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
```

**Comparison:** Original implementation; no upstream dependency.

**License:** MIT
