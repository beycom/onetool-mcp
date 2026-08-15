"""Tests for strict named-Context-owned worker artifacts."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

import ottools._worker.artifacts as artifact_module
from ottools._worker.artifacts import (
    ARTIFACT_MAX_BYTES,
    ArtifactError,
    ArtifactStore,
    encode_content,
)
from ottools._worker.context import ContextStore
from ottools._worker.lifecycle import HistoryStore, project_fingerprint
from ottools.worker import (
    artifact_create,
    artifact_delete,
    artifact_list,
    artifact_open,
    select,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _stores(tmp_path: Path) -> tuple[ContextStore, ArtifactStore]:
    state_root = tmp_path / ".onetool" / "state" / "worker"
    contexts = ContextStore(
        context_max_kb=16,
        state_root=state_root,
        project_root=tmp_path,
    )
    return contexts, ArtifactStore(context_store=contexts, project_root=tmp_path)


def _create_text(
    store: ArtifactStore,
    *,
    context: str = "feature-x",
    content: str = "evidence",
    label: str = "Evidence",
) -> str:
    metadata, warnings = store.create(
        context=context,
        content=content,
        kind="text",
        media_type="text/plain",
        label=label,
    )
    assert warnings == []
    return metadata.id


def test_create_open_list_and_delete_text_and_binary(tmp_path: Path) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)

    text_id = _create_text(store)
    binary, _ = store.create(
        context="feature-x",
        content=base64.b64encode(b"\x00\xff").decode("ascii"),
        kind="binary",
        media_type="application/octet-stream",
        label="Capture",
    )

    opened_text, warnings = store.open(
        context="feature-x", artifact_id=text_id
    )
    opened_binary, _ = store.open(
        context="feature-x", artifact_id=binary.id
    )
    page = store.list_artifacts(context="feature-x", limit=1, offset=1)

    assert opened_text.body == b"evidence"
    assert encode_content(opened_text) == "evidence"
    assert encode_content(opened_binary) == base64.b64encode(b"\x00\xff").decode(
        "ascii"
    )
    assert warnings == []
    assert page.total == 2
    assert len(page.items) == 1
    assert page.has_more is False
    assert page.items[0].id == binary.id

    assert store.delete(context="feature-x", artifact_id=text_id) == []
    with pytest.raises(ArtifactError, match="does not exist"):
        store.open(context="feature-x", artifact_id=text_id)
    with pytest.raises(ArtifactError, match="does not exist"):
        store.delete(context="feature-x", artifact_id=text_id)


def test_creation_requires_active_owner_but_archive_preserves_access(
    tmp_path: Path,
) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)
    artifact_id = _create_text(store)
    contexts.archive("feature-x")

    with pytest.raises(ArtifactError, match="archived"):
        _create_text(store, content="new")
    opened, _ = store.open(context="feature-x", artifact_id=artifact_id)
    assert opened.body == b"evidence"
    assert store.list_artifacts(
        context="feature-x", limit=20, offset=0
    ).total == 1
    store.delete(context="feature-x", artifact_id=artifact_id)

    context_path = (
        tmp_path
        / ".onetool"
        / "state"
        / "worker"
        / "contexts"
        / "feature-x.md"
    )
    assert context_path.is_file()
    assert "status: archived" in context_path.read_text(encoding="utf-8")


def test_unknown_invalid_and_cross_context_access_never_creates_or_escapes(
    tmp_path: Path,
) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)
    contexts.load("review", create=True)
    artifact_id = _create_text(store)

    with pytest.raises(ArtifactError, match="does not exist"):
        store.list_artifacts(context="unknown", limit=20, offset=0)
    with pytest.raises(ArtifactError, match="lowercase slug"):
        store.list_artifacts(context="../escape", limit=20, offset=0)
    with pytest.raises(ArtifactError, match="does not exist"):
        store.open(context="review", artifact_id=artifact_id)
    with pytest.raises(ArtifactError, match="opaque"):
        store.open(context="feature-x", artifact_id="../escape")

    assert not (
        tmp_path / ".onetool" / "state" / "worker" / "artifacts" / "unknown"
    ).exists()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "content": "not-base64!",
                "kind": "binary",
                "media_type": "application/octet-stream",
                "label": "Binary",
            },
            "strict base64",
        ),
        (
            {
                "content": "text",
                "kind": "text",
                "media_type": "Text/Plain; charset=utf-8",
                "label": "Text",
            },
            "lowercase type/subtype",
        ),
        (
            {
                "content": "text",
                "kind": "text",
                "media_type": "text/plain",
                "label": " ",
            },
            "must not be blank",
        ),
    ],
)
def test_create_rejects_invalid_encoding_media_type_and_label(
    tmp_path: Path,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)
    with pytest.raises(ArtifactError, match=message):
        store.create(context="feature-x", **kwargs)  # type: ignore[arg-type]


def test_size_count_and_total_limits_are_checked_before_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)
    with pytest.raises(ArtifactError, match="limit"):
        store.create(
            context="feature-x",
            content="x" * (ARTIFACT_MAX_BYTES + 1),
            kind="text",
            media_type="text/plain",
            label="Too large",
        )

    monkeypatch.setattr(artifact_module, "ARTIFACT_MAX_ITEMS", 2)
    _create_text(store, content="a")
    _create_text(store, content="b")
    with pytest.raises(ArtifactError, match="maximum 2"):
        _create_text(store, content="c")

    contexts.load("total-limit", create=True)
    monkeypatch.setattr(artifact_module, "ARTIFACT_MAX_ITEMS", 64)
    monkeypatch.setattr(artifact_module, "ARTIFACT_TOTAL_MAX_BYTES", 3)
    _create_text(store, context="total-limit", content="ab")
    with pytest.raises(ArtifactError, match="total body limit"):
        _create_text(store, context="total-limit", content="cd")


def test_collision_is_retried_without_overwriting_existing_artifact(
    tmp_path: Path,
) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)
    values = iter(["a" * 32, "a" * 32, "b" * 32])
    with patch.object(artifact_module, "token_hex", side_effect=lambda _n: next(values)):
        first = _create_text(store, content="first")
        second = _create_text(store, content="second")

    assert first == f"artifact-{'a' * 32}"
    assert second == f"artifact-{'b' * 32}"
    opened, _ = store.open(context="feature-x", artifact_id=first)
    assert opened.body == b"first"


def test_interrupted_staging_is_cleaned_and_failed_publish_is_not_visible(
    tmp_path: Path,
) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)
    root = tmp_path / ".onetool" / "state" / "worker" / "artifacts" / "feature-x"
    root.mkdir(parents=True)
    stale = root / ".staging-crash"
    stale.mkdir()
    (stale / "body").write_bytes(b"partial")

    assert store.list_artifacts(context="feature-x", limit=20, offset=0).total == 0
    assert not stale.exists()

    real_write = artifact_module._write_synced
    calls = 0

    def fail_metadata(path: Path, data: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated metadata failure")
        real_write(path, data)

    with (
        patch.object(artifact_module, "_write_synced", side_effect=fail_metadata),
        pytest.raises(OSError, match="simulated"),
    ):
        _create_text(store)

    assert list(root.glob(".staging-*")) == []
    assert store.list_artifacts(context="feature-x", limit=20, offset=0).total == 0


def test_inconsistent_final_and_symlinks_are_quarantined(
    tmp_path: Path,
) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)
    artifact_id = _create_text(store)
    final = (
        tmp_path
        / ".onetool"
        / "state"
        / "worker"
        / "artifacts"
        / "feature-x"
        / artifact_id
    )
    (final / "body").write_bytes(b"tampered")

    page = store.list_artifacts(context="feature-x", limit=20, offset=0)
    assert page.items == []
    assert page.warnings == [f"orphan:{artifact_id}"]
    with pytest.raises(ArtifactError, match="quarantined"):
        store.open(context="feature-x", artifact_id=artifact_id)

    outside = tmp_path / "outside"
    outside.mkdir()
    artifacts_root = tmp_path / ".onetool" / "state" / "worker" / "artifacts"
    for child in artifacts_root.iterdir():
        if child.is_dir():
            for nested in child.iterdir():
                if nested.is_dir():
                    for item in nested.iterdir():
                        item.unlink()
                    nested.rmdir()
            child.rmdir()
    artifacts_root.rmdir()
    artifacts_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ArtifactError, match="symlink"):
        _create_text(store)
    assert list(outside.iterdir()) == []


def test_metadata_unknown_fields_and_extra_files_are_quarantined(
    tmp_path: Path,
) -> None:
    contexts, store = _stores(tmp_path)
    contexts.load("feature-x", create=True)
    artifact_id = _create_text(store)
    final = (
        tmp_path
        / ".onetool"
        / "state"
        / "worker"
        / "artifacts"
        / "feature-x"
        / artifact_id
    )
    metadata_path = final / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["summary"] = "must not be accepted"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    page = store.list_artifacts(context="feature-x", limit=20, offset=0)
    assert page.total == 0
    assert page.warnings == [f"orphan:{artifact_id}"]


def test_public_operations_are_explicit_body_safe_and_channel_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    assert select(context="feature-x")["ok"] is True
    context_path = (
        tmp_path
        / ".onetool"
        / "state"
        / "worker"
        / "contexts"
        / "feature-x.md"
    )
    context_before = context_path.read_bytes()
    fingerprint_before = project_fingerprint(tmp_path)

    monkeypatch.setenv("OT_EPISODIC_WORKER", "1")
    created = artifact_create(
        context="feature-x",
        content="PRIVATE ARTIFACT BODY",
        kind="text",
        media_type="text/plain",
        label="Private evidence",
    )
    artifact_id = created["artifact"]["id"]  # type: ignore[index]
    listed = artifact_list(context="feature-x")
    opened = artifact_open(context="feature-x", artifact_id=str(artifact_id))
    deleted = artifact_delete(context="feature-x", artifact_id=str(artifact_id))

    assert created["ok"] is True
    assert "PRIVATE ARTIFACT BODY" not in repr(created)
    assert "content" not in repr(listed)
    assert opened["content"] == "PRIVATE ARTIFACT BODY"
    assert deleted["deleted"] is True
    assert context_path.read_bytes() == context_before
    assert project_fingerprint(tmp_path) == fingerprint_before
    assert HistoryStore(
        state_root=tmp_path / ".onetool" / "state" / "worker"
    ).read() == []
