"""Extension forge tools.

Provides tools for creating and validating new in-process extension tools.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path

from ot.paths import get_config_dir
from otpack import LogSpan

# Pack for dot notation: ot_forge.create_ext(), ot_forge.validate_ext()
pack = "ot_forge"
pack_aliases = ("forge",)

__all__ = ["create_ext", "validate_ext"]


def _get_templates_dir() -> Path:
    """Get the extension templates directory."""
    from ot.paths import get_global_templates_dir

    return get_global_templates_dir() / "tool_templates"


def _resolve_tools_pattern(pattern: str, config_dir: Path) -> str:
    """Resolve tools_dir glob patterns the same way config does."""
    expanded = Path(pattern).expanduser()
    if expanded.is_absolute():
        return str(expanded)
    return str(config_dir / pattern)


def _select_extension_file_path(name: str) -> Path:
    """Choose an extension file path that matches configured tools_dir globs."""
    from ot.config.loader import get_config

    try:
        config = get_config()
        patterns = list(config.tools_dir) if config.tools_dir else ["tools/*.py"]
    except Exception:
        patterns = ["tools/*.py"]
    config_dir = get_config_dir()
    base_tools_dir = config_dir / "tools"

    # Prefer flat layout when possible because default config is tools/*.py.
    flat_candidate = base_tools_dir / f"{name}.py"
    nested_candidate = base_tools_dir / name / f"{name}.py"
    candidates = [flat_candidate, nested_candidate]

    resolved_patterns = [
        _resolve_tools_pattern(pattern, config_dir) for pattern in patterns
    ]

    for candidate in candidates:
        candidate_str = str(candidate)
        if any(
            fnmatch.fnmatch(candidate_str, pattern) for pattern in resolved_patterns
        ):
            return candidate

    # Fallback keeps previous behavior if no configured pattern matches candidates.
    return nested_candidate


def create_ext(
    *,
    name: str,
    pack_name: str | None = None,
    function: str = "run",
    description: str = "My extension tool",
    function_description: str = "Execute the tool function",
    api_key: str = "MY_API_KEY",
) -> str:
    """Create a new extension tool.

    Creates a new in-process extension in a path compatible with tools_dir globs.

    Args:
        name: Extension name (will be used as directory and file name)
        pack_name: Pack name for dot notation (default: same as name)
        function: Main function name (default: run)
        description: Module description
        function_description: Function docstring description
        api_key: API key secret name (for optional API configuration)

    Returns:
        Success message with instructions, or error message

    Example:
        ot_forge.create_ext(name="my_tool")
        ot_forge.create_ext(name="my_tool", function="search")
    """
    with LogSpan(span="ot_forge.create_ext", name=name) as s:
        # Validate template inputs — all are substituted into generated source
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            return "Error: Name must be lowercase alphanumeric with underscores, starting with a letter"
        if pack_name is not None and not re.match(r"^[a-z][a-z0-9_]*$", pack_name):
            return "Error: pack_name must be lowercase alphanumeric with underscores, starting with a letter"
        if not re.match(r"^[a-z][a-z0-9_]*$", function):
            return "Error: function must be lowercase alphanumeric with underscores, starting with a letter"
        if api_key and not re.match(r"^[A-Z][A-Z0-9_]*$", api_key):
            return "Error: api_key must be an UPPER_SNAKE_CASE secret name"
        for label, text in (
            ("description", description),
            ("function_description", function_description),
        ):
            if '"""' in text or "'''" in text or "\n" in text or "\\" in text:
                return f"Error: {label} must be a single line without quotes-triples or backslashes"

        # Get extension template
        templates_dir = _get_templates_dir()
        template_file = templates_dir / "extension.py"

        if not template_file.exists():
            return "Error: Extension template not found"

        # Determine output path from active tools_dir patterns
        ext_file = _select_extension_file_path(name)
        ext_dir = ext_file.parent

        # Check if already exists
        if ext_file.exists():
            return f"Error: Extension already exists at {ext_file}"

        # Read and process template
        content = template_file.read_text()

        # Replace placeholders
        pack = pack_name or name
        replacements = {
            "{{pack}}": pack,
            "{{function}}": function,
            "{{description}}": description,
            "{{function_description}}": function_description,
            "{{API_KEY}}": api_key,
        }

        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)

        # Create directory and write file
        ext_dir.mkdir(parents=True, exist_ok=True)
        ext_file.write_text(content)

        s.add(path=str(ext_file))

        lines = [
            f"Created extension: {ext_file}",
            "",
            "Next steps:",
            "  1. Edit the file to implement your logic",
            f'  2. Validate before reload: ot_forge.validate_ext(path="{ext_file}")',
            "  3. Reload to activate: ot.reload()",
            f"  4. Use your tool: {pack}.{function}()",
        ]
        return "\n".join(lines)


def _check_best_practices(
    content: str, tree: ast.Module
) -> tuple[dict[str, bool], list[str]]:
    """Check for best practices violations.

    Args:
        content: The file content
        tree: The parsed AST

    Returns:
        Tuple of (checks dict, warnings list)
    """
    checks: dict[str, bool] = {}
    warnings: list[str] = []
    lines = content.split("\n")

    # Check for module docstring
    has_docstring = ast.get_docstring(tree) is not None
    checks["module_docstring"] = has_docstring
    if not has_docstring:
        warnings.append("Best practice: Add a module docstring describing the tool")

    # Check for from __future__ import annotations
    has_future_annotations = "from __future__ import annotations" in content
    checks["future_annotations"] = has_future_annotations
    if not has_future_annotations:
        warnings.append(
            "Best practice: Add 'from __future__ import annotations' for forward compatibility"
        )

    # Find line numbers of key elements
    pack_line = None
    first_import_line = None

    for i, line in enumerate(lines, 1):
        if line.startswith("pack = ") and pack_line is None:
            pack_line = i
        if (
            (line.startswith("import ") or line.startswith("from "))
            and first_import_line is None
            and "from __future__" not in line
        ):
            first_import_line = i

    # Check: pack before imports
    pack_before_imports = not (
        pack_line and first_import_line and pack_line > first_import_line
    )
    checks["pack_before_imports"] = pack_before_imports
    if not pack_before_imports:
        warnings.append("Best practice: 'pack = \"name\"' should appear before imports")

    # Check for LogSpan or log usage
    has_log_usage = "LogSpan" in content or "with log(" in content
    checks["log_usage"] = has_log_usage
    if not has_log_usage:
        warnings.append(
            "Best practice: Consider using LogSpan or log() for observability"
        )

    # Check for raise statements (should prefer return error strings)
    has_raise = any(isinstance(node, ast.Raise) for node in ast.walk(tree))
    checks["no_raise"] = not has_raise
    if has_raise:
        warnings.append(
            "Best practice: Consider returning error strings instead of raising exceptions"
        )

    # Check for keyword-only args in exported functions
    exported_funcs = _get_exported_functions(tree)
    all_kwonly = True
    for func in exported_funcs:
        if not func.args.kwonlyargs and func.args.args:
            all_kwonly = False
            break
    checks["keyword_only_args"] = all_kwonly
    if not all_kwonly:
        warnings.append(
            "Best practice: Use keyword-only args (*, param) for API clarity"
        )

    # Check for complete docstrings (Args, Returns, Example)
    docstring_complete = True
    for func in exported_funcs:
        docstring = ast.get_docstring(func)
        if docstring:
            has_args = "Args:" in docstring or not func.args.kwonlyargs
            has_returns = "Returns:" in docstring or "Return:" in docstring
            has_example = "Example:" in docstring or "Examples:" in docstring
            if not (has_args and has_returns and has_example):
                docstring_complete = False
                break
        else:
            docstring_complete = False
            break
    checks["docstring_complete"] = docstring_complete
    if not docstring_complete:
        warnings.append(
            "Best practice: Docstrings should have Args, Returns, and Example sections"
        )

    return checks, warnings


def _get_exported_functions(
    tree: ast.Module,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Get functions that are exported via __all__."""
    all_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, ast.List)
                ):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            all_names.add(elt.value)

    funcs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in all_names
        ):
            funcs.append(node)
    return funcs


def validate_ext(*, path: str) -> str:
    """Validate an extension before reload.

    Checks Python syntax, required structure, and best practices.

    Args:
        path: Full path to the extension file

    Returns:
        Validation result with any errors or warnings

    Example:
        ot_forge.validate_ext(path="/path/to/extension.py")
    """
    with LogSpan(span="ot_forge.validate_ext", path=path) as s:
        ext_path = Path(path)

        if not ext_path.exists():
            s.add(error="file_not_found")
            return f"Error: File not found: {path}"

        if ext_path.suffix != ".py":
            s.add(error="not_python_file")
            return f"Error: Not a Python file: {path}"

        try:
            content = ext_path.read_text()
        except OSError as e:
            s.add(error=str(e))
            return f"Error reading file: {e}"

        errors: list[str] = []
        warnings: list[str] = []

        # Check 1: Python syntax
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            s.add(error="syntax_error")
            return f"Syntax error at line {e.lineno}: {e.msg}"

        # Check 2: Required structure - pack variable
        has_pack = any(
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "pack" for t in node.targets)
            for node in ast.walk(tree)
        )
        if not has_pack:
            errors.append("Missing 'pack = \"name\"' variable for tool discovery")

        # Check 3: Required structure - __all__ variable
        has_all = any(
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            for node in ast.walk(tree)
        )
        if not has_all:
            errors.append("Missing '__all__ = [...]' export list")

        # Check: every __all__ name must be defined at module level
        defined_names = {
            n.name
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        } | {
            t.id
            for n in tree.body
            if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Name)
        }
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
                )
                and isinstance(node.value, (ast.List, ast.Tuple))
            ):
                for elt in node.value.elts:
                    if (
                        isinstance(elt, ast.Constant)
                        and isinstance(elt.value, str)
                        and elt.value not in defined_names
                    ):
                        errors.append(
                            f"__all__ lists '{elt.value}' but it is not defined in the module"
                        )

        # Check 4: Best practices
        checks, bp_warnings = _check_best_practices(content, tree)
        warnings.extend(bp_warnings)

        # Build result showing what passed and failed
        result: list[str] = []

        result.append("Checks:")
        result.append(f'  [{"x" if has_pack else " "}] pack = "name" variable')
        result.append(f"  [{'x' if has_all else ' '}] __all__ export list")
        result.append("  [x] Python syntax valid")
        result.append(
            f"  [{'x' if checks.get('module_docstring', True) else ' '}] module docstring"
        )
        result.append(
            f"  [{'x' if checks.get('future_annotations', True) else ' '}] from __future__ import annotations"
        )
        result.append(
            f"  [{'x' if checks.get('pack_before_imports', True) else ' '}] pack before imports"
        )
        result.append(
            f"  [{'x' if checks.get('keyword_only_args', True) else ' '}] keyword-only args"
        )
        result.append(
            f"  [{'x' if checks.get('docstring_complete', True) else ' '}] complete docstrings"
        )
        result.append(
            f"  [{'x' if checks.get('log_usage', True) else ' '}] logging usage"
        )
        result.append(
            f"  [{'x' if checks.get('no_raise', True) else ' '}] returns errors (no raise)"
        )

        if errors:
            s.add(valid=False, errors=len(errors), warnings=len(warnings))
            result.insert(0, "Validation FAILED")
            result.insert(1, "")
            result.append("")
            result.append("Errors:")
            for err in errors:
                result.append(f"  - {err}")
            if warnings:
                result.append("")
                result.append("Warnings:")
                for warn in warnings:
                    result.append(f"  - {warn}")
            return "\n".join(result)

        s.add(valid=True, warnings=len(warnings))
        result.insert(0, "Validation PASSED")
        result.insert(1, "")

        if warnings:
            result.append("")
            result.append("Warnings:")
            for warn in warnings:
                result.append(f"  - {warn}")

        result.append("")
        result.append("Ready to reload: ot.reload()")
        return "\n".join(result)
