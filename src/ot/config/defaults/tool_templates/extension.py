"""{{description}}

An extension tool with full onetool access.
Runs in-process with access to ot.logging, ot.config, and ot.tools.
Uses httpx (bundled) for HTTP requests.
"""

from __future__ import annotations

pack = "{{pack}}"

import httpx

__all__ = ["{{function}}"]

from ot.config import get_secret, get_tool_config
from ot.logging import LogSpan
# Optional: for calling other tools
# from ot.tools import call_tool, get_pack

# Shared HTTP client (connection pooling)
_client = httpx.Client(timeout=30.0, follow_redirects=True)


def {{function}}(
    *,
    input: str,
) -> str:
    """{{function_description}}

    Args:
        input: The input string

    Returns:
        Processed result or error message

    Example:
        {{pack}}.{{function}}(input="hello")
    """
    with LogSpan(span="{{pack}}.{{function}}", inputLen=len(input)) as s:
        try:
            # TODO: Implement your logic here
            # Access secrets: api_key = get_secret("MY_API_KEY")
            # Access config: timeout = get_tool_config("{{pack}}", "timeout", 30.0)
            # Call other tools: result = call_tool("llm.transform", input=text, prompt="...")
            result = f"Processed: {input}"
            s.add(outputLen=len(result))
            return result
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"
