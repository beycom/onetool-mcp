"""jmespath query for the ctx pack."""
from __future__ import annotations

import json
from typing import Any

import jmespath
import jmespath.exceptions

from ot.logging import LogSpan

from .store import HandleStore, _get_store, _resolve_handle, load_live_meta

log = LogSpan


def ctx_query(
    handle: str,
    expr: str,
    *,
    store: HandleStore | None = None,
) -> dict[str, Any]:
    """Evaluate a jmespath expression against a json or yaml handle.

    Args:
        handle: Context store handle (must be json or yaml format)
        expr: jmespath expression (e.g. "name", "spec.containers[0].image",
              "items[?status == 'active'].name")
        store: HandleStore instance (uses session default if not provided)
    """
    with log(span="ctx.query", handle=handle) as s:
        if store is None:
            store = _get_store()

        try:
            handle = _resolve_handle(handle)
        except TypeError as e:
            return {"error": str(e)}

        meta, err = load_live_meta(store, handle)
        if meta is None:
            return {"error": err}

        fmt = meta.get("format", "text")
        if fmt not in ("json", "yaml"):
            return {
                "error": (
                    f"ctx.query() requires json or yaml format (handle format is {fmt!r}). "
                    f"Use ctx.slice() for line ranges or ctx.grep() for pattern matching."
                )
            }

        try:
            content = store.read_content(handle)
        except OSError:
            return {"error": f"Content not found for handle: {handle}"}

        # Parse content
        try:
            if fmt == "json":
                data: Any = json.loads(content)
            else:
                import yaml

                data = yaml.safe_load(content)
        except Exception as e:
            return {"error": f"Failed to parse {fmt} content: {e}"}

        # Compile and run jmespath expression
        try:
            compiled = jmespath.compile(expr)
        except jmespath.exceptions.JMESPathError as e:
            return {"error": f"Invalid jmespath expression: {e}"}

        try:
            result = compiled.search(data)
        except jmespath.exceptions.JMESPathError as e:
            return {"error": f"jmespath evaluation failed: {e}"}

        if result is None:
            return {
                "error": "No match",
                "expr": expr,
                "hint": f"Use ctx.toc('{handle}') to see available keys",
            }

        # Serialise result
        if isinstance(result, (dict, list)):
            serialised: Any = json.dumps(result, indent=2)
        else:
            serialised = str(result)

        s.add("expr", expr)
        return {
            "handle": handle,
            "expr": expr,
            "result": serialised,
        }


__all__ = ["ctx_query"]
