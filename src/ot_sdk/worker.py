"""Worker main loop for JSON-RPC over stdin/stdout.

Workers receive JSON-RPC requests and dispatch to tool functions discovered
via module introspection.
"""

from __future__ import annotations

import inspect
import json
import sys
import traceback
from collections.abc import Callable
from typing import Any


def _get_callable_functions(
    frame_globals: dict[str, Any],
) -> dict[str, Callable[..., Any]]:
    """Extract public callable functions from the calling module's namespace.

    Args:
        frame_globals: The globals dict from the calling frame

    Returns:
        Dict mapping function names to callables
    """
    # Get SDK export names dynamically to avoid hardcoding
    import ot_sdk

    sdk_names = set(getattr(ot_sdk, "__all__", []))

    functions: dict[str, Callable[..., Any]] = {}

    for name, obj in frame_globals.items():
        # Skip private functions and special names
        if name.startswith("_"):
            continue
        # Skip imported modules
        if inspect.ismodule(obj):
            continue
        # Skip the SDK imports
        if name in sdk_names:
            continue
        # Only include callable functions defined in this module
        if callable(obj) and not inspect.isclass(obj):
            functions[name] = obj

    return functions


def worker_main() -> None:
    """Standard worker message loop.

    Reads JSON-RPC requests from stdin, dispatches to functions, writes responses
    to stdout. Errors are written to stderr.

    Request format:
        {"function": "name", "kwargs": {...}, "config": {...}, "secrets": {...}}

    Response format:
        {"result": ..., "error": null} or {"result": null, "error": "message"}
    """
    # Get the caller's globals to discover functions
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:
        print('{"result": null, "error": "Cannot determine caller frame"}', flush=True)
        return

    caller_globals = frame.f_back.f_globals
    functions = _get_callable_functions(caller_globals)

    # Store config and secrets for get_config/get_secret access
    import ot_sdk.config as config_module

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            response = {"result": None, "error": f"Invalid JSON: {e}"}
            print(json.dumps(response), flush=True)
            continue

        func_name = request.get("function")
        kwargs = request.get("kwargs", {})

        # Update config and secrets from request
        config_module._current_config = request.get("config", {})
        config_module._current_secrets = request.get("secrets", {})

        if func_name is None:
            response = {"result": None, "error": "Missing 'function' field"}
            print(json.dumps(response), flush=True)
            continue

        if func_name not in functions:
            available = ", ".join(sorted(functions.keys()))
            response = {
                "result": None,
                "error": f"Unknown function '{func_name}'. Available: {available}",
            }
            print(json.dumps(response), flush=True)
            continue

        try:
            func = functions[func_name]
            result = func(**kwargs)
            response = {"result": result, "error": None}
        except Exception as e:
            # Log full traceback to stderr
            traceback.print_exc(file=sys.stderr)
            response = {"result": None, "error": f"{type(e).__name__}: {e}"}

        print(json.dumps(response), flush=True)
