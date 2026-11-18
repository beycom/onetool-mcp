"""Static catalog checks. AST inspection only; native Monty owns execution syntax."""

from __future__ import annotations

import ast
import builtins
import difflib
import time
from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool

if TYPE_CHECKING:
    from onetool.gateway import Gateway

HELPERS = {"call_tool", "call_tools", "set_format", "results"}


def references(
    tree: ast.AST, servers: set[str]
) -> list[tuple[ast.Call, str | None, list[str] | None]]:
    """Names bound by submitted code conservatively make namespace references unresolved."""
    bound = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    bound.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
    bound.update(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            bound.update(item.asname or item.name.split(".")[0] for item in node.names)
    found: list[tuple[ast.Call, str | None, list[str] | None]] = []

    def keys(node: ast.AST | None) -> list[str] | None:
        if isinstance(node, ast.Dict) and all(
            isinstance(key, ast.Constant) and isinstance(key.value, str) for key in node.keys
        ):
            return [
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            ]
        return None

    def native(node: ast.Call, name: ast.AST | None, arguments: ast.AST | None) -> None:
        literal = (
            name.value if isinstance(name, ast.Constant) and isinstance(name.value, str) else None
        )
        found.append((node, literal, keys(arguments)))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name) and function.id in {"call_tool", "call_tools"}:
            if function.id in bound:
                found.append((node, None, None))
                continue
            if function.id == "call_tool":
                kwargs = {item.arg: item.value for item in node.keywords}
                native(
                    node,
                    node.args[0] if node.args else kwargs.get("name"),
                    node.args[1] if len(node.args) > 1 else kwargs.get("arguments"),
                )
            else:
                calls = (
                    node.args[0]
                    if node.args
                    else next((kw.value for kw in node.keywords if kw.arg == "calls"), None)
                )
                if not isinstance(calls, ast.List | ast.Tuple):
                    found.append((node, None, None))
                    continue
                for item in calls.elts:
                    if isinstance(item, ast.Tuple | ast.List) and len(item.elts) == 2:
                        native(node, item.elts[0], item.elts[1])
                    elif isinstance(item, ast.Dict):
                        fields = {
                            k.value: v
                            for k, v in zip(item.keys, item.values, strict=True)
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)
                        }
                        native(node, fields.get("tool"), fields.get("arguments"))
                    else:
                        found.append((node, None, None))
        elif isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            server = function.value.id
            if server in servers:
                name = None if server in bound else server + "_" + function.attr
                arguments = (
                    None
                    if node.args or any(kw.arg is None for kw in node.keywords)
                    else [kw.arg for kw in node.keywords if kw.arg]
                )
                found.append((node, name, arguments))
            elif server not in bound and server not in HELPERS and not hasattr(builtins, server):
                found.append((node, server + "_" + function.attr, None))
    return found


def analyze(
    tree: ast.AST, tools: dict[str, Tool], servers: set[str], unknown: set[str]
) -> dict[str, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for node, name, arguments in references(tree, servers):
        location = {"line": node.lineno, "column": node.col_offset + 1}
        if name is None:
            warnings.append(
                {**location, "message": "Computed or shadowed tool reference is unresolved"}
            )
            continue
        if name not in tools:
            if any(name.startswith(server + "_") for server in unknown):
                warnings.append({**location, "message": f"Schema unknown for {name}; unresolved"})
            else:
                errors.append(
                    {
                        **location,
                        "message": f"Unknown tool {name}",
                        "tool": name,
                        "suggestions": difflib.get_close_matches(name, list(tools), n=3),
                    }
                )
            continue
        if arguments is None:
            warnings.append(
                {**location, "message": f"Computed arguments for {name} are unresolved"}
            )
            continue
        schema = tools[name].parameters
        if "properties" in schema and schema.get("additionalProperties") is False:
            for key in sorted(set(arguments) - schema["properties"].keys()):
                errors.append(
                    {
                        **location,
                        "message": f"Unknown parameter {key} for {name}",
                        "suggestions": difflib.get_close_matches(
                            key, list(schema["properties"]), n=3
                        ),
                    }
                )
    return {"errors": errors, "warnings": warnings}


class InvalidCall(ToolError):
    def __init__(self, message: str, category: str):
        super().__init__(message)
        self.category = category


class Preflight:
    def __init__(self, gateway: Gateway):
        self.gateway = gateway

    def factory(self, get_catalog: Any) -> Tool:
        return Tool.from_function(self.check, name="check")

    def validate(self, tree: ast.AST, tools: dict[str, Tool]) -> None:
        result = analyze(tree, tools, set(self.gateway.backends), set())
        if result["errors"]:
            first = result["errors"][0]
            unavailable = any(
                first.get("tool", "").startswith(backend.name + "_") and backend.state != "ready"
                for backend in self.gateway.backends.values()
            )
            failure = self.gateway.failure_context.get() or {}
            category = failure.get("category", "unavailable" if unavailable else "config")
            raise InvalidCall(
                f"Preflight line {first['line']}, column {first['column']}: "
                f"{first['message']}; exact suggestions: {first.get('suggestions', [])}",
                category,
            )

    async def check(self, code: str) -> dict[str, Any]:
        """Inspect cached schemas without running code/connecting; syntax is provisional."""
        from onetool.sandbox import prepare

        gateway = self.gateway
        tools: dict[str, Tool] = {}
        unknown = set()
        ages: dict[str, float | None] = {}
        collisions = []
        for name, backend in gateway.backends.items():
            ages[name] = (
                time.monotonic() - backend.observed_at if backend.observed_at is not None else None
            )
            if not backend.enabled or backend.state != "ready" or backend.observed_at is None:
                unknown.add(name)
            else:
                for tool in backend.observed_tools:
                    if tool.name in tools:
                        collisions.append({"message": f"Namespace collision: {tool.name}"})
                    tools[tool.name] = tool
        try:
            tree = ast.parse(prepare(code))
            result = analyze(tree, tools, set(gateway.backends), unknown)
        except ToolError as exc:
            result = {"errors": [{"line": 1, "column": 1, "message": str(exc)}], "warnings": []}
        except SyntaxError as exc:
            result = {
                "errors": [
                    {
                        "line": exc.lineno,
                        "column": exc.offset,
                        "message": "Provisional syntax error",
                    }
                ],
                "warnings": [],
            }
        result["errors"].extend(collisions)
        return gateway.results.fit(
            {
                "valid": not result["errors"],
                **result,
                "syntax": "Provisional CPython inspection; native Monty parser owns execute",
                "catalog": {"age_seconds": ages, "unknown_servers": sorted(unknown)},
                "notice": "Check runs no code and does not guarantee later execution succeeds.",
            }
        )
