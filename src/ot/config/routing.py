"""Typed configuration for model, harness, and provider routing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Harness = Literal["claude", "codex"]
ModelSource = Literal["claude_subscription", "codex_subscription", "openrouter"]
Transport = Literal["direct", "cliproxy"]
PermissionMode = Literal["safe", "bypass"]
ModelModality = Literal["text", "image"]
GenerationInterface = Literal["responses", "chat_completions"]
StructuredOutputMode = Literal["json_object", "json_schema"]
ReasoningEffort = Literal["low", "medium", "high"]

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]

_VERSION_SPECIFIER = re.compile(
    r"^(?:(?:~=|==|!=|<=|>=|<|>)\s*[0-9]+(?:\.[0-9]+)*(?:[A-Za-z0-9.*+-]*)?)"
    r"(?:\s*,\s*(?:~=|==|!=|<=|>=|<|>)\s*[0-9]+"
    r"(?:\.[0-9]+)*(?:[A-Za-z0-9.*+-]*)?)*$"
)

_ROUTE_OWNED_FLAGS: dict[Harness, dict[str, str]] = {
    "claude": {
        "--model": "model",
        "--settings": "settings_path",
        "--permission-mode": "permission",
        "--dangerously-skip-permissions": "permission",
        "--allow-dangerously-skip-permissions": "permission",
    },
    "codex": {
        "--model": "model",
        "-m": "model",
        "--profile": "profile",
        "-p": "profile",
        "--config": "provider route",
        "-c": "provider route",
        "--sandbox": "permission",
        "-s": "permission",
        "--ask-for-approval": "permission",
        "-a": "permission",
        "--dangerously-bypass-approvals-and-sandbox": "permission",
    },
}
_LAUNCH_MODE_SUBCOMMANDS: dict[Harness, frozenset[str]] = {
    "claude": frozenset(
        {"auth", "agents", "attach", "install", "logs", "mcp", "plugin", "update"}
    ),
    "codex": frozenset(
        {
            "app",
            "app-server",
            "apply",
            "archive",
            "cloud",
            "completion",
            "debug",
            "delete",
            "doctor",
            "exec",
            "exec-server",
            "features",
            "fork",
            "login",
            "logout",
            "mcp",
            "mcp-server",
            "plugin",
            "remote-control",
            "resume",
            "review",
            "sandbox",
            "unarchive",
            "update",
        }
    ),
}


def _validate_http_url(value: str, *, field_name: str) -> str:
    """Validate and normalize an HTTP endpoint without accepting credentials."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{field_name} must be an absolute http or https URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{field_name} must not contain a query or fragment")
    return value.rstrip("/")


def _default_modalities() -> frozenset[ModelModality]:
    """Return the default text-only model capability."""
    return frozenset({"text"})


def validate_client_arguments(
    *,
    harness: Harness,
    arguments: tuple[str, ...] | list[str],
) -> None:
    """Reject arguments that could override a validated launcher route."""
    owned = _ROUTE_OWNED_FLAGS[harness]
    for index, argument in enumerate(arguments):
        flag = argument.split("=", 1)[0]
        owner = owned.get(flag)
        if owner is not None:
            raise ValueError(
                f"{harness} argument {argument!r} conflicts with launcher-owned "
                f"{owner}; use the typed OneTool option instead"
            )
        if index == 0 and argument in _LAUNCH_MODE_SUBCOMMANDS[harness]:
            raise ValueError(
                f"{harness} launch-mode subcommand {argument!r} is not valid in "
                "launcher arguments"
            )


class StrictRoutingModel(BaseModel):
    """Base for public routing configuration that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ModelEntryConfig(StrictRoutingModel):
    """Metadata for one user-configured model identity."""

    shortcut: Identifier
    id: Identifier
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    source: ModelSource
    proxy_alias: Identifier | None = None
    context_window: int = Field(gt=0)
    modalities: frozenset[ModelModality] = Field(default_factory=_default_modalities)
    harnesses: frozenset[Harness] = Field(min_length=1)
    interfaces: frozenset[GenerationInterface] = Field(default_factory=frozenset)
    structured_outputs: dict[
        GenerationInterface, frozenset[StructuredOutputMode]
    ] = Field(default_factory=dict)
    efforts: frozenset[ReasoningEffort] = Field(default_factory=frozenset)
    default_effort: ReasoningEffort | None = None

    @model_validator(mode="after")
    def validate_generation_capabilities(self) -> ModelEntryConfig:
        """Keep generation metadata explicit and internally consistent."""
        undeclared = set(self.structured_outputs) - set(self.interfaces)
        if undeclared:
            raise ValueError(
                "structured_outputs declares unsupported interfaces: "
                f"{', '.join(sorted(undeclared))}"
            )
        if self.default_effort is not None and self.default_effort not in self.efforts:
            raise ValueError("default_effort must be listed in efforts")
        return self


class GenerationSettings(StrictRoutingModel):
    """Provider-neutral settings shared by complete generation backends."""

    model: Identifier
    interface: GenerationInterface
    effort: ReasoningEffort | None = None
    timeout: float = Field(default=30.0, gt=0, le=300)
    max_output_tokens: int | None = Field(default=None, gt=0, le=1_000_000)


class CLIProxyGenerationConfig(GenerationSettings):
    """Generation through the externally managed CLIProxyAPI endpoint."""

    backend: Literal["cliproxy"]


class OpenAICompatibleGenerationConfig(GenerationSettings):
    """Explicit direct OpenAI-compatible generation backend."""

    backend: Literal["openai_compatible"]
    base_url: str
    secret_name: Identifier

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """Validate the independent direct-generation endpoint."""
        return _validate_http_url(value, field_name="base_url")


type LlmConfig = Annotated[
    CLIProxyGenerationConfig | OpenAICompatibleGenerationConfig,
    Field(discriminator="backend"),
]


class PartialGenerationConfig(StrictRoutingModel):
    """Provider-neutral nested overrides that preserve the broader backend."""

    model: Identifier | None = None
    effort: ReasoningEffort | None = None
    timeout: float | None = Field(default=None, gt=0, le=300)
    max_output_tokens: int | None = Field(default=None, gt=0, le=1_000_000)


type GenerationSelection = (
    PartialGenerationConfig
    | CLIProxyGenerationConfig
    | OpenAICompatibleGenerationConfig
)


class EmbeddingsConfig(StrictRoutingModel):
    """Independent OpenAI-compatible embedding configuration."""

    backend: Literal["openai_compatible"]
    model: Identifier
    base_url: str
    secret_name: Identifier
    dimensions: int = Field(gt=0)
    timeout: float = Field(default=60.0, gt=0, le=300)
    batch_size: int = Field(default=200, gt=0, le=2048)
    max_tokens: int = Field(default=8191, gt=0)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """Validate the embedding-only endpoint."""
        return _validate_http_url(value, field_name="base_url")


class ExternalClientConfig(StrictRoutingModel):
    """Common configuration for an externally owned executable."""

    executable: str
    version: str | None = None
    working_directory: str | None = None
    additional_arguments: tuple[str, ...] = ()

    @field_validator("executable")
    @classmethod
    def validate_executable(cls, value: str) -> str:
        """Reject shell fragments and ambiguous relative executable paths."""
        if not value or value.strip() != value or "\x00" in value:
            raise ValueError("executable must be one command name or one absolute path")
        path = Path(value)
        if not path.is_absolute():
            if any(char.isspace() for char in value):
                raise ValueError(
                    "executable must be one command name or one absolute path"
                )
            if "/" in value or "\\" in value:
                raise ValueError(
                    "executable must be a PATH command name or an absolute path"
                )
        return value

    @field_validator("version")
    @classmethod
    def validate_version_specifier(cls, value: str | None) -> str | None:
        """Validate a bounded PEP 440-style version constraint."""
        if value is not None and not _VERSION_SPECIFIER.fullmatch(value.strip()):
            raise ValueError(
                "version must be a comparison such as '>=2.1.0' or a "
                "comma-separated constraint"
            )
        return value.strip() if value is not None else None

    @field_validator("additional_arguments")
    @classmethod
    def validate_argument_tokens(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require explicit argument tokens rather than shell fragments."""
        if any(not argument or "\x00" in argument for argument in value):
            raise ValueError("additional_arguments must contain non-empty tokens")
        return value


class CodexClientConfig(ExternalClientConfig):
    """Codex executable configuration."""

    home_path: str | None = None


class CLIProxyClientConfig(ExternalClientConfig):
    """CLIProxyAPI executable used only for delegated login/version commands."""

    config_path: str | None = None


class CodeClientsConfig(StrictRoutingModel):
    """External clients the launcher may execute."""

    claude: ExternalClientConfig | None = None
    codex: CodexClientConfig | None = None
    cliproxy: CLIProxyClientConfig | None = None


class CLIProxyConnectionConfig(StrictRoutingModel):
    """Inference-only connection to an externally managed CLIProxyAPI."""

    base_url: str
    secret_name: Identifier
    connect_timeout: float = Field(default=2.0, gt=0, le=30)
    request_timeout: float = Field(default=5.0, gt=0, le=60)
    model_cache_ttl: float = Field(default=30.0, gt=0, le=3600)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """Validate the external inference endpoint."""
        return _validate_http_url(value, field_name="base_url")


class ClaudeModelSlotsConfig(StrictRoutingModel):
    """Complete Claude Code 2.x proxy model-slot mapping."""

    opus: Identifier
    sonnet: Identifier
    haiku: Identifier


class CodeRouteConfig(StrictRoutingModel):
    """One explicit, verified harness/source/transport route."""

    harness: Harness
    source: ModelSource
    transport: Transport
    model: Identifier
    enabled: bool = True

    # Claude-only, user-owned settings.
    settings_path: str | None = None
    model_slots: ClaudeModelSlotsConfig | None = None

    # Codex-only, user-owned settings and verified provider capabilities.
    profile: Identifier | None = None
    model_catalog_path: str | None = None
    supports_websockets: bool | None = None
    provider_id: Identifier | None = None

    # Required only for direct custom Codex providers.
    base_url: str | None = None
    secret_name: Identifier | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        """Validate an optional direct-provider endpoint."""
        if value is None:
            return None
        return _validate_http_url(value, field_name="base_url")

    @model_validator(mode="after")
    def validate_adapter_fields(self) -> CodeRouteConfig:
        """Reject unsupported route combinations and cross-harness settings."""
        combination = (self.harness, self.source, self.transport)
        supported = {
            ("claude", "claude_subscription", "direct"),
            ("claude", "claude_subscription", "cliproxy"),
            ("claude", "codex_subscription", "cliproxy"),
            ("claude", "openrouter", "cliproxy"),
            ("codex", "codex_subscription", "direct"),
            ("codex", "codex_subscription", "cliproxy"),
            ("codex", "openrouter", "direct"),
        }
        if combination not in supported:
            raise ValueError(
                "unsupported harness/source/transport combination: "
                f"{self.harness}/{self.source}/{self.transport}"
            )

        if self.harness == "claude":
            if any(
                value is not None
                for value in (
                    self.profile,
                    self.model_catalog_path,
                    self.supports_websockets,
                    self.provider_id,
                    self.base_url,
                    self.secret_name,
                )
            ):
                raise ValueError("Codex adapter fields are not valid on Claude routes")
        elif self.settings_path is not None or self.model_slots is not None:
            raise ValueError("Claude adapter fields are not valid on Codex routes")

        direct_custom = combination == ("codex", "openrouter", "direct")
        if direct_custom and (self.base_url is None or self.secret_name is None):
            raise ValueError(
                "direct Codex OpenRouter routes require base_url and secret_name"
            )
        if not direct_custom and (
            self.base_url is not None or self.secret_name is not None
        ):
            raise ValueError(
                "base_url and secret_name are valid only for direct Codex "
                "OpenRouter routes"
            )
        if self.transport == "direct" and self.model_slots is not None:
            raise ValueError("model_slots are valid only for proxied Claude routes")
        return self


class CodeDefaultsConfig(StrictRoutingModel):
    """Default route and permission choices."""

    claude_route: Identifier | None = None
    codex_route: Identifier | None = None
    permission: PermissionMode = "safe"


class CodePresentationConfig(StrictRoutingModel):
    """Default launcher presentation settings."""

    quiet: bool = False
    verbose: bool = False


class CodeConfig(StrictRoutingModel):
    """Strict launcher configuration."""

    clients: CodeClientsConfig = Field(default_factory=CodeClientsConfig)
    routes: dict[Identifier, CodeRouteConfig] = Field(default_factory=dict)
    defaults: CodeDefaultsConfig = Field(default_factory=CodeDefaultsConfig)
    cliproxy: CLIProxyConnectionConfig | None = None
    presentation: CodePresentationConfig = Field(default_factory=CodePresentationConfig)
    claude_subscription_proxy_enabled: bool = False

    @model_validator(mode="after")
    def validate_connection_and_defaults(self) -> CodeConfig:
        """Require proxy connection data and valid per-harness defaults."""
        if (
            any(route.transport == "cliproxy" for route in self.routes.values())
            and self.cliproxy is None
        ):
            raise ValueError("code.cliproxy is required when any route uses cliproxy")

        for harness, route_name in (
            ("claude", self.defaults.claude_route),
            ("codex", self.defaults.codex_route),
        ):
            if route_name is None:
                continue
            route = self.routes.get(route_name)
            if route is None:
                raise ValueError(
                    f"default {harness}_route {route_name!r} does not exist"
                )
            if route.harness != harness or not route.enabled:
                raise ValueError(
                    f"default {harness}_route must reference an enabled {harness} route"
                )

        for name, route in self.routes.items():
            if (
                route.harness == "claude"
                and route.source == "claude_subscription"
                and route.transport == "cliproxy"
                and route.enabled
                and not self.claude_subscription_proxy_enabled
            ):
                raise ValueError(
                    f"route {name!r} requires "
                    "code.claude_subscription_proxy_enabled: true"
                )

        if self.clients.claude is not None:
            validate_client_arguments(
                harness="claude",
                arguments=self.clients.claude.additional_arguments,
            )
        if self.clients.codex is not None:
            validate_client_arguments(
                harness="codex",
                arguments=self.clients.codex.additional_arguments,
            )
        return self


def validate_code_registry(
    *,
    models: dict[str, ModelEntryConfig],
    code: CodeConfig | None,
) -> None:
    """Validate cross-references between the shared model registry and routes."""
    identities: dict[str, str] = {}
    for key, model in models.items():
        if key != model.shortcut:
            raise ValueError(
                f"models.{key}.shortcut must match its mapping key ({key!r})"
            )
        for identity in (model.shortcut, model.id, model.proxy_alias):
            if identity is None:
                continue
            previous = identities.get(identity)
            if previous is not None and previous != key:
                raise ValueError(
                    f"model identity {identity!r} is ambiguous between "
                    f"{previous!r} and {key!r}"
                )
            identities[identity] = key

    if code is None:
        return

    for route_name, route in code.routes.items():
        model_key = identities.get(route.model)
        if model_key is None:
            raise ValueError(
                f"code.routes.{route_name}.model references unknown model "
                f"{route.model!r}"
            )
        model = models[model_key]
        if model.source != route.source:
            raise ValueError(
                f"code.routes.{route_name}.source {route.source!r} does not match "
                f"model source {model.source!r}"
            )
        if route.harness not in model.harnesses:
            raise ValueError(
                f"model {model.shortcut!r} is not verified for {route.harness}"
            )
        if route.transport == "cliproxy" and not (model.proxy_alias or model.id):
            raise ValueError(
                f"proxied route {route_name!r} has no discoverable model identity"
            )
        if route.model_slots is not None:
            for slot_name, alias in (
                ("opus", route.model_slots.opus),
                ("sonnet", route.model_slots.sonnet),
                ("haiku", route.model_slots.haiku),
            ):
                if alias not in identities:
                    raise ValueError(
                        f"code.routes.{route_name}.model_slots.{slot_name} "
                        f"references unknown model identity {alias!r}"
                    )


__all__ = [
    "CLIProxyClientConfig",
    "CLIProxyConnectionConfig",
    "CLIProxyGenerationConfig",
    "CodeClientsConfig",
    "CodeConfig",
    "CodeDefaultsConfig",
    "CodePresentationConfig",
    "CodeRouteConfig",
    "CodexClientConfig",
    "EmbeddingsConfig",
    "ExternalClientConfig",
    "GenerationInterface",
    "GenerationSelection",
    "Harness",
    "LlmConfig",
    "ModelEntryConfig",
    "ModelModality",
    "ModelSource",
    "OpenAICompatibleGenerationConfig",
    "PartialGenerationConfig",
    "PermissionMode",
    "ReasoningEffort",
    "StrictRoutingModel",
    "StructuredOutputMode",
    "Transport",
    "validate_client_arguments",
    "validate_code_registry",
]
