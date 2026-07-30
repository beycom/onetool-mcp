"""Small typed routing fixtures for focused tests."""

from __future__ import annotations

from typing import Any


def generation_config() -> dict[str, Any]:
    """Return a generation registry with its required proxy connection."""
    return {
        "version": 2,
        "models": {
            "sol": {
                "shortcut": "sol",
                "id": "gpt-5.6-sol",
                "source": "codex_subscription",
                "proxy_alias": "sol-wire",
                "modalities": ["text"],
                "interfaces": ["responses"],
                "structured_outputs": {
                    "responses": ["json_object", "json_schema"],
                },
                "efforts": ["low", "medium", "high"],
                "default_effort": "low",
            },
            "terra": {
                "shortcut": "terra",
                "id": "gpt-5.6-terra",
                "source": "codex_subscription",
                "modalities": ["text", "image"],
                "interfaces": ["responses", "chat_completions"],
                "structured_outputs": {
                    "responses": ["json_object"],
                    "chat_completions": ["json_object"],
                },
                "efforts": ["medium", "high"],
                "default_effort": "medium",
            },
        },
        "llm": {
            "backend": "cliproxy",
            "interface": "responses",
            "model": "sol",
            "timeout": 30,
            "max_output_tokens": 4096,
        },
        "code": {
            "proxy": {
                "routes": {
                    "codex_subscription": [{"id": "gpt-5.6-sol"}],
                }
            }
        },
    }


def proxy_launcher_config() -> dict[str, Any]:
    """Return a minimal launcher with exact proxy models and Claude policy."""
    return {
        "version": 2,
        "code": {
            "default": {
                "model": "gpt-5.6-sol",
                "route": "codex_subscription",
            },
            "proxy": {
                "base_url": "http://127.0.0.1:8317",
                "secret_name": "CLIPROXY_INFERENCE_KEY",
                "routes": {
                    "codex_subscription": [
                        {
                            "id": "gpt-5.6-sol",
                            "shortcut": "sol",
                            "label": "GPT-5.6 Sol",
                        }
                    ],
                    "openrouter": [
                        {
                            "id": "z-ai/glm-5.2",
                            "shortcut": "glm",
                            "claude": {
                                "context": "1m",
                                "auto_compact_window": 900_000,
                            },
                        }
                    ],
                    "claude_subscription": [
                        {
                            "id": "claude-sonnet-4-6",
                            "shortcut": "sonnet",
                            "claude": {"context": "standard"},
                        }
                    ],
                },
            },
        },
    }


def direct_codex_config() -> dict[str, Any]:
    """Return a minimal direct-only Codex profile configuration."""
    return {
        "version": 2,
        "code": {
            "default": {"model": "z-ai/glm-5.2", "profile": "openrouter"},
            "direct": {
                "codex": {
                    "profiles": {
                        "openrouter": [
                            {"id": "z-ai/glm-5.2", "shortcut": "glm"},
                        ]
                    }
                }
            },
        },
    }
