# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27.0", "pydantic>=2.0.0", "pyyaml>=6.0.0"]
# ///
"""{{description}}

This is an extension tool that runs in an isolated subprocess with its own
dependencies. Extension tools use ot_sdk for configuration and logging.
"""

from __future__ import annotations

# Pack name for dot notation: {{pack}}.{{function}}()
pack = "{{pack}}"

__all__ = ["{{function}}"]

from typing import Any

import httpx
from pydantic import BaseModel, Field

from ot_sdk import (
    cache,
    get_secret,
    log,
    worker_main,
)


class Config(BaseModel):
    """Pack configuration - discovered by registry.

    Configure in ot-serve.yaml under tools.{{pack}}:
        tools:
          {{pack}}:
            timeout: 60.0
    """

    timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds",
    )


# Shared HTTP client for connection pooling (persists across calls)
_client = httpx.Client(
    timeout=60.0,
    headers={"Accept": "application/json"},
)


def _get_api_key() -> str:
    """Get API key from secrets.

    Configure in secrets.yaml:
        {{API_KEY}}: "your-api-key"
    """
    return get_secret("{{API_KEY}}") or ""


def {{function}}(
    *,
    query: str,
    timeout: float | None = None,
) -> str:
    """{{function_description}}

    Args:
        query: The query parameter
        timeout: Request timeout in seconds (defaults to config)

    Returns:
        Result string or error message

    Example:
        {{pack}}.{{function}}(query="test")
    """
    api_key = _get_api_key()
    if not api_key:
        return "Error: {{API_KEY}} secret not configured"

    with log("{{pack}}.{{function}}", query=query) as span:
        try:
            # Make API request
            response = _client.get(
                "https://api.example.com/endpoint",
                params={"q": query},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=timeout or 60.0,
            )
            response.raise_for_status()

            result = response.json()
            span.add(status=response.status_code)
            return str(result)

        except Exception as e:
            span.add(error=str(e))
            return f"Error: {e}"


if __name__ == "__main__":
    worker_main()
