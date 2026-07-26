"""Tests for strict generation/embedding config and bounded HTTP routing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import call, patch

import httpx
import pytest
import yaml
from pydantic import ValidationError

from ot.config import OneToolConfig
from ot.config.loader import load_config
from ot.config.routing import (
    OpenAICompatibleGenerationConfig,
    PartialGenerationConfig,
)
from ot.generation import (
    GenerationError,
    GenerationRequest,
    check_generation_readiness,
    generate,
)
from ot.generation.resolver import resolve_generation
from tests.unit.core.routing_fixtures import valid_routing_config

pytestmark = [pytest.mark.unit, pytest.mark.core]

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "llm_routing"
_CODE_TEMPLATE = (
    Path(__file__).parents[3]
    / "src"
    / "ot"
    / "config"
    / "global_templates"
    / "code-routing.yaml"
)


def _config() -> OneToolConfig:
    return OneToolConfig.model_validate(valid_routing_config())


def test_generation_and_embeddings_are_strict_and_independent(tmp_path: Path) -> None:
    """Removed and backend-specific keys fail through nested strict validation."""
    for section, key, value in (
        ("llm", "embedding_model", "text-embedding-3-small"),
        ("llm", "base_url", "https://api.openai.com/v1"),
        ("embeddings", "interface", "responses"),
        ("embeddings", "backend", "cliproxy"),
    ):
        data = valid_routing_config()
        data[section][key] = value
        path = tmp_path / f"{section}-{key}.yaml"
        path.write_text(yaml.safe_dump(data))
        with pytest.raises(ValueError):
            load_config(path)


def test_removed_pack_provider_fields_use_normal_strict_validation() -> None:
    """Superseded mem, knowledge, image, and transform fields have no aliases."""
    from ottools._image.config import Config as ImageConfig
    from ottools.ot_llm import Config as TransformConfig
    from otutil.tools._knowledge.config import Config as KnowledgeConfig
    from otutil.tools._mem.config import Config as MemConfig

    for config_type, key in (
        (MemConfig, "model"),
        (MemConfig, "dimensions"),
        (KnowledgeConfig, "base_url"),
        (KnowledgeConfig, "enrich_model"),
        (ImageConfig, "base_url"),
        (TransformConfig, "max_tokens"),
    ):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            config_type.model_validate({key: "removed"})


def test_complete_backend_switch_and_explicit_interface_are_required() -> None:
    """Partial selectors cannot masquerade as incomplete backend switches."""
    with pytest.raises(ValidationError):
        OpenAICompatibleGenerationConfig.model_validate(
            {
                "backend": "openai_compatible",
                "model": "glm52",
                "interface": "chat_completions",
            }
        )

    data = valid_routing_config()
    data["llm"]["interface"] = "chat_completions"
    config = OneToolConfig.model_validate(data)
    with pytest.raises(GenerationError, match="requires interface 'responses'"):
        resolve_generation(config=config)


def test_omitted_subscription_route_is_not_inferred_from_model_source() -> None:
    """A Codex-subscription model alone never enables proxy generation."""
    data = valid_routing_config()
    data.pop("llm")
    config = OneToolConfig.model_validate(data)

    with pytest.raises(GenerationError, match="No generation route"):
        resolve_generation(config=config, model="sol")


def test_model_generation_metadata_is_internally_consistent() -> None:
    """Structured modes and default effort cannot imply undeclared support."""
    data = valid_routing_config()
    data["models"]["sol"]["interfaces"] = []
    with pytest.raises(ValidationError, match="unsupported interfaces"):
        OneToolConfig.model_validate(data)


def test_subscription_template_matches_recorded_capabilities() -> None:
    """Initial model ids, aliases, capabilities, and efficient default are recorded."""
    fixture = yaml.safe_load(
        (_FIXTURES / "cliproxyapi-7.2.95.yaml").read_text(encoding="utf-8")
    )
    template = yaml.safe_load(_CODE_TEMPLATE.read_text(encoding="utf-8"))

    for shortcut in ("sol", "luna", "terra"):
        configured = template["models"][shortcut]
        recorded = fixture["models"][configured["id"]]
        assert configured["proxy_alias"] == recorded["proxy_alias"]
        assert configured["modalities"] == recorded["modalities"]
        assert configured["interfaces"] == recorded["interfaces"]
        assert configured["structured_outputs"] == recorded["structured_outputs"]
        assert configured["efforts"] == recorded["efforts"]
        assert configured["default_effort"] == recorded["default_effort"]
    assert template["llm"]["model"] == "luna"
    assert template["llm"]["effort"] == "low"

    data = valid_routing_config()
    data["models"]["sol"]["default_effort"] = "high"
    data["models"]["sol"]["efforts"] = ["low"]
    with pytest.raises(ValidationError, match="default_effort"):
        OneToolConfig.model_validate(data)


def test_selection_precedence_and_atomic_backend_switch() -> None:
    """Call values override layers while a complete narrower backend is atomic."""
    config = _config()
    pack = OpenAICompatibleGenerationConfig(
        backend="openai_compatible",
        interface="chat_completions",
        model="glm52",
        base_url="https://openrouter.ai/api/v1",
        secret_name="OPENROUTER_API_KEY",
        effort="medium",
        timeout=12,
    )
    operation = PartialGenerationConfig(model="terra", effort="high")
    route = resolve_generation(
        config=config,
        pack=pack,
        operation=operation,
        model="glm52",
        effort="low",
    )

    assert route.backend == "openai_compatible"
    assert route.base_url == "https://openrouter.ai/api/v1"
    assert route.secret_name == "OPENROUTER_API_KEY"
    assert route.model_id == "z-ai/glm-5.2"
    assert route.effort == "low"
    assert route.timeout == 12


def test_model_default_effort_is_last_in_precedence() -> None:
    """The selected model default applies only when every route layer omits effort."""
    route = resolve_generation(config=_config())

    assert route.effort == "low"


def test_explicit_empty_model_does_not_fall_through_to_configured_default() -> None:
    """A supplied empty model fails instead of silently selecting another model."""
    with pytest.raises(GenerationError, match="required"):
        resolve_generation(config=_config(), model="")


@pytest.mark.parametrize(
    ("model", "effort", "modalities", "structured", "message"),
    [
        ("missing", None, frozenset({"text"}), None, "unknown"),
        ("sol", "high", frozenset({"image"}), None, "modalities"),
        ("sol", None, frozenset({"text"}), "json_schema", "json_schema"),
    ],
)
def test_capabilities_fail_before_network(
    model: str,
    effort: str | None,
    modalities: frozenset[str],
    structured: str | None,
    message: str,
) -> None:
    """Unknown or unsupported operation requirements fail during resolution."""
    config = _config()
    if structured == "json_schema":
        data = valid_routing_config()
        data["models"]["sol"]["structured_outputs"]["responses"] = ["json_object"]
        config = OneToolConfig.model_validate(data)

    with pytest.raises(GenerationError, match=message):
        resolve_generation(
            config=config,
            model=model,
            effort=effort,  # type: ignore[arg-type]
            required_modalities=modalities,
            structured_output=structured,  # type: ignore[arg-type]
        )


def test_cliproxy_responses_request_and_normalization() -> None:
    """Subscription generation uses discovery then exact Responses HTTP shape."""
    data = valid_routing_config()
    data["models"]["sol"]["proxy_alias"] = "gpt-5.6-sol"
    config = OneToolConfig.model_validate(data)
    route = resolve_generation(config=config, effort="high")
    fixture = yaml.safe_load(
        (_FIXTURES / "cliproxyapi-7.2.95.yaml").read_text(encoding="utf-8")
    )
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json=fixture["model_discovery"]["response"])
        observed["path"] = request.url.path
        observed["auth"] = request.headers["Authorization"]
        observed["body"] = json.loads(request.content)
        return httpx.Response(200, json=fixture["response"])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with patch("subprocess.Popen") as popen:
        result = generate(
            route=route,
            request=GenerationRequest(system="system", prompt="prompt"),
            secret_resolver=lambda name: "proxy-key" if name else None,
            client=client,
            proxy_config=config.code.cliproxy if config.code else None,
        )
    popen.assert_not_called()

    assert fixture["release"]["version"] == "7.2.95"
    assert observed["path"] == fixture["interface"]["path"]
    assert observed["auth"] == "Bearer proxy-key"
    expected = fixture["request"]
    expected["input"][0]["content"][0]["text"] = "prompt"
    expected["instructions"] = "system"
    assert observed["body"] == expected
    assert result.content == fixture["response"]["output"][0]["content"][0]["text"]
    assert result.usage.total_tokens == 14


def test_direct_chat_route_uses_only_its_endpoint_and_secret() -> None:
    """A direct backend does not discover or inherit the proxy connection."""
    data = valid_routing_config()
    data["llm"] = {
        "backend": "openai_compatible",
        "interface": "chat_completions",
        "model": "glm52",
        "base_url": "https://openrouter.ai/api/v1",
        "secret_name": "DIRECT_KEY",
    }
    config = OneToolConfig.model_validate(data)
    route = resolve_generation(config=config)
    fixture = yaml.safe_load(
        (_FIXTURES / "openai-compatible-chat.yaml").read_text(encoding="utf-8")
    )
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer direct-key"
        return httpx.Response(200, json=fixture["response"])

    with patch("ot.generation.client.logger.info") as logged:
        result = generate(
            route=route,
            request=GenerationRequest(prompt="private prompt"),
            secret_resolver=lambda _name: "direct-key",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    assert paths == [fixture["interface"]["path"]]
    assert result.content == fixture["response"]["choices"][0]["message"]["content"]
    fields = logged.call_args.args[0].fields
    assert fields["backend"] == "openai_compatible"
    assert fields["inputTokens"] == 2
    assert "private prompt" not in str(fields)
    assert "direct-key" not in str(fields)
    assert route.base_url not in str(fields)


def test_responses_route_rejects_payload_without_text() -> None:
    """A syntactically valid response without text is not a successful result."""
    config = _config()
    route = resolve_generation(config=config)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": route.proxy_identity}]})
        return httpx.Response(200, json={"output": [{"type": "reasoning"}]})

    with pytest.raises(GenerationError, match="no text content"):
        generate(
            route=route,
            request=GenerationRequest(prompt="prompt"),
            secret_resolver=lambda _name: "proxy-key",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            proxy_config=config.code.cliproxy if config.code else None,
        )


def test_readiness_resolves_full_model_id_without_lifecycle_mutation() -> None:
    """Startup readiness performs discovery only and supports every model identity."""
    data = valid_routing_config()
    data["llm"]["model"] = "gpt-5.6-sol"
    config = OneToolConfig.model_validate(data)

    with (
        patch("ot.generation.readiness.get_secret", return_value="proxy-key"),
        patch("ot.generation.readiness.ModelDiscovery") as discovery,
        patch("subprocess.Popen") as popen,
    ):
        state = check_generation_readiness(config)

    assert state.available is True
    discovery.return_value.validate.assert_called_once_with("sol", "gpt-5.6-sol")
    popen.assert_not_called()


def test_readiness_finds_pack_and_operation_proxy_routes() -> None:
    """Complete nested backend switches trigger readiness independently of root."""
    data = valid_routing_config()
    data["llm"] = {
        "backend": "openai_compatible",
        "interface": "chat_completions",
        "model": "glm52",
        "base_url": "https://openrouter.ai/api/v1",
        "secret_name": "DIRECT_KEY",
    }
    data["tools"] = {
        "ot_llm": {
            "llm": {
                "backend": "cliproxy",
                "interface": "responses",
                "model": "sol",
            }
        },
        "knowledge": {
            "enrich": {
                "llm": {
                    "backend": "cliproxy",
                    "interface": "responses",
                    "model": "terra",
                }
            }
        },
    }
    config = OneToolConfig.model_validate(data)

    with (
        patch("ot.generation.readiness.get_secret", return_value="proxy-key"),
        patch("ot.generation.readiness.ModelDiscovery") as discovery,
    ):
        state = check_generation_readiness(config)

    assert state.available is True
    assert discovery.return_value.validate.call_args_list == [
        call("sol", "gpt-5.6-sol"),
        call("terra", "gpt-5.6-terra"),
    ]


def test_request_body_is_bounded_before_network() -> None:
    """Oversize encoded image inputs fail before the HTTP adapter is called."""
    data = valid_routing_config()
    data["llm"] = {
        "backend": "openai_compatible",
        "interface": "chat_completions",
        "model": "terra",
        "base_url": "https://api.openai.com/v1",
        "secret_name": "DIRECT_KEY",
    }
    route = resolve_generation(
        config=OneToolConfig.model_validate(data),
        required_modalities=frozenset({"text", "image"}),
    )
    transport = httpx.MockTransport(
        lambda _request: pytest.fail("oversize request reached the network")
    )

    with pytest.raises(GenerationError, match="16 MiB"):
        generate(
            route=route,
            request=GenerationRequest(
                prompt="private prompt",
                images=(b"x" * (13 * 1_048_576),),
            ),
            secret_resolver=lambda _name: "direct-key",
            client=httpx.Client(transport=transport),
        )


def test_response_limit_and_errors_do_not_expose_bodies_or_secrets() -> None:
    """Bodies are bounded during streaming and upstream errors stay redacted."""
    data = valid_routing_config()
    data["llm"] = {
        "backend": "openai_compatible",
        "interface": "chat_completions",
        "model": "glm52",
        "base_url": "https://openrouter.ai/api/v1",
        "secret_name": "DIRECT_KEY",
    }
    route = resolve_generation(config=OneToolConfig.model_validate(data))
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                401,
                text="secret response body " + "x" * 100,
            )
        )
    )
    with pytest.raises(GenerationError, match="HTTP 401") as raised:
        generate(
            route=route,
            request=GenerationRequest(prompt="private prompt"),
            secret_resolver=lambda _name: "never-show-this",
            client=client,
        )
    text = str(raised.value)
    assert raised.value.status_code == 401
    assert "never-show-this" not in text
    assert "secret response body" not in text
    assert "private prompt" not in text


def test_proxy_failure_has_no_paid_or_transport_fallback() -> None:
    """One failed subscription request ends without another model or endpoint."""
    config = _config()
    route = resolve_generation(config=config)
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "sol"}]})
        return httpx.Response(503, text="upstream private error")

    with pytest.raises(GenerationError, match="HTTP 503"):
        generate(
            route=route,
            request=GenerationRequest(prompt="private prompt"),
            secret_resolver=lambda _name: "proxy-key",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            proxy_config=config.code.cliproxy if config.code else None,
        )

    assert paths == ["/v1/models", "/v1/responses"]
