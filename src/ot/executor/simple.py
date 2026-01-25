"""Simple executor - host process execution.

Executes tool code directly in the host Python process.
V1 uses this executor for all execution.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from typing import TYPE_CHECKING, Any

from loguru import logger

from ot.executor.base import ExecutionResult
from ot.logging import LogEntry, LogSpan
from ot.utils import serialize_result

if TYPE_CHECKING:
    from ot.registry import ToolInfo


class SimpleExecutor:
    """Host process executor (v1 behaviour).

    Loads and executes tool modules directly in the host Python process.
    Fast but no isolation - tools have full filesystem access.
    """

    @property
    def name(self) -> str:
        """Return the executor name."""
        return "simple"

    def _load_tool_module(self, module_name: str) -> Any:
        """Dynamically load a tool module.

        Args:
            module_name: Module path like 'tools.example'

        Returns:
            The loaded module object

        Raises:
            ImportError: If module cannot be loaded
        """
        from ot.config.loader import get_config

        # Get tool files from config
        config = get_config()
        tool_files = config.get_tool_files() if config else []
        if not tool_files:
            raise ImportError(
                f"No tool files configured. Cannot load module: {module_name}"
            )

        # Convert module path to file name (tools.example -> example.py)
        parts = module_name.split(".")
        if len(parts) < 2 or parts[-2] != "tools":
            raise ImportError(f"Invalid tool module: {module_name}")

        target_name = f"{parts[-1]}.py"

        # Find matching tool file from config
        file_path = None
        for tf in tool_files:
            if tf.name == target_name:
                file_path = tf
                break

        if file_path is None or not file_path.exists():
            raise ImportError(f"Tool file not found: {target_name}")

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module spec for: {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return module

    async def execute(
        self,
        func_name: str,
        kwargs: dict[str, Any],
        tool: ToolInfo,
    ) -> ExecutionResult:
        """Execute a tool function in the host process.

        Args:
            func_name: Name of the function to execute
            kwargs: Keyword arguments for the function
            tool: ToolInfo with module and signature info

        Returns:
            ExecutionResult with success status and result string
        """
        start_time = time.perf_counter()

        try:
            # Load the module and get the function
            module = self._load_tool_module(tool.module)
            func = getattr(module, func_name, None)

            if func is None:
                raise ValueError(
                    f"Function '{func_name}' not found in module {tool.module}"
                )

            # Execute the function with timing via LogSpan
            with LogSpan(span="executor.simple", tool=func_name) as span:
                span.add("kwargs", {k: str(v) for k, v in kwargs.items()})
                result = func(**kwargs)
                result_str = serialize_result(result)
                span.add("resultLength", len(result_str))

            duration = time.perf_counter() - start_time

            return ExecutionResult(
                success=True,
                result=result_str,
                duration_seconds=duration,
                executor="simple",
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                LogEntry(
                    span="executor.simple.error",
                    tool=func_name,
                    error=str(e),
                    errorType=type(e).__name__,
                    duration=duration,
                )
            )

            return ExecutionResult(
                success=False,
                result=f"Error executing tool '{func_name}': {e}",
                duration_seconds=duration,
                executor="simple",
                error_type=type(e).__name__,
            )

    async def start(self) -> None:
        """Start the executor (no-op for simple executor)."""
        logger.debug(LogEntry(span="executor.simple.start"))

    async def stop(self) -> None:
        """Stop the executor (no-op for simple executor)."""
        logger.debug(LogEntry(span="executor.simple.stop"))

    async def health_check(self) -> bool:
        """Check if the executor is healthy.

        Simple executor is always healthy.
        """
        return True
