"""Shared fixtures for core integration tests."""

from __future__ import annotations

import pytest

from tests._test_secrets import _secrets, _secrets_module


@pytest.fixture(autouse=True)
def _inject_secrets():
    """Inject decrypted test secrets into the runtime cache."""
    old = _secrets_module._secrets
    _secrets_module._secrets = _secrets
    yield
    _secrets_module._secrets = old
