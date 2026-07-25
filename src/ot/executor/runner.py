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
import re
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.config import get_config
from ot.executor.admission import ExecutionCapacityError, submit_execution
from ot.executor.fence_processor import strip_fences
from ot.executor.pack_proxy import build_execution_namespace
from ot.executor.tool_loader import load_tool_functions, load_tool_registry
from ot.logging import LogSpan
from ot.logging.entry import LogEntry
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

# D-a2: maximum nested __onetool(...) recursion depth. A small bound turns runaway
# recursion into a clear error well before the Python call stack is exhausted.
_MAX_NESTED_DEPTH = 5

# D3: bounded per-run execution timeout (seconds). A `run` command may chain several
# tool calls (each up to ~30s for webfetch/proxy) or loop, so this is a generous
# backstop against an indefinite hang — not a tight per-call SLA. On timeout the
# command surfaces as a clean isError:true rather than freezing the caller.
_TOOL_EXECUTION_TIMEOUT_SECS = 300.0


_DIRECT_META_PREFIX_RE = re.compile(
    r"^__format__\s*=\s*(['\"])(json_h|json|yml|yml_h|raw)\1\s*;\s*__sanitize__\s*=\s*(True|False)\s*$"
)


def _split_meta_wrapped_snippet(code: str) -> tuple[str, str] | None:
    """Extract direct-run metadata prefix and snippet body when present.

    Returns:
        (prefix_line, snippet_command) when code is:
            __format__='...'; __sanitize__=...
            :snippet ...
        None for all other inputs.
    """
    lines = code.splitlines()
    if len(lines) < 2:
        return None

    prefix = lines[0].strip()
    if not _DIRECT_META_PREFIX_RE.match(prefix):
        return None

    snippet_code = "\n".join(lines[1:]).strip()
    if not snippet_code.startswith(":"):
        return None

    return prefix, snippet_code


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
                    # D1: never re-quote a string containing control characters.
                    # Re-quoting to a single-line single-quoted literal would drop a
                    # real newline/tab inside the literal, producing an unterminated
                    # string (crash). Re-quoting is purely cosmetic, so skipping it
                    # for control-char strings is a no-op on correctness.
                    if "\n" in val or "\r" in val or any(ord(c) < 0x20 for c in val):
                        result.append(tok)
                        continue
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
    global_decl = "    global __format__, __sanitize__, __force_context__"

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


def _wrap_execution_error(e: Exception, offset: int) -> ValueError:
    """Map an exec'd-code exception into the standard wrapped ValueError.

    Shared by both the nested `__onetool(...)` error handler and the outer
    execute_python_code error handler so the two paths cannot drift: both must
    stamp the same attributes, notably `ot_original_error_name` (from the
    original exception's `.name`, present on NameError), which execute_command
    reads to drive the NameError "Did you mean <pack>?" fuzzy suggestion.

    Args:
        e: The exception raised during exec() of the (possibly nested) code.
        offset: Line offset to subtract when mapping the error back to source.

    Returns:
        A ValueError with the formatted message and `ot_original_error_type`,
        `ot_original_error_name`, and `ot_mapped` attributes set. Callers must
        `raise wrapped from e`.
    """
    error_msg, line_num = _map_error_line(e, offset)
    # D6: preserve the real exception type in the message and thread it through
    # to CommandResult.error_type via an attribute the outer handler reads.
    orig_type = type(e).__name__
    if line_num is not None:
        wrapped = ValueError(
            f"❗️Execution error at line {line_num}: {orig_type}: {error_msg}"
        )
    else:
        wrapped = ValueError(f"❗️Execution error: {orig_type}: {error_msg}")
    wrapped.ot_original_error_type = orig_type  # type: ignore[attr-defined]
    # Preserve the unresolved identifier of a NameError so execute_command can
    # offer a fuzzy pack-name suggestion (the wrapper drops the original .name).
    wrapped.ot_original_error_name = getattr(e, "name", None)  # type: ignore[attr-defined]
    wrapped.ot_mapped = True  # type: ignore[attr-defined]
    return wrapped


def execute_python_code(
    code: str,
    tool_functions: dict[str, Any] | None = None,
    tools_dir: Path | None = None,
    validate: bool = True,
    default_format: FormatMode = "json",
) -> tuple[str, Any, bool, FormatMode, bool, str | None]:
    """Execute Python code with tool functions available.

    Args:
        code: Python code to execute
        tool_functions: Pre-loaded tool functions (optional)
        tools_dir: Path to tools directory for loading functions
        validate: Whether to validate code before execution (default True)
        default_format: Format used when code does not set __format__

    Returns:
        Tuple of (serialized string, raw Python object, sanitize flag, format mode,
        force_context flag, raw-only serialized string). The last element is
        `serialize_result(raw_result, fmt)` with no stdout prefix — the exact
        string a caller would otherwise recompute for deflection storage — or
        `None` when there is no return value to serialize (R8 P3: lets callers
        reuse it instead of re-serializing raw_result a second time).

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

    _nested_depth = 0
    _magic_keys = ("__format__", "__sanitize__", "__force_context__")

    def _nested_run(command: str) -> Any:
        """Execute a nested OneTool command string from Python workflows."""
        nonlocal _nested_depth
        if not isinstance(command, str) or not command.strip():
            raise ValueError("__onetool(command) requires a non-empty command string")

        # D-a2: bound nested recursion so a self-referential __onetool(...) call
        # raises a clear error instead of exhausting the Python stack (RecursionError).
        if _nested_depth >= _MAX_NESTED_DEPTH:
            raise ValueError(
                f"nested __onetool call depth exceeded (limit {_MAX_NESTED_DEPTH})"
            )

        prepared = prepare_command(command)
        if prepared.error:
            raise ValueError(prepared.error)

        nested_code, nested_has_return = prepare_code_for_exec(prepared.code)
        nested_wrapped_code, nested_offset = wrap_code_for_exec(
            nested_code, nested_has_return
        )

        # D5: exec into a child namespace (shallow copy) so nested variables and
        # magic settings cannot leak into the outer command's namespace. Snapshot
        # the three magics from the outer namespace and restore them afterward as
        # belt-and-suspenders in case a nested command writes them back.
        child_ns = dict(namespace)
        magic_snapshot = {k: namespace[k] for k in _magic_keys if k in namespace}
        _nested_depth += 1
        try:
            exec(nested_wrapped_code, child_ns)
        except Exception as e:
            # An error from a deeper nested level is already mapped/formatted — let it
            # propagate unchanged rather than wrapping it again at each level.
            if getattr(e, "ot_mapped", False):
                raise
            # D-a4: map the error line against the *nested* code's offset, not the
            # outer command's, and mark it so the outer handler does not re-map it.
            raise _wrap_execution_error(e, nested_offset) from e
        finally:
            _nested_depth -= 1
            for k in _magic_keys:
                if k in magic_snapshot:
                    namespace[k] = magic_snapshot[k]
                else:
                    namespace.pop(k, None)

        nested_result = child_ns.get("__result__", _NO_RETURN)
        return None if nested_result is _NO_RETURN else nested_result

    namespace["__onetool"] = _nested_run

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
            fmt = (
                default_format
                if default_format in ("json", "json_h", "yml", "yml_h", "raw")
                else "json"
            )

        # Read __sanitize__ and __force_context__ from namespace, defaulting to config settings
        config = get_config()
        should_sanitize: bool = namespace.get(
            "__sanitize__", config.security.sanitize.enabled
        )
        should_force_context: bool = namespace.get("__force_context__", False)

        # Determine output and raw_result
        raw_result = None
        # R8 P3: compute the raw-only serialization once here so callers (e.g. the
        # deflection block in execute_command) can reuse it instead of calling
        # serialize_result(raw_result, fmt) a second time.
        raw_serialized: str | None = None
        if result is _NO_RETURN:
            output = stdout_output or "Code executed successfully (no return value)"
        elif result is None:
            output = stdout_output or "None"
        else:
            raw_result = result
            raw_serialized = serialize_result(result, fmt)
            if stdout_output:
                output = f"{stdout_output}\n{raw_serialized}"
            else:
                output = raw_serialized

        return (
            output,
            raw_result,
            should_sanitize,
            fmt,
            should_force_context,
            raw_serialized,
        )

    except Exception as e:
        # A nested __onetool(...) error is already mapped against its own source
        # offset and formatted (D-a4); re-raise it unchanged rather than re-mapping
        # against the outer command's line offset.
        if getattr(e, "ot_mapped", False):
            raise
        raise _wrap_execution_error(e, line_offset) from e


@dataclass
class PreparedCommand:
    """Result of command preparation (before execution)."""

    code: str
    original: str
    command_type: str = "python"
    snippet: str | None = None
    prepared_lines: int = 0
    prepared_length: int = 0
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
    # D-a1: an empty/whitespace-only command has no discoverable intent — refuse it
    # explicitly rather than executing an empty function body and reporting success.
    if not stripped_cmd:
        return PreparedCommand(
            code="",
            original=command,
            error="Command is empty. Provide a Python expression or tool call, "
            "e.g. pack.tool(arg=value).",
        )
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

    # Step 4: Handle snippet expansion (:name key=val)
    # direct run prepends __format__/__sanitize__ metadata before command text,
    # so detect that wrapper and expand snippets from the wrapped body.
    snippet_target = stripped
    meta_prefix: str | None = None
    wrapped = _split_meta_wrapped_snippet(stripped)
    if wrapped is not None:
        meta_prefix, snippet_target = wrapped

    command_type = "snippet" if is_snippet(snippet_target) else "python"
    snippet_name: str | None = None
    if command_type == "snippet":
        try:
            parsed = parse_snippet(snippet_target)
            snippet_name = parsed.name
            expanded = expand_snippet(parsed, config)
            stripped = f"{meta_prefix}\n{expanded}" if meta_prefix else expanded
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
    # D1: normalization is cosmetic. If it ever raises (e.g. a re-quoting edge case),
    # fall back to the already-validated, executable code rather than crashing `run`.
    if validation.ast_tree is not None:
        try:
            stripped, _ = _normalize_code(stripped, validation.ast_tree)
        except Exception as e:
            logger.warning(f"Code normalization failed, using unnormalized code: {e}")

    return PreparedCommand(
        code=stripped,
        original=command,
        command_type=command_type,
        snippet=snippet_name,
        prepared_lines=len(stripped.splitlines()),
        prepared_length=len(stripped),
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
    - Expands snippets (:name key=val)
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
        prepared = PreparedCommand(
            code=stripped,
            original=command,
            command_type="prepared",
            prepared_lines=len(stripped.splitlines()),
            prepared_length=len(stripped),
        )
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
                should_sanitize=False,  # D-b2: first-party error text
            )
        stripped = prepared.code

    # Step 6: Load tools with pack support
    tool_registry = load_tool_registry(tools_dir)
    tool_namespace = build_execution_namespace(tool_registry)

    # Step 7: Execute as Python code.
    # Always offload user code to a worker thread (D3) so the event loop stays free
    # to service concurrent run/ping/cancellation and any proxy calls the user code
    # issues — a blocking tool call can no longer freeze the whole server.

    # Determine validation behavior
    should_validate = not skip_validation and prepared_code is None

    # Extract tool name only for single top-level call commands.
    tool_name = _extract_single_call_name(stripped)

    with LogSpan(
        span="runner.execute",
        command=prepared.original.strip(),
        commandType=prepared.command_type,
        snippet=prepared.snippet,
        preparedLines=prepared.prepared_lines,
        preparedLength=prepared.prepared_length,
        tool=tool_name,
    ) as span:
        logger.debug(
            LogEntry(
                event="runner.execute.prepared",
                commandType=prepared.command_type,
                preparedCode=stripped,
                preparedLines=prepared.prepared_lines,
                preparedLength=prepared.prepared_length,
                tool=tool_name,
            )
        )
        try:
            # The underlying concurrent future owns its capacity slot until the
            # thread really finishes. Shielding prevents caller timeout or
            # cancellation from releasing that slot while side effects continue.
            execution_future = submit_execution(
                execute_python_code,
                stripped,
                tool_functions=tool_namespace,
                validate=should_validate,
                default_format="json",
            )
            (
                text_result,
                raw_result,
                sanitize,
                result_fmt,
                force_context,
                raw_serialized,
            ) = await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(execution_future)),
                timeout=_TOOL_EXECUTION_TIMEOUT_SECS,
            )

            # D7: scrub lone UTF-16 surrogates (e.g. from surrogateescape-decoded
            # filesystem names) so the size measurement below and any downstream
            # encode cannot raise UnicodeEncodeError on otherwise-correct output.
            # R8 P3: keep the encoded bytes from this pass so the size check below
            # can reuse them instead of re-encoding text_result a second time.
            encoded_text_result = text_result.encode("utf-8", "replace")
            text_result = encoded_text_result.decode()

            # Check for large output and store if needed
            config = get_config()
            max_size = config.output.max_inline_size

            from ot.services import get_services

            output_policy = get_services().output_policy_for(tool_name)
            effective_sanitize = sanitize and output_policy.allow_sanitize
            if output_policy.allow_deflect:
                result_size = len(encoded_text_result)
                if force_context or (max_size > 0 and result_size > max_size):
                    from ot.executor.result_store import get_result_store
                    from ot.utils.sanitize import (
                        sanitize_tag_closes,
                        sanitize_triggers,
                    )

                    # D-b3: serialize the stored body in the caller's requested
                    # format (not always JSON) so a later ctx.read matches what the
                    # inline response would have shown.
                    # R8 P3: raw_serialized is exactly serialize_result(raw_result,
                    # result_fmt) — already computed inside execute_python_code —
                    # so reuse it instead of re-serializing raw_result here.
                    ctx_content = (
                        raw_serialized if raw_serialized is not None else text_result
                    )
                    # D-b3: sanitize before storing so trigger patterns cannot
                    # survive to the model via a ctx.read that bypasses the run()
                    # sanitization boundary.
                    if effective_sanitize:
                        ctx_content = sanitize_tag_closes(
                            sanitize_triggers(ctx_content)
                        )
                    result_store = get_result_store()
                    stored = result_store.store(ctx_content, tool=stripped[:50])
                    summary_dict = result_store.format_store_response(stored)
                    text_result = serialize_result(summary_dict, "json")
                    raw_result = summary_dict
                    span.add("storedHandle", summary_dict.get("handle"))
                    span.add("storedSize", result_size)

            span.add("resultLength", len(text_result))
            return CommandResult(
                command=command,
                result=text_result,
                raw=raw_result,
                executor="python",
                success=True,
                should_sanitize=effective_sanitize,
                format=result_fmt,
            )
        except ExecutionCapacityError as e:
            return CommandResult(
                command=command,
                result=str(e),
                executor="python",
                success=False,
                error_type="ExecutionCapacityError",
                should_sanitize=False,
            )
        except TimeoutError:
            return CommandResult(
                command=command,
                result=(
                    f"Execution timed out after {_TOOL_EXECUTION_TIMEOUT_SECS:.0f}s. "
                    "Underlying in-process work may continue and cause side effects "
                    "until it finishes."
                ),
                executor="python",
                success=False,
                error_type="TimeoutError",
                should_sanitize=False,
            )
        except Exception as e:
            # D-b2: first-party error text is not untrusted external content, so it
            # is not boundary-wrapped or trigger-redacted. D6: report the real
            # exception type threaded through from execute_python_code.
            orig_type = getattr(e, "ot_original_error_type", type(e).__name__)
            result_text = str(e)
            # Seam 2: a typo'd pack name surfaces as a NameError. Enrich it with a
            # fuzzy did-you-mean drawn from the same namespace the command ran
            # against, plus a pointer to ot.packs(). Other error types are unchanged.
            if orig_type == "NameError":
                failed_name = getattr(e, "ot_original_error_name", None) or getattr(
                    e, "name", None
                )
                if failed_name:
                    from ot.meta._help_formatting import _fuzzy_match

                    suggestions = _fuzzy_match(
                        failed_name, sorted(tool_namespace.keys())
                    )
                    if suggestions:
                        suggestion_list = ", ".join(f"'{s}'" for s in suggestions[:3])
                        result_text = (
                            f"{result_text}. Did you mean: {suggestion_list}? "
                            "Use ot.packs() to list all available packs."
                        )
                    else:
                        result_text = f"{result_text}. Use ot.packs() to list all available packs."
            return CommandResult(
                command=command,
                result=result_text,
                executor="python",
                success=False,
                error_type=orig_type,
                should_sanitize=False,
            )
