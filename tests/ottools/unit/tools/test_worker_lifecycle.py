"""Tests for mechanical worker episode observation and History."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from ottools._worker.lifecycle import (
    ConsoleObserver,
    HistoryError,
    HistoryStore,
    classify_changes,
    project_fingerprint,
)
from ottools._worker.models import HistoryRecord

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _history_record(*, episode_id: str = "episode-1") -> HistoryRecord:
    return HistoryRecord(
        episode_id=episode_id,
        context="feature-x",
        started_at=datetime(2026, 8, 15, tzinfo=UTC),
        finished_at=datetime(2026, 8, 15, 0, 0, 1, tzinfo=UTC),
        status="completed",
        turn_count=1,
        context_revision_before=1,
        context_revision_after=2,
        console=[{"id": "console-1", "kind": "markdown"}],
        local_changes=[{"path": "src/feature.py", "classification": "created"}],
        warnings=[],
    )


def _console_message(path: Path, *, message_id: str, kind: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "id": message_id,
                "metadata": {"id": message_id, "kind": kind},
                "inline_payload": body,
            }
        ),
        encoding="utf-8",
    )


class TestProjectFingerprint:
    """Verify VCS-independent content-sensitive Local Changes."""

    def test_classifies_created_modified_and_deleted_in_stable_order(
        self, tmp_path: Path
    ) -> None:
        modified = tmp_path / "modified.txt"
        deleted = tmp_path / "deleted.txt"
        modified.write_text("before", encoding="utf-8")
        deleted.write_text("delete", encoding="utf-8")
        before = project_fingerprint(tmp_path)

        modified.write_text("after", encoding="utf-8")
        deleted.unlink()
        (tmp_path / "created.txt").write_text("created", encoding="utf-8")
        after = project_fingerprint(tmp_path)

        assert [
            item.model_dump(mode="python") for item in classify_changes(before, after)
        ] == [
            {"path": "created.txt", "classification": "created"},
            {"path": "deleted.txt", "classification": "deleted"},
            {"path": "modified.txt", "classification": "modified"},
        ]

    def test_detects_further_change_to_preexisting_dirty_file(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "already-dirty.py"
        path.write_text("first\n", encoding="utf-8")
        before = project_fingerprint(tmp_path)
        path.write_text("second\n", encoding="utf-8")

        assert classify_changes(before, project_fingerprint(tmp_path))[
            0
        ].classification == ("modified")

    def test_excludes_git_onetool_caches_and_symlinks(self, tmp_path: Path) -> None:
        (tmp_path / "tracked.txt").write_text("tracked", encoding="utf-8")
        for relative in (
            ".git/index",
            ".onetool/state/worker/history.jsonl",
            ".pytest_cache/state",
            "__pycache__/module.pyc",
            "node_modules/package/index.js",
            "tmp/output.txt",
        ):
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("excluded", encoding="utf-8")
        outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
        outside.write_text("outside", encoding="utf-8")
        try:
            (tmp_path / "outside-link").symlink_to(outside)
            assert set(project_fingerprint(tmp_path)) == {"tracked.txt"}
        finally:
            outside.unlink()


class TestConsoleObserver:
    """Capture only identifiers and kinds for episode Console publications."""

    def test_returns_only_new_body_free_metadata(self, tmp_path: Path) -> None:
        messages = (
            tmp_path
            / ".onetool"
            / "state"
            / "console"
            / "instances"
            / "instance-1"
            / "messages"
        )
        _console_message(
            messages / "before.json",
            message_id="before",
            kind="text",
            body="PREVIOUS PRIVATE BODY",
        )
        observer = ConsoleObserver(project_root=tmp_path)
        observer.capture_before()
        _console_message(
            messages / "created.json",
            message_id="created",
            kind="markdown",
            body="NEW PRIVATE BODY",
        )

        observer.capture_current()
        result = [item.model_dump(mode="python") for item in observer.created()]

        assert result == [{"id": "created", "kind": "markdown"}]
        assert "PRIVATE BODY" not in repr(result)

    def test_capture_failure_becomes_bounded_warning(self, tmp_path: Path) -> None:
        observer = ConsoleObserver(project_root=tmp_path)
        observer.capture_before()
        root = tmp_path / ".onetool" / "state" / "console" / "instances"
        root.parent.mkdir(parents=True, exist_ok=True)
        root.write_text("not a directory", encoding="utf-8")

        observer.capture_current()

        assert observer.warning == "console_observation_failed"
        assert observer.created() == []


class TestHistoryStore:
    """Verify canonical durable append and strict valid-prefix recovery."""

    def test_appends_canonical_body_free_record(self, tmp_path: Path) -> None:
        store = HistoryStore(state_root=tmp_path / ".onetool" / "state" / "worker")
        store.append(_history_record())

        text = store.path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert "feature-x" in text
        assert "src/feature.py" in text
        for prohibited in (
            "prompt",
            "description",
            "tags",
            "body",
            "diff",
            "tool_result",
        ):
            assert prohibited not in text
        assert store.read() == [_history_record()]

    def test_ignores_only_one_malformed_final_line_after_valid_prefix(
        self, tmp_path: Path
    ) -> None:
        store = HistoryStore(state_root=tmp_path)
        record = _history_record()
        store.append(record)
        with store.path.open("a", encoding="utf-8") as stream:
            stream.write('{"incomplete":')

        assert store.read() == [record]

    def test_rejects_malformed_nonfinal_or_only_line(self, tmp_path: Path) -> None:
        store = HistoryStore(state_root=tmp_path)
        store.path.write_text("not-json\n{}\n", encoding="utf-8")
        with pytest.raises(HistoryError, match="line 1"):
            store.read()

        store.path.write_text("not-json", encoding="utf-8")
        with pytest.raises(HistoryError, match="line 1"):
            store.read()
