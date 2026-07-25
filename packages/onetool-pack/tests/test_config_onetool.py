"""Test otpack config delegation to ot.config when in onetool mode."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.pkg
def test_get_tool_config_delegates_to_ot_config() -> None:
    """get_tool_config should delegate to ot.config.get_tool_config when importable."""
    from pydantic import BaseModel

    from otpack import get_tool_config

    class FakeConfig(BaseModel):
        timeout: float = 5.0

    fake_config = FakeConfig(timeout=30.0)
    mock_ot_config = MagicMock()
    mock_ot_config.get_tool_config.return_value = fake_config

    with patch.dict(sys.modules, {"ot.config": mock_ot_config}):
        result = get_tool_config("sample_pack", FakeConfig)

    assert result is fake_config
    mock_ot_config.get_tool_config.assert_called_once_with("sample_pack", FakeConfig)


@pytest.mark.unit
@pytest.mark.pkg
@pytest.mark.parametrize(
    "error",
    [
        ValueError("hosted validation failed"),
        RuntimeError("hosted runtime failed"),
        ImportError("hosted delegate import failed"),
    ],
)
def test_get_tool_config_propagates_hosted_failures(error: Exception) -> None:
    """Hosted delegate failures propagate instead of selecting standalone mode."""
    from pydantic import BaseModel

    from otpack import get_tool_config

    class FakeConfig(BaseModel):
        timeout: int = 30

    mock_ot_config = MagicMock()
    mock_ot_config.get_tool_config.side_effect = error

    with (
        patch.dict(sys.modules, {"ot.config": mock_ot_config}),
        pytest.raises(type(error), match=str(error)),
    ):
        get_tool_config("sample", FakeConfig)

    mock_ot_config.get_tool_config.assert_called_once_with("sample", FakeConfig)


@pytest.mark.unit
@pytest.mark.pkg
def test_get_secret_delegates_to_ot_config() -> None:
    """get_secret should delegate to ot.config.secrets.get_secret when importable."""
    import sys

    mock_secrets = MagicMock()
    mock_secrets.get_secret = MagicMock(return_value="test-api-key")

    original_ot = sys.modules.get("ot")
    original_ot_config = sys.modules.get("ot.config")
    original_secrets = sys.modules.get("ot.config.secrets")
    sys.modules["ot"] = MagicMock()
    sys.modules["ot.config"] = MagicMock()
    sys.modules["ot.config.secrets"] = mock_secrets

    try:
        import importlib

        import otpack.config as cfg

        importlib.reload(cfg)

        result = cfg.get_secret("MY_API_KEY")
        assert result == "test-api-key"
        mock_secrets.get_secret.assert_called_once_with("MY_API_KEY")
    finally:
        if original_ot is None:
            sys.modules.pop("ot", None)
        else:
            sys.modules["ot"] = original_ot
        if original_ot_config is None:
            sys.modules.pop("ot.config", None)
        else:
            sys.modules["ot.config"] = original_ot_config
        if original_secrets is None:
            sys.modules.pop("ot.config.secrets", None)
        else:
            sys.modules["ot.config.secrets"] = original_secrets
        import importlib

        import otpack.config as cfg

        importlib.reload(cfg)


@pytest.mark.unit
@pytest.mark.pkg
def test_is_log_verbose_delegates_to_ot_config() -> None:
    """is_log_verbose should check OT_LOG_VERBOSE env var first, then ot.config."""
    import os

    # Env var takes priority
    os.environ["OT_LOG_VERBOSE"] = "true"
    try:
        from otpack.config import is_log_verbose

        assert is_log_verbose() is True
    finally:
        del os.environ["OT_LOG_VERBOSE"]
