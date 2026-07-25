"""Unit tests for the image pack.

Covers config loading, source resolution, resize, store, vision, tools, and
lifecycle — all with mocked I/O and no network calls.
"""

from __future__ import annotations

import base64
import hashlib
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


def _canonical_handle(seed: str) -> str:
    return f"img_{hashlib.sha256(seed.encode()).hexdigest()}"


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
        "hash": sha or handle_name.removeprefix("img_"),
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
    def test_defaults(
        self, _mock_llm: MagicMock, mock_secret: MagicMock, mock_gtc: MagicMock
    ) -> None:
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

        fmt = validate_image_bytes(
            b"<svg xmlns='http://www.w3.org/2000/svg'>", "icon.svg"
        )
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

        fmt = validate_image_bytes(
            b"<SVG xmlns='http://www.w3.org/2000/svg'>", "icon.svg"
        )
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

    def test_handle_rejected_as_load_source(self) -> None:
        from ottools._image.sources import ImageSourceError, resolve_source

        handle = f"#{_canonical_handle('source')}"
        with pytest.raises(ImageSourceError, match="sources"):
            resolve_source(handle)

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

    @pytest.mark.skipif(
        sys.platform == "linux", reason="clipboard not supported on Linux"
    )
    def test_clipboard_file_reference_loads_first_path(self, tmp_path: Path) -> None:
        """list return from ImageGrab.grabclipboard() resolves to first path."""
        from ottools._image.sources import _grab_clipboard

        png = _make_png_bytes()
        img_path = tmp_path / "shot.png"
        img_path.write_bytes(png)

        with patch("PIL.ImageGrab.grabclipboard", return_value=[str(img_path)]):
            result = _grab_clipboard()

        assert result == png

    @pytest.mark.skipif(
        sys.platform == "linux", reason="clipboard not supported on Linux"
    )
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
                mock_img.save = MagicMock(
                    side_effect=lambda buf, format: buf.write(b"\x89PNG\r\n\x1a\n")
                )
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

    @pytest.mark.skipif(
        not _CAIROSVG_AVAILABLE, reason="cairosvg/libcairo not available"
    )
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

        handle = _canonical_handle("round-trip")
        with patch.object(store, "_images_dir", return_value=tmp_path):
            store.save_image(_make_png_bytes(), handle, _make_meta(handle), fmt="PNG")
            loaded = store.load_meta(handle)
            assert loaded is not None
            assert loaded["handle"] == handle

    def test_load_meta_returns_none_for_missing(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = store.load_meta(_canonical_handle("missing"))
            assert result is None

    def test_save_summary_writes_in_place(self, tmp_path: Path) -> None:
        from ottools._image import store

        handle = _canonical_handle("summary")
        with patch.object(store, "_images_dir", return_value=tmp_path):
            store.save_image(
                _make_png_bytes(),
                handle,
                _make_meta(handle, dims=[50, 50]),
                fmt="PNG",
            )
            store.save_summary(handle, {"text": "hello", "mode": "light"})
            loaded = store.load_meta(handle)
            assert loaded is not None
            assert loaded["summary"]["text"] == "hello"

    def test_save_summary_atomic_leaves_no_tmp_file(self, tmp_path: Path) -> None:
        from ottools._image import store

        handle = _canonical_handle("atomic")
        with patch.object(store, "_images_dir", return_value=tmp_path):
            store.save_image(_make_png_bytes(), handle, _make_meta(handle), fmt="PNG")
            store.save_summary(handle, {"type": "ui"})

        assert not list(tmp_path.glob("*.tmp"))
        loaded = json.loads(
            (tmp_path / f"{handle}.meta.json").read_text(encoding="utf-8")
        )
        assert loaded["summary"] == {"type": "ui"}

    def test_save_summary_concurrent_writes_stay_valid(self, tmp_path: Path) -> None:
        """Concurrent save_summary calls (daemon vs main thread) never tear meta.json."""
        import threading

        from ottools._image import store

        handle = _canonical_handle("race")
        with patch.object(store, "_images_dir", return_value=tmp_path):
            store.save_image(_make_png_bytes(), handle, _make_meta(handle), fmt="PNG")

            def worker(i: int) -> None:
                for _ in range(20):
                    store.save_summary(handle, {"type": f"t{i}"})

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            final = store.load_meta(handle)  # raises if JSON is torn

        assert final is not None
        assert final["summary"]["type"] in {"t0", "t1", "t2", "t3"}

    def test_complete_hash_maps_to_exact_handle(self) -> None:
        from ottools._image import store

        sha = "a" * 64
        assert store.handle_name_for_hash(sha) == f"img_{sha}"

    def test_hash_scan_api_removed(self) -> None:
        from ottools._image import store

        assert not hasattr(store, "find_by_hash")

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
        handles = [_canonical_handle(seed) for seed in ("a", "b", "c")]
        for handle in handles:
            store.cache_put(handle, dummy)

        # Access "a" to make it MRU
        store.cache_get(handles[0])

        keys = store._session_cache.keys()
        assert keys[-1] == handles[0]

        store._session_cache.clear()

    def test_cache_evict_removes_handle(self) -> None:
        from ottools._image import store

        store._session_cache.clear()

        dummy = _make_png_bytes(10, 10)
        handle = _canonical_handle("evict")
        store.cache_put(handle, dummy)
        store.cache_evict(handle)

        assert store.cache_get(handle) is None

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
        result = call_vision([b"png"], "What is this?", config)
        assert result.startswith("Error:")
        assert "model" in result or "ot_image" in result

    def test_api_key_missing_returns_error(self) -> None:
        from ottools._image.vision import call_vision

        config = self._make_config()
        self._api_key_patch.stop()
        with patch("ottools._image.vision.get_image_api_key", return_value=None):
            result = call_vision([b"png"], "What is this?", config)
        self._api_key_patch.start()
        assert result.startswith("Error:")

    def test_single_question_call(self) -> None:
        from ottools._image.vision import ask_questions

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "It is a cat."

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            answers = ask_questions(
                [_make_png_bytes()], ["What is in the image?"], config
            )

        assert answers == ["It is a cat."]

    def test_batch_questions_parsed_in_order(self) -> None:
        """Batched JSON response is parsed into ordered answers."""
        from ottools._image.vision import ask_questions

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {"answers": ["A screenshot of a terminal.", "Yes, it is dark mode."]}
        )

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            create = MockOpenAI.return_value.chat.completions.create
            create.return_value = mock_response
            answers = ask_questions(
                [_make_png_bytes()],
                ["What is shown?", "Is it dark mode?"],
                config,
            )

        assert answers == ["A screenshot of a terminal.", "Yes, it is dark mode."]
        assert create.call_count == 1  # no fallback

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
            result = call_vision([_make_png_bytes()], "test", config)

        assert result.startswith("Error:")

    def test_batch_fenced_json_with_preamble_parsed(self) -> None:
        """Fenced / preambled JSON is still recovered without fallback."""
        from ottools._image.vision import ask_questions

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[
            0
        ].message.content = (
            'Here you go:\n```json\n{"answers": ["A terminal.", "Dark mode."]}\n```'
        )

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            create = MockOpenAI.return_value.chat.completions.create
            create.return_value = mock_response
            answers = ask_questions(
                [_make_png_bytes()],
                ["What is shown?", "Is it dark mode?"],
                config,
            )

        assert answers == ["A terminal.", "Dark mode."]
        assert create.call_count == 1

    def test_malformed_batch_response_falls_back_per_question(self) -> None:
        """Non-JSON batched response triggers one call per question, in order."""
        from ottools._image.vision import ask_questions

        config = self._make_config()

        def _resp(text: str) -> MagicMock:
            m = MagicMock()
            m.choices[0].message.content = text
            return m

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            create = MockOpenAI.return_value.chat.completions.create
            create.side_effect = [
                _resp("**1.** Python code editor.\n**2.** Light mode."),  # bad batch
                _resp("Python code editor."),
                _resp("Light mode."),
            ]
            answers = ask_questions(
                [_make_png_bytes()],
                ["What is shown?", "What is the colour mode?"],
                config,
            )

        assert answers == ["Python code editor.", "Light mode."]
        assert create.call_count == 3

    def test_answer_count_mismatch_falls_back(self) -> None:
        """Valid JSON with the wrong answer count triggers the fallback."""
        from ottools._image.vision import ask_questions

        config = self._make_config()

        def _resp(text: str) -> MagicMock:
            m = MagicMock()
            m.choices[0].message.content = text
            return m

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            create = MockOpenAI.return_value.chat.completions.create
            create.side_effect = [
                _resp(json.dumps({"answers": ["only one"]})),
                _resp("Answer one."),
                _resp("Answer two."),
            ]
            answers = ask_questions(
                [_make_png_bytes()],
                ["Q1?", "Q2?"],
                config,
            )

        assert answers == ["Answer one.", "Answer two."]
        assert create.call_count == 3

    def test_batch_api_error_short_circuits_without_fallback(self) -> None:
        """An API error on the batched call returns [error] with no retries."""
        from ottools._image.vision import ask_questions

        config = self._make_config()

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            create = MockOpenAI.return_value.chat.completions.create
            create.side_effect = RuntimeError("Connection refused")
            answers = ask_questions(
                [_make_png_bytes()],
                ["Q1?", "Q2?"],
                config,
            )

        assert len(answers) == 1
        assert answers[0].startswith("Error:")
        assert create.call_count == 1

    def test_multi_image_call_interleaves_labels(self) -> None:
        """Multi-image calls send labelled image blocks in order."""
        from ottools._image.vision import call_vision

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "They differ in colour."

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            create = MockOpenAI.return_value.chat.completions.create
            create.return_value = mock_response
            result = call_vision([b"img-one", b"img-two"], "what differs?", config)

        assert result == "They differ in colour."
        content = create.call_args.kwargs["messages"][0]["content"]
        kinds = [block["type"] for block in content]
        assert kinds == ["text", "image_url", "text", "image_url", "text"]
        assert content[0]["text"] == "Image 1:"
        assert content[2]["text"] == "Image 2:"

    def test_extract_summary_uses_shared_json_helper(self) -> None:
        """extract_summary() parses via parse_json_payload (fenced JSON works)."""
        from ottools._image.vision import extract_summary

        config = self._make_config()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '```json\n{"type": "photo", "mode": "light", "colours": ["red"], '
            '"description": "d", "content": "c"}\n```'
        )

        with patch("ottools._image.vision.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response
            result = extract_summary(_make_png_bytes(), config)

        assert isinstance(result, dict)
        assert result["type"] == "photo"


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
            h1 = tools.load(img=str(img_path))
            h2 = tools.load(img=str(img_path))

        assert h1["handle"] == h2["handle"]

    def test_custom_handle_parameter_removed(self, tmp_path: Path) -> None:
        from ottools._image import tools

        path = tmp_path / "a.png"
        path.write_bytes(_make_png_bytes())
        with pytest.raises(TypeError, match="handle"):
            tools.load(img=str(path), handle="myref")  # type: ignore[call-arg]

    def test_linux_clipboard_returns_error(self) -> None:
        from ottools._image import tools

        with patch("ottools._image.sources.sys.platform", "linux"):
            result = tools.load(img="clip")

        assert "error" in result
        assert "linux" in result["error"].lower()

    def test_clipboard_missing_pillow_returns_friendly_error(self) -> None:
        from ottools._image import tools

        with patch(
            "ottools._image.sources._grab_clipboard",
            side_effect=ImportError(
                "Pillow is required for clipboard capture. Install with: pip install Pillow"
            ),
        ):
            result = tools.load(img="clip")

        assert "error" in result
        assert "missing optional dependency" in result["error"]
        assert "pip install Pillow" in result["error"]

    def test_missing_decoder_returns_friendly_error(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        png = _make_png_bytes()
        img_path = tmp_path / "dep_test.png"
        img_path.write_bytes(png)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch(
                "ottools._image.tools.prepare_for_model",
                side_effect=ImportError(
                    "resvg-py is required for SVG support. Install with: pip install resvg-py"
                ),
            ),
        ):
            result = tools.load(img=str(img_path))

        assert "error" in result
        assert "missing optional dependency" in result["error"]
        assert "pip install resvg-py" in result["error"]

    def test_clip_handle_state_removed(self) -> None:
        from ottools._image import tools

        assert not hasattr(tools, "_clip_handle")

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
            mock_t = MagicMock()
            mock_thread.return_value = mock_t

            tools.load(img=str(img_path))

        # Thread should have been created and started for background summary
        mock_thread.assert_called_once()
        call_kwargs = mock_thread.call_args
        assert call_kwargs.kwargs.get("daemon") is True
        mock_t.start.assert_called_once()

    def test_background_summary_not_spawned_when_no_model(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.config import Config

        path = tmp_path / "no-model.png"
        path.write_bytes(_make_png_bytes())
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch(
                "ottools._image.tools.get_image_config",
                return_value=Config(session_cache_size=10, model=""),
            ),
            patch("ottools._image.tools.threading.Thread") as mock_thread,
        ):
            tools.load(img=str(path))

        mock_thread.assert_not_called()


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
        assert result["result"] == [
            {"question": "Describe the image.", "answer": "A red square."}
        ]
        assert result["handle"] == handle

    def test_unknown_handle_returns_error(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            from ottools._image.config import Config

            mock_cfg.return_value = Config(session_cache_size=10)
            missing = f"#{_canonical_handle('missing')}"
            result = tools.ask(img=missing, q="test")

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
            handle = tools.load(img=str(img_path))["handle"]
            result = tools.ask(img=handle, q="test")

        # Vision model error surfaces as top-level error dict
        assert "error" in result
        assert result["error"].startswith("Error:")

    def test_bare_handle_name_rejected(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            handle = self._setup(tmp_path, mock_cfg)
            bare = handle.lstrip("#")  # strip the "#" prefix

            with patch("ottools._image.vision.OpenAI") as MockOAI:
                result = tools.ask(img=bare, q="Describe the image.")

        assert "error" in result
        assert "# prefix" in result["error"]
        MockOAI.assert_not_called()

    def test_clip_ask_refreshes_clipboard_each_call(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.config import Config

        img_a = _make_png_bytes()
        img_b = _make_png_bytes(101, 100)

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch("ottools._image.tools.ask_questions", return_value=["ok"]),
            patch(
                "ottools._image.sources._grab_clipboard", side_effect=[img_a, img_b]
            ) as mock_clip,
        ):
            mock_cfg.return_value = Config(
                session_cache_size=10, model="openai/gpt-4o-mini"
            )
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
            handle = tools.load(img=str(img_path))["handle"]
            tools.summary(img=handle)  # First call
            result = tools.summary(img=handle)  # Second call — should be cached

        assert result["cached"] is True
        # Model should only have been called once
        assert MockOAI.return_value.chat.completions.create.call_count == 1

    def test_auto_load_uses_configured_max_edge(self, tmp_path: Path) -> None:
        """summary() auto-load passes config.max_edge through to load()."""
        from ottools._image import store, tools
        from ottools._image.config import Config

        png = _make_png_bytes()
        img_path = tmp_path / "sum_edge.png"
        img_path.write_bytes(png)

        summary_data = {
            "type": "ui",
            "mode": "light",
            "colours": [],
            "description": "d",
            "content": "c",
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
                max_edge=512,
            )
            MockOAI.return_value.chat.completions.create.return_value = mock_resp

            result = tools.summary(img=str(img_path))  # auto-load path
            meta = store.load_meta(result["handle"].lstrip("#"))

        assert meta is not None
        assert meta["max_edge"] == 512

    def test_clip_ask_delegates_to_ask(self, tmp_path: Path) -> None:
        from ottools._image import tools

        with patch.object(
            tools, "ask", return_value={"result": [], "handle": "#h"}
        ) as mock_ask:
            tools.clip_ask(q="What is this?")

        mock_ask.assert_called_once_with(img="clip", q="What is this?", max_edge=1568)

    def test_clip_ask_custom_max_edge(self, tmp_path: Path) -> None:
        from ottools._image import tools

        with patch.object(
            tools, "ask", return_value={"result": [], "handle": "#h"}
        ) as mock_ask:
            tools.clip_ask(q="Describe", max_edge=800)

        mock_ask.assert_called_once_with(img="clip", q="Describe", max_edge=800)

    def test_clip_view_delegates_to_summary(self, tmp_path: Path) -> None:
        from ottools._image import tools

        with patch.object(
            tools,
            "summary",
            return_value={"summary": {}, "handle": "#h", "cached": False},
        ) as mock_summary:
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
            patch(
                "ottools._image.tools.get_image_config",
                return_value=Config(session_cache_size=10, model="openai/gpt-4o-mini"),
            ),
            patch(
                "ottools._image.sources._grab_clipboard", side_effect=[img_a, img_b]
            ) as mock_clip,
            patch("ottools._image.vision.OpenAI") as MockOAI,
            patch("ottools._image.tools.threading.Thread"),
        ):
            MockOAI.return_value.chat.completions.create.return_value = mock_resp
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

    def _write_meta(self, tmp_path: Path, seed: str, **overrides: Any) -> str:
        """Write a minimal meta.json for a handle."""
        handle_name = _canonical_handle(seed)
        meta = {
            "handle": handle_name,
            "source": "file",
            "hash": handle_name.removeprefix("img_"),
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
        return handle_name

    def test_list_empty_dir(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import list_images

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = list_images()

        assert result == []

    def test_list_with_images(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import list_images

        first = self._write_meta(tmp_path, "first")
        second = self._write_meta(tmp_path, "second")

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = list_images()

        assert len(result) == 2
        handles = {r["handle"] for r in result}
        assert f"#{first}" in handles
        assert f"#{second}" in handles

    def test_delete_known_handle(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import delete_image

        handle = self._write_meta(tmp_path, "delete")

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = delete_image(handle=f"#{handle}")

        assert result["deleted"] == f"#{handle}"
        assert "bytes_freed" in result
        assert not (tmp_path / f"{handle}.png").exists()
        assert not (tmp_path / f"{handle}.meta.json").exists()

    def test_delete_unknown_handle_returns_error(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import delete_image

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = delete_image(handle=f"#{_canonical_handle('not-exist')}")

        assert "error" in result
        assert "not found" in result["error"]

    def test_purge_all_deletes_everything(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import purge_images

        self._write_meta(tmp_path, "purge-1")
        self._write_meta(tmp_path, "purge-2")

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = purge_images(all=True)

        assert result["purged"] == 2
        assert "deleted" not in result
        assert not list(tmp_path.glob("*.meta.json"))

    def test_purge_by_age_skips_recent(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import purge_images

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        new_ts = datetime.now(timezone.utc).isoformat()

        old_handle = self._write_meta(tmp_path, "old", created_at=old_ts)
        new_handle = self._write_meta(tmp_path, "new", created_at=new_ts)

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = purge_images(minutes=120)

        assert result["purged"] == 1
        assert (tmp_path / f"{new_handle}.meta.json").exists()
        assert not (tmp_path / f"{old_handle}.meta.json").exists()

    def test_purge_zero_minutes_raises(self) -> None:
        from ottools._image.lifecycle import purge_images

        with pytest.raises(ValueError, match="positive"):
            purge_images(minutes=0)

    def test_purge_default_skips_recent_images(self, tmp_path: Path) -> None:
        """purge_images() default (minutes=15) leaves images created just now."""
        from ottools._image import store
        from ottools._image.lifecycle import purge_images

        self._write_meta(tmp_path, "fresh")  # created_at = now

        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = purge_images()

        assert result["purged"] == 0


# ---------------------------------------------------------------------------
# Constants test
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestPackConstants:
    """Verify image declares metadata aliases."""

    def test_image_short_alias(self) -> None:
        import ottools.ot_image as image

        assert image.pack_aliases == ("img",)


# ---------------------------------------------------------------------------
# Format-preserving storage + multi-image ask (ot-image-capabilities)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestStoreExtensions:
    """Stored originals keep their source-format extension (design D2)."""

    def setup_method(self) -> None:
        self._thread_patcher = patch("ottools._image.tools.threading.Thread")
        self._thread_patcher.start().return_value = MagicMock()

    def teardown_method(self) -> None:
        self._thread_patcher.stop()

    def _load(self, tmp_path: Path, data: bytes, name: str) -> str:
        from ottools._image import store, tools
        from ottools._image.config import Config

        img_path = tmp_path / name
        img_path.write_bytes(data)
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            mock_cfg.return_value = Config(session_cache_size=10)
            result = tools.load(img=str(img_path))
        assert "error" not in result, result
        return str(result["handle"]).lstrip("#")

    def test_jpeg_stored_as_jpg_without_file_meta(self, tmp_path: Path) -> None:
        from ottools._image import store

        handle = self._load(tmp_path, _make_jpeg_bytes(), "photo.jpeg")
        assert (tmp_path / f"{handle}.jpg").exists()
        assert not (tmp_path / f"{handle}.png").exists()
        with patch.object(store, "_images_dir", return_value=tmp_path):
            meta = store.load_meta(handle)
        assert meta is not None
        assert "file" not in meta
        assert meta["original_format"] == "JPEG"

    def test_svg_stored_as_svg(self, tmp_path: Path) -> None:
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>'
        handle = self._load(tmp_path, svg, "shape.svg")
        assert (tmp_path / f"{handle}.svg").exists()
        assert (tmp_path / f"{handle}.svg").read_bytes() == svg

    def test_legacy_short_handle_is_rejected(self, tmp_path: Path) -> None:
        from ottools._image import store

        png = _make_png_bytes()
        (tmp_path / "img_legacy1.png").write_bytes(png)
        (tmp_path / "img_legacy1.meta.json").write_text(
            json.dumps({"handle": "img_legacy1", "hash": "x"}), encoding="utf-8"
        )
        with patch.object(store, "_images_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="64 lowercase"):
                store.load_raw_bytes("img_legacy1")
        assert (tmp_path / "img_legacy1.png").read_bytes() == png
        assert (tmp_path / "img_legacy1.meta.json").exists()

    def test_delete_frees_non_png_content_files(self, tmp_path: Path) -> None:
        from ottools._image import store

        handle = self._load(tmp_path, _make_jpeg_bytes(), "photo.jpeg")
        jpg_size = (tmp_path / f"{handle}.jpg").stat().st_size
        with patch.object(store, "_images_dir", return_value=tmp_path):
            found, freed = store.delete_handle_files(handle)
        assert found is True
        assert freed >= jpg_size
        assert not list(tmp_path.glob(f"{handle}.*"))

    def test_purge_frees_non_png_entries(self, tmp_path: Path) -> None:
        from ottools._image import lifecycle, store

        handle = self._load(tmp_path, _make_jpeg_bytes(), "photo.jpeg")
        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = lifecycle.purge_images(all=True)
        assert result["purged"] >= 1
        assert result["bytes_freed"] > 0
        assert not (tmp_path / f"{handle}.jpg").exists()


@pytest.mark.unit
@pytest.mark.tools
class TestAskMultiImage:
    """ask() with a list of image references (design D1)."""

    def setup_method(self) -> None:
        import ottools._image.vision as _v

        _v._client = None
        _v._client_key = ("", "")
        self._thread_patcher = patch("ottools._image.tools.threading.Thread")
        self._thread_patcher.start().return_value = MagicMock()
        self._api_key_patch = patch(
            "ottools._image.vision.get_image_api_key", return_value="sk-test"
        )
        self._api_key_patch.start()

    def teardown_method(self) -> None:
        self._thread_patcher.stop()
        self._api_key_patch.stop()

    def _load_two(self, tmp_path: Path, mock_cfg: MagicMock) -> tuple[str, str]:
        from ottools._image import store, tools
        from ottools._image.config import Config

        mock_cfg.return_value = Config(
            session_cache_size=10, model="openai/gpt-4o-mini"
        )
        (tmp_path / "a.png").write_bytes(_make_png_bytes(20, 20))
        (tmp_path / "b.png").write_bytes(_make_png_bytes(40, 40))
        with patch.object(store, "_images_dir", return_value=tmp_path):
            h1 = tools.load(img=str(tmp_path / "a.png"))["handle"]
            h2 = tools.load(img=str(tmp_path / "b.png"))["handle"]
        return h1, h2

    def test_two_handles_return_handles_list_and_ordered_payloads(
        self, tmp_path: Path
    ) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            h1, h2 = self._load_two(tmp_path, mock_cfg)

            captured: dict[str, Any] = {}

            def fake_ask(
                images: list[bytes], questions: list[str], config: Any
            ) -> list[str]:
                captured["images"] = images
                return ["they differ"]

            with patch("ottools._image.tools.ask_questions", side_effect=fake_ask):
                result = tools.ask(img=[h1, h2], q="what differs?")

        assert result["handles"] == [h1, h2]
        assert "handle" not in result
        assert len(captured["images"]) == 2
        assert captured["images"][0] != captured["images"][1]

    def test_single_element_list_returns_handles_key(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            h1, _ = self._load_two(tmp_path, mock_cfg)
            with patch("ottools._image.tools.ask_questions", return_value=["one"]):
                result = tools.ask(img=[h1], q="q?")

        assert result["handles"] == [h1]
        assert "handle" not in result

    def test_string_input_still_returns_handle_key(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
        ):
            h1, _ = self._load_two(tmp_path, mock_cfg)
            with patch("ottools._image.tools.ask_questions", return_value=["one"]):
                result = tools.ask(img=h1, q="q?")

        assert result["handle"] == h1
        assert "handles" not in result

    def test_empty_list_and_cap_error_without_model_call(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch("ottools._image.tools.ask_questions") as mock_ask,
        ):
            from ottools._image.config import Config

            mock_cfg.return_value = Config(session_cache_size=10)
            empty = tools.ask(img=[], q="q?")
            over = tools.ask(img=[f"#h{i}" for i in range(9)], q="q?")

        assert empty["error"] == "img list is empty"
        assert "8" in over["error"]
        mock_ask.assert_not_called()

    def test_unresolvable_entry_fails_fast_naming_reference(
        self, tmp_path: Path
    ) -> None:
        from ottools._image import store, tools

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch("ottools._image.tools.ask_questions") as mock_ask,
        ):
            h1, _ = self._load_two(tmp_path, mock_cfg)
            result = tools.ask(img=[h1, str(tmp_path / "missing.png")], q="q?")

        assert "error" in result
        assert result["handle"] == str(tmp_path / "missing.png")
        mock_ask.assert_not_called()
