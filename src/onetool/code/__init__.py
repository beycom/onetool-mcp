"""Minimal CLIProxyAPI launch support for Claude Code and Codex."""

from onetool.code.adapters import (
    build_invocation,
    connection_from_environment,
    replace_process,
)
from onetool.code.domain import LaunchInvocation
from onetool.code.proxy import DiscoveredModel, ModelDiscovery
from onetool.code.selection import parse_context, resolve_model_query

__all__ = [
    "DiscoveredModel",
    "LaunchInvocation",
    "ModelDiscovery",
    "build_invocation",
    "connection_from_environment",
    "parse_context",
    "replace_process",
    "resolve_model_query",
]
