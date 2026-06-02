from __future__ import annotations

import pytest
from pydantic import ValidationError

from ot.display.models import ShowRequest


@pytest.mark.unit
@pytest.mark.core
class TestShowRequest:
    """Validate strict display payload contracts."""

    def test_accepts_supported_kind(self) -> None:
        request = ShowRequest(kind="markdown", content="# Result")

        assert request.kind == "markdown"
        assert request.expand == "auto"

    def test_accepts_expand_mode(self) -> None:
        request = ShowRequest(kind="markdown", content="# Result", expand="expanded")

        assert request.expand == "expanded"

    def test_rejects_invalid_expand_mode(self) -> None:
        with pytest.raises(ValidationError):
            ShowRequest(kind="markdown", content="# Result", expand="open")

    def test_rejects_unsupported_kind(self) -> None:
        with pytest.raises(ValidationError):
            ShowRequest(kind="html", content="<h1>No</h1>")

    def test_rejects_missing_kind_payload(self) -> None:
        with pytest.raises(ValidationError):
            ShowRequest(kind="text")

    def test_rejects_remote_path(self) -> None:
        with pytest.raises(ValidationError):
            ShowRequest(kind="file", path="https://wikipedia.org/wiki/OneTool")

    def test_rejects_file_url(self) -> None:
        with pytest.raises(ValidationError):
            ShowRequest(kind="file", path="file:///tmp/report.txt")
