"""Tests for the slim, inline-only Console message models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ot.console.models import ShowRequest


@pytest.mark.unit
@pytest.mark.core
class TestShowRequest:
    """Validate strict inline-only Console message payload contracts."""

    def test_accepts_supported_kind(self) -> None:
        request = ShowRequest(
            kind="markdown", content="# Result", metadata={"task": "audit"}
        )

        assert request.kind == "markdown"
        assert request.metadata == {"task": "audit"}

    def test_rejects_unknown_field(self) -> None:
        with pytest.raises(ValidationError):
            ShowRequest(kind="markdown", content="# Result", expand="expanded")  # type: ignore[call-arg]

    def test_rejects_unsupported_kind(self) -> None:
        with pytest.raises(ValidationError):
            ShowRequest(kind="html", content="<h1>No</h1>")  # type: ignore[arg-type]

    def test_rejects_missing_content(self) -> None:
        with pytest.raises(ValidationError):
            ShowRequest(kind="text")  # type: ignore[call-arg]

    def test_rejects_file_kind(self) -> None:
        """File-backed kinds are out of scope until the full display pack ships (3.1)."""
        with pytest.raises(ValidationError):
            ShowRequest(kind="file", content="report.txt")  # type: ignore[arg-type]

    def test_accepts_structured_content(self) -> None:
        request = ShowRequest(kind="json", content={"ok": True, "items": [1, 2]})

        assert request.content == {"ok": True, "items": [1, 2]}
