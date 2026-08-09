"""Strict configuration values for generation and embeddings."""

from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

ReasoningEffort = Literal["low", "medium", "high"]
StructuredOutputMode = Literal["json_object", "json_schema"]
GenerationBackend = Literal["openai_compatible", "cliproxy"]
GenerationInterface = Literal["chat_completions", "responses"]

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]


def _validate_direct_model_id(value: str) -> str:
    """Reject empty or control-bearing IDs without changing accepted values."""
    if not value.strip():
        raise ValueError("model must not be empty")
    if any(
        ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F for character in value
    ):
        raise ValueError("model must not contain control characters")
    return value


DirectModelId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512),
    AfterValidator(_validate_direct_model_id),
]


def _validate_http_url(value: str, *, field_name: str) -> str:
    """Validate and normalize an HTTP endpoint without accepting credentials."""
    if any(
        ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F for character in value
    ):
        raise ValueError(f"{field_name} must not contain control characters")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{field_name} must be an absolute http or https URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{field_name} must not contain a query or fragment")
    return value.rstrip("/")


class StrictRoutingModel(BaseModel):
    """Base for public connection configuration that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class LlmConfig(StrictRoutingModel):
    """Lean backend-aware connection for shared MCP generation."""

    backend: GenerationBackend = "openai_compatible"
    interface: GenerationInterface = "chat_completions"
    base_url: str = "https://api.openai.com/v1"
    model: DirectModelId = "gpt-5.4-nano"
    secret_name: Identifier = "OPENAI_API_KEY"
    effort: ReasoningEffort | None = None
    timeout: float = Field(default=30.0, gt=0, le=300)
    max_tokens: int | None = Field(default=4096, gt=0, le=1_000_000)

    @model_validator(mode="before")
    @classmethod
    def apply_backend_defaults(cls, value: object) -> object:
        """Apply backend defaults and reject configurable CLIProxy routing."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if data.get("backend", "openai_compatible") != "cliproxy":
            return data

        forbidden = sorted(
            field
            for field in ("interface", "secret_name")
            if field in data
        )
        if forbidden:
            fields = ", ".join(forbidden)
            raise ValueError(f"cliproxy does not accept configurable fields: {fields}")
        data.setdefault("interface", "responses")
        data.setdefault("base_url", "http://127.0.0.1:8317/v1")
        data.setdefault("secret_name", "CLIPROXY_INFERENCE_KEY")
        return data

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """Require a normalized HTTP API base URL."""
        return _validate_http_url(value, field_name="base_url")


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


__all__ = [
    "DirectModelId",
    "EmbeddingsConfig",
    "GenerationBackend",
    "GenerationInterface",
    "Identifier",
    "LlmConfig",
    "ReasoningEffort",
    "StrictRoutingModel",
    "StructuredOutputMode",
]
