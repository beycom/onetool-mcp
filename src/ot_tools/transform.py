# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=1.0.0", "httpx>=0.27.0", "pyyaml>=6.0.0"]
# ///
"""Transform - LLM-powered data transformation.

Takes input data and a prompt, uses an LLM to transform/process it.

Example:
    llm.transform(
        brave.search(query="metal prices", count=10),
        prompt="Extract prices as YAML with fields: metal, price, unit, url",
    )

Supports OpenAI API and OpenRouter (OpenAI-compatible).

**Requires configuration:**
- OPENAI_API_KEY in secrets.yaml
- transform.base_url in ot-serve.yaml (e.g., https://openrouter.ai/api/v1)
- transform.model in ot-serve.yaml (e.g., openai/gpt-5-mini)

Tool is not available until all three are configured.
"""

from __future__ import annotations

# Namespace for dot notation: llm.transform()
namespace = "llm"

__all__ = ["transform"]

from typing import Any

from openai import OpenAI

from ot_sdk import get_config, get_secret, log, worker_main


def _get_api_config() -> tuple[str | None, str | None, str | None]:
    """Get API configuration from settings.

    Returns:
        Tuple of (api_key, base_url, default_model) - all None if not configured
    """
    api_key = get_secret("OPENAI_API_KEY")
    base_url = get_config("transform.base_url")
    default_model = get_config("transform.model")
    return api_key, base_url, default_model


def transform(
    *,
    input: Any,
    prompt: str,
    model: str | None = None,
) -> str:
    """Transform input data using an LLM.

    Takes any input data (typically a string result from another tool call)
    and processes it according to the prompt instructions.

    Args:
        input: Data to transform (will be converted to string if not already)
        prompt: Instructions for how to transform/process the input
        model: AI model to use (uses transform.model from config if not specified)

    Returns:
        The LLM's response as a string, or error message if not configured

    Examples:
        # Extract structured data from search results
        llm.transform(
            input=brave.search(query="gold price today", count=5),
            prompt="Extract the current gold price in USD/oz as a single number",
        )

        # Convert to YAML format
        llm.transform(
            input=brave.search(query="metal prices", count=10),
            prompt="Return ONLY valid YAML with fields: metal, price, unit, url",
        )

        # Summarize content
        llm.transform(
            input=some_long_text,
            prompt="Summarize this in 3 bullet points"
        )
    """
    with log("llm.transform", promptLen=len(prompt)) as s:
        # Get API config
        api_key, base_url, default_model = _get_api_config()

        # Check if transform tool is configured
        if not api_key:
            s.add(error="not_configured")
            return "Error: Transform tool not available. Set OPENAI_API_KEY in secrets.yaml."

        if not base_url:
            s.add(error="no_base_url")
            return (
                "Error: Transform tool not available. Set transform.base_url in config."
            )

        # Convert input to string
        input_str = str(input)
        s.add(inputLen=len(input_str))

        # Create client
        client = OpenAI(api_key=api_key, base_url=base_url)

        # Build the message
        user_message = f"""Input data:
{input_str}

Instructions:
{prompt}"""

        used_model = model or default_model
        if not used_model:
            s.add(error="no_model")
            return "Error: Transform tool not available. Set transform.model in config."

        s.add(model=used_model)

        try:
            response = client.chat.completions.create(
                model=used_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data transformation assistant. Follow the user's instructions precisely. Output ONLY the requested format, no explanations.",
                    },
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
            )
            result = response.choices[0].message.content or ""
            s.add(outputLen=len(result))
            return result
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"


if __name__ == "__main__":
    worker_main()
