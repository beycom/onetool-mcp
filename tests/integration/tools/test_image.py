"""Integration tests for the ot_image pack.

Exercises real PIL I/O with temp files — no vision API calls.
Store I/O is redirected to tmp_path to avoid polluting .onetool/images/.

Vision (ask/summary) requires a configured API key and is skipped when absent.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from .conftest import get_test_secret


def _make_png(tmp_path: Path, name: str = "test.png", size: tuple[int, int] = (100, 100)) -> Path:
    """Write a minimal PNG to tmp_path and return the path."""
    try:
        from PIL import Image as PIL_Image
    except ImportError:
        pytest.fail("Pillow not installed")
    img = PIL_Image.new("RGB", size, color=(0, 128, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    p = tmp_path / name
    p.write_bytes(buf.getvalue())
    return p


@pytest.mark.integration
@pytest.mark.tools
class TestImageLoad:
    """Load images from real files."""

    def test_load_returns_handle(self, tmp_path: Path) -> None:
        """load() from a file returns a valid handle with correct metadata."""
        from ottools._image import store
        from ottools.ot_image import load

        img_path = _make_png(tmp_path)
        with patch.object(store, "_images_dir", return_value=tmp_path):
            result = load(img=str(img_path))

        assert "handle" in result
        assert result["handle"].startswith("#img_")
        assert result["dims"] == [100, 100]
        assert result["dedup"] is False

    def test_load_dedup_same_file(self, tmp_path: Path) -> None:
        """Loading the same file twice returns the same handle."""
        from ottools._image import store
        from ottools.ot_image import load

        img_path = _make_png(tmp_path)
        with patch.object(store, "_images_dir", return_value=tmp_path):
            h1 = load(img=str(img_path))
            h2 = load(img=str(img_path))

        assert h1["handle"] == h2["handle"]
        assert h2["dedup"] is True


@pytest.mark.integration
@pytest.mark.tools
class TestImageLifecycle:
    """delete and purge reflect real store state."""

    def test_delete_removes_image(self, tmp_path: Path) -> None:
        """delete() removes the image from disk and from list()."""
        from ottools._image import store
        from ottools._image.lifecycle import delete_image, list_images
        from ottools.ot_image import load

        img_path = _make_png(tmp_path)
        with patch.object(store, "_images_dir", return_value=tmp_path):
            handle = load(img=str(img_path))["handle"]

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.lifecycle._images_dir", return_value=tmp_path),
        ):
            result = delete_image(handle=handle)
            handles = [r["handle"] for r in list_images()]

        assert result["deleted"] == handle
        assert handle not in handles

    def test_purge_removes_old_images(self, tmp_path: Path) -> None:
        """purge(minutes=60) removes images older than 60 minutes."""
        from ottools._image import store
        from ottools._image.lifecycle import purge_images

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        handle_name = "img_oldimage"
        meta = {
            "handle": handle_name,
            "source": "file",
            "hash": "a" * 64,
            "original_dims": [10, 10],
            "model_dims": [10, 10],
            "resized": False,
            "max_edge": 1568,
            "original_format": "PNG",
            "created_at": old_ts,
            "summary": None,
        }
        (tmp_path / f"{handle_name}.meta.json").write_text(json.dumps(meta))
        (tmp_path / f"{handle_name}.png").write_bytes(b"fake")

        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.lifecycle._images_dir", return_value=tmp_path),
        ):
            result = purge_images(minutes=60)

        assert result["purged"] == 1


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.api
@pytest.mark.tools
class TestImageVision:
    """Vision tools — skipped when API key is absent."""

    @pytest.fixture(autouse=True)
    def require_vision_config(self) -> None:
        """Skip if vision API key or model is not configured."""
        if not get_test_secret("OPENAI_API_KEY") and not get_test_secret("OT_LLM_API_KEY"):
            pytest.fail("No vision API key configured (OPENAI_API_KEY or OT_LLM_API_KEY)")

        from ottools._image.config import get_image_config
        config = get_image_config()
        if not config.model:
            pytest.fail("tools.ot_image.model not configured in onetool.yaml")

    def test_ask_returns_answer(self, tmp_path: Path) -> None:
        """ask() returns a non-empty answer for a simple question."""
        from ottools._image import store
        from ottools.ot_image import ask, load

        img_path = _make_png(tmp_path)
        with patch.object(store, "_images_dir", return_value=tmp_path):
            handle = load(img=str(img_path))["handle"]
            result = ask(img=handle, q="What colour is this image?")

        if "error" in result:
            err = result["error"]
            if "Authentication" in err or "api_key" in err.lower():
                pytest.fail(f"Vision API auth failed (check OPENAI_API_KEY / OT_LLM_API_KEY): {err}")
            pytest.fail(f"ask() returned unexpected error: {err}")
        assert "result" in result
        assert result["result"][0]["answer"]
