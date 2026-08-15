"""Tests for strict project-local named Context storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ottools._worker.context import (
    ContextError,
    ContextStore,
    normalize_body,
    render_context,
    validate_context_name,
)
from ottools._worker.models import ContextMetadata

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _store(tmp_path: Path, *, max_kb: int = 16) -> ContextStore:
    return ContextStore(
        context_max_kb=max_kb,
        state_root=tmp_path / ".onetool" / "state" / "worker",
        project_root=tmp_path,
    )


class TestContextNames:
    """Validate filesystem-safe unambiguous names and containment."""

    @pytest.mark.parametrize(
        "name",
        ["default", "feature-x", "review-feature-x", "x1", "123"],
    )
    def test_accepts_lowercase_slugs(self, name: str) -> None:
        assert validate_context_name(name) == name

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "Feature-X",
            "feature_x",
            "feature.x",
            "feature--x",
            "-feature",
            "feature-",
            "../feature",
            "feature/x",
            "feature\\x",
            " feature",
            "feature ",
            "x" * 65,
        ],
    )
    def test_rejects_invalid_or_ambiguous_names(self, name: str) -> None:
        with pytest.raises(ContextError, match="lowercase slug"):
            validate_context_name(name)

    def test_context_file_is_contained_in_project_state(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        loaded, created = store.load("feature-x", create=True)

        path = tmp_path / ".onetool" / "state" / "worker" / "contexts" / "feature-x.md"
        assert created is True
        assert path.is_file()
        assert loaded.name == "feature-x"


class TestContextFiles:
    """Validate canonical Markdown files and strict frontmatter parsing."""

    def test_missing_context_is_created_atomically_with_canonical_frontmatter(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        first, first_created = store.load("default", create=True)
        second, second_created = store.load("default", create=True)

        assert first_created is True
        assert second_created is False
        assert first == second
        assert first.metadata == ContextMetadata(
            schema_version=1,
            revision=1,
            status="active",
            description="",
            tags=[],
        )
        path = tmp_path / ".onetool" / "state" / "worker" / "contexts" / "default.md"
        assert path.read_text(encoding="utf-8") == render_context(first.metadata, "")

    def test_listing_is_stable_and_body_free(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        for name in ("zeta", "default", "alpha"):
            loaded, _ = store.load(name, create=True)
            if name == "alpha":
                store.commit_body(loaded=loaded, body="PRIVATE CONTEXT BODY")

        result = [item.model_dump(mode="python") for item in store.list_contexts()]

        assert [item["name"] for item in result] == ["alpha", "default", "zeta"]
        assert all("body" not in item for item in result)
        assert "PRIVATE CONTEXT BODY" not in repr(result)

    @pytest.mark.parametrize(
        ("content", "message"),
        [
            ("not frontmatter\n", "strict YAML frontmatter"),
            ("---\ntags: [\n---\n", "invalid Context frontmatter YAML"),
            (
                "---\nschema_version: 1\nrevision: 1\nstatus: active\n"
                "description: &description secret\ntags: [*description]\n---\n",
                "aliases are not allowed",
            ),
            (
                "---\nschema_version: 1\nrevision: 1\nrevision: 2\nstatus: active\n"
                "description: ''\ntags: []\n---\n",
                "duplicate YAML key",
            ),
            (
                "---\nschema_version: 1\nrevision: 1\nstatus: active\n"
                "description: ''\ntags: []\nunknown: value\n---\n",
                "Extra inputs are not permitted",
            ),
            (
                "---\nschema_version: 2\nrevision: 1\nstatus: active\n"
                "description: ''\ntags: []\n---\n",
                "Input should be 1",
            ),
        ],
    )
    def test_rejects_invalid_frontmatter(
        self,
        tmp_path: Path,
        content: str,
        message: str,
    ) -> None:
        path = tmp_path / ".onetool" / "state" / "worker" / "contexts" / "default.md"
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")

        with pytest.raises(ContextError, match=message):
            _store(tmp_path).load("default", create=False)
        assert path.read_text(encoding="utf-8") == content

    def test_rejects_invalid_utf8_without_rewriting(self, tmp_path: Path) -> None:
        path = tmp_path / ".onetool" / "state" / "worker" / "contexts" / "default.md"
        path.parent.mkdir(parents=True)
        original = b"---\n\xff\n---\n"
        path.write_bytes(original)

        with pytest.raises(ContextError, match="could not read Context"):
            _store(tmp_path).load("default", create=False)
        assert path.read_bytes() == original

    def test_rejects_oversized_complete_file(self, tmp_path: Path) -> None:
        store = _store(tmp_path, max_kb=1)
        loaded, _ = store.load("default", create=True)

        with pytest.raises(ContextError, match="limit is 1 KB"):
            store.commit_body(loaded=loaded, body="x" * 2_000)
        current, _ = store.load("default", create=False)
        assert current.metadata.revision == 1
        assert current.body == ""

    def test_normalizes_body_line_endings_and_trailing_whitespace(self) -> None:
        assert normalize_body("\r\n# Goal  \r\n\r\nWork\t\r\n") == "# Goal\n\nWork"


class TestContextMetadata:
    """Verify explicit upsert semantics and archival behavior."""

    def test_update_creates_missing_context_with_supplied_metadata(
        self, tmp_path: Path
    ) -> None:
        loaded, created = _store(tmp_path).update_metadata(
            "feature-x",
            description="Implement feature X",
            tags=["feature", "active"],
        )

        assert created is True
        assert loaded.metadata.revision == 1
        assert loaded.metadata.description == "Implement feature X"
        assert loaded.metadata.tags == ["feature", "active"]
        assert loaded.body == ""

    def test_update_distinguishes_omitted_and_empty_values(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        store.update_metadata(
            "feature-x",
            description="Existing",
            tags=["one", "two"],
        )

        tags_only, created = store.update_metadata(
            "feature-x",
            description=None,
            tags=[],
        )
        cleared, _ = store.update_metadata(
            "feature-x",
            description="",
            tags=None,
        )

        assert created is False
        assert tags_only.metadata.description == "Existing"
        assert tags_only.metadata.tags == []
        assert cleared.metadata.description == ""
        assert cleared.metadata.tags == []
        assert cleared.metadata.revision == 3

    def test_update_replaces_tags_and_preserves_body(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        loaded, _ = store.load("feature-x", create=True)
        committed = store.commit_body(loaded=loaded, body="# State\n\nKeep me")

        updated, _ = store.update_metadata(
            "feature-x",
            description="Updated",
            tags=["replacement"],
        )

        assert updated.body == committed.body
        assert updated.metadata.tags == ["replacement"]
        assert updated.metadata.revision == 3

    def test_rejects_missing_update_fields_and_invalid_tags(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        with pytest.raises(ContextError, match="description or tags is required"):
            store.update_metadata("feature-x", description=None, tags=None)
        with pytest.raises(ContextError, match="tags must be unique"):
            store.update_metadata("feature-x", description=None, tags=["one", "one"])
        with pytest.raises(ContextError, match="at least 1 character"):
            store.update_metadata("feature-x", description=None, tags=[" "])

    def test_archive_preserves_content_and_reserves_identity(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        loaded, _ = store.update_metadata(
            "feature-x",
            description="Feature",
            tags=["active"],
        )
        committed = store.commit_body(loaded=loaded, body="# Private state")
        archived = store.archive("feature-x")

        assert archived.metadata.status == "archived"
        assert archived.metadata.revision == committed.metadata.revision + 1
        assert archived.metadata.description == "Feature"
        assert archived.metadata.tags == ["active"]
        assert archived.body == "# Private state"
        assert [item.name for item in store.list_contexts(status="archived")] == [
            "feature-x"
        ]
        assert [item.name for item in store.list_contexts(status="active")] == []
        with pytest.raises(ContextError, match="archived"):
            store.load("feature-x", create=True)
        with pytest.raises(ContextError, match="archived"):
            store.update_metadata("feature-x", description="Again", tags=None)

    def test_archive_rejects_default_unknown_and_already_archived(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        store.load("default", create=True)
        store.load("feature-x", create=True)
        store.archive("feature-x")

        with pytest.raises(ContextError, match="cannot be archived"):
            store.archive("default")
        with pytest.raises(ContextError, match="does not exist"):
            store.archive("unknown")
        with pytest.raises(ContextError, match="already archived"):
            store.archive("feature-x")


class TestContextCommit:
    """Verify bounded atomic complete-body replacement and conflict checks."""

    def test_commit_increments_revision_once(self, tmp_path: Path) -> None:
        store = _store(tmp_path)
        loaded, _ = store.load("default", create=True)

        committed = store.commit_body(loaded=loaded, body="# Goal\n\nCurrent state")

        assert committed.metadata.revision == 2
        assert committed.body == "# Goal\n\nCurrent state"

    def test_revision_or_digest_conflict_preserves_manual_edit(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        loaded, _ = store.load("default", create=True)
        path = tmp_path / ".onetool" / "state" / "worker" / "contexts" / "default.md"
        manual = path.read_text(encoding="utf-8").replace(
            "description: ''", "description: manual"
        )
        path.write_text(manual, encoding="utf-8")

        with pytest.raises(ContextError, match="changed during operation"):
            store.commit_body(loaded=loaded, body="worker replacement")
        assert path.read_text(encoding="utf-8") == manual

    def test_rejects_escaping_or_missing_local_markdown_references(
        self, tmp_path: Path
    ) -> None:
        store = _store(tmp_path)
        loaded, _ = store.load("default", create=True)

        with pytest.raises(ContextError, match="escapes project"):
            store.commit_body(loaded=loaded, body="[outside](../secret.md)")
        with pytest.raises(ContextError, match="existing regular file"):
            store.commit_body(loaded=loaded, body="[missing](docs/missing.md)")

    def test_accepts_existing_project_and_external_references(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "docs" / "guide.md"
        target.parent.mkdir()
        target.write_text("guide", encoding="utf-8")
        store = _store(tmp_path)
        loaded, _ = store.load("default", create=True)

        committed = store.commit_body(
            loaded=loaded,
            body="[guide](docs/guide.md) [web](https://www.wikipedia.org/)",
        )
        assert "docs/guide.md" in committed.body
