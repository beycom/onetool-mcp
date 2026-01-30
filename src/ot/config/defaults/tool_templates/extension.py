# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.0.0", "pyyaml>=6.0.0"]
# ///
"""{{description}}

An extension tool that runs in an isolated subprocess.
Add dependencies to the script block above as needed.
"""

from __future__ import annotations

# Pack name for dot notation: {{pack}}.{{function}}()
pack = "{{pack}}"

__all__ = ["{{function}}"]

from ot_sdk import log, worker_main

# --- Optional: Additional SDK imports ---
# Uncomment the imports you need:
# from ot_sdk import get_secret, get_config, cache
# from ot_sdk import http, safe_request, api_headers
# from ot_sdk import call_tool, get_pack

# --- Optional: HTTP client for API calls ---
# Add "httpx>=0.27.0" to dependencies above, then uncomment:
# import httpx
# _client = httpx.Client(
#     timeout=60.0,
#     headers={"Accept": "application/json"},
# )

# --- Optional: API key configuration ---
# def _get_api_key() -> str:
#     """Get API key from secrets.yaml: {{API_KEY}}: "your-key" """
#     return get_secret("{{API_KEY}}") or ""


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
    with log("{{pack}}.{{function}}", inputLen=len(input)) as span:
        try:
            # TODO: Implement your logic here
            result = f"Processed: {input}"
            span.add(outputLen=len(result))
            return result
        except Exception as e:
            span.add(error=str(e))
            return f"Error: {e}"


if __name__ == "__main__":
    worker_main()
