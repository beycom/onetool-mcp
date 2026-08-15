"""Tests for deterministic episodic worker context contracts and storage."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from ottools._worker.context import (
    ContextError,
    ContextStore,
    normalize_context,
    render_context,
)
from ottools._worker.models import (
    CommittedContext,
    ExecutionPolicy,
    InternalTerminalOutput,
    PublicWorkerResult,
    WorkerContext,
)
from ottools.worker import Config

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _context(*, reference: str | None = None, summary: str = "Current work") -> dict:
    references = []
    if reference is not None:
        references.append({"path": reference, "purpose": "Useful evidence"})
    return {
        "goal": {
            "status": "active",
            "objective": "Finish the worker",
            "success_criteria": ["Tests pass"],
        },
        "work": {
            "summary": summary,
            "next_actions": ["Implement the adapter"],
            "blockers": [],
        },
        "knowledge": [{"kind": "decision", "text": "Use one result"}],
        "questions": [],
        "references": references,
    }


def test_strict_models_reject_unknown_blank_and_invalid_values() -> None:
    context = WorkerContext.model_validate(_context())
    assert context.goal.status == "active"
    for mutation in (
        {**_context(), "unknown": True},
        {**_context(), "questions": ["  "]},
        {**_context(), "goal": {**_context()["goal"], "status": "paused"}},
    ):
        with pytest.raises(ValidationError):
            WorkerContext.model_validate(mutation)

    with pytest.raises(ValidationError):
        PublicWorkerResult.model_validate(
            {
                "session_id": "ep-1",
                "status": "completed",
                "message": "done",
                "context": {},
            }
        )


def test_execution_terminal_result_and_config_shapes_are_strict() -> None:
    policy = ExecutionPolicy.model_validate(
        {"cwd": "/project", "approval_policy": "never", "sandbox": "read-only"}
    )
    assert policy.approval_policy == "never"
    terminal = InternalTerminalOutput.model_validate(
        {"status": "completed", "message": "done", "context": _context()}
    )
    assert terminal.context is not None
    public = PublicWorkerResult.model_validate(
        {"session_id": "ep-1", "status": "completed", "message": "done"}
    )
    assert set(public.model_dump()) == {"session_id", "status", "message"}

    assert Config().context_max_kb == 16
    assert Config(model="gpt-5.6-sol", effort="xhigh", context_max_kb=8).effort == "xhigh"
    for invalid in (
        {"context_max_kb": 0},
        {"context_max_kb": 1.5},
        {"model": " "},
        {"effort": " "},
        {"timeout": 30},
    ):
        with pytest.raises(ValidationError):
            Config.model_validate(invalid)


def test_normalization_and_canonical_rendering_are_deterministic() -> None:
    raw = _context(reference=r"docs\.\guide.md", summary="\r\n  current  \t\r\n")
    raw["goal"]["success_criteria"] = ["Tests pass ", "", "Tests pass"]
    raw["knowledge"] *= 2
    raw["references"] *= 2
    normalized = normalize_context(raw)
    assert normalized.work.summary == "  current"
    assert normalized.goal.success_criteria == ["Tests pass"]
    assert len(normalized.knowledge) == 1
    assert normalized.references[0].path == "docs/guide.md"

    committed = CommittedContext(
        schema_version=1,
        revision=3,
        **normalized.model_dump(mode="python"),
    )
    rendered = render_context(committed)
    assert rendered.startswith("schema_version: 1\nrevision: 3\n")
    assert rendered.endswith("\n") and not rendered.endswith("\n\n")
    assert "&id" not in rendered and "*id" not in rendered
    assert yaml.safe_load(rendered)["work"]["summary"] == "  current"


def test_store_creates_project_scoped_session_and_commits_atomically(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    state = project / ".onetool" / "state" / "episodic-context"
    project.mkdir()
    (project / "notes.md").write_text("evidence", encoding="utf-8")
    store = ContextStore(context_max_kb=16, state_root=state, project_root=project)

    session_id = store.create_session()
    loaded = store.preflight(session_id)
    assert loaded.value == {"schema_version": 1, "revision": 0, "context": None}

    committed = store.commit(
        session_id=session_id,
        loaded_revision=0,
        context=normalize_context(_context(reference="notes.md")),
    )
    assert committed.revision == 1
    context_file = state / session_id / "context.yaml"
    assert context_file.read_text(encoding="utf-8") == render_context(committed)
    assert list(context_file.parent.glob(".context-*")) == []

    loaded_again = store.preflight(session_id)
    assert loaded_again.revision == 1
    assert loaded_again.value["goal"]["objective"] == "Finish the worker"


def test_store_rejects_sessions_references_stale_revisions_and_oversize(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    state = project / ".onetool" / "state" / "episodic-context"
    project.mkdir()
    store = ContextStore(context_max_kb=1, state_root=state, project_root=project)
    session_id = store.create_session()

    other_project = tmp_path / "other-project"
    other_project.mkdir()
    other_store = ContextStore(
        context_max_kb=1,
        state_root=other_project / ".onetool" / "state" / "episodic-context",
        project_root=other_project,
    )
    with pytest.raises(ContextError, match="session_id"):
        other_store.preflight(session_id)

    with pytest.raises(ContextError, match="session_id"):
        store.preflight("ep-00000000000000000000000000000000")
    with pytest.raises(ContextError, match="existing regular file"):
        store.commit(
            session_id=session_id,
            loaded_revision=0,
            context=normalize_context(_context(reference="missing.md")),
        )
    directory = project / "folder"
    directory.mkdir()
    for reference in ("/tmp/outside.md", "../outside.md", "folder"):
        with pytest.raises((ContextError, ValidationError)):
            store.commit(
                session_id=session_id,
                loaded_revision=0,
                context=normalize_context(_context(reference=reference)),
            )
    with pytest.raises(ContextError, match="bytes"):
        store.commit(
            session_id=session_id,
            loaded_revision=0,
            context=normalize_context(_context(summary="x" * 2000)),
        )

    first = store.commit(
        session_id=session_id,
        loaded_revision=0,
        context=normalize_context(_context()),
    )
    with pytest.raises(ContextError, match="revision changed"):
        store.commit(
            session_id=session_id,
            loaded_revision=0,
            context=normalize_context(_context()),
        )
    assert store.preflight(session_id).revision == first.revision

    context_path = state / session_id / "context.yaml"
    before = context_path.read_text(encoding="utf-8")
    with (
        patch("pathlib.Path.replace", side_effect=OSError("interrupted")),
        pytest.raises(OSError, match="interrupted"),
    ):
        store.commit(
            session_id=session_id,
            loaded_revision=1,
            context=normalize_context(_context(summary="new")),
        )
    assert context_path.read_text(encoding="utf-8") == before
    assert list(context_path.parent.glob(".context-*")) == []


def test_preflight_rewrites_safe_noncanonical_yaml(tmp_path: Path) -> None:
    project = tmp_path / "project"
    state = project / ".onetool" / "state" / "episodic-context"
    project.mkdir()
    store = ContextStore(context_max_kb=16, state_root=state, project_root=project)
    session_id = store.create_session()
    committed = store.commit(
        session_id=session_id,
        loaded_revision=0,
        context=normalize_context(_context()),
    )
    path = state / session_id / "context.yaml"
    path.write_text(render_context(committed).replace("\n", "\r\n") + "\r\n")

    loaded = store.preflight(session_id)

    assert loaded.revision == 1
    assert path.read_text(encoding="utf-8") == render_context(committed)


@pytest.mark.parametrize(
    "content",
    [
        "not: [valid",
        "!!python/object:builtins.object {}",
        "shared: &value [x]\nalias: *value\n",
    ],
)
def test_preflight_rejects_unsafe_or_invalid_yaml_without_rewrite(
    tmp_path: Path,
    content: str,
) -> None:
    project = tmp_path / "project"
    state = project / ".onetool" / "state" / "episodic-context"
    project.mkdir()
    store = ContextStore(context_max_kb=16, state_root=state, project_root=project)
    session_id = store.create_session()
    path = state / session_id / "context.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ContextError):
        store.preflight(session_id)
    assert path.read_text(encoding="utf-8") == content
