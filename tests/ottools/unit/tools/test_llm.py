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

    @patch("ottools.ot_llm.get_tool_config")
    @patch("ottools.ot_llm.get_secret")
    def test_returns_all_config(self, mock_secret, mock_get_tool_config):
        from ottools.ot_llm import Config, _get_api_config

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

    @patch("ottools.ot_llm.get_tool_config")
    @patch("ottools.ot_llm.get_secret")
    @patch("ot.config.get_llm_config")
    def test_returns_none_for_missing(self, mock_llm, mock_secret, mock_get_tool_config):
        from ot.config import LlmConfig
        from ottools.ot_llm import Config, _get_api_config

        mock_secret.return_value = None
        mock_get_tool_config.return_value = Config(base_url="", model="")
        mock_llm.return_value = LlmConfig()

        api_key, base_url, model, config = _get_api_config()

        assert api_key is None
        assert base_url == "https://api.openai.com/v1"
        assert model == "gpt-5.4-nano"
        assert config.timeout == 30  # Default
        assert config.max_tokens is None  # Default


# -----------------------------------------------------------------------------
# Transform Function Tests
# -----------------------------------------------------------------------------


def _make_config(timeout: int = 30, max_tokens: int | None = None):
    """Helper to create Config for tests."""
    from ottools.ot_llm import Config

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
        from ottools.ot_llm import transform

        result = transform(data="test data", prompt="")

        assert "Error" in result
        assert "prompt" in result
        assert "empty" in result

    def test_whitespace_prompt_returns_error(self):
        from ottools.ot_llm import transform

        result = transform(data="test data", prompt="   ")

        assert "Error" in result
        assert "prompt" in result
        assert "empty" in result

    def test_empty_data_returns_error(self):
        from ottools.ot_llm import transform

        result = transform(data="", prompt="transform this")

        assert "Error" in result
        assert "data" in result
        assert "empty" in result

    def test_whitespace_data_returns_error(self):
        from ottools.ot_llm import transform

        result = transform(data="   ", prompt="transform this")

        assert "Error" in result
        assert "data" in result
        assert "empty" in result


@pytest.mark.unit
@pytest.mark.tools
class TestTransform:
    """Test transform function with mocked OpenAI client."""

    def setup_method(self):
        import ottools.ot_llm

        ottools.ot_llm._client_cache.clear()

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_successful_transform(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

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

        result = transform(data="test data", prompt="Transform this")

        assert result == "Transformed result"
        mock_client.chat.completions.create.assert_called_once()

    @patch("ottools.ot_llm._get_api_config")
    def test_missing_api_key(self, mock_config):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            None,
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        result = transform(data="test", prompt="transform")

        assert "Error" in result
        assert "OPENAI_API_KEY" in result

    @patch("ottools.ot_llm._get_api_config")
    def test_missing_base_url(self, mock_config):
        from ottools.ot_llm import transform

        mock_config.return_value = ("sk-test", None, "gpt-4", _make_config())

        result = transform(data="test", prompt="transform")

        assert "Error" in result
        assert "base_url" in result

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_missing_model(self, mock_config, _mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            None,
            _make_config(),
        )

        result = transform(data="test", prompt="transform")

        assert "Error" in result
        assert "model" in result

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_custom_model_override(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "default-model",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(data="test", prompt="transform", model="custom-model")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "custom-model"

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_handles_api_error(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

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

        result = transform(data="test", prompt="transform")

        assert "Error" in result
        assert "rate limit" in result

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_converts_input_to_string(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(data={"key": "value"}, prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        user_message = next(m for m in messages if m["role"] == "user")
        assert "{'key': 'value'}" in user_message["content"]

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_handles_empty_response(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

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

        result = transform(data="test", prompt="transform")

        assert result == ""

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_message_format(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(data="my data", prompt="my prompt")

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        system_msg = next(m for m in messages if m["role"] == "system")
        assert "data transformation" in system_msg["content"].lower()

        user_msg = next(m for m in messages if m["role"] == "user")
        assert "my data" in user_msg["content"]
        assert "my prompt" in user_msg["content"]

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_uses_low_temperature(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(data="test", prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.1


@pytest.mark.unit
@pytest.mark.tools
class TestTransformConfig:
    """Test transform configuration options."""

    def setup_method(self):
        import ottools.ot_llm

        ottools.ot_llm._client_cache.clear()

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_timeout_passed_to_client(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(timeout=60),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(data="test", prompt="transform")

        mock_openai.assert_called_once_with(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=60,
        )

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_max_tokens_passed_to_api(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(max_tokens=1000),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(data="test", prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 1000

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_max_tokens_not_set_when_none(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(max_tokens=None),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(data="test", prompt="transform")

        call_args = mock_client.chat.completions.create.call_args
        assert "max_tokens" not in call_args.kwargs


@pytest.mark.unit
@pytest.mark.tools
class TestTransformJsonMode:
    """Test JSON mode functionality."""

    def setup_method(self):
        import ottools.ot_llm

        ottools.ot_llm._client_cache.clear()

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_json_mode_sets_response_format(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

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

        result = transform(data="test", prompt="transform to json", json_mode=True)

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["response_format"] == {"type": "json_object"}
        assert result == '{"key": "value"}'

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_json_mode_false_no_response_format(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

        mock_config.return_value = (
            "sk-test",
            "https://api.openai.com/v1",
            "gpt-4",
            _make_config(),
        )

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        transform(data="test", prompt="transform", json_mode=False)

        call_args = mock_client.chat.completions.create.call_args
        assert "response_format" not in call_args.kwargs


@pytest.mark.unit
@pytest.mark.tools
class TestTransformErrorSanitization:
    """Test error message sanitization."""

    def setup_method(self):
        import ottools.ot_llm

        ottools.ot_llm._client_cache.clear()

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_sanitizes_api_key_in_error(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

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

        result = transform(data="test", prompt="transform")

        assert "Error" in result
        # The actual key value should not be exposed
        assert "sk-abc123xyz" not in result
        assert "Authentication error" in result

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_sanitizes_sk_prefix_in_error(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

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

        result = transform(data="test", prompt="transform")

        assert "Error" in result
        # The actual key value should not be exposed
        assert "sk-proj-abc123" not in result
        assert "Authentication error" in result

    @patch("ottools.ot_llm.OpenAI")
    @patch("ottools.ot_llm._get_api_config")
    def test_non_sensitive_errors_passed_through(self, mock_config, mock_openai):
        from ottools.ot_llm import transform

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

        result = transform(data="test", prompt="transform")

        assert "Error" in result
        assert "Connection timeout" in result


# -----------------------------------------------------------------------------
# Transform File Tests
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_cwd_path(tmp_path):
    """Mock resolve_cwd_path to use tmp_path as base directory."""
    with patch(
        "ottools.ot_llm.resolve_cwd_path", side_effect=lambda p: tmp_path / p
    ):
        yield tmp_path


@pytest.mark.unit
@pytest.mark.tools
class TestTransformFileValidation:
    """Test input validation for transform_file function."""

    def test_empty_prompt_returns_error(self, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_file = mock_cwd_path / "input.txt"
        input_file.write_text("test content")

        result = transform_file(prompt="", in_file="input.txt", out_file="output.txt")

        assert "Error" in result
        assert "prompt" in result
        assert "empty" in result

    def test_input_file_not_found(self, mock_cwd_path):  # noqa: ARG002
        from ottools.ot_llm import transform_file

        result = transform_file(
            prompt="transform this", in_file="nonexistent.txt", out_file="output.txt"
        )

        assert "Error" in result
        assert "not found" in result

    def test_input_path_is_directory(self, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_dir = mock_cwd_path / "inputdir"
        input_dir.mkdir()

        result = transform_file(
            prompt="transform this", in_file="inputdir", out_file="output.txt"
        )

        assert "Error" in result
        assert "not a file" in result

    def test_empty_input_file(self, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_file = mock_cwd_path / "input.txt"
        input_file.write_text("")

        result = transform_file(
            prompt="transform this", in_file="input.txt", out_file="output.txt"
        )

        assert "Error" in result
        assert "empty" in result


@pytest.mark.unit
@pytest.mark.tools
class TestTransformFile:
    """Test transform_file function with mocked transform."""

    @patch("ottools.ot_llm.transform")
    def test_successful_transform_file(self, mock_transform, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_file = mock_cwd_path / "input.txt"
        input_file.write_text("original content")
        output_file = mock_cwd_path / "output.txt"

        mock_transform.return_value = "transformed content"

        result = transform_file(
            prompt="transform this", in_file="input.txt", out_file="output.txt"
        )

        assert "OK" in result
        assert "input.txt" in result
        assert "output.txt" in result
        assert output_file.exists()
        assert output_file.read_text() == "transformed content"
        mock_transform.assert_called_once_with(
            data="original content",
            prompt="transform this",
            model=None,
            json_mode=False,
        )

    @patch("ottools.ot_llm.transform")
    def test_passes_model_parameter(self, mock_transform, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_file = mock_cwd_path / "input.txt"
        input_file.write_text("content")

        mock_transform.return_value = "result"

        transform_file(
            prompt="transform",
            in_file="input.txt",
            out_file="output.txt",
            model="gpt-4",
        )

        mock_transform.assert_called_once_with(
            data="content",
            prompt="transform",
            model="gpt-4",
            json_mode=False,
        )

    @patch("ottools.ot_llm.transform")
    def test_passes_json_mode(self, mock_transform, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_file = mock_cwd_path / "input.txt"
        input_file.write_text("content")

        mock_transform.return_value = '{"key": "value"}'

        transform_file(
            prompt="to json",
            in_file="input.txt",
            out_file="output.json",
            json_mode=True,
        )

        mock_transform.assert_called_once_with(
            data="content",
            prompt="to json",
            model=None,
            json_mode=True,
        )

    @patch("ottools.ot_llm.transform")
    def test_transform_error_propagates(self, mock_transform, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_file = mock_cwd_path / "input.txt"
        input_file.write_text("content")
        output_file = mock_cwd_path / "output.txt"

        mock_transform.return_value = "Error: API rate limit exceeded"

        result = transform_file(
            prompt="transform", in_file="input.txt", out_file="output.txt"
        )

        assert "Error" in result
        assert "rate limit" in result
        assert not output_file.exists()

    @patch("ottools.ot_llm.transform")
    def test_creates_parent_directories(self, mock_transform, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_file = mock_cwd_path / "input.txt"
        input_file.write_text("content")
        output_file = mock_cwd_path / "subdir" / "nested" / "output.txt"

        mock_transform.return_value = "result"

        result = transform_file(
            prompt="transform",
            in_file="input.txt",
            out_file="subdir/nested/output.txt",
        )

        assert "OK" in result
        assert output_file.exists()
        assert output_file.read_text() == "result"

    @patch("ottools.ot_llm.transform")
    def test_reports_bytes_written(self, mock_transform, mock_cwd_path):
        from ottools.ot_llm import transform_file

        input_file = mock_cwd_path / "input.txt"
        input_file.write_text("content")

        mock_transform.return_value = "result data"  # 11 bytes

        result = transform_file(
            prompt="transform", in_file="input.txt", out_file="output.txt"
        )

        assert "11 bytes" in result
