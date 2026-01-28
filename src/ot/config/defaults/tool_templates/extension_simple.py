# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.0.0", "pyyaml>=6.0.0"]
# ///
"""{{description}}

A simple extension tool that runs in an isolated subprocess.
"""

from __future__ import annotations

# Pack name for dot notation: {{pack}}.{{function}}()
pack = "{{pack}}"

__all__ = ["{{function}}"]

from ot_sdk import log, worker_main


def {{function}}(
    *,
    input: str,
) -> str:
    """{{function_description}}

    Args:
        input: The input string

    Returns:
        Processed result

    Example:
        {{pack}}.{{function}}(input="hello")
    """
    with log("{{pack}}.{{function}}", inputLen=len(input)) as span:
        # Process the input
        result = f"Processed: {input}"
        span.add(outputLen=len(result))
        return result


if __name__ == "__main__":
    worker_main()
