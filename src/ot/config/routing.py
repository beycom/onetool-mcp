"""Typed configuration for model, harness, and provider routing."""

from __future__ import annotations

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
PermissionMode = Literal["normal", "bypass"]
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

_ROUTE_OWNED_FLAGS: dict[Harness, dict[str, str]] = {
    "claude": {
        "--model": "model",
        "--fallback-model": "model",
        "--permission-mode": "permission",
        "--dangerously-skip-permissions": "permission",
        "--allow-dangerously-skip-permissions": "permission",
    },
    "codex": {
        "--model": "model",
        "-m": "model",
        "--profile": "direct profile",
        "-p": "direct profile",
        "--oss": "provider route",
        "--config": "provider route",
        "-c": "provider route",
        "--dangerously-bypass-approvals-and-sandbox": "permission",
    },
}


def _validate_http_url(value: str, *, field_name: str) -> str:
    """Validate and normalize an HTTP endpoint without accepting credentials."""
    if any(ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F for character in value):
        raise ValueError(f"{field_name} must not contain control characters")
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
    for argument in arguments:
        flag = argument.split("=", 1)[0]
        owner = owned.get(flag)
        if owner is None:
            owner = next(
                (
                    short_owner
                    for short_flag, short_owner in owned.items()
                    if len(short_flag) == 2
                    and argument.startswith(short_flag)
                    and len(argument) > 2
                ),
                None,
            )
        if owner is not None:
            raise ValueError(
                f"{harness} argument {argument!r} conflicts with launcher-owned "
                f"{owner}; use the typed OneTool option instead"
            )


class StrictRoutingModel(BaseModel):
    """Base for public routing configuration that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ModelEntryConfig(StrictRoutingModel):
    """Generation-only metadata for one user-configured model identity."""

    shortcut: Identifier
    id: Identifier
    source: ModelSource
    proxy_alias: Identifier | None = None
    modalities: frozenset[ModelModality] = Field(default_factory=_default_modalities)
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


class ClaudeContextConfig(StrictRoutingModel):
    """Operational Claude context policy for one launcher model."""

    context: Literal["standard", "1m"]
    auto_compact_window: int | None = Field(default=None, gt=0, lt=1_000_000)

    @model_validator(mode="after")
    def validate_compaction_policy(self) -> ClaudeContextConfig:
        """Require auto-compaction to accompany one-million-token context."""
        if self.auto_compact_window is not None and self.context != "1m":
            raise ValueError("auto_compact_window requires context '1m'")
        return self


class CodeModelConfig(StrictRoutingModel):
    """One launcher model with exact selectable identities."""

    id: Identifier
    shortcut: Identifier | None = None
    label: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None
    claude: ClaudeContextConfig | None = None


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

    @field_validator("additional_arguments")
    @classmethod
    def validate_argument_tokens(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require explicit argument tokens rather than shell fragments."""
        if any("\x00" in argument for argument in value):
            raise ValueError("additional_arguments must not contain NUL bytes")
        return value


class ClaudeClientConfig(ExternalClientConfig):
    """Claude executable configuration."""

    executable: str = "claude"


class CodexClientConfig(ExternalClientConfig):
    """Codex executable configuration."""

    executable: str = "codex"
    home_path: str | None = None


class CodeClientsConfig(StrictRoutingModel):
    """Optional process-level harness overrides."""

    claude: ClaudeClientConfig = Field(default_factory=ClaudeClientConfig)
    codex: CodexClientConfig = Field(default_factory=CodexClientConfig)


class CodeProxyConfig(StrictRoutingModel):
    """Shared CLIProxyAPI connection and canonical launcher model routes."""

    base_url: str = "http://127.0.0.1:8317"
    secret_name: Identifier = "CLIPROXY_INFERENCE_KEY"
    connect_timeout: float = Field(default=2.0, gt=0, le=30)
    request_timeout: float = Field(default=5.0, gt=0, le=60)
    routes: dict[ModelSource, list[CodeModelConfig]] = Field(min_length=1)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """Validate the external inference endpoint."""
        return _validate_http_url(value, field_name="base_url")

    @model_validator(mode="after")
    def validate_routes(self) -> CodeProxyConfig:
        """Reject empty routes and duplicate ids within one route."""
        for route, models in self.routes.items():
            if not models:
                raise ValueError(f"code.proxy.routes.{route} must not be empty")
            seen: set[str] = set()
            duplicates: set[str] = set()
            for model in models:
                if model.id in seen:
                    duplicates.add(model.id)
                seen.add(model.id)
            if duplicates:
                raise ValueError(
                    f"code.proxy.routes.{route} contains duplicate model ids: "
                    f"{', '.join(sorted(duplicates))}"
                )
        return self


class DirectCodexConfig(StrictRoutingModel):
    """Named user-owned Codex profiles and their selectable models."""

    profiles: dict[Identifier, list[CodeModelConfig]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_profiles(self) -> DirectCodexConfig:
        """Reject empty profiles, duplicate ids, and unused Claude policy."""
        for profile, models in self.profiles.items():
            if not models:
                raise ValueError(
                    f"code.direct.codex.profiles.{profile} must not be empty"
                )
            seen: set[str] = set()
            duplicates: set[str] = set()
            for model in models:
                if model.claude is not None:
                    raise ValueError(
                        "Claude context policy is not valid in a direct Codex profile"
                    )
                if model.id in seen:
                    duplicates.add(model.id)
                seen.add(model.id)
            if duplicates:
                raise ValueError(
                    f"code.direct.codex.profiles.{profile} contains duplicate "
                    f"model ids: {', '.join(sorted(duplicates))}"
                )
        return self


class CodeDirectConfig(StrictRoutingModel):
    """Direct official-client targets that do not use CLIProxyAPI."""

    codex: DirectCodexConfig


class CodeDefaultConfig(StrictRoutingModel):
    """Optional default launcher model and exact target."""

    model: Identifier
    route: ModelSource | None = None
    profile: Identifier | None = None

    @model_validator(mode="after")
    def validate_target(self) -> CodeDefaultConfig:
        """A default cannot select proxy and direct targets simultaneously."""
        if self.route is not None and self.profile is not None:
            raise ValueError("default.route and default.profile are mutually exclusive")
        return self


class CodePresentationConfig(StrictRoutingModel):
    """Default launcher presentation settings."""

    quiet: bool = False
    verbose: bool = False


class CodeConfig(StrictRoutingModel):
    """Strict proxy/direct code-launcher configuration."""

    default: CodeDefaultConfig | None = None
    permission: PermissionMode = "normal"
    proxy: CodeProxyConfig | None = None
    direct: CodeDirectConfig | None = None
    clients: CodeClientsConfig = Field(default_factory=CodeClientsConfig)
    presentation: CodePresentationConfig = Field(default_factory=CodePresentationConfig)

    @model_validator(mode="after")
    def validate_default_and_arguments(self) -> CodeConfig:
        """Validate targets, identities, default, and opaque arguments."""
        targets: list[tuple[str, str, CodeModelConfig]] = []
        if self.proxy is not None:
            targets.extend(
                ("route", route, model)
                for route, models in self.proxy.routes.items()
                for model in models
            )
        if self.direct is not None:
            targets.extend(
                ("profile", profile, model)
                for profile, models in self.direct.codex.profiles.items()
                for model in models
            )
        if not targets:
            raise ValueError(
                "code requires at least one proxy route or direct Codex profile"
            )

        identities: dict[str, tuple[str, str, str]] = {}
        for kind, target, model in targets:
            if model.shortcut is None:
                continue
            previous = identities.get(model.shortcut)
            if previous is not None:
                raise ValueError(
                    f"launcher shortcut {model.shortcut!r} is ambiguous between "
                    f"{previous[0]} {previous[1]!r} and {kind} {target!r}"
                )
            identities[model.shortcut] = (kind, target, model.id)
        for _kind, _target, model in targets:
            previous = identities.get(model.id)
            if previous is not None and previous[2] != model.id:
                raise ValueError(
                    f"launcher identity {model.id!r} conflicts with shortcut under "
                    f"{previous[0]} {previous[1]!r}"
                )

        if self.default is not None:
            if self.default.route is not None:
                if self.proxy is None:
                    raise ValueError("default.route requires code.proxy")
                models = self.proxy.routes.get(self.default.route, [])
                if not any(model.id == self.default.model for model in models):
                    raise ValueError(
                        f"default model {self.default.model!r} is not configured "
                        f"under route {self.default.route!r}"
                    )
            elif self.default.profile is not None:
                if self.direct is None:
                    raise ValueError("default.profile requires code.direct.codex")
                models = self.direct.codex.profiles.get(self.default.profile, [])
                if not any(model.id == self.default.model for model in models):
                    raise ValueError(
                        f"default model {self.default.model!r} is not configured "
                        f"under profile {self.default.profile!r}"
                    )
            else:
                containing_targets = [
                    (kind, target)
                    for kind, target, model in targets
                    if model.id == self.default.model
                ]
                if not containing_targets:
                    raise ValueError(
                        f"default model {self.default.model!r} is not configured"
                    )
                if len(containing_targets) > 1:
                    raise ValueError(
                        f"default model {self.default.model!r} is configured under "
                        "multiple targets; set default.route or default.profile"
                    )

        validate_client_arguments(
            harness="claude",
            arguments=self.clients.claude.additional_arguments,
        )
        validate_client_arguments(
            harness="codex",
            arguments=self.clients.codex.additional_arguments,
        )
        return self


def validate_model_registry(*, models: dict[str, ModelEntryConfig]) -> None:
    """Validate generation-registry identities without launcher coupling."""
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


__all__ = [
    "CLIProxyGenerationConfig",
    "ClaudeClientConfig",
    "ClaudeContextConfig",
    "CodeClientsConfig",
    "CodeConfig",
    "CodeDefaultConfig",
    "CodeDirectConfig",
    "CodeModelConfig",
    "CodePresentationConfig",
    "CodeProxyConfig",
    "CodexClientConfig",
    "DirectCodexConfig",
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
    "validate_client_arguments",
    "validate_model_registry",
]
