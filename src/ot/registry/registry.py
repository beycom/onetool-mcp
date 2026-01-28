"""Tool registry class for auto-discovering Python tools."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.logging import LogEntry

from .parser import parse_function

if TYPE_CHECKING:
    from .models import ToolInfo


class ToolRegistry:
    """Registry for auto-discovered Python tools.

    Scans a directory for Python files and extracts function information
    using AST parsing (no execution required).
    """

    def __init__(self, tools_path: Path | None = None) -> None:
        """Initialize the registry.

        Args:
            tools_path: Path to tools directory. Defaults to 'src/ot_tools/'.
        """
        self._tools_path = tools_path or Path("src/ot_tools")
        self._tools: dict[str, ToolInfo] = {}

    @property
    def tools_path(self) -> Path:
        """Return the tools directory path."""
        return self._tools_path

    @property
    def tools(self) -> dict[str, ToolInfo]:
        """Return dictionary of registered tools by name."""
        return self._tools.copy()

    def scan_files(self, files: list[Path]) -> list[ToolInfo]:
        """Scan specific Python files and register public functions.

        Args:
            files: List of Python files to scan.

        Returns:
            List of registered ToolInfo objects.
        """
        # Track previous state to detect changes
        previous_tools = dict(self._tools)
        self._tools.clear()

        for py_file in files:
            if not py_file.exists():
                logger.debug(
                    LogEntry(span="registry.scan", path=str(py_file), exists=False)
                )
                continue
            try:
                tools = self.parse_file(py_file)
                for tool in tools:
                    if tool.name in self._tools:
                        logger.warning(
                            LogEntry(
                                span="registry.duplicate",
                                tool=tool.name,
                                file=str(py_file),
                            )
                        )
                    self._tools[tool.name] = tool
            except SyntaxError as e:
                logger.warning(
                    LogEntry(
                        span="registry.error",
                        file=str(py_file),
                        error=str(e),
                        errorType="SyntaxError",
                    )
                )
            except Exception as e:
                logger.warning(
                    LogEntry(
                        span="registry.error",
                        file=str(py_file),
                        error=str(e),
                        errorType=type(e).__name__,
                    )
                )

        # Detect added/changed/removed tools
        added: list[str] = []
        changed: list[str] = []
        removed: list[str] = []

        for name, tool in self._tools.items():
            if name not in previous_tools:
                added.append(name)
            elif tool.signature != previous_tools[name].signature:
                changed.append(name)

        for name in previous_tools:
            if name not in self._tools:
                removed.append(name)

        # Only log if this is first scan or there are changes
        if not previous_tools:
            # First scan - log all tools
            logger.info(
                LogEntry(
                    span="registry.ready",
                    path="tools",
                    toolCount=len(self._tools),
                    tools=[tool.name for tool in self._tools.values()],
                )
            )
        elif added or changed or removed:
            # Subsequent scan with changes
            logger.info(
                LogEntry(
                    span="registry.changed",
                    path="tools",
                    toolCount=len(self._tools),
                    added=added if added else None,
                    changed=changed if changed else None,
                    removed=removed if removed else None,
                )
            )

        return list(self._tools.values())

    def scan_directory(self, path: Path | None = None) -> list[ToolInfo]:
        """Scan directory for Python files and register public functions.

        Args:
            path: Directory to scan. Defaults to self.tools_path.

        Returns:
            List of registered ToolInfo objects.
        """
        scan_path = path or self._tools_path

        if not scan_path.exists():
            logger.debug(
                LogEntry(span="registry.scan", path=str(scan_path), exists=False)
            )
            return []

        if not scan_path.is_dir():
            logger.warning(
                LogEntry(span="registry.scan", path=str(scan_path), isDir=False)
            )
            return []

        py_files = list(scan_path.glob("*.py"))
        return self.scan_files(py_files)

    def parse_file(self, path: Path) -> list[ToolInfo]:
        """Parse a Python file and extract public function information.

        Args:
            path: Path to Python file.

        Returns:
            List of ToolInfo for exported functions (respects __all__ and pack).
        """
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        # Module name: tools/gold_prices.py -> tools.gold_prices
        module_name = f"tools.{path.stem}"

        # Extract pack variable (e.g., pack = "code")
        pack = self._extract_pack(tree)

        # Extract __all__ list if present
        export_names = self._extract_all(tree)

        # Extract __ot_requires__ dependencies
        requires = self._extract_requires(tree)

        tools: list[ToolInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions
                if node.name.startswith("_"):
                    continue

                # If __all__ is defined, only include exported functions
                if export_names is not None and node.name not in export_names:
                    continue

                tool = parse_function(node, module_name, pack=pack)
                # Attach module-level requires to tool
                if requires:
                    tool.requires = requires
                tools.append(tool)

        return tools

    def _extract_pack(self, tree: ast.Module) -> str | None:
        """Extract pack variable from module AST.

        Looks for module-level assignment: pack = "pack_name"

        Args:
            tree: Parsed AST module.

        Returns:
            Pack name string if found, None otherwise.
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

    def _extract_all(self, tree: ast.Module) -> set[str] | None:
        """Extract __all__ list from module AST.

        Looks for module-level assignment: __all__ = ["func1", "func2"]

        Args:
            tree: Parsed AST module.

        Returns:
            Set of exported names if __all__ is defined, None otherwise.
        """
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "__all__"
                        and isinstance(node.value, ast.List)
                    ):
                        names: set[str] = set()
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                names.add(elt.value)
                        return names
        return None

    def _extract_requires(self, tree: ast.Module) -> dict[str, list[str]] | None:
        """Extract __ot_requires__ dict from module AST.

        Looks for module-level assignment: __ot_requires__ = {"cli": [...], "lib": [...]}

        Args:
            tree: Parsed AST module.

        Returns:
            Dict with 'cli' and 'lib' dependency lists if found, None otherwise.
        """
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__ot_requires__":
                        try:
                            # Safely evaluate the dict literal
                            return ast.literal_eval(ast.unparse(node.value))
                        except (ValueError, TypeError):
                            return None
        return None

    def format_json(self) -> str:
        """Format registry as JSON for LLM context.

        Returns:
            JSON string with tool definitions.
        """
        if not self._tools:
            return '{"tools":[]}'

        tools_list: list[dict[str, Any]] = []
        for tool in self._tools.values():
            tool_dict: dict[str, Any] = {
                "name": tool.name,
                "module": tool.module,
                "signature": tool.signature,
            }
            if tool.description:
                tool_dict["description"] = tool.description
            if tool.args:
                tool_dict["args"] = [
                    {
                        k: v
                        for k, v in {
                            "name": arg.name,
                            "type": arg.type,
                            "default": arg.default,
                            "description": arg.description if arg.description else None,
                        }.items()
                        if v is not None
                    }
                    for arg in tool.args
                ]
            if tool.returns:
                tool_dict["returns"] = tool.returns

            tools_list.append(tool_dict)

        return json.dumps({"tools": tools_list}, ensure_ascii=False, indent=2)

    def format_summary(self) -> str:
        """Format registry summary for CLI display.

        Returns:
            Human-readable summary of registered tools.
        """
        if not self._tools:
            return "No tools registered."

        lines = [f"Registered tools ({len(self._tools)}):"]
        for tool in self._tools.values():
            lines.append(f"  - {tool.signature}")
            if tool.description:
                lines.append(f"      {tool.description}")

        return "\n".join(lines)

    def get_tool(self, name: str) -> ToolInfo | None:
        """Get tool by name.

        Args:
            name: Tool function name.

        Returns:
            ToolInfo if found, None otherwise.
        """
        return self._tools.get(name)

    def register_tool(self, tool: ToolInfo) -> None:
        """Register a tool programmatically.

        Used for tools that aren't loaded from files (e.g., ot pack tools).

        Args:
            tool: ToolInfo object to register.
        """
        self._tools[tool.name] = tool

    def describe_tool(self, name: str) -> str:
        """Get detailed description of a tool.

        Args:
            name: Tool function name.

        Returns:
            Detailed tool description string.
        """
        tool = self._tools.get(name)
        if not tool:
            return f"Tool '{name}' not found."

        lines = [
            f"Tool: {tool.name}",
            f"Module: {tool.module}",
            f"Signature: {tool.signature}",
        ]

        # Show deprecation warning first
        if tool.deprecated:
            msg = tool.deprecated_message or "This tool is deprecated"
            lines.append(f"DEPRECATED: {msg}")

        if not tool.enabled:
            lines.append("Status: DISABLED")

        if tool.description:
            lines.append(f"Description: {tool.description}")

        if tool.tags:
            lines.append(f"Tags: {', '.join(tool.tags)}")

        if tool.args:
            lines.append("Arguments:")
            for arg in tool.args:
                arg_line = f"  - {arg.name}: {arg.type}"
                if arg.default is not None:
                    arg_line += f" = {arg.default}"
                lines.append(arg_line)
                if arg.description:
                    lines.append(f"      {arg.description}")

        if tool.returns:
            lines.append(f"Returns: {tool.returns}")

        if tool.examples:
            lines.append("Examples:")
            for example in tool.examples:
                lines.append(f"  {example}")

        return "\n".join(lines)
