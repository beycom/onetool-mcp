"""Extension scaffolding tools.

Provides tools for creating new extension tools from templates.
Extensions are user-created tools that run in isolated worker subprocesses.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from ot.logging import LogSpan
from ot.paths import get_global_dir, get_project_dir

# Pack for dot notation: scaffold.create(), scaffold.templates(), scaffold.list()
pack = "scaffold"

__all__ = ["create", "extensions", "templates", "validate"]


def _get_templates_dir() -> Path:
    """Get the extension templates directory."""
    from ot.paths import get_bundled_config_dir

    return get_bundled_config_dir() / "tool_templates"


def templates() -> str:
    """List available extension templates.

    Returns:
        Formatted list of templates with descriptions

    Example:
        scaffold.templates()
    """
    with LogSpan(span="scaffold.templates") as s:
        templates_dir = _get_templates_dir()

        if not templates_dir.exists():
            s.add(error="templates_dir_missing")
            return "Error: Templates directory not found"

        templates = []
        for template_file in templates_dir.glob("*.py"):
            if template_file.name.startswith("_"):
                continue

            # Read the module docstring
            content = template_file.read_text()
            docstring = ""
            if '"""' in content:
                match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                if match:
                    lines = match.group(1).strip().split("\n")
                    # Skip placeholder lines like {{description}}
                    for line in lines:
                        line = line.strip()
                        if line and "{{" not in line:
                            docstring = line
                            break

            templates.append({
                "name": template_file.stem,
                "description": docstring or "No description",
            })

        if not templates:
            return "No templates found"

        lines = ["Available extension templates:", ""]
        for t in templates:
            lines.append(f"  {t['name']}")
            lines.append(f"    {t['description']}")
            lines.append("")

        lines.append("Use scaffold.create() to create a new extension from a template.")
        s.add(count=len(templates))
        return "\n".join(lines)


def create(
    *,
    name: str,
    template: str = "extension",
    pack_name: str | None = None,
    function: str = "run",
    description: str = "My extension tool",
    function_description: str = "Execute the tool function",
    api_key: str = "MY_API_KEY",
    scope: str = "project",
) -> str:
    """Create a new extension tool from a template.

    Creates a new extension in .onetool/tools/{name}/{name}.py or
    ~/.onetool/tools/{name}/{name}.py depending on scope.

    Args:
        name: Extension name (will be used as directory and file name)
        template: Template name (default: extension)
        pack_name: Pack name for dot notation (default: same as name)
        function: Main function name (default: run)
        description: Module description
        function_description: Function docstring description
        api_key: API key secret name (for optional API configuration)
        scope: Where to create - "project" (default) or "global"

    Returns:
        Success message with instructions, or error message

    Example:
        scaffold.create(name="my_tool", function="search")
        scaffold.create(name="api_tool", api_key="MY_API_KEY")
    """
    with LogSpan(span="scaffold.create", name=name, template=template) as s:
        # Validate name
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            return "Error: Name must be lowercase alphanumeric with underscores, starting with a letter"

        # Get templates directory
        templates_dir = _get_templates_dir()
        template_file = templates_dir / f"{template}.py"

        if not template_file.exists():
            available = [f.stem for f in templates_dir.glob("*.py") if not f.name.startswith("_")]
            return f"Error: Template '{template}' not found. Available: {', '.join(available)}"

        # Determine output directory
        if scope == "global":
            base_dir = get_global_dir() / "tools"
        else:
            project_dir = get_project_dir()
            if not project_dir:
                # Create .onetool if it doesn't exist
                from ot.paths import ensure_project_dir
                project_dir = ensure_project_dir(quiet=True)
            base_dir = project_dir / "tools"

        ext_dir = base_dir / name
        ext_file = ext_dir / f"{name}.py"

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

        s.add(path=str(ext_file), scope=scope)

        # Build helpful output with next steps
        lines = [
            f"Created extension: {ext_file}",
            "",
            "Next steps:",
            "  1. Edit the file to implement your logic",
            f"  2. Validate before reload: scaffold.validate(path=\"{ext_file}\")",
            "  3. Reload to activate: ot.reload()",
            f"  4. Use your tool: {pack}.{function}()",
        ]
        return "\n".join(lines)


def extensions() -> str:
    """List extension tools loaded from tools_dir config.

    Shows all extension tool files currently loaded, with full paths.
    Tools are loaded from paths specified in the tools_dir config.

    Returns:
        Formatted list of loaded extension files

    Example:
        scaffold.extensions()
    """
    with LogSpan(span="scaffold.extensions") as s:
        from ot.config.loader import get_config

        config = get_config()
        if config is None:
            s.add(error="no_config")
            return "No configuration loaded"

        tool_files = config.get_tool_files()

        if not tool_files:
            s.add(count=0)
            return "No extensions loaded. Create one with scaffold.create()"

        lines = ["Loaded extensions:", ""]
        for path in sorted(tool_files):
            lines.append(f"  {path}")

        lines.append("")
        lines.append(f"Total: {len(tool_files)} files")

        s.add(count=len(tool_files))
        return "\n".join(lines)


def _has_pep723_deps(content: str) -> bool:
    """Check if content has PEP 723 script metadata with dependencies."""
    if "# /// script" not in content:
        return False
    # Look for dependencies line in the script block
    in_script_block = False
    for line in content.split("\n"):
        if line.strip() == "# /// script":
            in_script_block = True
        elif line.strip() == "# ///":
            in_script_block = False
        elif in_script_block and "dependencies" in line:
            return True
    return False


def _check_best_practices(content: str, tree: ast.Module) -> tuple[dict[str, bool], list[str]]:
    """Check for best practices violations.

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
        warnings.append("Best practice: Add 'from __future__ import annotations' for forward compatibility")

    # Find line numbers of key elements
    pack_line = None
    first_import_line = None

    for i, line in enumerate(lines, 1):
        if line.startswith("pack = ") and pack_line is None:
            pack_line = i
        if (line.startswith("import ") or line.startswith("from ")) and first_import_line is None and "from __future__" not in line:
            first_import_line = i

    # Check: pack before imports
    pack_before_imports = not (pack_line and first_import_line and pack_line > first_import_line)
    checks["pack_before_imports"] = pack_before_imports
    if not pack_before_imports:
        warnings.append("Best practice: 'pack = \"name\"' should appear before imports")

    # Check for LogSpan or log usage
    has_log_usage = "LogSpan" in content or "with log(" in content
    checks["log_usage"] = has_log_usage
    if not has_log_usage:
        warnings.append("Best practice: Consider using LogSpan or log() for observability")

    # Check for raise statements (should prefer return error strings)
    has_raise = any(isinstance(node, ast.Raise) for node in ast.walk(tree))
    checks["no_raise"] = not has_raise
    if has_raise:
        warnings.append("Best practice: Consider returning error strings instead of raising exceptions")

    # Check for keyword-only args in exported functions
    exported_funcs = _get_exported_functions(tree)
    all_kwonly = True
    for func in exported_funcs:
        if not func.args.kwonlyargs and func.args.args:
            # Has positional args but no keyword-only args
            all_kwonly = False
            break
    checks["keyword_only_args"] = all_kwonly
    if not all_kwonly:
        warnings.append("Best practice: Use keyword-only args (*, param) for API clarity")

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
        warnings.append("Best practice: Docstrings should have Args, Returns, and Example sections")

    return checks, warnings


def _get_exported_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    """Get functions that are exported via __all__."""
    # Find __all__ list
    all_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, ast.List):
                    for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                all_names.add(elt.value)

    # Find exported functions
    funcs: list[ast.FunctionDef] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in all_names:
            funcs.append(node)
    return funcs


def validate(*, path: str) -> str:
    """Validate an extension before reload.

    Checks Python syntax, required structure, and best practices.

    Args:
        path: Full path to the extension file

    Returns:
        Validation result with any errors or warnings

    Example:
        scaffold.validate(path="/path/to/extension.py")
    """
    with LogSpan(span="scaffold.validate", path=path) as s:
        ext_path = Path(path)

        if not ext_path.exists():
            s.add(error="file_not_found")
            return f"Error: File not found: {path}"

        if ext_path.suffix != ".py":
            s.add(error="not_python_file")
            return f"Error: Not a Python file: {path}"

        try:
            content = ext_path.read_text()
        except Exception as e:
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

        # Check 4: worker_main() if PEP 723 deps present
        if _has_pep723_deps(content):
            has_worker_main = "worker_main()" in content
            if not has_worker_main:
                errors.append("Missing 'worker_main()' call - required for extensions with PEP 723 dependencies")

        # Check 5: Best practices
        checks, warnings = _check_best_practices(content, tree)

        # Build result showing what passed and failed
        result: list[str] = []

        # Show check results
        result.append("Checks:")
        result.append(f"  [{'x' if has_pack else ' '}] pack = \"name\" variable")
        result.append(f"  [{'x' if has_all else ' '}] __all__ export list")
        if _has_pep723_deps(content):
            has_worker = "worker_main()" in content
            result.append(f"  [{'x' if has_worker else ' '}] worker_main() (PEP 723)")
        result.append("  [x] Python syntax valid")
        result.append(f"  [{'x' if checks.get('module_docstring', True) else ' '}] module docstring")
        result.append(f"  [{'x' if checks.get('future_annotations', True) else ' '}] from __future__ import annotations")
        result.append(f"  [{'x' if checks.get('pack_before_imports', True) else ' '}] pack before imports")
        result.append(f"  [{'x' if checks.get('keyword_only_args', True) else ' '}] keyword-only args")
        result.append(f"  [{'x' if checks.get('docstring_complete', True) else ' '}] complete docstrings")
        result.append(f"  [{'x' if checks.get('log_usage', True) else ' '}] logging usage")
        result.append(f"  [{'x' if checks.get('no_raise', True) else ' '}] returns errors (no raise)")

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
