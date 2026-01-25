"""AST parsing utilities for extracting function information."""

from __future__ import annotations

import ast
from typing import Any

from docstring_parser import parse as parse_docstring_lib

from .models import ArgInfo, ToolInfo


def parse_function(
    node: ast.FunctionDef, module: str, pack: str | None = None
) -> ToolInfo:
    """Extract information from a function AST node.

    Args:
        node: AST FunctionDef node.
        module: Module path for the function.
        pack: Optional pack name for namespace-qualified tool names.

    Returns:
        ToolInfo with extracted signature and docstring info.
    """
    # Extract signature (with pack-qualified name if pack is provided)
    signature = extract_signature(node, pack=pack)

    # Parse docstring
    docstring = ast.get_docstring(node) or ""
    doc_info = parse_docstring(docstring)

    # Extract args
    args = extract_args(node, doc_info.get("args", {}))

    # Extract @tool decorator metadata if present
    decorator_info = extract_tool_decorator(node)

    # Decorator description overrides docstring if provided
    description = decorator_info.get("description") or doc_info.get("description", "")

    # Use pack-qualified name if pack is provided
    qualified_name = f"{pack}.{node.name}" if pack else node.name

    return ToolInfo(
        name=qualified_name,
        pack=pack,
        module=module,
        signature=signature,
        description=description,
        args=args,
        returns=doc_info.get("returns", ""),
        examples=decorator_info.get("examples", []),
        tags=decorator_info.get("tags", []),
        enabled=decorator_info.get("enabled", True),
        deprecated=decorator_info.get("deprecated", False),
        deprecated_message=decorator_info.get("deprecated_message"),
    )


def extract_tool_decorator(node: ast.FunctionDef) -> dict[str, Any]:
    """Extract metadata from @tool decorator if present.

    Args:
        node: AST FunctionDef node.

    Returns:
        Dict with decorator metadata (description, examples, tags, enabled, deprecated).
    """
    result: dict[str, Any] = {}

    for decorator in node.decorator_list:
        # Look for @tool(...) decorator
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Name) and func.id == "tool":
                # Extract keyword arguments
                for keyword in decorator.keywords:
                    if keyword.arg == "description":
                        if isinstance(keyword.value, ast.Constant):
                            result["description"] = keyword.value.value
                    elif keyword.arg == "examples":
                        if isinstance(keyword.value, ast.List):
                            result["examples"] = [
                                elt.value
                                for elt in keyword.value.elts
                                if isinstance(elt, ast.Constant)
                            ]
                    elif keyword.arg == "tags":
                        if isinstance(keyword.value, ast.List):
                            result["tags"] = [
                                elt.value
                                for elt in keyword.value.elts
                                if isinstance(elt, ast.Constant)
                            ]
                    elif keyword.arg == "enabled":
                        if isinstance(keyword.value, ast.Constant):
                            result["enabled"] = keyword.value.value
                    elif keyword.arg == "deprecated" and isinstance(
                        keyword.value, ast.Constant
                    ):
                        result["deprecated"] = keyword.value.value
                    elif keyword.arg == "deprecated_message" and isinstance(
                        keyword.value, ast.Constant
                    ):
                        result["deprecated_message"] = keyword.value.value
                break

    return result


def extract_signature(node: ast.FunctionDef, pack: str | None = None) -> str:
    """Extract function signature string.

    Args:
        node: AST FunctionDef node.
        pack: Optional pack name for namespace-qualified tool names.

    Returns:
        Signature string like 'pack.func_name(arg: type = default) -> return_type'
    """
    parts: list[str] = []

    # Process regular args
    args = node.args
    defaults = args.defaults
    num_defaults = len(defaults)
    num_args = len(args.args)

    for i, arg in enumerate(args.args):
        arg_str = arg.arg
        # Add type annotation
        if arg.annotation:
            arg_str += f": {annotation_to_str(arg.annotation)}"

        # Add default value if present
        default_idx = i - (num_args - num_defaults)
        if default_idx >= 0:
            default = defaults[default_idx]
            arg_str += f" = {value_to_str(default)}"

        parts.append(arg_str)

    # Process keyword-only args
    kw_defaults = args.kw_defaults
    for i, arg in enumerate(args.kwonlyargs):
        arg_str = arg.arg
        if arg.annotation:
            arg_str += f": {annotation_to_str(arg.annotation)}"
        if kw_defaults[i] is not None:
            arg_str += f" = {value_to_str(kw_defaults[i])}"
        parts.append(arg_str)

    # Build signature with pack-qualified name if pack is provided
    func_name = f"{pack}.{node.name}" if pack else node.name
    sig = f"{func_name}({', '.join(parts)})"

    # Add return type
    if node.returns:
        sig += f" -> {annotation_to_str(node.returns)}"

    return sig


def annotation_to_str(node: ast.expr) -> str:
    """Convert AST annotation node to string.

    Args:
        node: AST expression node representing a type annotation.

    Returns:
        String representation of the type.
    """
    return ast.unparse(node)


def value_to_str(node: ast.expr | None) -> str:
    """Convert AST value node to string representation.

    Args:
        node: AST expression node representing a default value.

    Returns:
        String representation of the value.
    """
    if node is None:
        return "None"
    return ast.unparse(node)


def extract_args(
    node: ast.FunctionDef, docstring_args: dict[str, str]
) -> list[ArgInfo]:
    """Extract argument information from function node.

    Args:
        node: AST FunctionDef node.
        docstring_args: Dict of arg_name -> description from docstring.

    Returns:
        List of ArgInfo objects.
    """
    result: list[ArgInfo] = []
    args = node.args
    defaults = args.defaults
    num_defaults = len(defaults)
    num_args = len(args.args)

    for i, arg in enumerate(args.args):
        type_str = "Any"
        if arg.annotation:
            type_str = annotation_to_str(arg.annotation)

        default_str: str | None = None
        default_idx = i - (num_args - num_defaults)
        if default_idx >= 0:
            default_str = value_to_str(defaults[default_idx])

        result.append(
            ArgInfo(
                name=arg.arg,
                type=type_str,
                default=default_str,
                description=docstring_args.get(arg.arg, ""),
            )
        )

    # Keyword-only args
    kw_defaults = args.kw_defaults
    for i, arg in enumerate(args.kwonlyargs):
        type_str = "Any"
        if arg.annotation:
            type_str = annotation_to_str(arg.annotation)

        default_str = None
        if kw_defaults[i] is not None:
            default_str = value_to_str(kw_defaults[i])

        result.append(
            ArgInfo(
                name=arg.arg,
                type=type_str,
                default=default_str,
                description=docstring_args.get(arg.arg, ""),
            )
        )

    return result


def parse_docstring(docstring: str) -> dict[str, Any]:
    """Parse Google-style docstring.

    Args:
        docstring: The docstring to parse.

    Returns:
        Dict with 'description', 'args', and 'returns' keys.
    """
    if not docstring:
        return {"description": "", "args": {}, "returns": ""}

    parsed = parse_docstring_lib(docstring)

    return {
        "description": parsed.short_description or "",
        "args": {p.arg_name: p.description or "" for p in parsed.params},
        "returns": parsed.returns.description if parsed.returns else "",
    }
