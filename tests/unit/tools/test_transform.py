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

    @patch("ot_tools.transform.get_config")
    @patch("ot_tools.transform.get_secret")
    def test_returns_all_config(self, mock_secret, mock_config):
        from ot_tools.transform import _get_api_config

        mock_secret.return_value = "sk-test-key"
        mock_config.side_effect = lambda k: {
            "transform.base_url": "https://api.openai.com/v1",
            "transform.model": "gpt-4",
        }.get(k)

        api_key, base_url, model = _get_api_config()

        assert api_key == "sk-test-key"
        assert base_url == "https://api.openai.com/v1"
        assert model == "gpt-4"

    @patch("ot_tools.transform.get_config")
    @patch("ot_tools.transform.get_secret")
    def test_returns_none_for_missing(self, mock_secret, mock_config):
        from ot_tools.transform import _get_api_config

        mock_secret.return_value = None
        mock_config.return_value = None

        api_key, base_url, model = _get_api_config()

        assert api_key is None
        assert base_url is None
        assert model is None


# -----------------------------------------------------------------------------
# Transform Function Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestTransform:
    """Test transform function with mocked OpenAI client."""

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_successful_transform(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = ("sk-test", "https://api.openai.com/v1", "gpt-4")

        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Transformed result"
        mock_client.chat.completions.create.return_value = mock_response

        result = transform(input="test data", prompt="Transform this")

        assert result == "Transformed result"
        mock_client.chat.completions.create.assert_called_once()

    @patch("ot_tools.transform._get_api_config")
    def test_missing_api_key(self, mock_config):
        from ot_tools.transform import transform

        mock_config.return_value = (None, "https://api.openai.com/v1", "gpt-4")

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        assert "OPENAI_API_KEY" in result

    @patch("ot_tools.transform._get_api_config")
    def test_missing_base_url(self, mock_config):
        from ot_tools.transform import transform

        mock_config.return_value = ("sk-test", None, "gpt-4")

        result = transform(input="test", prompt="transform")

        assert "Error" in result
        assert "base_url" in result

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_missing_model(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = ("sk-test", "https://api.openai.com/v1", None)

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
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        transform(input="test", prompt="transform", model="custom-model")

        # Verify the custom model was used
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "custom-model"

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_handles_api_error(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = ("sk-test", "https://api.openai.com/v1", "gpt-4")

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

        mock_config.return_value = ("sk-test", "https://api.openai.com/v1", "gpt-4")

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        # Pass dict instead of string
        transform(input={"key": "value"}, prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        user_message = next(m for m in messages if m["role"] == "user")
        assert "{'key': 'value'}" in user_message["content"]

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_handles_empty_response(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = ("sk-test", "https://api.openai.com/v1", "gpt-4")

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None  # Empty response
        mock_client.chat.completions.create.return_value = mock_response

        result = transform(input="test", prompt="transform")

        # Should return empty string, not error
        assert result == ""

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_message_format(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = ("sk-test", "https://api.openai.com/v1", "gpt-4")

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        transform(input="my data", prompt="my prompt")

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        # Check system message
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "data transformation" in system_msg["content"].lower()

        # Check user message contains input and prompt
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "my data" in user_msg["content"]
        assert "my prompt" in user_msg["content"]

    @patch("ot_tools.transform.OpenAI")
    @patch("ot_tools.transform._get_api_config")
    def test_uses_low_temperature(self, mock_config, mock_openai):
        from ot_tools.transform import transform

        mock_config.return_value = ("sk-test", "https://api.openai.com/v1", "gpt-4")

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        mock_client.chat.completions.create.return_value = mock_response

        transform(input="test", prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.1
