# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.28.0"]
# ///
"""{{description}}

An isolated tool with external dependencies.
Runs in a subprocess with full dependency isolation via PEP 723.
Add dependencies to the script block above as needed.

Note: Isolated tools cannot access onetool secrets, config, or call other tools.
Use environment variables for secrets and hardcode config values.
"""

from __future__ import annotations

import json
import sys

pack = "{{pack}}"

__all__ = ["{{function}}"]


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
    # TODO: Implement your logic here
    # Access env vars for secrets: api_key = os.environ.get("MY_API_KEY", "")
    return f"Processed: {input}"


# JSON-RPC main loop for subprocess communication
if __name__ == "__main__":
    _functions = {
        "{{function}}": {{function}},
    }
    for line in sys.stdin:
        request = json.loads(line)
        func = _functions.get(request["function"])
        if func is None:
            print(json.dumps({"error": f"Unknown function: {request['function']}"}), flush=True)
            continue
        try:
            result = func(**request.get("kwargs", {}))
            print(json.dumps({"result": result}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
