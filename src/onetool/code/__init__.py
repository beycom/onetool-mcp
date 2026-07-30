"""Typed Claude Code and Codex launcher support."""

from onetool.code.adapters import build_invocation, replace_process
from onetool.code.domain import LaunchInvocation, ResolvedModel, ResolvedTarget
from onetool.code.proxy import ModelDiscovery
from onetool.code.resolver import resolve_target

__all__ = [
    "LaunchInvocation",
    "ModelDiscovery",
    "ResolvedModel",
    "ResolvedTarget",
    "build_invocation",
    "replace_process",
    "resolve_target",
]
