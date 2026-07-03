"""Runtime service hooks for pack-owned framework integrations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


class ResultStoreBackend(Protocol):
    """Backend interface for storing and querying large execution results."""

    def store(self, content: str, *, tool: str = "", preview_lines: int | None = None) -> Any:
        """Store content and return backend-specific stored-result metadata."""
        ...

    def query(
        self,
        handle: str,
        *,
        offset: int = 1,
        limit: int = 100,
        search: str = "",
        fuzzy: bool = False,
        tail: int = 0,
        context: int = 0,
    ) -> Any:
        """Query stored content."""
        ...

    def cleanup(self) -> int:
        """Clean expired stored content."""
        ...

    def format_store_response(self, stored: Any) -> dict[str, Any]:
        """Format stored-result metadata for runner responses."""
        ...


@dataclass(frozen=True)
class OutputPolicy:
    """Output handling policy for a resolved tool call."""

    allow_deflect: bool = True
    allow_sanitize: bool = True


OutputPolicyHook = Callable[[str], OutputPolicy | None]
LlmService = Callable[..., str]
ReloadHook = Callable[[], None]


@dataclass
class ServiceRegistry:
    """Holds runtime services registered by loaded packs."""

    output_policy_hooks: list[OutputPolicyHook] = field(default_factory=list)
    result_store_backend: ResultStoreBackend | None = None
    llm_service: LlmService | None = None
    reload_hooks: list[ReloadHook] = field(default_factory=list)

    def register_output_policy(self, hook: OutputPolicyHook) -> None:
        """Register an output-policy hook."""
        self.output_policy_hooks.append(hook)

    def output_policy_for(self, tool_name: str | None) -> OutputPolicy:
        """Return the first matching output policy, or the default policy."""
        if not tool_name:
            return OutputPolicy()
        for hook in reversed(self.output_policy_hooks):
            policy = hook(tool_name)
            if policy is not None:
                return policy
        return OutputPolicy()

    def register_result_store(self, backend: ResultStoreBackend) -> None:
        """Register the active large-output result store backend."""
        self.result_store_backend = backend

    def register_llm(self, service: LlmService) -> None:
        """Register the active LLM transform service."""
        self.llm_service = service

    def llm_transform(self, **kwargs: Any) -> str:
        """Transform text through the registered LLM service."""
        if self.llm_service is None:
            raise RuntimeError("No LLM service registered")
        return self.llm_service(**kwargs)

    def register_reload_hook(self, hook: ReloadHook) -> None:
        """Register a pack-owned runtime cache reload hook."""
        self.reload_hooks.append(hook)

    def run_reload_hooks(self) -> None:
        """Invoke registered reload hooks."""
        for hook in list(self.reload_hooks):
            hook()

    def reset(self) -> None:
        """Clear all registered runtime hooks."""
        self.output_policy_hooks.clear()
        self.result_store_backend = None
        self.llm_service = None
        self.reload_hooks.clear()


_registry = ServiceRegistry()


def get_services() -> ServiceRegistry:
    """Return the process-global service registry."""
    return _registry


def reset_services() -> None:
    """Reset the process-global service registry."""
    _registry.reset()
