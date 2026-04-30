"""Unified command runner for OneTool.

Routes all command execution through Python code mode:
- Function calls: search(query="test")
- Python code blocks: for metal in metals: search(...)
- Code with fences: ```python ... ```

Delegates to specialized modules:
- fence_processor: Strips markdown fences and execution prefixes
- tool_loader: Discovers and caches tool functions
- pack_proxy: Creates proxy objects for dot notation access
"""

from __future__ import annotations

import ast
import asyncio
import io
import json
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.config import get_config
from ot.executor.fence_processor import strip_fences
from ot.executor.pack_proxy import build_execution_namespace
from ot.executor.tool_loader import load_tool_functions, load_tool_registry
from ot.logging import LogSpan
from ot.utils import serialize_result

if TYPE_CHECKING:
    from pathlib import Path

    from ot.utils.format import FormatMode


@dataclass
class CommandResult:
    """Result from command execution."""

    command: str
    result: str
    executor: str = "runner"
    success: bool = True
    error_type: str | None = None
    line_number: int | None = None
    raw: Any = None
    should_sanitize: bool = True
    format: str = "json"


# Sentinel value to distinguish explicit None return from no return
_NO_RETURN = object()


def _apply_compact(text: str) -> str:
    """Apply ot_caveman compaction to text. Returns original on any failure."""
    try:
        from ottools.ot_caveman import _compact_text

        return _compact_text(text)
    except ImportError:
        logger.warning("ot_caveman not available for __compact__ — returning original output")
        return text
    except RuntimeError as e:
        logger.warning("__compact__ failed: {} — returning original output", e)
        return text


# -----------------------------------------------------------------------------
# Code Execution
# -----------------------------------------------------------------------------


def _force_single_quotes(code: str) -> str:
    """Rewrite double-quoted string literals to use single quotes.

    Triple-quoted strings and f-strings are left unchanged.
    Falls back to original code on tokenize error.
    """
    import tokenize as _tok

    result = []
    try:
        for tok in _tok.generate_tokens(io.StringIO(code).readline):
            if (
                tok.type == _tok.STRING
                and tok.string.startswith('"')
                and not tok.string.startswith('"""')
            ):
                val = ast.literal_eval(tok.string)
                if isinstance(val, str):
                    escaped = val.replace("\\", "\\\\").replace("'", "\\'")
                    result.append(tok._replace(string=f"'{escaped}'"))
                    continue
            result.append(tok)
        return _tok.untokenize(result).strip()
    except _tok.TokenError:
        return code


def _normalize_code(code: str, tree: ast.Module) -> tuple[str, ast.Module]:
    """Normalize to one-statement-per-line with single-quoted strings.

    Uses ast.unparse() to put each statement on its own line, which:
    - Eliminates semicolon-separated statements (cleaner display in Claude UI)
    - Ensures col_offset for each statement is 0 (fixes non-ASCII byte-offset bug)
    - Converts double-quoted strings to single quotes (cleaner JSON wire format)
    """
    if not tree.body:
        return code, tree
    normalized = "\n".join(ast.unparse(stmt) for stmt in tree.body)
    normalized = _force_single_quotes(normalized)
    return normalized, ast.parse(normalized)


def _call_name(func: ast.expr) -> str | None:
    """Return dotted function path for a call target when representable."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts: list[str] = []
        node: ast.expr = func
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
    return None


def _extract_single_call_name(code: str) -> str | None:
    """Extract call target when code is exactly one top-level call expression."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    if len(tree.body) != 1:
        return None

    stmt = tree.body[0]
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return None

    return _call_name(stmt.value.func)


def _has_top_level_return(tree: ast.Module) -> bool:
    """Check for return statements at top level only (not inside functions/classes).

    Returns inside function definitions should not prevent implicit return capture
    for the final expression at module level.

    Args:
        tree: Parsed AST module

    Returns:
        True if there's a return statement at the top level
    """
    for node in tree.body:
        # Skip function and class definitions - returns inside them don't count
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        # Check this top-level statement and its children for return
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                return True
    return False


def prepare_code_for_exec(
    code: str, tree: ast.Module | None = None
) -> tuple[str, bool]:
    """Prepare code for execution, handling result capture.

    Uses AST to detect if the last statement is an expression (needs return),
    or if there's an explicit return statement, or if we should just execute.

    Args:
        code: Python code to prepare
        tree: Pre-parsed AST tree (optional, avoids reparsing)

    Returns:
        Tuple of (prepared code, whether result capture was added)
    """
    stripped = code.strip()

    if tree is None:
        try:
            tree = ast.parse(stripped)
        except SyntaxError:
            # Syntax error - return as-is and let exec() report the error
            return code, False

    stripped, tree = _normalize_code(stripped, tree)

    if not tree.body:
        return code, False

    last_stmt = tree.body[-1]

    # Check if already has explicit return at top level (not inside functions)
    if _has_top_level_return(tree):
        # Has explicit return - use as-is
        return stripped, False

    if isinstance(last_stmt, ast.Expr):
        # Last statement is an expression - capture its value
        # Use AST to find where the expression starts (handles semicolon-separated statements)
        lines = stripped.split("\n")
        expr_start_line = last_stmt.lineno - 1  # AST is 1-indexed
        expr_col = last_stmt.col_offset

        # Insert 'return ' at the expression start position
        line = lines[expr_start_line]
        lines[expr_start_line] = line[:expr_col] + "return " + line[expr_col:]

        return "\n".join(lines), True

    # Last statement is not an expression (e.g., assignment, for loop)
    return stripped, False


def wrap_code_for_exec(code: str, has_explicit_return: bool) -> tuple[str, int]:
    """Wrap code in a function for execution.

    Handles indentation correctly for already-indented code.

    Args:
        code: Python code to wrap
        has_explicit_return: Whether the code has an explicit return statement

    Returns:
        Tuple of (wrapped code with __execute__ function, line offset for error mapping)
    """
    lines = code.split("\n")

    # Indent each line by 4 spaces
    indented_lines = []
    for line in lines:
        if line.strip():  # Non-empty line
            indented_lines.append("    " + line)
        else:  # Empty line - preserve
            indented_lines.append("")

    indented_code = "\n".join(indented_lines)

    # Add global declarations for magic variables so they can be read from outer namespace
    global_decl = "    global __format__, __sanitize__, __compact__, __force_context__"

    # Use sentinel if no explicit return to distinguish from explicit None
    if has_explicit_return:
        wrapped = f"""def __execute__():
{global_decl}
{indented_code}

__result__ = __execute__()
"""
    else:
        wrapped = f"""def __execute__():
{global_decl}
{indented_code}
    return __NO_RETURN__

__result__ = __execute__()
"""

    # Line offset: "def __execute__():" + global decl adds 2 lines before user code
    return wrapped, 2


def _map_error_line(error: Exception, line_offset: int) -> tuple[str, int | None]:
    """Extract and adjust error line number from exception.

    Args:
        error: The exception that occurred
        line_offset: Number of lines added by wrapping

    Returns:
        Tuple of (error message, adjusted line number or None)
    """
    import traceback

    # Get the last frame from the traceback
    tb = traceback.extract_tb(error.__traceback__)
    if tb:
        for frame in reversed(tb):
            if frame.filename == "<string>" and frame.lineno is not None:
                # This is from our exec'd code
                original_line = frame.lineno - line_offset
                if original_line > 0:
                    return str(error), original_line

    return str(error), None


def execute_python_code(
    code: str,
    tool_functions: dict[str, Any] | None = None,
    tools_dir: Path | None = None,
    validate: bool = True,
    default_format: FormatMode = "json",
) -> tuple[str, Any, bool, str, bool]:
    """Execute Python code with tool functions available.

    Args:
        code: Python code to execute
        tool_functions: Pre-loaded tool functions (optional)
        tools_dir: Path to tools directory for loading functions
        validate: Whether to validate code before execution (default True)
        default_format: Format used when code does not set __format__

    Returns:
        Tuple of (serialized string, raw Python object, sanitize flag, format mode, force_context flag)

    Raises:
        ValueError: If validation fails or execution fails
    """
    from ot.executor.validator import validate_for_exec

    # Step 1: Validate code before execution
    ast_tree: ast.Module | None = None
    if validate:
        validation = validate_for_exec(code)
        if not validation.valid:
            errors = "; ".join(validation.errors)
            raise ValueError(f"Code validation failed: {errors}")

        # Log warnings but continue execution
        for warning in validation.warnings:
            logger.warning(f"Code validation warning: {warning}")

        # Reuse AST from validation
        ast_tree = validation.ast_tree

    # Step 2: Load tool functions if not provided
    if tool_functions is None:
        tool_functions = load_tool_functions(tools_dir)

    # Step 3: Create execution namespace with tools and sentinel
    namespace: dict[str, Any] = {
        **tool_functions,
        "__builtins__": __builtins__,
        "__NO_RETURN__": _NO_RETURN,
    }

    # Step 4: Prepare code for result capture (reuse AST if available)
    prepared_code, has_return = prepare_code_for_exec(code, tree=ast_tree)

    # Step 5: Wrap in function for execution
    wrapped_code, line_offset = wrap_code_for_exec(prepared_code, has_return)

    # Step 6: Execute with stdout capture
    stdout_buffer = io.StringIO()
    try:
        with redirect_stdout(stdout_buffer):
            exec(wrapped_code, namespace)
        result = namespace.get("__result__")
        stdout_output = stdout_buffer.getvalue().strip()

        # Read __format__ from namespace.
        fmt: FormatMode = namespace.get("__format__", default_format)
        if fmt not in ("json", "json_h", "yml", "yml_h", "raw"):
            fmt = default_format if default_format in ("json", "json_h", "yml", "yml_h", "raw") else "json"

        # Read __sanitize__, __compact__, and __force_context__ from namespace, defaulting to config settings
        config = get_config()
        should_sanitize: bool = namespace.get("__sanitize__", config.security.sanitize.enabled)
        should_compact: bool = namespace.get("__compact__", config.output.compact)
        should_force_context: bool = namespace.get("__force_context__", False)

        # Determine output and raw_result
        raw_result = None
        if result is _NO_RETURN:
            output = stdout_output or "Code executed successfully (no return value)"
        elif result is None:
            output = stdout_output or "None"
        else:
            raw_result = result
            if stdout_output:
                output = f"{stdout_output}\n{serialize_result(result, fmt)}"
            else:
                output = serialize_result(result, fmt)

        # Apply compaction if requested (after serialize, before ctx-store threshold check)
        if should_compact:
            output = _apply_compact(output)

        return output, raw_result, should_sanitize, fmt, should_force_context

    except Exception as e:
        error_msg, line_num = _map_error_line(e, line_offset)
        if line_num is not None:
            raise ValueError(
                f"❗️Execution error at line {line_num}: {error_msg}"
            ) from e
        raise ValueError(f"❗️Execution error: {error_msg}") from e


@dataclass
class PreparedCommand:
    """Result of command preparation (before execution)."""

    code: str
    original: str
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def prepare_command(command: str) -> PreparedCommand:
    """Prepare a command for execution (validate but don't execute).

    This performs all preprocessing steps:
    - Strips markdown fences
    - Expands snippets
    - Resolves aliases
    - Validates for security patterns

    Returns:
        PreparedCommand with prepared code and any errors.
    """
    from ot.config import get_config
    from ot.executor.validator import validate_for_exec
    from ot.shortcuts.aliases import resolve_alias
    from ot.shortcuts.snippets import expand_snippet, is_snippet, parse_snippet

    # Step 1: Check for legacy !onetool prefix (rejected)
    stripped_cmd = command.strip()
    if stripped_cmd.startswith("!onetool"):
        return PreparedCommand(
            code="",
            original=command,
            error="The !onetool prefix is no longer supported. "
            "Use backtick syntax: `func(args)` or ```python\\ncode\\n```",
        )

    # Step 2: Strip fences
    stripped, _ = strip_fences(command)

    # Step 3: Load configuration for aliases and snippets
    config = get_config()

    # Step 4: Handle snippet expansion ($name key=val)
    if is_snippet(stripped):
        try:
            parsed = parse_snippet(stripped)
            stripped = expand_snippet(parsed, config)
        except ValueError as e:
            return PreparedCommand(
                code="",
                original=command,
                error=str(e),
            )

    # Step 5: Resolve aliases (ws -> brave.web_search)
    stripped = resolve_alias(stripped, config)

    # Step 6: Validate code (but don't execute)
    validation = validate_for_exec(stripped)
    if not validation.valid:
        errors = "; ".join(validation.errors)
        return PreparedCommand(
            code=stripped,
            original=command,
            error=f"Code validation failed: {errors}",
        )

    # Log warnings (validation passed but has warnings)
    for warning in validation.warnings:
        logger.warning(f"Code validation warning: {warning}")

    # Step 7: Normalize (reuse AST from validation — no extra parse)
    if validation.ast_tree is not None:
        stripped, _ = _normalize_code(stripped, validation.ast_tree)

    return PreparedCommand(
        code=stripped,
        original=command,
        warnings=validation.warnings,
    )


# -----------------------------------------------------------------------------
# Unified Command Execution
# -----------------------------------------------------------------------------


async def execute_command(
    command: str,
    tools_dir: Path | None = None,
    *,
    skip_validation: bool = False,
    prepared_code: str | None = None,
) -> CommandResult:
    """Execute a command through the unified runner.

    This is the single entry point for all command execution:
    - Strips markdown fences
    - Rejects legacy !onetool prefix
    - Expands snippets ($name key=val)
    - Resolves aliases (ws -> brave.web_search)
    - Executes as Python code with namespace support

    Args:
        command: Raw command from LLM (may have fences)
        tools_dir: Path to tools directory
        skip_validation: If True, skip validation (use when already validated)
        prepared_code: Pre-processed code to execute (bypasses preparation steps)

    Returns:
        CommandResult with execution result
    """
    # If prepared_code is provided, use it directly (already preprocessed)
    if prepared_code is not None:
        stripped = prepared_code
    else:
        # Use prepare_command for preprocessing
        prepared = prepare_command(command)
        if prepared.error:
            return CommandResult(
                command=command,
                result=f"Error: {prepared.error}",
                executor="python",
                success=False,
                error_type="ValueError",
            )
        stripped = prepared.code

    # Step 6: Load tools with pack support
    tool_registry = load_tool_registry(tools_dir)
    tool_namespace = build_execution_namespace(tool_registry)

    # Step 7: Execute as Python code
    # Use thread pool only when proxy servers are connected (to avoid deadlock)
    from ot.proxy import get_proxy_manager

    proxy = get_proxy_manager()
    use_thread_pool = bool(proxy.servers)

    # Determine validation behavior
    should_validate = not skip_validation and prepared_code is None

    # Extract tool name only for single top-level call commands.
    tool_name = _extract_single_call_name(stripped)

    with LogSpan(span="runner.execute", command=stripped, tool=tool_name) as span:
        try:
            if use_thread_pool:
                # Run in thread pool so event loop can process proxy calls
                text_result, raw_result, sanitize, result_fmt, force_context = await asyncio.to_thread(
                    execute_python_code,
                    stripped,
                    tool_functions=tool_namespace,
                    validate=should_validate,
                    default_format="json",
                )
            else:
                # Direct execution for non-proxy calls (no overhead)
                text_result, raw_result, sanitize, result_fmt, force_context = execute_python_code(
                    stripped,
                    tool_functions=tool_namespace,
                    validate=should_validate,
                    default_format="json",
                )

            # Check for large output and store if needed
            config = get_config()
            max_size = config.output.max_inline_size

            _no_deflect = (tool_name or "").startswith("ctx.") or tool_name in {
                "ot.result",
                "ot.help",
                "ot.tool_info",
            }
            if not _no_deflect:
                result_size = len(text_result.encode("utf-8"))
                if force_context or (max_size > 0 and result_size > max_size):
                    # Store large output via ctx backend and return summary
                    from ot.ctx.write import ctx_write
                    ctx_content = (
                        json.dumps(raw_result, indent=2, ensure_ascii=False)
                        if raw_result is not None and isinstance(raw_result, (dict, list))
                        else text_result
                    )
                    write_result = ctx_write(ctx_content, source=stripped[:50], verbose=True)
                    handle = write_result["handle"]
                    content_type = write_result.get("content_type", "text")
                    summary_dict = {
                        "handle": handle,
                        "total_lines": write_result["total_lines"],
                        "size_bytes": write_result["size_bytes"],
                        "content_type": content_type,
                        "preview": write_result.get("preview", ""),
                        "status": write_result.get("status", "pending"),
                        "next_commands": [
                            f"ctx.toc(handle='{handle}')",
                            f"ctx.ask(handle='{handle}', q='What matters most here?')",
                            f"ctx.read(handle='{handle}', limit=80)",
                        ],
                    }
                    text_result = serialize_result(summary_dict, "json")
                    raw_result = summary_dict
                    span.add("storedHandle", handle)
                    span.add("storedSize", result_size)

            span.add("resultLength", len(text_result))
            return CommandResult(
                command=command,
                result=text_result,
                raw=raw_result,
                executor="python",
                success=True,
                should_sanitize=sanitize,
                format=result_fmt,
            )
        except Exception as e:
            return CommandResult(
                command=command,
                result=str(e),
                executor="python",
                success=False,
                error_type=type(e).__name__,
            )
