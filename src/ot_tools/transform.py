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
- transform.base_url in onetool.yaml (e.g., https://openrouter.ai/api/v1)
- transform.model in onetool.yaml (e.g., openai/gpt-5-mini)

Tool is not available until all three are configured.
"""

from __future__ import annotations

# Pack for dot notation: llm.transform()
pack = "llm"

__all__ = ["transform"]

# Dependency declarations for CLI validation
__ot_requires__ = {
    "lib": [("openai", "pip install openai")],
    "secrets": ["OPENAI_API_KEY"],
}

from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

from ot.config import get_secret, get_tool_config
from ot.logging import LogSpan


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    base_url: str = Field(
        default="",
        description="OpenAI-compatible API base URL (e.g., https://openrouter.ai/api/v1)",
    )
    model: str = Field(
        default="",
        description="Model to use for transformation (e.g., openai/gpt-4o-mini)",
    )
    timeout: int = Field(
        default=30,
        description="API timeout in seconds",
    )
    max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens in response (None=no limit)",
    )


def _get_config() -> Config:
    """Get transform pack configuration."""
    return get_tool_config("transform", Config)


def _get_api_config() -> tuple[str | None, str | None, str | None, Config]:
    """Get API configuration from settings.

    Returns:
        Tuple of (api_key, base_url, default_model, config) - api_key/base_url/model
        are None if not configured
    """
    config = _get_config()
    api_key = get_secret("OPENAI_API_KEY")
    base_url = config.base_url or None
    default_model = config.model or None
    return api_key, base_url, default_model, config


def transform(
    *,
    input: Any,
    prompt: str,
    model: str | None = None,
    json_mode: bool = False,
) -> str:
    """Transform input data using an LLM.

    Takes any input data (typically a string result from another tool call)
    and processes it according to the prompt instructions.

    Args:
        input: Data to transform (will be converted to string if not already)
        prompt: Instructions for how to transform/process the input
        model: AI model to use (uses transform.model from config if not specified)
        json_mode: If True, request JSON output format from the model

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

        # Get JSON output
        llm.transform(
            input=data,
            prompt="Extract name and email as JSON",
            json_mode=True
        )
    """
    with LogSpan(span="llm.transform", promptLen=len(prompt)) as s:
        # Validate inputs
        if not prompt or not prompt.strip():
            s.add(error="empty_prompt")
            return "Error: prompt is required and cannot be empty"

        input_str = str(input)
        if not input_str.strip():
            s.add(error="empty_input")
            return "Error: input is required and cannot be empty"

        s.add(inputLen=len(input_str))

        # Get API config
        api_key, base_url, default_model, config = _get_api_config()

        # Check if transform tool is configured
        if not api_key:
            s.add(error="not_configured")
            return "Error: Transform tool not available. Set OPENAI_API_KEY in secrets.yaml."

        if not base_url:
            s.add(error="no_base_url")
            return (
                "Error: Transform tool not available. Set transform.base_url in config."
            )

        # Create client with timeout
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=config.timeout)

        # Build the message
        user_message = f"""Input data:
{input_str}

Instructions:
{prompt}"""

        used_model = model or default_model
        if not used_model:
            s.add(error="no_model")
            return "Error: Transform tool not available. Set transform.model in config."

        s.add(model=used_model, jsonMode=json_mode)

        try:
            # Build API call kwargs
            api_kwargs: dict[str, Any] = {
                "model": used_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a data transformation assistant. Follow the user's instructions precisely. Output ONLY the requested format, no explanations.",
                    },
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.1,
            }

            if config.max_tokens is not None:
                api_kwargs["max_tokens"] = config.max_tokens

            if json_mode:
                api_kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**api_kwargs)
            result = response.choices[0].message.content or ""
            s.add(outputLen=len(result))

            # Log token usage if available
            if response.usage:
                s.add(
                    inputTokens=response.usage.prompt_tokens,
                    outputTokens=response.usage.completion_tokens,
                    totalTokens=response.usage.total_tokens,
                )

            return result
        except Exception as e:
            error_msg = str(e)
            # Sanitize sensitive info from error messages
            if "api_key" in error_msg.lower() or "sk-" in error_msg:
                error_msg = "Authentication error - check OPENAI_API_KEY in secrets.yaml"
            s.add(error=error_msg)
            return f"Error: {error_msg}"
