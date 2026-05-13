"""Extension forge tools.

Provides tools for creating and validating new in-process extension tools.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path

from otpack import LogSpan, cache, get_effective_cwd

from ot.paths import get_config_dir

# Pack for dot notation: ot_forge.create_ext(), ot_forge.validate_ext(), ot_forge.install_skills()
pack = "ot_forge"
pack_aliases = ("forge",)

__all__ = ["create_ext", "install_skills", "validate_ext"]


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

    resolved_patterns = [_resolve_tools_pattern(pattern, config_dir) for pattern in patterns]

    for candidate in candidates:
        candidate_str = str(candidate)
        if any(fnmatch.fnmatch(candidate_str, pattern) for pattern in resolved_patterns):
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
        # Validate name
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            return "Error: Name must be lowercase alphanumeric with underscores, starting with a letter"

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
            f"  2. Validate before reload: ot_forge.validate_ext(path=\"{ext_file}\")",
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
    all_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, ast.List):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            all_names.add(elt.value)

    funcs: list[ast.FunctionDef] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in all_names:
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

        # Check 4: Best practices
        checks, bp_warnings = _check_best_practices(content, tree)
        warnings.extend(bp_warnings)

        # Check 5: Warn about deprecated ot_sdk imports
        if "from ot_sdk" in content or "import ot_sdk" in content:
            warnings.append("DEPRECATED: ot_sdk imports are deprecated. Use ot.* imports for extension tools")

        # Build result showing what passed and failed
        result: list[str] = []

        result.append("Checks:")
        result.append(f"  [{'x' if has_pack else ' '}] pack = \"name\" variable")
        result.append(f"  [{'x' if has_all else ' '}] __all__ export list")
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


# =============================================================================
# Skill Installation
# =============================================================================


@cache.memoize(ttl=3600)
def _get_tools_config() -> dict:
    """Load tool path configuration from global_templates/skills.md."""
    import yaml

    from ot.paths import get_global_templates_dir

    tools_yaml = get_global_templates_dir() / "skills.md"
    if not tools_yaml.exists():
        return {}
    raw = yaml.safe_load(tools_yaml.read_text()) or {}
    return raw.get("tools", {})


@cache.memoize(ttl=3600)
def _get_skill_stub_template() -> str:
    """Load the Jinja2 skill stub template."""
    from ot.paths import get_global_templates_dir

    tmpl = get_global_templates_dir() / "skill_stub.md.j2"
    if not tmpl.exists():
        return (
            "---\nname: {{ name }}\ndescription: {{ description }}\n---\n\n"
            "To load this skill: `>>> ot.skills(name=\"{{ name }}\")`\n"
        )
    return tmpl.read_text(encoding="utf-8")


@cache.memoize(ttl=3600)
def _list_bundled_skills() -> list[str]:
    """Return sorted list of bundled skill names."""
    from ot.paths import get_global_templates_dir

    skills_dir = get_global_templates_dir() / "skills"
    if not skills_dir.exists():
        return []
    return sorted(f.stem for f in skills_dir.glob("*.md") if not f.name.startswith("_"))


@cache.memoize(ttl=3600)
def _get_skill_description(skill_name: str) -> str:
    """Get the description from a bundled skill's frontmatter."""
    import yaml

    from ot.paths import get_global_templates_dir

    skill_file = get_global_templates_dir() / "skills" / f"{skill_name}.md"
    if not skill_file.exists():
        return skill_name

    content = skill_file.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(content[3:end]) or {}
                return fm.get("description", skill_name)
            except yaml.YAMLError:
                pass
    return skill_name


@cache.memoize(ttl=3600)
def _get_skill_body(skill_name: str) -> str:
    """Get the body content from a bundled skill."""
    from ot.paths import get_global_templates_dir

    skill_file = get_global_templates_dir() / "skills" / f"{skill_name}.md"
    if not skill_file.exists():
        return ""

    content = skill_file.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:].strip()
    return content.strip()


def install_skills(
    *,
    install: str = "all",
    exclude: list[str] | None = None,
    tool: str = "claude",
) -> str:
    """Install a skill stub for an AI tool.

    Writes a stub file to the appropriate location for the specified AI tool.
    Use ot.skills() to list available skills.

    Args:
        install: Skill name to install, or "all" to install all skills (default)
        exclude: Skill names to skip when install="all"
        tool: Target AI tool — "claude" (default), "codex", or "opencode"

    Returns:
        Status message describing what was done

    Example:
        ot_forge.install_skills()
        ot_forge.install_skills(install="ot-ref")
        ot_forge.install_skills(install="ot-ref", tool="codex")
        ot_forge.install_skills(install="all", tool="opencode")
        ot_forge.install_skills(install="ot-ref", tool="pi")
    """
    exclude = exclude or []
    with LogSpan(span="ot_forge.install_skills", install=install, tool=tool) as s:
        tools_config = _get_tools_config()
        bundled = _list_bundled_skills()

        # Validate tool
        if tool not in tools_config:
            supported = ", ".join(sorted(tools_config.keys())) or "none"
            s.add(error="unsupported_tool", tool=tool)
            return f"Error: Unsupported tool '{tool}'. Supported: {supported}"

        tool_cfg = tools_config[tool]
        stub_path_template = tool_cfg.get("stub_path", "")

        # Resolve list of skills to install
        if install == "all":
            to_install = [skill for skill in bundled if skill not in exclude]
        else:
            if install not in bundled:
                s.add(error="unknown_skill", install=install)
                return (
                    f"Error: Unknown skill '{install}'. "
                    f"Available: {', '.join(bundled) or '(none)'}"
                )
            to_install = [install]

        # Render and write stubs
        try:
            from jinja2 import Template

            template_src = _get_skill_stub_template()
            tmpl = Template(template_src)
        except ImportError:
            return "Error: jinja2 is required for ot_forge.install_skills(). Install it: pip install jinja2"

        from ot.paths import expand_path

        cwd = get_effective_cwd()

        results: list[str] = []
        for skill_name in to_install:
            description = _get_skill_description(skill_name)
            body = _get_skill_body(skill_name)
            rendered = tmpl.render(name=skill_name, description=description, body=body, tool=tool)

            # Resolve stub path
            raw_path = stub_path_template.format(name=skill_name)
            if raw_path.startswith("~"):
                stub_file = expand_path(raw_path)
            elif Path(raw_path).is_absolute():
                stub_file = Path(raw_path)
            else:
                stub_file = cwd / raw_path

            # Write the stub
            stub_file.parent.mkdir(parents=True, exist_ok=True)
            existed = stub_file.exists()
            stub_file.write_text(rendered, encoding="utf-8")
            action = "updated" if existed else "installed"
            results.append(f"  {action}: {stub_file}")

        s.add(installed=len(to_install), tool=tool)
        summary = f"Skill stubs for '{tool}' ({len(to_install)} skills):\n" + "\n".join(results)
        return summary
