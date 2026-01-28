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
    """Information about a tool file.

    Attributes:
        path: Path to the tool file.
        pack: Pack name (e.g., "brave" for brave.search).
        functions: List of public function names.
        is_worker: True if tool uses worker subprocess (PEP 723 with deps).
        is_internal: True if tool is bundled with OneTool (from ot_tools package).
        metadata: Parsed PEP 723 metadata if present.
        config_class_source: Source code of Config class if present.
    """

    path: Path
    pack: str | None = None
    functions: list[str] = field(default_factory=list)
    is_worker: bool = False
    is_internal: bool = False
    metadata: ScriptMetadata | None = None
    config_class_source: str | None = None


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


def _extract_functions_from_ast(tree: ast.Module) -> list[str]:
    """Extract public function names from a parsed AST.

    Args:
        tree: Parsed AST module

    Returns:
        List of public function names
    """
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


def _extract_pack_from_ast(tree: ast.Module) -> str | None:
    """Extract the pack declaration from a parsed AST.

    Looks for: pack = "name" at the top of the file.

    Args:
        tree: Parsed AST module

    Returns:
        Pack string, or None if not declared
    """
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


def _extract_config_from_ast(tree: ast.Module, content: str) -> str | None:
    """Extract the Config class source from a parsed AST.

    Looks for: class Config(BaseModel): in the module body.
    The class must inherit from BaseModel (pydantic).

    Args:
        tree: Parsed AST module
        content: Original file content (needed for source extraction)

    Returns:
        Config class source code as string, or None if not found
    """
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Config":
            # Verify it inherits from BaseModel
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr

                if base_name == "BaseModel":
                    # Extract source code using line numbers
                    lines = content.split("\n")
                    start_line = node.lineno - 1  # 0-indexed
                    end_line = node.end_lineno or node.lineno
                    config_source = "\n".join(lines[start_line:end_line])
                    return config_source

    return None


def analyze_tool_file(path: Path) -> ToolFileInfo:
    """Analyze a tool file for metadata, pack, functions, and config.

    Reads the file once and extracts all information in a single pass.

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

    # Parse AST once for all extractions
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return info

    # Extract pack, functions, and config class from pre-parsed AST
    info.pack = _extract_pack_from_ast(tree)
    info.functions = _extract_functions_from_ast(tree)
    info.config_class_source = _extract_config_from_ast(tree, content)

    return info


def categorize_tools(
    tool_files: list[Path],
    internal_paths: set[Path] | None = None,
) -> tuple[list[ToolFileInfo], list[ToolFileInfo]]:
    """Categorize tool files into extension tools and internal tools.

    Internal tools (bundled with OneTool) run in-process.
    Extension tools (user-created with PEP 723) run in worker subprocesses.

    Args:
        tool_files: List of tool file paths.
        internal_paths: Set of paths that are internal tools (from ot_tools package).
            If provided, tools in this set are marked as is_internal=True.

    Returns:
        Tuple of (worker_tools, inprocess_tools)
    """
    worker_tools: list[ToolFileInfo] = []
    inprocess_tools: list[ToolFileInfo] = []
    internal_paths = internal_paths or set()

    for path in tool_files:
        info = analyze_tool_file(path)
        # Mark internal tools (bundled with OneTool)
        info.is_internal = path.resolve() in internal_paths
        if info.is_worker:
            worker_tools.append(info)
        else:
            inprocess_tools.append(info)

    return worker_tools, inprocess_tools
