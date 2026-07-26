"""Unit tests for the image pack.

Covers config loading, source resolution, resize, store, vision, tools, and
lifecycle — all with mocked I/O and no network calls.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from ot.generation import GenerationError

if TYPE_CHECKING:
    from pathlib import Path

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


def _generation_result(content: str) -> SimpleNamespace:
    return SimpleNamespace(content=content)


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
        "created_at": datetime.now(UTC).isoformat(),
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
    def test_defaults(self, mock_gtc: MagicMock) -> None:
        from ottools._image.config import Config, get_image_config

        mock_gtc.return_value = Config()
        config = get_image_config()
        assert config.max_edge == 1568
        assert config.session_cache_size == 10
        assert config.llm is None

    def test_partial_generation_selection(self) -> None:
        from ottools._image.config import Config

        config = Config.model_validate({"llm": {"model": "terra", "effort": "high"}})
        assert config.llm is not None
        assert config.llm.model == "terra"

    def test_removed_provider_fields_are_rejected(self) -> None:
        from pydantic import ValidationError

        from ottools._image.config import Config

        for key in ("model", "base_url"):
            with pytest.raises(ValidationError, match="extra_forbidden"):
                Config.model_validate({key: "removed"})


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

        with (
            patch("PIL.ImageGrab.grabclipboard", return_value=[]),
            pytest.raises(ValueError, match="No image found in clipboard"),
        ):
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
        from unittest.mock import MagicMock, patch

        from ottools._image.resize import prepare_for_model

        # Fake HEIC bytes (ISOBMFF with heic brand)
        heic_bytes = b"\x00\x00\x00\x18" + b"ftyp" + b"heic" + b"\x00" * 100

        mock_heif = MagicMock()
        mock_img = MagicMock()
        mock_img.format = "HEIF"
        mock_img.width = 50
        mock_img.height = 50
        mock_img.mode = "RGB"

        with (
            patch.dict("sys.modules", {"pillow_heif": mock_heif}),
            patch("PIL.Image.open", return_value=mock_img),
        ):
            mock_img.resize.return_value = mock_img
            mock_img.save = MagicMock(
                side_effect=lambda buf, **_: buf.write(b"\x89PNG\r\n\x1a\n")
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
            with (
                patch.dict("sys.modules", {"pillow_heif": None}),
                pytest.raises(ImportError, match="pillow-heif"),
            ):
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
        with (
            patch.dict("sys.modules", {"resvg_py": None}),
            pytest.raises(ImportError, match="resvg-py"),
        ):
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
            store.save_image(
                _make_png_bytes(), "img_abc12345", _make_meta("img_abc12345")
            )
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
            store.save_image(
                _make_png_bytes(), "img_test1", _make_meta("img_test1", dims=[50, 50])
            )
            store.save_summary("img_test1", {"text": "hello", "mode": "light"})
            loaded = store.load_meta("img_test1")
            assert loaded is not None
            assert loaded["summary"]["text"] == "hello"

    def test_save_summary_atomic_leaves_no_tmp_file(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            store.save_image(_make_png_bytes(), "img_atomic", _make_meta("img_atomic"))
            store.save_summary("img_atomic", {"type": "ui"})

        assert not list(tmp_path.glob("*.tmp"))
        loaded = json.loads(
            (tmp_path / "img_atomic.meta.json").read_text(encoding="utf-8")
        )
        assert loaded["summary"] == {"type": "ui"}

    def test_save_summary_concurrent_writes_stay_valid(self, tmp_path: Path) -> None:
        """Concurrent save_summary calls (daemon vs main thread) never tear meta.json."""
        import threading

        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            store.save_image(_make_png_bytes(), "img_race", _make_meta("img_race"))

            def worker(i: int) -> None:
                for _ in range(20):
                    store.save_summary("img_race", {"type": f"t{i}"})

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            final = store.load_meta("img_race")  # raises if JSON is torn

        assert final is not None
        assert final["summary"]["type"] in {"t0", "t1", "t2", "t3"}

    def test_find_by_hash_returns_existing(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            sha = "a" * 64
            store.save_image(
                _make_png_bytes(10, 10),
                "img_aaaaaaaa",
                _make_meta("img_aaaaaaaa", dims=[10, 10], sha=sha),
            )
            found = store.find_by_hash(sha)
            assert found == "img_aaaaaaaa"

    def test_find_by_hash_returns_none_for_unknown(self, tmp_path: Path) -> None:
        from ottools._image import store

        with patch.object(store, "_images_dir", return_value=tmp_path):
            assert store.find_by_hash("b" * 64) is None

    def test_lru_eviction_at_limit(self) -> None:
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

    def _make_config(self, **kwargs: Any) -> Any:
        from ottools._image.config import Config

        defaults = {
            "llm": {"model": "test-gemini"},
            "max_edge": 1568,
            "session_cache_size": 10,
        }
        defaults.update(kwargs)
        return Config(**defaults)

    def test_vision_not_configured_returns_error(self) -> None:
        from ottools._image.vision import call_vision

        config = self._make_config(llm=None)
        with patch(
            "ottools._image.vision.resolve_generation",
            side_effect=GenerationError("No generation route is configured"),
        ):
            result = call_vision([b"png"], "What is this?", config)
        assert result.startswith("Error:")
        assert "generation route" in result

    def test_api_key_missing_returns_error(self) -> None:
        from ottools._image.vision import call_vision

        config = self._make_config()
        with patch(
            "ottools._image.vision.generate",
            side_effect=GenerationError("Named generation secret is not configured"),
        ):
            result = call_vision([b"png"], "What is this?", config)
        assert result.startswith("Error:")

    def test_single_question_call(self) -> None:
        from ottools._image.vision import ask_questions

        config = self._make_config()
        with patch(
            "ottools._image.vision.generate",
            return_value=_generation_result("It is a cat."),
        ):
            answers = ask_questions(
                [_make_png_bytes()], ["What is in the image?"], config
            )

        assert answers == ["It is a cat."]

    def test_batch_questions_parsed_in_order(self) -> None:
        """Batched JSON response is parsed into ordered answers."""
        from ottools._image.vision import ask_questions

        config = self._make_config()
        response = json.dumps(
            {"answers": ["A screenshot of a terminal.", "Yes, it is dark mode."]}
        )
        with patch(
            "ottools._image.vision.generate",
            return_value=_generation_result(response),
        ) as create:
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
        with patch(
            "ottools._image.vision.generate",
            return_value=_generation_result(summary_json),
        ):
            result = extract_summary(_make_png_bytes(), config)

        assert isinstance(result, dict)
        assert result["type"] == "screenshot"
        assert result["mode"] == "light"
        assert "Submit" in result["content"]

    def test_summary_fills_missing_keys(self) -> None:
        from ottools._image.vision import extract_summary

        config = self._make_config()
        # Only partial JSON from model
        with patch(
            "ottools._image.vision.generate",
            return_value=_generation_result('{"description": "A thing."}'),
        ):
            result = extract_summary(_make_png_bytes(), config)

        assert isinstance(result, dict)
        assert result["content"] == ""
        assert result["mode"] == "unknown"
        assert result["colours"] == []

    def test_api_error_returns_error_string(self) -> None:
        from ottools._image.vision import call_vision

        config = self._make_config()

        with patch(
            "ottools._image.vision.generate",
            side_effect=GenerationError("Generation endpoint is unavailable"),
        ):
            result = call_vision([_make_png_bytes()], "test", config)

        assert result.startswith("Error:")

    def test_batch_fenced_json_with_preamble_parsed(self) -> None:
        """Fenced / preambled JSON is still recovered without fallback."""
        from ottools._image.vision import ask_questions

        config = self._make_config()
        response = (
            'Here you go:\n```json\n{"answers": ["A terminal.", "Dark mode."]}\n```'
        )
        with patch(
            "ottools._image.vision.generate",
            return_value=_generation_result(response),
        ) as create:
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

        with patch("ottools._image.vision.generate") as create:
            create.side_effect = [
                _generation_result("**1.** Python code editor.\n**2.** Light mode."),
                _generation_result("Python code editor."),
                _generation_result("Light mode."),
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

        with patch("ottools._image.vision.generate") as create:
            create.side_effect = [
                _generation_result(json.dumps({"answers": ["only one"]})),
                _generation_result("Answer one."),
                _generation_result("Answer two."),
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

        with patch(
            "ottools._image.vision.generate",
            side_effect=GenerationError("Generation endpoint is unavailable"),
        ) as create:
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
        with patch(
            "ottools._image.vision.generate",
            return_value=_generation_result("They differ in colour."),
        ) as create:
            result = call_vision([b"img-one", b"img-two"], "what differs?", config)

        assert result == "They differ in colour."
        request = create.call_args.kwargs["request"]
        assert request.images == (b"img-one", b"img-two")
        assert "numeric order" in request.prompt

    def test_extract_summary_uses_shared_json_helper(self) -> None:
        """extract_summary() parses via parse_json_payload (fenced JSON works)."""
        from ottools._image.vision import extract_summary

        config = self._make_config()
        response = (
            '```json\n{"type": "photo", "mode": "light", "colours": ["red"], '
            '"description": "d", "content": "c"}\n```'
        )

        with patch(
            "ottools._image.vision.generate",
            return_value=_generation_result(response),
        ):
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
                llm={"model": "test-gemini"},
            )
            mock_t = MagicMock()
            mock_thread.return_value = mock_t

            tools.load(img=str(img_path))

        # Thread should have been created and started for background summary
        mock_thread.assert_called_once()
        call_kwargs = mock_thread.call_args
        assert call_kwargs.kwargs.get("daemon") is True
        mock_t.start.assert_called_once()

    def test_background_summary_worker_uses_shared_route(self) -> None:
        """Worker delegates route validation to the shared generation layer."""
        from ottools._image import tools
        from ottools._image.config import Config

        with (
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch("ottools._image.tools.extract_summary") as mock_extract,
        ):
            mock_cfg.return_value = Config(session_cache_size=10)
            mock_extract.return_value = "Error: generation route unavailable"
            tools._background_summarise("img_abc12345", b"fake_bytes")

        mock_extract.assert_called_once()


@pytest.mark.unit
@pytest.mark.tools
class TestAsk:
    """Tests for ask()."""

    def setup_method(self) -> None:
        self._thread_patcher = patch("ottools._image.tools.threading.Thread")
        self._mock_thread_cls = self._thread_patcher.start()
        self._mock_thread_cls.return_value = MagicMock()

    def teardown_method(self) -> None:
        self._thread_patcher.stop()

    def _setup(self, tmp_path: Path, mock_cfg: MagicMock) -> str:
        """Load a test image and return its handle name."""
        from ottools._image import store, tools
        from ottools._image.config import Config

        png = _make_png_bytes()
        img_path = tmp_path / "ask_test.png"
        img_path.write_bytes(png)

        mock_cfg.return_value = Config(
            session_cache_size=10,
            llm={"model": "test-gemini"},
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

            with patch(
                "ottools._image.tools.ask_questions",
                return_value=["A red square."],
            ):
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
            patch(
                "ottools._image.tools.ask_questions",
                return_value=["Error: generation route unavailable"],
            ),
        ):
            mock_cfg.return_value = Config(session_cache_size=10)
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

            with patch(
                "ottools._image.tools.ask_questions",
                return_value=["A red square."],
            ):
                result = tools.ask(img=bare, q="Describe the image.")

        assert "result" in result
        assert result["result"] == [
            {"question": "Describe the image.", "answer": "A red square."}
        ]

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
                session_cache_size=10,
                llm={"model": "test-gemini"},
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
        self._thread_patcher = patch("ottools._image.tools.threading.Thread")
        self._mock_thread_cls = self._thread_patcher.start()
        self._mock_thread_cls.return_value = MagicMock()

    def teardown_method(self) -> None:
        self._thread_patcher.stop()

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
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch(
                "ottools._image.tools.extract_summary",
                return_value=summary_data,
            ),
        ):
            mock_cfg.return_value = Config(
                session_cache_size=10,
                llm={"model": "test-gemini"},
            )
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
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch(
                "ottools._image.tools.extract_summary",
                return_value=summary_data,
            ) as extract,
        ):
            mock_cfg.return_value = Config(
                session_cache_size=10,
                llm={"model": "test-gemini"},
            )
            handle = tools.load(img=str(img_path))["handle"]
            tools.summary(img=handle)  # First call
            result = tools.summary(img=handle)  # Second call — should be cached

        assert result["cached"] is True
        # Model should only have been called once
        assert extract.call_count == 1

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
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.get_image_config") as mock_cfg,
            patch(
                "ottools._image.tools.extract_summary",
                return_value=summary_data,
            ),
        ):
            mock_cfg.return_value = Config(
                session_cache_size=10,
                llm={"model": "test-gemini"},
                max_edge=512,
            )
            result = tools.summary(img=str(img_path))  # auto-load path
            meta = store.load_meta(result["handle"].lstrip("#"))

        assert meta is not None
        assert meta["max_edge"] == 512

    def test_clip_ask_delegates_to_ask(self) -> None:
        from ottools._image import tools

        with patch.object(
            tools, "ask", return_value={"result": [], "handle": "#h"}
        ) as mock_ask:
            tools.clip_ask(q="What is this?")

        mock_ask.assert_called_once_with(
            img="clip",
            q="What is this?",
            max_edge=1568,
            model=None,
            effort=None,
        )

    def test_clip_ask_custom_max_edge(self) -> None:
        from ottools._image import tools

        with patch.object(
            tools, "ask", return_value={"result": [], "handle": "#h"}
        ) as mock_ask:
            tools.clip_ask(q="Describe", max_edge=800)

        mock_ask.assert_called_once_with(
            img="clip",
            q="Describe",
            max_edge=800,
            model=None,
            effort=None,
        )

    def test_clip_view_delegates_to_summary(self) -> None:
        from ottools._image import tools

        with patch.object(
            tools,
            "summary",
            return_value={"summary": {}, "handle": "#h", "cached": False},
        ) as mock_summary:
            tools.clip_view()

        mock_summary.assert_called_once_with(img="clip", model=None, effort=None)

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
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch(
                "ottools._image.tools.get_image_config",
                return_value=Config(
                    session_cache_size=10,
                    llm={"model": "test-gemini"},
                ),
            ),
            patch(
                "ottools._image.sources._grab_clipboard", side_effect=[img_a, img_b]
            ) as mock_clip,
            patch(
                "ottools._image.tools.extract_summary",
                return_value=summary_payload,
            ),
            patch("ottools._image.tools.threading.Thread"),
        ):
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
            "created_at": datetime.now(UTC).isoformat(),
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

        assert result["purged"] == 2
        assert "deleted" not in result
        assert not list(tmp_path.glob("*.meta.json"))

    def test_purge_by_age_skips_recent(self, tmp_path: Path) -> None:
        from ottools._image import store
        from ottools._image.lifecycle import purge_images

        old_ts = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
        new_ts = datetime.now(UTC).isoformat()

        self._write_meta(tmp_path, "img_old", created_at=old_ts)
        self._write_meta(tmp_path, "img_new", created_at=new_ts)

        with (
            patch("ottools._image.lifecycle._images_dir", return_value=tmp_path),
            patch.object(store, "_images_dir", return_value=tmp_path),
        ):
            result = purge_images(minutes=120)

        assert result["purged"] == 1
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

    def test_jpeg_stored_as_jpg_with_file_meta(self, tmp_path: Path) -> None:
        from ottools._image import store

        handle = self._load(tmp_path, _make_jpeg_bytes(), "photo.jpeg")
        assert (tmp_path / f"{handle}.jpg").exists()
        assert not (tmp_path / f"{handle}.png").exists()
        with patch.object(store, "_images_dir", return_value=tmp_path):
            meta = store.load_meta(handle)
        assert meta is not None
        assert meta["file"] == f"{handle}.jpg"

    def test_svg_stored_as_svg(self, tmp_path: Path) -> None:
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>'
        handle = self._load(tmp_path, svg, "shape.svg")
        assert (tmp_path / f"{handle}.svg").exists()
        assert (tmp_path / f"{handle}.svg").read_bytes() == svg

    def test_legacy_png_without_file_key_still_resolves(self, tmp_path: Path) -> None:
        from ottools._image import store

        png = _make_png_bytes()
        (tmp_path / "img_legacy1.png").write_bytes(png)
        (tmp_path / "img_legacy1.meta.json").write_text(
            json.dumps({"handle": "img_legacy1", "hash": "x"}), encoding="utf-8"
        )
        with patch.object(store, "_images_dir", return_value=tmp_path):
            assert store.load_raw_bytes("img_legacy1") == png
            found, freed = store.delete_handle_files("img_legacy1")
        assert found is True
        assert freed > 0
        assert not (tmp_path / "img_legacy1.png").exists()
        assert not (tmp_path / "img_legacy1.meta.json").exists()

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
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.lifecycle._images_dir", return_value=tmp_path),
        ):
            result = lifecycle.purge_images(all=True)
        assert result["purged"] >= 1
        assert result["bytes_freed"] > 0
        assert not (tmp_path / f"{handle}.jpg").exists()


@pytest.mark.unit
@pytest.mark.tools
class TestAskMultiImage:
    """ask() with a list of image references (design D1)."""

    def setup_method(self) -> None:
        self._thread_patcher = patch("ottools._image.tools.threading.Thread")
        self._thread_patcher.start().return_value = MagicMock()

    def teardown_method(self) -> None:
        self._thread_patcher.stop()

    def _load_two(self, tmp_path: Path, mock_cfg: MagicMock) -> tuple[str, str]:
        from ottools._image import store, tools
        from ottools._image.config import Config

        mock_cfg.return_value = Config(
            session_cache_size=10,
            llm={"model": "test-gemini"},
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
                images: list[bytes],
                _questions: list[str],
                _config: Any,
                **_: Any,
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
