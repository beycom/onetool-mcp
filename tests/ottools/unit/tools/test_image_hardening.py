"""Boundary tests for canonical image storage and bounded remote sources."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError


def _png_bytes(width: int = 16, height: int = 16) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(10, 20, 30))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _handle(seed: str) -> str:
    return f"img_{hashlib.sha256(seed.encode()).hexdigest()}"


class _TrackingStream(httpx.SyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.yielded = 0
        self.closed = False

    def __iter__(self) -> Any:
        for chunk in self.chunks:
            self.yielded += 1
            yield chunk

    def close(self) -> None:
        self.closed = True


def _client_for_response(
    *,
    chunks: list[bytes],
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[httpx.Client, _TrackingStream]:
    stream = _TrackingStream(chunks)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers=headers or {"content-type": "image/png"},
            stream=stream,
        )

    return httpx.Client(transport=httpx.MockTransport(handler)), stream


@pytest.mark.unit
@pytest.mark.tools
class TestRemoteImageBoundary:
    """URL transport owns limits, cleanup, and expected-error normalization."""

    url = "https://raw.githubusercontent.com/acme/assets/main/photo.png"

    def test_fixed_limit_and_exact_limit_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ottools._image import sources

        assert sources.MAX_ORIGINAL_RESPONSE_BYTES == 20 * 1024 * 1024
        monkeypatch.setattr(sources, "MAX_ORIGINAL_RESPONSE_BYTES", 8)
        client, stream = _client_for_response(chunks=[b"1234", b"5678"])
        with (
            client,
            patch("ot.http_client._get_shared_client", return_value=client),
        ):
            assert sources._fetch_url(self.url) == b"12345678"
        assert stream.yielded == 2
        assert stream.closed

    def test_declared_oversize_rejected_before_body(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ottools._image import sources

        monkeypatch.setattr(sources, "MAX_ORIGINAL_RESPONSE_BYTES", 8)
        client, stream = _client_for_response(
            chunks=[b"must not be read"],
            headers={"content-type": "image/png", "content-length": "9"},
        )
        with (
            client,
            patch("ot.http_client._get_shared_client", return_value=client),
            pytest.raises(sources.ImageSourceError, match="20 MiB"),
        ):
            sources._fetch_url(self.url)
        assert stream.yielded == 0
        assert stream.closed

    def test_observed_oversize_stops_at_crossing_chunk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ottools._image import sources

        monkeypatch.setattr(sources, "MAX_ORIGINAL_RESPONSE_BYTES", 8)
        client, stream = _client_for_response(
            chunks=[b"12345678", b"9", b"must not be read"],
            headers={"content-type": "image/png", "content-length": "8"},
        )
        with (
            client,
            patch("ot.http_client._get_shared_client", return_value=client),
            pytest.raises(sources.ImageSourceError, match="20 MiB"),
        ):
            sources._fetch_url(self.url)
        assert stream.yielded == 2
        assert stream.closed

    @pytest.mark.parametrize(
        ("status", "headers"),
        [
            (503, {"content-type": "image/png"}),
            (200, {"content-type": "text/plain"}),
        ],
    )
    def test_status_and_content_type_failures_close_response(
        self, status: int, headers: dict[str, str]
    ) -> None:
        from ottools._image import sources

        client, stream = _client_for_response(
            chunks=[b"not an image"],
            status=status,
            headers=headers,
        )
        with (
            client,
            patch("ot.http_client._get_shared_client", return_value=client),
            pytest.raises(sources.ImageSourceError),
        ):
            sources._fetch_url(self.url)
        assert stream.closed

    @pytest.mark.parametrize(
        "failure",
        [
            httpx.ConnectError("connection failed"),
            httpx.ReadTimeout("timed out"),
        ],
    )
    def test_expected_transport_failures_return_structured_error(
        self, failure: httpx.HTTPError
    ) -> None:
        from ottools._image import tools

        def handler(_request: httpx.Request) -> httpx.Response:
            raise failure

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with (
            client,
            patch("ot.http_client._get_shared_client", return_value=client),
        ):
            result = tools.load(img=self.url)
        assert "error" in result
        assert "failed to download image" in result["error"]

    def test_http_status_is_structured_across_public_auto_load_paths(
        self, tmp_path: Path
    ) -> None:
        from ottools._image import store, tools

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, headers={"content-type": "image/png"})

        local = tmp_path / "local.png"
        local.write_bytes(_png_bytes())
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with (
            client,
            patch("ot.http_client._get_shared_client", return_value=client),
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch("ottools._image.tools.threading.Thread"),
        ):
            loaded = tools.load(img=self.url)
            batch = tools.load_batch(img=[self.url, str(local)])
            asked = tools.ask(img=self.url, q="What is this?")
            summarized = tools.summary(img=self.url)

        assert "error" in loaded
        assert "error" in batch[0]
        assert "handle" in batch[1]
        assert "error" in asked
        assert asked["handle"] == self.url
        assert "error" in summarized
        assert summarized["handle"] == self.url

    def test_overflow_runs_no_decode_store_cache_or_thread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ottools._image import sources, tools

        monkeypatch.setattr(sources, "MAX_ORIGINAL_RESPONSE_BYTES", 8)
        client, _stream = _client_for_response(chunks=[b"12345678", b"9"])
        with (
            client,
            patch("ot.http_client._get_shared_client", return_value=client),
            patch("ottools._image.tools.prepare_for_model") as prepare,
            patch("ottools._image.tools.save_image") as save,
            patch("ottools._image.tools.cache_put") as cache,
            patch("ottools._image.tools.threading.Thread") as thread,
        ):
            result = tools.load(img=self.url)
        assert "error" in result
        prepare.assert_not_called()
        save.assert_not_called()
        cache.assert_not_called()
        thread.assert_not_called()

    def test_programming_failure_propagates(self) -> None:
        from ottools._image import tools

        def handler(_request: httpx.Request) -> httpx.Response:
            raise AssertionError("programming defect")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with (
            client,
            patch("ot.http_client._get_shared_client", return_value=client),
            pytest.raises(AssertionError, match="programming defect"),
        ):
            tools.load(img=self.url)


@pytest.mark.unit
@pytest.mark.tools
class TestCanonicalImageBoundary:
    """Every public lifecycle boundary shares one strict reference grammar."""

    @pytest.mark.parametrize(
        "reference",
        [
            "",
            ".",
            "..",
            "named",
            "/tmp/not-an-image-handle",
            "#",
            "##img_" + "a" * 64,
            "#img_" + "a" * 63,
            "#img_" + "A" * 64,
            "img_" + "a" * 64,
            "#named",
            "#/tmp/outside",
            "#../outside",
            "#img_" + "a" * 64 + "/outside",
            "#img_" + "a" * 64 + "*",
            "#img_" + "a" * 64 + "\x00",
        ],
    )
    def test_invalid_forms_fail_before_storage_io(self, reference: str) -> None:
        from ottools._image import store, tools
        from ottools._image.lifecycle import delete_image

        with patch.object(
            store,
            "_images_dir",
            side_effect=AssertionError("storage I/O must not run"),
        ):
            loaded = tools.load(img=reference)
            asked = tools.ask(img=reference, q="What is shown?")
            summarized = tools.summary(img=reference)
            deleted = delete_image(handle=reference)

        for result in (loaded, asked, summarized, deleted):
            assert "error" in result

    def test_full_digest_handle_and_direct_dedup(self, tmp_path: Path) -> None:
        from ottools._image import store, tools

        raw = _png_bytes()
        source = tmp_path / "photo.png"
        source.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        expected = f"#img_{digest}"
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            patch.object(
                Path,
                "iterdir",
                side_effect=AssertionError("dedup must not scan"),
            ),
        ):
            first = tools.load(img=str(source))
            second = tools.load(img=str(source))

        assert first["handle"] == expected
        assert second["handle"] == expected
        assert second["dedup"] is True
        assert len(expected.removeprefix("#img_")) == 64

    def test_different_content_has_distinct_complete_digest(
        self, tmp_path: Path
    ) -> None:
        from ottools._image import store, tools

        first_path = tmp_path / "first.png"
        second_path = tmp_path / "second.png"
        first_path.write_bytes(_png_bytes(16, 16))
        second_path.write_bytes(_png_bytes(17, 16))
        with patch.object(store, "_images_dir", return_value=tmp_path):
            first = str(tools.load(img=str(first_path))["handle"])
            second = str(tools.load(img=str(second_path))["handle"])
        assert first != second
        assert len(first.removeprefix("#img_")) == 64
        assert len(second.removeprefix("#img_")) == 64

    def test_symlinked_content_is_never_followed(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.lifecycle import (
            delete_image,
            list_images,
            purge_images,
        )

        source = tmp_path / "source.png"
        source.write_bytes(_png_bytes())
        with patch.object(store, "_images_dir", return_value=tmp_path):
            handle = str(tools.load(img=str(source))["handle"])
            handle_name = handle[1:]
            content = tmp_path / f"{handle_name}.png"
            content.unlink()
            outside = tmp_path.parent / f"{tmp_path.name}-{handle_name}-outside.png"
            outside.write_bytes(b"outside")
            content.symlink_to(outside)
            store._session_cache.clear()

            with patch("ottools._image.tools.ask_questions") as ask_model:
                asked = tools.ask(img=handle, q="What is shown?")
            summarized = tools.summary(img=handle)
            listed = list_images()
            deleted = delete_image(handle=handle)
            purged = purge_images(all=True)

        assert "error" in asked
        assert "error" in summarized
        assert listed == []
        assert "error" in deleted
        assert purged["purged"] == 0
        assert outside.read_bytes() == b"outside"
        ask_model.assert_not_called()

    def test_symlinked_and_tampered_metadata_fail_closed(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.lifecycle import delete_image, list_images

        handle_name = _handle("metadata")
        handle = f"#{handle_name}"
        outside = tmp_path.parent / f"{tmp_path.name}-{handle_name}.meta.json"
        outside.write_text("outside", encoding="utf-8")
        (tmp_path / f"{handle_name}.meta.json").symlink_to(outside)
        with patch.object(store, "_images_dir", return_value=tmp_path):
            assert "error" in tools.ask(img=handle, q="What is shown?")
            assert "error" in tools.summary(img=handle)
            assert "error" in delete_image(handle=handle)
            assert list_images() == []
        assert outside.read_text(encoding="utf-8") == "outside"

        (tmp_path / f"{handle_name}.meta.json").unlink()
        for filename in ("../../outside.png", str(outside.resolve())):
            meta = {
                "handle": handle_name,
                "hash": handle_name.removeprefix("img_"),
                "original_format": "PNG",
                "file": filename,
            }
            (tmp_path / f"{handle_name}.meta.json").write_text(
                json.dumps(meta),
                encoding="utf-8",
            )
            (tmp_path / f"{handle_name}.png").write_bytes(_png_bytes())
            with patch.object(store, "_images_dir", return_value=tmp_path):
                assert "error" in delete_image(handle=handle)
            assert (tmp_path / f"{handle_name}.png").exists()

    def test_existing_symlink_blocks_storage_write(self, tmp_path: Path) -> None:
        from ottools._image import store

        handle_name = _handle("write")
        meta = {
            "handle": handle_name,
            "hash": handle_name.removeprefix("img_"),
            "original_format": "PNG",
        }
        outside = tmp_path.parent / f"{tmp_path.name}-outside-write.png"
        outside.write_bytes(b"keep")
        (tmp_path / f"{handle_name}.png").symlink_to(outside)
        with (
            patch.object(store, "_images_dir", return_value=tmp_path),
            pytest.raises(ValueError, match="symlink"),
        ):
            store.save_image(_png_bytes(), handle_name, meta, fmt="PNG")
        assert outside.read_bytes() == b"keep"

    def test_symlinked_image_directory_is_rejected(self, tmp_path: Path) -> None:
        from ottools._image import store

        session = tmp_path / "session"
        outside = tmp_path / "outside"
        session.mkdir()
        outside.mkdir()
        (session / "images").symlink_to(outside, target_is_directory=True)
        with (
            patch("ottools._image.store.get_session_dir", return_value=session),
            pytest.raises(ValueError, match="must not be a symlink"),
        ):
            store._images_dir()

    def test_mismatched_metadata_identity_is_rejected(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.lifecycle import delete_image

        handle_name = _handle("addressed")
        other_name = _handle("other")
        meta = {
            "handle": other_name,
            "hash": other_name.removeprefix("img_"),
            "original_format": "PNG",
        }
        (tmp_path / f"{handle_name}.meta.json").write_text(
            json.dumps(meta),
            encoding="utf-8",
        )
        (tmp_path / f"{handle_name}.png").write_bytes(_png_bytes())
        with patch.object(store, "_images_dir", return_value=tmp_path):
            assert "error" in tools.ask(
                img=f"#{handle_name}",
                q="What is shown?",
            )
            assert "error" in tools.summary(img=f"#{handle_name}")
            assert "error" in delete_image(handle=f"#{handle_name}")
        assert (tmp_path / f"{handle_name}.png").exists()

    def test_delete_removes_only_exact_entry(self, tmp_path: Path) -> None:
        from ottools._image import store, tools
        from ottools._image.lifecycle import delete_image

        source = tmp_path / "delete.png"
        source.write_bytes(_png_bytes())
        with patch.object(store, "_images_dir", return_value=tmp_path):
            handle = str(tools.load(img=str(source))["handle"])
            handle_name = handle[1:]
            unrelated = tmp_path / f"{handle_name}.backup"
            unrelated.write_bytes(b"keep")
            result = delete_image(handle=handle)

        assert result["deleted"] == handle
        assert unrelated.read_bytes() == b"keep"


@pytest.mark.unit
@pytest.mark.tools
class TestImageCacheConfiguration:
    def test_non_positive_values_fail_on_config_field(self) -> None:
        from ottools._image.config import Config

        for value in (0, -1):
            with pytest.raises(
                ValidationError,
                match="session_cache_size",
            ):
                Config(session_cache_size=value)

    @pytest.mark.parametrize("value", [0, -1])
    def test_hosted_config_reports_pack_and_field(self, value: int) -> None:
        from ot.config.loader import get_tool_config
        from ottools._image.config import Config

        with (
            patch(
                "ot.config.loader._get_raw_config",
                return_value={"session_cache_size": value},
            ),
            pytest.raises(
                ValueError,
                match=r"(?s)Invalid tools\.ot_image configuration:.*session_cache_size",
            ),
        ):
            get_tool_config("ot_image", Config)

    @pytest.mark.parametrize("capacity", [1, 3])
    def test_module_initialization_uses_exact_positive_capacity(
        self, capacity: int
    ) -> None:
        import importlib

        from ottools._image import store
        from ottools._image.config import Config

        handles = [_handle(str(index)) for index in range(capacity + 2)]
        try:
            with patch(
                "ottools._image.config.get_image_config",
                return_value=Config(session_cache_size=capacity),
            ):
                importlib.reload(store)
            for handle in handles:
                store.cache_put(handle, b"model bytes")
            assert store._session_cache.keys() == handles[-capacity:]
        finally:
            importlib.reload(store)
