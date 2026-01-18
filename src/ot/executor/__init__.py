"""Execution engines for OneTool.

Provides direct host execution via SimpleExecutor.
The unified runner provides a single entry point for all command execution.
"""

from ot.executor.base import ExecutionResult
from ot.executor.fence_processor import strip_fences
from ot.executor.runner import (
    CommandResult,
    execute_command,
    execute_python_code,
)
from ot.executor.simple import SimpleExecutor
from ot.executor.validator import (
    ValidationResult,
    validate_for_exec,
    validate_python_code,
)

__all__ = [
    "CommandResult",
    "ExecutionResult",
    "SimpleExecutor",
    "ValidationResult",
    "execute_command",
    "execute_python_code",
    "strip_fences",
    "validate_for_exec",
    "validate_python_code",
]
