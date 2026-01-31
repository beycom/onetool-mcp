"""{{description}}

A simple in-process tool with no external dependencies.
Uses httpx (bundled) for HTTP requests.
"""

from __future__ import annotations

pack = "{{pack}}"

import httpx

__all__ = ["{{function}}"]

from ot.logging import LogSpan

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
            result = f"Processed: {input}"
            s.add(outputLen=len(result))
            return result
        except Exception as e:
            s.add(error=str(e))
            return f"Error: {e}"
