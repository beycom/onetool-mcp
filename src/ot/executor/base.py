"""Base types for executor module."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result from executing a tool."""

    success: bool
    result: str
    duration_seconds: float = 0.0
    executor: str = "simple"
    error_type: str | None = None
