"""Shared fixtures for integration tests.

Reloads secrets from project root for API key access.
"""

from __future__ import annotations

from ot.config.secrets import get_secret, get_secrets

# Force reload to pick up secrets.yaml from project root
get_secrets(reload=True)

# Re-export get_secret for use by test modules
__all__ = ["get_secret"]
