"""Tests for the lean strict generation configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ot.config import OneToolConfig
from tests.unit.core.routing_fixtures import generation_config

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_default_generation_connection_matches_main() -> None:
    config = OneToolConfig.model_validate({"version": 2})

    assert config.llm.backend == "openai_compatible"
    assert config.llm.interface == "chat_completions"
    assert config.llm.base_url == "https://api.openai.com/v1"
    assert config.llm.model == "gpt-5.4-nano"
    assert config.llm.secret_name == "OPENAI_API_KEY"
    assert config.llm.max_tokens == 4096
    assert config.embeddings is None


def test_exact_main_generation_configuration_remains_valid() -> None:
    config = OneToolConfig.model_validate(
        {
            "version": 2,
            "llm": {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-5.4-nano",
            },
        }
    )

    assert config.llm.backend == "openai_compatible"
    assert config.llm.interface == "chat_completions"
    assert config.llm.secret_name == "OPENAI_API_KEY"


def test_explicit_cliproxy_uses_fixed_responses_connection() -> None:
    config = OneToolConfig.model_validate(generation_config())

    assert config.llm.backend == "cliproxy"
    assert config.llm.interface == "responses"
    assert config.llm.secret_name == "CLIPROXY_INFERENCE_KEY"
    assert config.embeddings is None


def test_direct_model_id_is_preserved_without_legacy_identifier_grammar() -> None:
    model = "vendor/model+preview@2026"
    config = OneToolConfig.model_validate({"version": 2, "llm": {"model": model}})

    assert config.llm.model == model


@pytest.mark.parametrize("model", ["", "   ", "model\nnext"])
def test_direct_model_id_must_be_nonempty_and_control_safe(model: str) -> None:
    with pytest.raises(ValidationError):
        OneToolConfig.model_validate({"version": 2, "llm": {"model": model}})


@pytest.mark.parametrize(
    "invalid",
    [
        {"models": {}},
        {"code": {}},
        {"llm": {"unknown": True}},
        {"llm": {"max_output_tokens": 4096}},
        {"llm": {"embedding_model": "text-embedding-3-small"}},
    ],
)
def test_removed_or_unknown_routing_fields_fail_strict_validation(
    invalid: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        OneToolConfig.model_validate({"version": 2, **invalid})


@pytest.mark.parametrize("field", ["interface", "secret_name"])
def test_cliproxy_rejects_configurable_connection_fields(field: str) -> None:
    value = {
        "interface": "responses",
        "secret_name": "OTHER_KEY",
    }[field]
    with pytest.raises(ValidationError, match="cliproxy does not accept"):
        OneToolConfig.model_validate(
            {"version": 2, "llm": {"backend": "cliproxy", field: value}}
        )


@pytest.mark.parametrize("effort", ["med", "xhigh", "max"])
def test_noncanonical_effort_is_rejected(effort: str) -> None:
    data = generation_config()
    data["llm"]["effort"] = effort
    with pytest.raises(ValidationError):
        OneToolConfig.model_validate(data)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://user:password@proxy.test/v1",
        "http://proxy.test/v1?key=secret",
        "http://proxy.test/v1\nnext",
    ],
)
def test_generation_base_url_is_safe(base_url: str) -> None:
    data = generation_config()
    data["llm"]["base_url"] = base_url
    with pytest.raises(ValidationError):
        OneToolConfig.model_validate(data)


def test_embeddings_remain_independent() -> None:
    data = generation_config()
    data["embeddings"] = {
        "backend": "openai_compatible",
        "model": "text-embedding-3-small",
        "base_url": "https://api.openai.com/v1",
        "secret_name": "OPENAI_API_KEY",
        "dimensions": 1536,
    }
    config = OneToolConfig.model_validate(data)

    assert config.embeddings is not None
    assert config.embeddings.secret_name == "OPENAI_API_KEY"
