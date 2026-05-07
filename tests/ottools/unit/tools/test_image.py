"""Unit tests for the image pack.

Covers config loading, source resolution, resize, store, vision, tools, and
lifecycle — all with mocked I/O and no network calls.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

try:
    import cairosvg  # noqa: F401
    _CAIROSVG_AVAILABLE = True
except (ImportError, OSError):
    _CAIROSVG_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal valid PNG image in memory."""
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(width: int = 50, height: int = 50) -> bytes:
    """Create a minimal valid JPEG image in memory."""
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_meta(
    handle_name: str,
    dims: list[int] | None = None,
    sha: str | None = None,
) -> dict:
    """Build a minimal image metadata dict for store tests."""
    d = dims or [100, 100]
    return {
        "handle": handle_name,
        "source": "file",
        "hash": sha or "a" * 64,
        "original_dims": d,
        "model_dims": d,
        "resized": False,
        "max_edge": 1568,
        "original_format": "PNG",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": None,
    }


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestImageConfig:
    """Tests for get_image_config()."""

    @patch("ottools._image.config.get_tool_config")
    @patch("ottools._image.config.get_secret")
    @patch("ot.config.get_llm_config", side_effect=Exception("no llm config"))
    def test_defaults(self, _mock_llm: MagicMock, mock_secret: MagicMock, mock_gtc: MagicMock) -> None:
        from ottools._image.config import Config, get_image_config

        mock_gtc.return_value = Config()
        mock_secret.return_value = None
        config = get_image_config()
        assert config.max_edge == 1568
        assert config.session_cache_size == 10
        assert config.model == ""

    @patch("ottools._image.config.get_secret")
    def test_api_key_from_secret(self, mock_secret: MagicMock) -> None:
        from ottools._image.config import get_image_api_key

        mock_secret.return_value = "sk-test-key"
        assert get_image_api_key() == "sk-test-key"

    @patch("ottools._image.config.get_tool_config")
    @patch("ot.config.get_llm_config")
    def test_base_url_and_model_fallback_from_llm_config(
        self, mock_glc: MagicMock, mock_gtc: MagicMock
    ) -> None:
        from ottools._image.config import Config, get_image_config
        from ot.config.models import LlmConfig

        mock_gtc.return_value = Config()
        mock_glc.return_value = LlmConfig(
            base_url="https://openrouter.ai/api/v1",
            model="google/gemini-3-flash-preview",
        )
        config = get_image_config()
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.model == "google/gemini-3-flash-preview"


# ---------------------------------------------------------------------------
# Source resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestValidateImageBytes:
    """Tests for validate_image_bytes()."""

    def test_valid_png(self) -> None:
        from ottools._image.sources import validate_image_bytes

        data = _make_png_bytes()
        fmt = validate_image_bytes(data)
        assert fmt == "PNG"

    def test_valid_jpeg(self) -> None:
        from ottools._image.sources import validate_image_bytes

        data = _make_jpeg_bytes()
        fmt = validate_image_bytes(data)
        assert fmt == "JPEG"

    def test_valid_tiff_le(self) -> None:
        from ottools._image.sources import validate_image_bytes

        # Little-endian TIFF magic
        fmt = validate_image_bytes(b"II*\x00" + b"\x00" * 100)
        assert fmt == "TIFF"

    def test_valid_tiff_be(self) -> None:
        from ottools._image.sources import validate_image_bytes

        # Big-endian TIFF magic
        fmt = validate_image_bytes(b"MM\x00*" + b"\x00" * 100)
        assert fmt == "TIFF"

    def test_valid_heic(self) -> None:
        from ottools._image.sources import validate_image_bytes

        # ISOBMFF with heic brand
        data = b"\x00\x00\x00\x18" + b"ftyp" + b"heic" + b"\x00" * 100
        fmt = validate_image_bytes(data)
        assert fmt == "HEIC"

    def test_valid_heif(self) -> None:
        from ottools._image.sources import validate_image_bytes

        data = b"\x00\x00\x00\x18" + b"ftyp" + b"heif" + b"\x00" * 100
        fmt = validate_image_bytes(data)
        assert fmt == "HEIC"

    def test_valid_avif(self) -> None:
        from ottools._image.sources import validate_image_bytes

        data = b"\x00\x00\x00\x18" + b"ftyp" + b"avif" + b"\x00" * 100
        fmt = validate_image_bytes(data)
        assert fmt == "AVIF"

    def test_valid_svg(self) -> None:
        from ottools._image.sources import validate_image_bytes

        fmt = validate_image_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'>", "icon.svg")
        assert fmt == "SVG"

    def test_valid_svg_xml_declaration(self) -> None:
        from ottools._image.sources import validate_image_bytes

        fmt = validate_image_bytes(b"<?xml version='1.0'?><svg>", "diagram.svg")
        assert fmt == "SVG"

    def test_valid_svg_with_bom(self) -> None:
        from ottools._image.sources import validate_image_bytes

        fmt = validate_image_bytes(b"\xef\xbb\xbf<svg>", "icon.svg")
        assert fmt == "SVG"

    def test_valid_svg_uppercase(self) -> None:
        from ottools._image.sources import validate_image_bytes

        fmt = validate_image_bytes(b"<SVG xmlns='http://www.w3.org/2000/svg'>", "icon.svg")
        assert fmt == "SVG"

    def test_invalid_format_raises(self) -> None:
        from ottools._image.sources import validate_image_bytes

        with pytest.raises(ValueError, match="Unsupported image format"):
            validate_image_bytes(b"this is not an image", "test.txt")

    def test_error_message_lists_supported_formats(self) -> None:
        from ottools._image.sources import validate_image_bytes

        with pytest.raises(ValueError, match="TIFF"):
            validate_image_bytes(b"garbage")
        with pytest.raises(ValueError, match="HEIC"):
            validate_image_bytes(b"garbage")
        with pytest.raises(ValueError, match="AVIF"):
            validate_image_bytes(b"garbage")
        with pytest.raises(ValueError, match="SVG"):
            validate_image_bytes(b"garbage")


@pytest.mark.unit
@pytest.mark.tools
class TestResolveSource:
    """Tests for resolve_source() type detection."""

    def test_clip_detected(self) -> None:
        from ottools._image.sources import resolve_source

        with patch("ottools._image.sources._grab_clipboard", return_value=b"png"):
            source_type, _ = resolve_source("clip")
        assert source_type == "clipboard"

    def test_clipboard_alias_detected(self) -> None:
        from ottools._image.sources import resolve_source

        with patch("ottools._image.sources._grab_clipboard", return_value=b"png"):
            source_type, _ = resolve_source("clipboard")
        assert source_type == "clipboard"

    def test_handle_detected(self) -> None:
        from ottools._image.sources import resolve_source

        source_type, handle_name = resolve_source("#img_abc12345")
        assert source_type == "handle"
        assert handle_name == "img_abc12345"

    def test_url_detected(self) -> None:
        from ottools._image.sources import resolve_source

        with patch("ottools._image.sources._fetch_url", return_value=b"png"):
            source_type, _ = resolve_source("https://example.org/img.png")
        assert source_type == "url"

    def test_glob_detected(self) -> None:
        from ottools._image.sources import resolve_source

        source_type, data = resolve_source("~/screenshots/*.png")
        assert source_type == "glob"
        assert data == "~/screenshots/*.png"

    def test_file_detected(self) -> None:
        from ottools._image.sources import resolve_source

        with patch("ottools._image.sources._load_file", return_value=b"png"):
            source_type, _ = resolve_source("~/image.png")
        assert source_type == "file"

    def test_file_not_found_raises(self) -> None:
        from ottools._image.sources import _load_file

        with pytest.raises(FileNotFoundError):
            _load_file("/nonexistent/path/image.png")

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-only")
    def test_clipboard_linux_raises(self) -> None:
        from ottools._image.sources import _grab_clipboard

        with pytest.raises(NotImplementedError, match="Linux"):
            _grab_clipboard()

    @pytest.mark.skipif(sys.platform == "linux", reason="clipboard not supported on Linux")
    def test_clipboard_file_reference_loads_first_path(self, tmp_path: Path) -> None:
        """list return from ImageGrab.grabclipboard() resolves to first path."""
        from ottools._image.sources import _grab_clipboard

        png = _make_png_bytes()
        img_path = tmp_path / "shot.png"
        img_path.write_bytes(png)

        with patch("PIL.ImageGrab.grabclipboard", return_value=[str(img_path)]):
            result = _grab_clipboard()

        assert result == png

    @pytest.mark.skipif(sys.platform == "linux", reason="clipboard not supported on Linux")
    def test_clipboard_empty_list_raises(self) -> None:
        from ottools._image.sources import _grab_clipboard

        with patch("PIL.ImageGrab.grabclipboard", return_value=[]):
            with pytest.raises(ValueError, match="No image found in clipboard"):
                _grab_clipboard()


# ---------------------------------------------------------------------------
# Resize tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestPrepareForModel:
    """Tests for prepare_for_model()."""

    def test_small_image_passes_through_unchanged(self) -> None:
        from ottools._image.resize import prepare_for_model

        raw = _make_png_bytes(100, 100)
        result = prepare_for_model(raw, max_edge=1568)
        assert not result.resized
        assert result.original_dims == (100, 100)
        assert result.model_dims == (100, 100)
        assert result.model_bytes[:4] == b"\x89PNG"

    def test_oversized_image_resized(self) -> None:
        from ottools._image.resize import prepare_for_model

        raw = _make_png_bytes(3000, 1500)
        result = prepare_for_model(raw, max_edge=1568)
        assert result.resized
        assert result.original_dims == (3000, 1500)
        # Longest edge should be <= max_edge
        assert max(result.model_dims) <= 1568
        # Aspect ratio preserved within 1px rounding
        orig_ratio = 3000 / 1500
        model_ratio = result.model_dims[0] / result.model_dims[1]
        assert abs(orig_ratio - model_ratio) < 0.01

    def test_original_dims_recorded_correctly(self) -> None:
        from ottools._image.resize import prepare_for_model

        raw = _make_png_bytes(800, 600)
        result = prepare_for_model(raw, max_edge=1568)
        assert result.original_dims == (800, 600)

    def test_tiff_passthrough(self) -> None:
        from PIL import Image

        from ottools._image.resize import prepare_for_model

        img = Image.new("RGB", (100, 100), color=(0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="TIFF")
        raw = buf.getvalue()
        result = prepare_for_model(raw, max_edge=1568)
        assert not result.resized
        assert result.original_dims == (100, 100)
        assert result.model_bytes[:4] == b"\x89PNG"

    def test_heic_registers_pillow_heif(self) -> None:
        from unittest.mock import MagicMock, call, patch

        from ottools._image.resize import prepare_for_model

        # Fake HEIC bytes (ISOBMFF with heic brand)
        heic_bytes = b"\x00\x00\x00\x18" + b"ftyp" + b"heic" + b"\x00" * 100

        mock_heif = MagicMock()
        mock_img = MagicMock()
        mock_img.format = "HEIF"
        mock_img.width = 50
        mock_img.height = 50
        mock_img.mode = "RGB"

        with patch.dict("sys.modules", {"pillow_heif": mock_heif}):
            with patch("PIL.Image.open", return_value=mock_img) as mock_open:
                mock_img.resize.return_value = mock_img
                mock_img.save = MagicMock(side_effect=lambda buf, format: buf.write(b"\x89PNG\r\n\x1a\n"))
                prepare_for_model(heic_bytes, max_edge=1568)

        mock_heif.register_heif_opener.assert_called_once()

    def test_heic_missing_pillow_heif_raises(self) -> None:
        import sys

        from ottools._image.resize import prepare_for_model

        heic_bytes = b"\x00\x00\x00\x18" + b"ftyp" + b"heic" + b"\x00" * 100

        # Remove pillow_heif from sys.modules and block its import
        original = sys.modules.pop("pillow_heif", None)
        try:
            with patch.dict("sys.modules", {"pillow_heif": None}):
                with pytest.raises(ImportError, match="pillow-heif"):
                    prepare_for_model(heic_bytes, max_edge=1568)
        finally:
            if original is not None:
                sys.modules["pillow_heif"] = original

    @pytest.mark.skipif(not _CAIROSVG_AVAILABLE, reason="cairosvg/libcairo not available")
    def test_svg_rasterized_to_png(self) -> None:
        from ottools._image.resize import prepare_for_model

        svg_bytes = b"<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><rect width='100' height='100' fill='red'/></svg>"
        result = prepare_for_model(svg_bytes, max_edge=1568)
        assert result.model_bytes[:4] == b"\x89PNG"
        assert result.original_dims == (100, 100)

    def test_svg_missing_resvg_py_raises(self) -> None:
        from ottools._image.resize import prepare_for_model

        svg_bytes = b"<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>"
        with patch.dict("sys.modules", {"resvg_py": None}):
            with pytest.raises(ImportError, match="resvg-py"):
                prepare_for_model(svg_bytes, max_edge=1568)


# ---------------------------------------------------------------------------
# Store tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestStore:
    """Tests for disk persistence and session LRU cache."""

    def test_save_and_load_meta_round_trip(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            store.save_image(_make_png_bytes(), "img_abc12345", _make_meta("img_abc12345"))
            loaded = store.load_meta("img_abc12345")
            assert loaded is not None
            assert loaded["handle"] == "img_abc12345"

    def test_load_meta_returns_none_for_missing(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = store.load_meta("nonexistent")
            assert result is None

    def test_save_summary_writes_in_place(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            store.save_image(_make_png_bytes(), "img_test1", _make_meta("img_test1", dims=[50, 50]))
            store.save_summary("img_test1", {"text": "hello", "mode": "light"})
            loaded = store.load_meta("img_test1")
            assert loaded is not None
            assert loaded["summary"]["text"] == "hello"

    def test_find_by_hash_returns_existing(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            sha = "a" * 64
            store.save_image(_make_png_bytes(10, 10), "img_aaaaaaaa", _make_meta("img_aaaaaaaa", dims=[10, 10], sha=sha))
            found = store.find_by_hash(sha)
            assert found == "img_aaaaaaaa"

    def test_find_by_hash_returns_none_for_unknown(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            assert store.find_by_hash("b" * 64) is None

    def test_lru_eviction_at_limit(self) -> None:
        from ottools._image import store
        from ot.utils.cache import Cache

        # Use a small temp cache to test eviction (session_cache is sized at import)
        small_cache = Cache(max_size=3)
        dummy = _make_png_bytes(10, 10)
        b64 = base64.b64encode(dummy).decode()
        for i in range(4):
            small_cache.set(f"handle_{i}", b64)

        keys = small_cache.keys()
        assert len(keys) == 3
        # Oldest (handle_0) should have been evicted
        assert small_cache.get("handle_0") is None
        assert small_cache.get("handle_3") is not None

    def test_cache_get_moves_to_end(self) -> None:
        from ottools._image import store

        store._session_cache.clear()

        dummy = _make_png_bytes(10, 10)
        store.cache_put("a", dummy)
        store.cache_put("b", dummy)
        store.cache_put("c", dummy)

        # Access "a" to make it MRU
        store.cache_get("a")

        keys = store._session_cache.keys()
        assert keys[-1] == "a"  # "a" is most recently used

        store._session_cache.clear()

    def test_cache_evict_removes_handle(self) -> None:
        from ottools._image import store

        store._session_cache.clear()

        dummy = _make_png_bytes(10, 10)
        store.cache_put("evict_me", dummy)
        store.cache_evict("evict_me")

        assert store.cache_get("evict_me") is None

        store._session_cache.clear()

    def test_images_dir_resolves_to_session_dir(self, tmp_path: Path) -> None:
        from ottools._image import store

        session_dir = tmp_path / "2026-03-04-aabbccdd"
        session_dir.mkdir()
        with patch("ottools._image.store.get_session_dir", return_value=session_dir):
            result = store._images_dir()
        assert result == session_dir / "images"
        assert result.exists()


# ---------------------------------------------------------------------------
# Vision tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestVision:
    """Tests for vision model integration (mocked)."""

    def setup_method(self) -> None:
        import ottools._image.vision as _v
        _v._client = None
        _v._client_key = ("", "")
        self._api_key_patch = patch(
            "ottools._image.vision.get_image_api_key", return_value="sk-test"
        )
        self._api_key_patch.start()

    def teardown_method(self) -> None:
        self._api_key_patch.stop()

    def _make_config(self, **kwargs: Any) -> Any:
        from ottools._image.config import Config

        defaults = {
            "model": "openai/gpt-4o-mini",
            "base_url": "https://openrouter.ai/api/v1",
            "max_edge": 1568,
            "session_cache_size": 10,
        }
        defaults.update(kwargs)
        return Config(**defaults)

    def test_vision_not_configured_returns_error(self) -> None:
        from ottools._image.vision import call_vision

        config = self._make_config(model="")
        result = call_vision(b"png", "What is this?", config)
        assert result.startswith("Error:")
        assert "model" in result or "ot_image" in result

    def test_api_key_missing_returns_error(self) -> None:
        from ottools._image.vision import call_vision

        config = self._make_config()
        self._api_key_patch.stop()
        with patch("ottools._image.vision.get_image_api_key", return_value=None):
            result = call_vision(b"png", "What is this?", config)
        self._api_key_patch.start()
        assert result.startswith("Error:")

    def test_single_question_call(self) -> None:
        from ottools._image.vision import ask_questions

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "It is a cat."

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            answers = ask_questions(_make_png_bytes(), ["What is in the image?"], config)

        assert answers == ["It is a cat."]

    def test_batch_questions_parsed_in_order(self) -> None:
        from ottools._image.vision import ask_questions

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            "1. A screenshot of a terminal.\n2. Yes, it is dark mode."
        )

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            answers = ask_questions(
                _make_png_bytes(),
                ["What is shown?", "Is it dark mode?"],
                config,
            )

        assert len(answers) == 2
        assert "screenshot" in answers[0].lower() or "terminal" in answers[0].lower()
        assert "dark" in answers[1].lower()

    def test_summary_json_parsed_correctly(self) -> None:
        from ottools._image.vision import extract_summary

        config = self._make_config()
        summary_json = json.dumps(
            {
                "type": "screenshot",
                "mode": "light",
                "colours": ["white", "black"],
                "description": "A simple web form.",
                "content": "## Form\n\nHello world\n\n**[Submit]**",
            }
        )
        mock_response = MagicMock()
        mock_response.choices[0].message.content = summary_json

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            result = extract_summary(_make_png_bytes(), config)

        assert isinstance(result, dict)
        assert result["type"] == "screenshot"
        assert result["mode"] == "light"
        assert "Submit" in result["content"]

    def test_summary_fills_missing_keys(self) -> None:
        from ottools._image.vision import extract_summary

        config = self._make_config()
        # Only partial JSON from model
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"description": "A thing."}'

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            result = extract_summary(_make_png_bytes(), config)

        assert isinstance(result, dict)
        assert result["content"] == ""
        assert result["mode"] == "unknown"
        assert result["colours"] == []

    def test_api_error_returns_error_string(self) -> None:
        from ottools._image.vision import call_vision

        config = self._make_config()

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.side_effect = RuntimeError(
                "Connection refused"
            )
            result = call_vision(_make_png_bytes(), "test", config)

        assert result.startswith("Error:")

    def test_batch_questions_markdown_header_format(self) -> None:
        """Model returns answers with ### N. heading format — must be split correctly."""
        from ottools._image.vision import ask_questions

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            "### 1. A screenshot of a terminal.\n### 2. Yes, it is dark mode."
        )

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            answers = ask_questions(
                _make_png_bytes(),
                ["What is shown?", "Is it dark mode?"],
                config,
            )

        assert len(answers) == 2
        assert "terminal" in answers[0].lower() or "screenshot" in answers[0].lower()
        assert "dark" in answers[1].lower()

    def test_batch_questions_bold_number_format(self) -> None:
        """Model returns answers with **N.** bold format — must be split correctly."""
        from ottools._image.vision import ask_questions

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            "**1.** Python code editor.\n**2.** Light mode."
        )

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            answers = ask_questions(
                _make_png_bytes(),
                ["What is shown?", "What is the colour mode?"],
                config,
            )

        assert len(answers) == 2
        assert "python" in answers[0].lower() or "editor" in answers[0].lower()
        assert "light" in answers[1].lower()


# ---------------------------------------------------------------------------
# Core tool tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestLoad:
    """Tests for load()."""

    def setup_method(self) -> None:
        """Suppress background summary threads so they don't leak into other tests."""
        self._thread_patcher = patch("ottools._image.tools.threading.Thread")
        self._mock_thread_cls = self._thread_patcher.start()
        self._mock_thread_cls.return_value = MagicMock()

    def teardown_method(self) -> None:
        self._thread_patcher.stop()

    def _patch_store(self, tmp_path: Path) -> Any:
        """Return a context manager that redirects store I/O to tmp_path."""
        from ottools._image import store

        return patch.object(store, "_images_dir", return_value=tmp_path)

    def test_load_file_returns_handle(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        png = _make_png_bytes()
        img_path = tmp_path / "test.png"
        img_path.write_bytes(png)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            from ottools._image.config import Config

            mock_cfg.return_value = Config(session_cache_size=10)
            tools._clip_handle = None

            result = tools.load(img=str(img_path))

        assert result["handle"].startswith("#img_")
        assert result["source"] == str(img_path)
        assert result["dims"] == [100, 100]
        assert result["resized"] is False
        assert result["dedup"] is False

    def test_load_dedup_returns_metadata(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        png = _make_png_bytes()
        img_path = tmp_path / "dedup_meta.png"
        img_path.write_bytes(png)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            from ottools._image.config import Config

            mock_cfg.return_value = Config(session_cache_size=10)
            tools._clip_handle = None

            tools.load(img=str(img_path))
            result = tools.load(img=str(img_path))  # dedup

        assert result["dedup"] is True
        assert result["dims"] is not None

    def test_glob_returns_error(self) -> None:
        from ottools._image import tools

        result = tools.load(img="~/screenshots/*.png")
        assert "error" in result
        assert "load_batch" in result["error"]

    def test_dedup_returns_same_handle(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        png = _make_png_bytes()
        img_path = tmp_path / "dedup.png"
        img_path.write_bytes(png)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            from ottools._image.config import Config

            mock_cfg.return_value = Config(session_cache_size=10)
            tools._clip_handle = None

            h1 = tools.load(img=str(img_path))
            h2 = tools.load(img=str(img_path))

        assert h1["handle"] == h2["handle"]

    def test_named_handle_collision_returns_error(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        png_a = _make_png_bytes(50, 50)
        png_b = _make_png_bytes(80, 80)
        path_a = tmp_path / "a.png"
        path_b = tmp_path / "b.png"
        path_a.write_bytes(png_a)
        path_b.write_bytes(png_b)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            from ottools._image.config import Config

            mock_cfg.return_value = Config(session_cache_size=10)
            tools._clip_handle = None

            tools.load(img=str(path_a), handle="myref")
            result = tools.load(img=str(path_b), handle="myref")

        assert "error" in result
        assert "already exists" in result["error"]

    def test_linux_clipboard_returns_error(self) -> None:
        from ottools._image import tools

        with patch("ottools._image.sources.sys.platform", "linux"):
            result = tools.load(img="clip")

        assert "error" in result
        assert "linux" in result["error"].lower()

    def test_background_summary_spawned_on_load(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.config import Config

        png = _make_png_bytes()
        img_path = tmp_path / "bg_test.png"
        img_path.write_bytes(png)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch("ottools._image.tools.threading.Thread") as mock_thread,
        ):
            mock_cfg.return_value = Config(
                session_cache_size=10,
                model="openai/gpt-4o-mini",
            )
            tools._clip_handle = None
            mock_t = MagicMock()
            mock_thread.return_value = mock_t

            tools.load(img=str(img_path))

        # Thread should have been created and started for background summary
        mock_thread.assert_called_once()
        call_kwargs = mock_thread.call_args
        assert call_kwargs.kwargs.get("daemon") is True
        mock_t.start.assert_called_once()

    def test_background_summary_worker_skips_when_no_model(self, tmp_path: Path) -> None:
        """Worker exits early when model is not configured; no API call made."""
        from ottools._image import tools
        from ottools._image.config import Config

        with patch("ottools._image.tools.get_image_config") as mock_cfg, \
             patch("ottools._image.tools.extract_summary") as mock_extract:
            mock_cfg.return_value = Config(session_cache_size=10, model="")
            tools._background_summarise("img_abc12345", b"fake_bytes")

        mock_extract.assert_not_called()


@pytest.mark.unit
@pytest.mark.tools
class TestAsk:
    """Tests for ask()."""

    def setup_method(self) -> None:
        import ottools._image.vision as _v
        _v._client = None
        _v._client_key = ("", "")
        self._thread_patcher = patch("ottools._image.tools.threading.Thread")
        self._mock_thread_cls = self._thread_patcher.start()
        self._mock_thread_cls.return_value = MagicMock()
        self._api_key_patch = patch(
            "ottools._image.vision.get_image_api_key", return_value="sk-test"
        )
        self._api_key_patch.start()

    def teardown_method(self) -> None:
        self._thread_patcher.stop()
        self._api_key_patch.stop()

    def _setup(self, tmp_path: Path, mock_cfg: MagicMock) -> str:
        """Load a test image and return its handle name."""
        from ottools._image import store, tools
        from ottools._image.config import Config

        png = _make_png_bytes()
        img_path = tmp_path / "ask_test.png"
        img_path.write_bytes(png)

        mock_cfg.return_value = Config(
            session_cache_size=10,
            model="openai/gpt-4o-mini",
        )
        tools._clip_handle = None

        with patch.object(store, "_images_dir", return_value=tmp_path):
            handle = tools.load(img=str(img_path))["handle"]
        return handle

    def test_single_question_returns_answers_list(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            handle = self._setup(tmp_path, mock_cfg)

            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "A red square."

            with patch("ottools._image.vision.OpenAI") as MockOAI:
                MockOAI.return_value.chat.completions.create.return_value = mock_resp
                result = tools.ask(img=handle, q="Describe the image.")

        assert "result" in result
        assert result["result"] == [{"question": "Describe the image.", "answer": "A red square."}]
        assert result["handle"] == handle

    def test_unknown_handle_returns_error(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            from ottools._image.config import Config

            mock_cfg.return_value = Config(session_cache_size=10)
            result = tools.ask(img="#nonexistent", q="test")

        assert "error" in result
        assert "Error" in result["error"]
        assert "not found" in result["error"]

    def test_vision_not_configured_returns_error(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.config import Config

        png = _make_png_bytes()
        img_path = tmp_path / "vision_test.png"
        img_path.write_bytes(png)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            mock_cfg.return_value = Config(session_cache_size=10, model="")
            tools._clip_handle = None
            handle = tools.load(img=str(img_path))["handle"]
            result = tools.ask(img=handle, q="test")

        # Vision model error surfaces as top-level error dict
        assert "error" in result
        assert result["error"].startswith("Error:")

    def test_bare_handle_name_accepted(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            handle = self._setup(tmp_path, mock_cfg)
            bare = handle.lstrip("#")  # strip the "#" prefix

            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = "A red square."

            with patch("ottools._image.vision.OpenAI") as MockOAI:
                MockOAI.return_value.chat.completions.create.return_value = mock_resp
                result = tools.ask(img=bare, q="Describe the image.")

        assert "result" in result
        assert result["result"] == [{"question": "Describe the image.", "answer": "A red square."}]

    def test_clip_ask_refreshes_clipboard_each_call(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.config import Config

        img_a = _make_png_bytes()
        img_b = _make_png_bytes(101, 100)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch("ottools._image.tools.ask_questions", return_value=["ok"]),
            patch("ottools._image.sources._grab_clipboard", side_effect=[img_a, img_b]) as mock_clip,
        ):
            mock_cfg.return_value = Config(session_cache_size=10, model="openai/gpt-4o-mini")
            tools._clip_handle = None
            first = tools.ask(img="clip", q="q1")
            second = tools.ask(img="clip", q="q2")

        assert first["handle"] != second["handle"]
        assert mock_clip.call_count == 2


@pytest.mark.unit
@pytest.mark.tools
class TestSummary:
    """Tests for summary()."""

    def setup_method(self) -> None:
        import ottools._image.vision as _v
        _v._client = None
        _v._client_key = ("", "")
        self._thread_patcher = patch("ottools._image.tools.threading.Thread")
        self._mock_thread_cls = self._thread_patcher.start()
        self._mock_thread_cls.return_value = MagicMock()
        self._api_key_patch = patch(
            "ottools._image.vision.get_image_api_key", return_value="sk-test"
        )
        self._api_key_patch.start()

    def teardown_method(self) -> None:
        self._thread_patcher.stop()
        self._api_key_patch.stop()

    def test_first_call_calls_model(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.config import Config

        png = _make_png_bytes()
        img_path = tmp_path / "sum_test.png"
        img_path.write_bytes(png)

        summary_data = {
            "type": "screenshot",
            "mode": "light",
            "colours": ["red"],
            "description": "A red square.",
            "content": "A red square image.",
        }
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(summary_data)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch("ottools._image.vision.OpenAI") as MockOAI,
        ):
            mock_cfg.return_value = Config(
                session_cache_size=10,
                model="openai/gpt-4o-mini",
            )
            MockOAI.return_value.chat.completions.create.return_value = mock_resp
            tools._clip_handle = None

            handle = tools.load(img=str(img_path))["handle"]
            result = tools.summary(img=handle)

        assert result["cached"] is False
        assert result["summary"]["mode"] == "light"

    def test_repeat_call_returns_cached(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.config import Config

        png = _make_png_bytes()
        img_path = tmp_path / "sum_cached.png"
        img_path.write_bytes(png)

        summary_data = {
            "type": "ui",
            "mode": "dark",
            "colours": [],
            "description": "Cached.",
            "content": "Cached content.",
        }
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(summary_data)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch("ottools._image.vision.OpenAI") as MockOAI,
        ):
            mock_cfg.return_value = Config(
                session_cache_size=10,
                model="openai/gpt-4o-mini",
            )
            MockOAI.return_value.chat.completions.create.return_value = mock_resp
            tools._clip_handle = None

            handle = tools.load(img=str(img_path))["handle"]
            tools.summary(img=handle)  # First call
            result = tools.summary(img=handle)  # Second call — should be cached

        assert result["cached"] is True
        # Model should only have been called once
        assert MockOAI.return_value.chat.completions.create.call_count == 1

    def test_clip_ask_delegates_to_ask(self, tmp_path: Path) -> None:
        from ottools._image import tools

        with patch.object(tools, "ask", return_value={"result": [], "handle": "#h"}) as mock_ask:
            tools.clip_ask(q="What is this?")

        mock_ask.assert_called_once_with(img="clip", q="What is this?", max_edge=1568)

    def test_clip_ask_custom_max_edge(self, tmp_path: Path) -> None:
        from ottools._image import tools

        with patch.object(tools, "ask", return_value={"result": [], "handle": "#h"}) as mock_ask:
            tools.clip_ask(q="Describe", max_edge=800)

        mock_ask.assert_called_once_with(img="clip", q="Describe", max_edge=800)

    def test_clip_view_delegates_to_summary(self, tmp_path: Path) -> None:
        from ottools._image import tools

        with patch.object(tools, "summary", return_value={"summary": {}, "handle": "#h", "cached": False}) as mock_summary:
            tools.clip_view()

        mock_summary.assert_called_once_with(img="clip")

    def test_clip_summary_refreshes_clipboard_each_call(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.config import Config

        img_a = _make_png_bytes()
        img_b = _make_png_bytes(101, 100)

        summary_payload = {
            "type": "ui",
            "mode": "light",
            "colours": ["green"],
            "description": "desc",
            "content": "content",
        }
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(summary_payload)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config", return_value=Config(session_cache_size=10, model="openai/gpt-4o-mini")),
            patch("ottools._image.sources._grab_clipboard", side_effect=[img_a, img_b]) as mock_clip,
            patch("ottools._image.vision.OpenAI") as MockOAI,
            patch("ottools._image.tools.threading.Thread"),
        ):
            MockOAI.return_value.chat.completions.create.return_value = mock_resp
            tools._clip_handle = None
            first = tools.summary(img="clip")
            second = tools.summary(img="clip")

        assert first["handle"] != second["handle"]
        assert mock_clip.call_count == 2


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestLifecycle:
    """Tests for list_images(), delete_image(), purge_images()."""

    def _write_meta(self, tmp_path: Path, handle_name: str, **overrides: Any) -> None:
        """Write a minimal meta.json for a handle."""
        meta = {
            "handle": handle_name,
            "source": "file",
            "hash": "a" * 64,
            "original_dims": [100, 100],
            "model_dims": [100, 100],
            "resized": False,
            "max_edge": 1568,
            "original_format": "PNG",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary": None,
        }
        meta.update(overrides)
        (tmp_path / f"{handle_name}.meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        (tmp_path / f"{handle_name}.png").write_bytes(_make_png_bytes())

    def test_list_empty_dir(self, tmp_path: Path) -> None:
        from ottools._image.lifecycle import list_images

        with patch("ottools._image.lifecycle._images_dir", return_value=tmp_path):
            result = list_images()

        assert result == []

    def test_list_with_images(self, tmp_path: Path) -> None:
        from ottools._image.lifecycle import list_images

        self._write_meta(tmp_path, "img_aaaabbbb")
        self._write_meta(tmp_path, "img_ccccdddd")

        with patch("ottools._image.lifecycle._images_dir", return_value=tmp_path):
            result = list_images()

        assert len(result) == 2
        handles = {r["handle"] for r in result}
        assert "#img_aaaabbbb" in handles
        assert "#img_ccccdddd" in handles

    def test_delete_known_handle(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import delete_image

        self._write_meta(tmp_path, "img_deleteme")

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = delete_image(handle="#img_deleteme")

        assert result["deleted"] == "#img_deleteme"
        assert "bytes_freed" in result
        assert not (tmp_path / "img_deleteme.png").exists()
        assert not (tmp_path / "img_deleteme.meta.json").exists()

    def test_delete_unknown_handle_returns_error(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import delete_image

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = delete_image(handle="#img_notexist")

        assert "error" in result
        assert "not found" in result["error"]

    def test_purge_all_deletes_everything(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import purge_images

        self._write_meta(tmp_path, "img_purge1")
        self._write_meta(tmp_path, "img_purge2")

        with (
            patch("ottools._image.lifecycle._images_dir", return_value=tmp_path),
            patch.object(store, "_images_dir", return_value=tmp_path),
        ):
            result = purge_images(all=True)

        assert result["deleted"] == 2
        assert not list(tmp_path.glob("*.meta.json"))

    def test_purge_by_age_skips_recent(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import purge_images

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        new_ts = datetime.now(timezone.utc).isoformat()

        self._write_meta(tmp_path, "img_old", created_at=old_ts)
        self._write_meta(tmp_path, "img_new", created_at=new_ts)

        with (
            patch("ottools._image.lifecycle._images_dir", return_value=tmp_path),
            patch.object(store, "_images_dir", return_value=tmp_path),
        ):
            result = purge_images(minutes=120)

        assert result["deleted"] == 1
        assert (tmp_path / "img_new.meta.json").exists()
        assert not (tmp_path / "img_old.meta.json").exists()

    def test_purge_zero_minutes_raises(self) -> None:
        from ottools._image.lifecycle import purge_images

        with pytest.raises(ValueError, match="positive"):
            purge_images(minutes=0)

    def test_purge_default_skips_recent_images(self, tmp_path: Path) -> None:
        """purge_images() default (minutes=15) leaves images created just now."""
        from ottools._image import store
        from ottools._image.lifecycle import purge_images

        self._write_meta(tmp_path, "img_fresh")  # created_at = now

        with (
            patch("ottools._image.lifecycle._images_dir", return_value=tmp_path),
            patch.object(store, "_images_dir", return_value=tmp_path),
        ):
            result = purge_images()

        assert result["deleted"] == 0


# ---------------------------------------------------------------------------
# Constants test
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestPackConstants:
    """Verify image is registered in PACK_SHORT_NAMES."""

    def test_image_short_alias(self) -> None:
        from ot.meta._constants import PACK_SHORT_NAMES

        assert PACK_SHORT_NAMES.get("ot_image") == "img"
