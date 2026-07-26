"""Shared typed routing fixtures."""

from __future__ import annotations

from typing import Any


def _model(
    shortcut: str,
    model_id: str,
    source: str,
    *,
    harnesses: list[str],
    proxy_alias: str | None = None,
    modalities: list[str] | None = None,
) -> dict[str, Any]:
    """Build one model fixture."""
    result: dict[str, Any] = {
        "shortcut": shortcut,
        "id": model_id,
        "label": shortcut.title(),
        "source": source,
        "context_window": 1_000_000,
        "modalities": modalities or ["text"],
        "harnesses": harnesses,
        "interfaces": ["responses", "chat_completions"],
        "structured_outputs": {
            "responses": ["json_object", "json_schema"],
            "chat_completions": ["json_object", "json_schema"],
        },
        "efforts": ["low", "medium", "high"],
        "default_effort": "low",
    }
    if proxy_alias is not None:
        result["proxy_alias"] = proxy_alias
    return result


def valid_routing_config() -> dict[str, Any]:
    """Return a complete direct/proxy launcher fixture."""
    return {
        "version": 2,
        "models": {
            "sonnet": _model(
                "sonnet",
                "claude-sonnet-4-6",
                "claude_subscription",
                harnesses=["claude"],
            ),
            "sol": _model(
                "sol",
                "gpt-5.6-sol",
                "codex_subscription",
                harnesses=["claude", "codex"],
                proxy_alias="sol",
            ),
            "glm52": _model(
                "glm52",
                "z-ai/glm-5.2",
                "openrouter",
                harnesses=["claude", "codex"],
                proxy_alias="glm52",
            ),
            "terra": _model(
                "terra",
                "gpt-5.6-terra",
                "codex_subscription",
                harnesses=["claude", "codex"],
                proxy_alias="terra",
                modalities=["text", "image"],
            ),
        },
        "llm": {
            "backend": "cliproxy",
            "interface": "responses",
            "model": "sol",
            "timeout": 30,
            "max_output_tokens": 4096,
        },
        "embeddings": {
            "backend": "openai_compatible",
            "model": "text-embedding-3-small",
            "base_url": "https://api.openai.com/v1",
            "secret_name": "OPENAI_API_KEY",
            "dimensions": 1536,
            "timeout": 60,
            "batch_size": 200,
            "max_tokens": 8191,
        },
        "code": {
            "clients": {
                "claude": {
                    "executable": "claude",
                    "version": ">=2.1.0",
                    "additional_arguments": ["--no-chrome"],
                },
                "codex": {
                    "executable": "/opt/homebrew/bin/codex",
                    "version": ">=0.145.0",
                    "home_path": "/tmp/codex-home",
                    "additional_arguments": ["--search"],
                },
                "cliproxy": {
                    "executable": "cliproxyapi",
                    "config_path": "/opt/homebrew/etc/cliproxyapi.conf",
                },
            },
            "cliproxy": {
                "base_url": "http://127.0.0.1:8317",
                "secret_name": "CLIPROXY_INFERENCE_KEY",
                "connect_timeout": 2,
                "request_timeout": 5,
                "model_cache_ttl": 30,
            },
            "routes": {
                "claude-native": {
                    "harness": "claude",
                    "source": "claude_subscription",
                    "transport": "direct",
                    "model": "sonnet",
                },
                "claude-sol": {
                    "harness": "claude",
                    "source": "codex_subscription",
                    "transport": "cliproxy",
                    "model": "sol",
                    "settings_path": "/tmp/claude-settings.json",
                    "model_slots": {
                        "opus": "sol",
                        "sonnet": "sol",
                        "haiku": "sol",
                    },
                },
                "codex-native": {
                    "harness": "codex",
                    "source": "codex_subscription",
                    "transport": "direct",
                    "model": "sol",
                },
                "codex-proxy": {
                    "harness": "codex",
                    "source": "codex_subscription",
                    "transport": "cliproxy",
                    "model": "sol",
                    "provider_id": "onetool_proxy",
                },
                "codex-openrouter": {
                    "harness": "codex",
                    "source": "openrouter",
                    "transport": "direct",
                    "model": "glm52",
                    "base_url": "https://openrouter.ai/api/v1",
                    "secret_name": "OPENROUTER_API_KEY",
                    "provider_id": "onetool_openrouter",
                    "profile": "openrouter",
                    "model_catalog_path": "/tmp/openrouter-models.json",
                    "supports_websockets": False,
                },
            },
            "defaults": {
                "claude_route": "claude-native",
                "codex_route": "codex-native",
                "permission": "safe",
            },
        },
    }
