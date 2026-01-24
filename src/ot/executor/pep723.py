"""PEP 723 inline script metadata detection and parsing.

PEP 723 defines inline script metadata for Python scripts, allowing them
to declare dependencies and Python version requirements.

Example:
    # /// script
    # requires-python = ">=3.11"
    # dependencies = [
    #   "httpx>=0.27.0",
    #   "trafilatura>=2.0.0",
    # ]
    # ///

This module detects such headers and extracts tool functions for worker routing.
"""

from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Regex to match PEP 723 script block
# Matches: # /// script ... # ///
PEP723_PATTERN = re.compile(
    r"^# /// script\s*$"
    r"(.*?)"
    r"^# ///$",
    re.MULTILINE | re.DOTALL,
)


@dataclass
class ScriptMetadata:
    """Parsed PEP 723 script metadata."""

    requires_python: str | None = None
    dependencies: list[str] = field(default_factory=list)
    raw_content: str = ""

    @property
    def has_dependencies(self) -> bool:
        """Check if script declares any dependencies."""
        return bool(self.dependencies)


@dataclass
class ToolFileInfo:
    """Information about a tool file."""

    path: Path
    pack: str | None = None
    functions: list[str] = field(default_factory=list)
    is_worker: bool = False
    metadata: ScriptMetadata | None = None


def parse_pep723_metadata(content: str) -> ScriptMetadata | None:
    """Parse PEP 723 inline script metadata from file content.

    Args:
        content: File content to parse

    Returns:
        ScriptMetadata if found, None otherwise
    """
    match = PEP723_PATTERN.search(content)
    if not match:
        return None

    raw_content = match.group(1).strip()

    # Strip "# " prefix from each line to get valid TOML
    toml_lines = [
        line[2:] if line.startswith("# ") else line.lstrip("#")
        for line in raw_content.split("\n")
    ]
    toml_content = "\n".join(toml_lines)

    try:
        data = tomllib.loads(toml_content)
    except tomllib.TOMLDecodeError:
        return None

    return ScriptMetadata(
        requires_python=data.get("requires-python"),
        dependencies=data.get("dependencies", []),
        raw_content=raw_content,
    )


def has_pep723_header(path: Path) -> bool:
    """Check if a file has a PEP 723 script header.

    Args:
        path: Path to Python file

    Returns:
        True if file has PEP 723 header
    """
    try:
        content = path.read_text()
        return PEP723_PATTERN.search(content) is not None
    except OSError:
        return False


def extract_tool_functions(path: Path) -> list[str]:
    """Extract public function names from a tool file using AST.

    Args:
        path: Path to Python file

    Returns:
        List of public function names
    """
    try:
        content = path.read_text()
        tree = ast.parse(content)
    except (OSError, SyntaxError):
        return []

    functions: list[str] = []

    # Check for __all__ definition
    all_names: list[str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, ast.List)
                ):
                    all_names = []
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            all_names.append(elt.value)

    # Extract function definitions
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            name = node.name
            # Skip private functions
            if name.startswith("_"):
                continue
            # If __all__ is defined, only include those
            if all_names is not None and name not in all_names:
                continue
            functions.append(name)

    return functions


def extract_pack(path: Path) -> str | None:
    """Extract the pack declaration from a tool file.

    Looks for: pack = "name" at the top of the file.

    Args:
        path: Path to Python file

    Returns:
        Pack string, or None if not declared
    """
    try:
        content = path.read_text()
        tree = ast.parse(content)
    except (OSError, SyntaxError):
        return None

    # Look for pack assignment in module body
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "pack"
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    return node.value.value
    return None


def analyze_tool_file(path: Path) -> ToolFileInfo:
    """Analyze a tool file for metadata, pack, and functions.

    Args:
        path: Path to Python file

    Returns:
        ToolFileInfo with all extracted information
    """
    info = ToolFileInfo(path=path)

    try:
        content = path.read_text()
    except OSError:
        return info

    # Check for PEP 723 metadata
    info.metadata = parse_pep723_metadata(content)
    info.is_worker = info.metadata is not None and info.metadata.has_dependencies

    # Extract pack and functions
    info.pack = extract_pack(path)
    info.functions = extract_tool_functions(path)

    return info


def categorize_tools(
    tool_files: list[Path],
) -> tuple[list[ToolFileInfo], list[ToolFileInfo]]:
    """Categorize tool files into worker tools and in-process tools.

    Args:
        tool_files: List of tool file paths

    Returns:
        Tuple of (worker_tools, inprocess_tools)
    """
    worker_tools: list[ToolFileInfo] = []
    inprocess_tools: list[ToolFileInfo] = []

    for path in tool_files:
        info = analyze_tool_file(path)
        if info.is_worker:
            worker_tools.append(info)
        else:
            inprocess_tools.append(info)

    return worker_tools, inprocess_tools
