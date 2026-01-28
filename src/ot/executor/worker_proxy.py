"""Worker proxy for routing tool calls to persistent workers.

Creates proxy objects that can be added to the execution namespace,
allowing dot notation access (e.g., brave.search()) to route to workers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ot.executor.param_resolver import get_tool_param_names, resolve_kwargs
from ot.executor.worker_pool import get_worker_pool
from ot.stats import timed_tool_call


class WorkerFunctionProxy:
    """Proxy for a single function that routes calls to a worker."""

    def __init__(
        self,
        tool_path: Path,
        function_name: str,
        config: dict[str, Any],
        secrets: dict[str, str],
    ) -> None:
        """Initialize function proxy.

        Args:
            tool_path: Path to the tool Python file
            function_name: Name of the function to call
            config: Configuration dict to pass to worker
            secrets: Secrets dict to pass to worker
        """
        self.tool_path = tool_path
        self.function_name = function_name
        self.config = config
        self.secrets = secrets

    def __call__(self, **kwargs: Any) -> Any:
        """Call the function in the worker process.

        Args:
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the function
        """
        tool_name = f"{self.tool_path.stem}.{self.function_name}"

        # Resolve abbreviated parameter names (cached lookup)
        if kwargs:
            param_names = get_tool_param_names(tool_name)
            if param_names:
                kwargs = resolve_kwargs(kwargs, list(param_names))

        with timed_tool_call(tool_name):
            pool = get_worker_pool()
            return pool.call(
                tool_path=self.tool_path,
                function=self.function_name,
                kwargs=kwargs,
                config=self.config,
                secrets=self.secrets,
            )

    def __repr__(self) -> str:
        return f"<WorkerFunctionProxy {self.tool_path.stem}.{self.function_name}>"


class WorkerPackProxy:
    """Proxy for a tool pack that routes attribute access to functions.

    Provides dot notation access: pack.function(**kwargs)
    """

    def __init__(
        self,
        tool_path: Path,
        functions: list[str],
        config: dict[str, Any],
        secrets: dict[str, str],
    ) -> None:
        """Initialize pack proxy.

        Args:
            tool_path: Path to the tool Python file
            functions: List of function names available in the tool
            config: Configuration dict to pass to worker
            secrets: Secrets dict to pass to worker
        """
        self.tool_path = tool_path
        self.functions = set(functions)
        self.config = config
        self.secrets = secrets
        self._function_cache: dict[str, WorkerFunctionProxy] = {}

    def __getattr__(self, name: str) -> WorkerFunctionProxy:
        """Get a function proxy by name.

        Args:
            name: Function name

        Returns:
            WorkerFunctionProxy for the function

        Raises:
            AttributeError: If function name is not available
        """
        if name.startswith("_"):
            raise AttributeError(f"Cannot access private attribute '{name}'")

        if name not in self.functions:
            available = ", ".join(sorted(self.functions))
            raise AttributeError(
                f"Tool '{self.tool_path.stem}' has no function '{name}'. "
                f"Available: {available}"
            )

        if name not in self._function_cache:
            self._function_cache[name] = WorkerFunctionProxy(
                tool_path=self.tool_path,
                function_name=name,
                config=self.config,
                secrets=self.secrets,
            )

        return self._function_cache[name]

    def __repr__(self) -> str:
        funcs = ", ".join(sorted(self.functions))
        return f"<WorkerPackProxy {self.tool_path.stem}: {funcs}>"

    def __dir__(self) -> list[str]:
        """Return available function names for introspection."""
        return list(self.functions)


def create_worker_proxy(
    tool_path: Path,
    functions: list[str],
    config: dict[str, Any] | None = None,
    secrets: dict[str, str] | None = None,
) -> WorkerPackProxy:
    """Create a worker proxy for a tool.

    Args:
        tool_path: Path to the tool Python file
        functions: List of function names available in the tool
        config: Configuration dict to pass to worker
        secrets: Secrets dict to pass to worker

    Returns:
        WorkerPackProxy for the tool
    """
    return WorkerPackProxy(
        tool_path=tool_path,
        functions=functions,
        config=config or {},
        secrets=secrets or {},
    )


def create_worker_function(
    tool_path: Path,
    function_name: str,
    config: dict[str, Any] | None = None,
    secrets: dict[str, str] | None = None,
) -> Callable[..., Any]:
    """Create a single worker function proxy.

    Use this when you need a standalone function rather than a pack.

    Args:
        tool_path: Path to the tool Python file
        function_name: Name of the function to call
        config: Configuration dict to pass to worker
        secrets: Secrets dict to pass to worker

    Returns:
        Callable that routes to the worker
    """
    return WorkerFunctionProxy(
        tool_path=tool_path,
        function_name=function_name,
        config=config or {},
        secrets=secrets or {},
    )
