"""Extension scaffolding tools.

Provides tools for creating new extension tools from templates.
Extensions are user-created tools that run in isolated worker subprocesses.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ot.logging import LogSpan
from ot.paths import get_global_dir, get_project_dir

if TYPE_CHECKING:
    from pathlib import Path

# Pack for dot notation: scaffold.create(), scaffold.templates(), scaffold.list()
pack = "scaffold"

__all__ = ["create", "list_extensions", "templates"]


def _get_templates_dir() -> Path:
    """Get the extension templates directory."""
    from ot.paths import get_bundled_config_dir

    return get_bundled_config_dir() / "tool-templates"


def _get_extension_dirs() -> list[tuple[Path, str]]:
    """Get extension directories (project and global).

    Returns:
        List of (path, scope) tuples where scope is "project" or "global"
    """
    dirs: list[tuple[Path, str]] = []

    # Project extensions: .onetool/tools/
    project_dir = get_project_dir()
    if project_dir:
        ext_dir = project_dir / "tools"
        if ext_dir.exists():
            dirs.append((ext_dir, "project"))

    # Global extensions: ~/.onetool/tools/
    global_dir = get_global_dir()
    global_ext_dir = global_dir / "tools"
    if global_ext_dir.exists():
        dirs.append((global_ext_dir, "global"))

    return dirs


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
                    docstring = match.group(1).strip().split("\n")[0]

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
    template: str = "extension_simple",
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
        template: Template name (default: extension_simple)
        pack_name: Pack name for dot notation (default: same as name)
        function: Main function name (default: run)
        description: Module description
        function_description: Function docstring description
        api_key: API key secret name (for api template)
        scope: Where to create - "project" (default) or "global"

    Returns:
        Success message with created file path, or error message

    Example:
        scaffold.create(name="my_tool", function="search")
        scaffold.create(name="api_tool", template="extension", api_key="MY_API_KEY")
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
        return f"Created extension: {ext_file}\n\nTo use: {pack}.{function}()"


def list_extensions() -> str:
    """List installed extensions.

    Returns:
        Formatted list of extensions by scope

    Example:
        scaffold.list_extensions()
    """
    with LogSpan(span="scaffold.list") as s:
        ext_dirs = _get_extension_dirs()

        if not ext_dirs:
            return "No extension directories found. Create one with scaffold.create()"

        lines = ["Installed extensions:", ""]
        total = 0

        for ext_path, scope in ext_dirs:
            extensions = []
            for subdir in ext_path.iterdir():
                if subdir.is_dir():
                    # Look for main .py file
                    py_files = list(subdir.glob("*.py"))
                    if py_files:
                        extensions.append(subdir.name)

            if extensions:
                lines.append(f"{scope.capitalize()} ({ext_path}):")
                for ext in sorted(extensions):
                    lines.append(f"  - {ext}")
                lines.append("")
                total += len(extensions)

        if total == 0:
            return "No extensions installed. Create one with scaffold.create()"

        s.add(count=total)
        return "\n".join(lines)
