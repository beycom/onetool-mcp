"""JMESPath query for structured memory content."""

from __future__ import annotations

import json
from typing import Any

from otpack import LogSpan

from .db import _get_connection


def query(
    *,
    topic: str,
    expr: str,
    id: str | None = None,
) -> dict[str, Any]:
    """Evaluate a JMESPath expression against a memory stored as JSON or YAML.

    Raises a clear error if content is not valid JSON or YAML.

    Args:
        topic: Exact topic path to query
        expr: JMESPath expression (e.g. "name", "items[?active].id")
        id: Optional memory ID for direct lookup (overrides topic match)

    Returns:
        {"topic": str, "expr": str, "result": str} on success.
        {"topic": str, "error": str} on failure.

    Example:
        mem.query(topic="config/servers", expr="servers[0].host")
        mem.query(topic="specs/api", expr="endpoints[?method == 'POST'].path")
    """
    label = id if id else topic

    with LogSpan(span="mem.query", topic=topic) as s:
        try:
            import jmespath
            import jmespath.exceptions
        except ImportError:
            err = "jmespath is required. Install with: pip install jmespath"
            s.add(error=err)
            return {"topic": label, "error": err}

        try:
            conn = _get_connection()

            columns = "id, topic, content"
            if id:
                row = conn.execute(
                    f"SELECT {columns} FROM memories WHERE id = ?",
                    [id],
                ).fetchone()
            else:
                row = conn.execute(
                    f"SELECT {columns} FROM memories WHERE topic = ?",
                    [topic],
                ).fetchone()

            if not row:
                err = f"No memory found for {'id' if id else 'topic'} '{label}'"
                s.add(error=err)
                return {"topic": label, "error": err}

            content = row[2]

        except Exception as e:
            err = f"Error reading memory: {e}"
            s.add(error=err)
            return {"topic": label, "error": err}

        # Try to parse as JSON, then YAML
        data: Any = None
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            try:
                import yaml

                parsed = yaml.safe_load(content)
                if isinstance(parsed, (dict, list)):
                    data = parsed
            except Exception:
                pass

        if data is None:
            err = (
                f"mem.query() requires JSON or YAML content. "
                f"Topic '{row[1]}' content could not be parsed as JSON or YAML. "
                f"Use mem.grep() for pattern matching or mem.slice() for line ranges."
            )
            s.add(error=err)
            return {"topic": row[1], "error": err}

        try:
            compiled = jmespath.compile(expr)
        except jmespath.exceptions.JMESPathError as e:
            err = f"Invalid JMESPath expression: {e}"
            s.add(error=err)
            return {"topic": row[1], "error": err}

        try:
            result = compiled.search(data)
        except jmespath.exceptions.JMESPathError as e:
            err = f"JMESPath evaluation failed: {e}"
            s.add(error=err)
            return {"topic": row[1], "error": err}

        if result is None:
            return {
                "topic": row[1],
                "error": "No match",
                "expr": expr,
                "hint": f"Use mem.toc(topic='{row[1]}') to see available keys",
            }

        if isinstance(result, (dict, list)):
            serialised: Any = json.dumps(result, indent=2)
        else:
            serialised = str(result)

        s.add("expr", expr)
        return {
            "topic": row[1],
            "expr": expr,
            "result": serialised,
        }


__all__ = ["query"]
