"""Tests for transform LLM tool.

Tests configuration validation and OpenAI client mocks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# -----------------------------------------------------------------------------
# Configuration Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestGetApiConfig:
    """Test _get_api_config function."""

    @patch("ot_tools.transform.get_tool_config")
    @patch("ot_tools.transform.get_secret")
    def test_returns_all_config(self, mock_secret, mock_get_tool_config):
        from ot_tools.transform import Config, _get_api_config

        mock_secret.return_value = "sk-test-key"
        mock_get_tool_config.return_value = Config(
            base_url="https://api.openai.com/v1",
            model="gpt-4",
            timeout=60,
            max_tokens=1000,
        )

        api_key, base_url, model, config = _get_api_config()

        assert api_key == "sk-test-key"
        assert base_url == "https://api.openai.com/v1"
        assert model == "gpt-4"
        assert config.timeout == 60
        assert config.max_tokens == 1000

    @patch("ot_tools.transform.get_tool_config")
    @patch("ot_tools.transform.get_secret")
    def test_returns_none_for_missing(self, mock_secret, mock_get_tool_config):
        from ot_tools.transform import Config, _get_api_config

        mock_secret.return_value = None
        mock_get_tool_config.return_value = Config(base_url="", model="")

        api_key, base_url, model, config = _get_api_config()

        assert api_key is None
        assert base_url is None
        assert model is None
        assert config.timeout == 30  # Default
        assert config.max_tokens is None  # Default


# -----------------------------------------------------------------------------
# Transform Function Tests
# -----------------------------------------------------------------------------


def _make_config(timeout: int = 30, max_tokens: int | None = None):
    """Helper to create Config for tests."""
    from ot_tools.transform import Config

    return Config(
        base_url="https://api.openai.com/v1",
        model="gpt-4",
        timeout=timeout,
        max_tokens=max_tokens,
    )


def _mock_response(content: str = "result", with_usage: bool = True):
    """Helper to create mock OpenAI response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    if with_usage:
        mock_resp.usage = MagicMock()
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 20
        mock_resp.usage.total_tokens = 30
    else:
        mock_resp.usage = None
    return mock_resp


@pytest.mark.unit
@pytest.mark.tools
class TestTransformValidation:
    """Test input validation for transform function."""

    def test_empty_prompt_returns_error(self):
        from ot_tools.transform import transform

        result = transform(input="test data", prompt="")

        assert "Error" in result
        assert "prompt" in result
        assert "empty" in result

    def test_whitespace_prompt_returns_error(self):
        from ot_tools.transform import transform

        result = transform(input="test data", prompt="   ")

        assert "Error" in result
        assert "prompt" in result
        assert "empty" in result

    def test_empty_input_returns_error(self):
        from ot_tools.transform import transform

        result = transform(input="", prompt="transform this")

        assert "Error" in result
        assert "input" in result
        assert "empty" in result

    def test_whitespace_input_returns_error(self):
        from ot_tools.transform import transform

        result = transform(input="   ", prompt="transform this")

        assert "Error" in result
        assert "input" in result
        assert "empty" in result


@pytest.mark.unit
@pytest.mark.tools
class TestTransform:
    """Test transform function with mocked OpenAI client."""

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_successful_transform(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response(
            "Transformed result"
        )

        result = transform(input="test data", prompt="Transform this")

        assert result == "Transformed result"
        mock_client.chat.completions.create.assert_called_once()

    @patch("ot_tools.transform._get_api_config")
    def test_missing_api_key(self, mock_config):
        from ot_tools.transform import transform

        mock_config.return_value = (
            None,
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        assert "OPENAI_API_KEY" in result

    @patch("ot_tools.transform._get_api_config")
    def test_missing_base_url(self, mock_config):
        from ot_tools.transform import transform

        mock_config.return_value = ("sk-test", None, "gpt-4", _make_config())

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        assert "base_url" in result

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_missing_model(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            None,
            _make_config(),
        )

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        assert "model" in result

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_custom_model_override(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "default-model",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(input="test", prompt="transform", model="custom-model")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "custom-model"

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_handles_api_error(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception(
            "API rate limit exceeded"
        )

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        assert "rate limit" in result

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_converts_input_to_string(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(input={"key": "value"}, prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        user_message = next(m for m in messages if m["role"] == "user")
        assert "{'key': 'value'}" in user_message["content"]

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_handles_empty_response(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_resp = _mock_response()
        mock_resp.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_resp

        result = transform(input="test", prompt="transform")

        assert result == ""

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_message_format(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(input="my data", prompt="my prompt")

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        system_msg = next(m for m in messages if m["role"] == "system")
        assert "data transformation" in system_msg["content"].lower()

        user_msg = next(m for m in messages if m["role"] == "user")
        assert "my data" in user_msg["content"]
        assert "my prompt" in user_msg["content"]

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_uses_low_temperature(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(input="test", prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.1


@pytest.mark.unit
@pytest.mark.tools
class TestTransformConfig:
    """Test transform configuration options."""

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_timeout_passed_to_client(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(timeout=60),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(input="test", prompt="transform")

        mock_openai.assert_called_once_with(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=60,
        )

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_max_tokens_passed_to_api(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(max_tokens=1000),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(input="test", prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 1000

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_max_tokens_not_set_when_none(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(max_tokens=None),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(input="test", prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        assert "max_tokens" not in call_args.kwargs


@pytest.mark.unit
@pytest.mark.tools
class TestTransformJsonMode:
    """Test JSON mode functionality."""

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_json_mode_sets_response_format(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response(
            '{"key": "value"}'
        )

        result = transform(input="test", prompt="transform to json", json_mode=True)

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["response_format"] == {"type": "json_object"}
        assert result == '{"key": "value"}'

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_json_mode_false_no_response_format(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(input="test", prompt="transform", json_mode=False)

        call_args = mock_client.chat.completions.create.call_args
        assert "response_format" not in call_args.kwargs


@pytest.mark.unit
@pytest.mark.tools
class TestTransformErrorSanitization:
    """Test error message sanitization."""

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_sanitizes_api_key_in_error(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception(
            "Invalid api_key: sk-abc123xyz"
        )

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        # The actual key value should not be exposed
        assert "sk-abc123xyz" not in result
        assert "Authentication error" in result

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_sanitizes_sk_prefix_in_error(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception(
            "Error with key sk-proj-abc123"
        )

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        # The actual key value should not be exposed
        assert "sk-proj-abc123" not in result
        assert "Authentication error" in result

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_non_sensitive_errors_passed_through(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception(
            "Connection timeout"
        )

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        assert "Connection timeout" in result
