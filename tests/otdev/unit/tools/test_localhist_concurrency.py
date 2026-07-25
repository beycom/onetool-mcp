"""Separate-process concurrency tests for local-history Git mutations."""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from queue import Empty
from typing import TYPE_CHECKING, Any

import pytest

from otdev.tools import localhist
from otdev.tools._localhist.autosave import run_once

if TYPE_CHECKING:
    from multiprocessing.context import SpawnContext
    from multiprocessing.sharedctypes import Synchronized
    from multiprocessing.synchronize import Event

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(project: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=project,
        env={
            **os.environ,
            "GIT_DIR": str(project / ".localhist"),
            "GIT_WORK_TREE": str(project),
        },
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _worker(
    project: str,
    operation: str,
    kwargs: dict[str, Any],
    hold_acquisition: int,
    entered: Event,
    release: Event,
    active: Synchronized[int],
    max_active: Synchronized[int],
    results: multiprocessing.Queue[dict[str, Any]],
    fail_snapshot: bool,
) -> None:
    """Run one public operation while observing the real interprocess lock."""

    os.environ["OT_CWD"] = project

    from otdev.tools import localhist as child_localhist
    from otdev.tools._localhist import core
    from otdev.tools._localhist.autosave import run_once as child_run_once

    real_repository_lock = core.repository_lock
    acquisition_count = 0

    @contextmanager
    def observed_repository_lock(paths: Any):
        nonlocal acquisition_count
        with real_repository_lock(paths):
            acquisition_count += 1
            with active.get_lock(), max_active.get_lock():
                active.value += 1
                max_active.value = max(max_active.value, active.value)
            try:
                if acquisition_count == hold_acquisition:
                    entered.set()
                    if not release.wait(timeout=20):
                        raise TimeoutError("test barrier release timed out")
                yield
            finally:
                with active.get_lock():
                    active.value -= 1

    core.repository_lock = observed_repository_lock

    if fail_snapshot:

        def raise_snapshot(*_args: Any, **_kwargs: Any) -> dict[str, object]:
            raise RuntimeError("injected snapshot failure")

        core._create_snapshot_unlocked = raise_snapshot

    try:
        if operation == "autosave":
            result: dict[str, Any] = dict(child_run_once(project_root=Path(project)))
        else:
            function = getattr(child_localhist, operation)
            result = dict(function(**kwargs))
        results.put(
            {
                "operation": operation,
                "result": result,
                "acquisitions": acquisition_count,
            }
        )
    except BaseException as exc:
        results.put(
            {
                "operation": operation,
                "exception": f"{type(exc).__name__}: {exc}",
                "acquisitions": acquisition_count,
            }
        )


def _spawn_context() -> SpawnContext:
    return multiprocessing.get_context("spawn")


def _start_worker(
    context: SpawnContext,
    *,
    project: Path,
    operation: str,
    kwargs: dict[str, Any] | None = None,
    hold_acquisition: int = 1,
    entered: Event,
    release: Event,
    active: Synchronized[int],
    max_active: Synchronized[int],
    results: multiprocessing.Queue[dict[str, Any]],
    fail_snapshot: bool = False,
) -> multiprocessing.Process:
    process = context.Process(
        target=_worker,
        args=(
            str(project),
            operation,
            kwargs or {},
            hold_acquisition,
            entered,
            release,
            active,
            max_active,
            results,
            fail_snapshot,
        ),
    )
    process.start()
    return process


def _run_blocked_pair(
    project: Path,
    *,
    first_operation: str,
    first_kwargs: dict[str, Any] | None = None,
    first_hold_acquisition: int = 1,
    second_operation: str,
    second_kwargs: dict[str, Any] | None = None,
    fail_first_snapshot: bool = False,
) -> list[dict[str, Any]]:
    context = _spawn_context()
    first_entered = context.Event()
    first_release = context.Event()
    second_entered = context.Event()
    second_release = context.Event()
    second_release.set()
    active = context.Value("i", 0)
    max_active = context.Value("i", 0)
    results = context.Queue()

    first = _start_worker(
        context,
        project=project,
        operation=first_operation,
        kwargs=first_kwargs,
        hold_acquisition=first_hold_acquisition,
        entered=first_entered,
        release=first_release,
        active=active,
        max_active=max_active,
        results=results,
        fail_snapshot=fail_first_snapshot,
    )
    assert first_entered.wait(timeout=15)

    second = _start_worker(
        context,
        project=project,
        operation=second_operation,
        kwargs=second_kwargs,
        entered=second_entered,
        release=second_release,
        active=active,
        max_active=max_active,
        results=results,
    )
    assert not second_entered.wait(timeout=0.4)
    first_release.set()
    assert second_entered.wait(timeout=15)

    first.join(timeout=20)
    second.join(timeout=20)
    assert first.exitcode == 0
    assert second.exitcode == 0
    assert max_active.value == 1

    payloads: list[dict[str, Any]] = []
    try:
        payloads = [results.get(timeout=5), results.get(timeout=5)]
    except Empty:
        pytest.fail("worker did not report its result")
    return payloads


def _result_for(payloads: list[dict[str, Any]], operation: str) -> dict[str, Any]:
    payload = next(item for item in payloads if item["operation"] == operation)
    assert "exception" not in payload
    return payload


def _assert_repository_integrity(project: Path) -> None:
    assert _git(project, "diff", "--cached", "--name-only") == ""
    _git(project, "fsck", "--no-dangling")
    assert not (project / ".localhist" / "index.lock").exists()
    assert (project / ".onetool" / "state" / "localhist" / "repository.lock").exists()
    tracked = _git(project, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    assert not any(path.startswith(".onetool/state/localhist/") for path in tracked)


def test_autosave_and_manual_save_serialize_complete_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "base\n")
    assert localhist.save(message="baseline")["created"] is True
    _write(tmp_path / "a.txt", "dirty\n")

    state = run_once(project_root=tmp_path)
    state["last_event_at"] = 0
    state["last_save"] = None
    (tmp_path / ".onetool/state/localhist/autosave-state.json").write_text(
        json.dumps(state),
        encoding="utf-8",
    )

    payloads = _run_blocked_pair(
        tmp_path,
        first_operation="autosave",
        first_hold_acquisition=2,
        second_operation="save",
        second_kwargs={"message": "manual overlap"},
    )

    autosave = _result_for(payloads, "autosave")
    manual = _result_for(payloads, "save")
    assert autosave["result"]["last_save"]["result"]["created"] is True
    assert manual["result"]["ok"] is True
    assert _git(tmp_path, "show", "HEAD:a.txt") == "dirty\n"
    subjects = _git(tmp_path, "log", "--format=%s").splitlines()
    assert subjects[0].startswith("autosave:")
    assert subjects[-1] == "baseline"
    _assert_repository_integrity(tmp_path)


def test_save_and_restore_serialize_nested_safety_and_audit_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "one\n")
    _write(tmp_path / "b.txt", "b1\n")
    baseline = localhist.save(message="baseline")
    baseline_ref = str(baseline["commit"]["hash"])
    _write(tmp_path / "a.txt", "two unsaved\n")
    _write(tmp_path / "b.txt", "b2\n")

    payloads = _run_blocked_pair(
        tmp_path,
        first_operation="save",
        first_kwargs={"message": "save b", "paths": "b.txt"},
        second_operation="restore",
        second_kwargs={
            "ref": baseline_ref,
            "paths": ["a.txt"],
            "dry_run": False,
        },
    )

    saved = _result_for(payloads, "save")
    restored = _result_for(payloads, "restore")
    assert saved["result"]["created"] is True
    assert restored["result"]["ok"] is True
    assert restored["result"]["pre_restore_snapshot"]["created"] is True
    assert restored["result"]["restore_snapshot"]["created"] is True
    assert restored["acquisitions"] == 1
    assert (tmp_path / "a.txt").read_text() == "one\n"
    assert _git(tmp_path, "show", "HEAD:b.txt") == "b2\n"
    assert _git(tmp_path, "log", "--format=%s", "-3").splitlines() == [
        f"restore from {baseline_ref}",
        f"pre-restore safety before {baseline_ref}",
        "save b",
    ]
    _assert_repository_integrity(tmp_path)


def test_save_and_applied_prune_serialize_ref_rewrite_and_gc(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "old one\n")
    assert localhist.save(message="old-1")["created"] is True

    def backdate(date: str) -> None:
        subprocess.run(
            ["git", "commit", "--amend", "--no-edit"],
            cwd=tmp_path,
            env={
                **os.environ,
                "GIT_DIR": str(tmp_path / ".localhist"),
                "GIT_WORK_TREE": str(tmp_path),
                "GIT_AUTHOR_DATE": date,
                "GIT_COMMITTER_DATE": date,
            },
            check=True,
            capture_output=True,
        )

    backdate("2020-01-01T00:00:00Z")
    _write(tmp_path / "a.txt", "old two\n")
    assert localhist.save(message="old-2")["created"] is True
    backdate("2020-02-01T00:00:00Z")
    _write(tmp_path / "a.txt", "recent\n")
    assert localhist.save(message="recent")["created"] is True
    _write(tmp_path / "a.txt", "overlap save\n")

    payloads = _run_blocked_pair(
        tmp_path,
        first_operation="save",
        first_kwargs={"message": "overlap"},
        second_operation="prune",
        second_kwargs={"older_than_days": 30, "gc": True, "dry_run": False},
    )

    assert _result_for(payloads, "save")["result"]["created"] is True
    pruned = _result_for(payloads, "prune")["result"]
    assert pruned == {"ok": True, "dropped": 1, "kept": 3, "gc": True}
    assert _git(tmp_path, "rev-list", "--count", "HEAD").strip() == "3"
    assert _git(tmp_path, "show", "HEAD:a.txt") == "overlap save\n"
    assert _git(tmp_path, "symbolic-ref", "--short", "HEAD").strip()
    _assert_repository_integrity(tmp_path)


def test_init_and_save_serialize_repository_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "content\n")

    payloads = _run_blocked_pair(
        tmp_path,
        first_operation="init",
        second_operation="save",
        second_kwargs={"message": "first snapshot"},
    )

    assert _result_for(payloads, "init")["result"]["ok"] is True
    assert _result_for(payloads, "save")["result"]["created"] is True
    assert _git(tmp_path, "rev-list", "--count", "HEAD").strip() == "1"
    assert _git(tmp_path, "show", "HEAD:a.txt") == "content\n"
    _assert_repository_integrity(tmp_path)


def test_snapshot_exception_releases_repository_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "content\n")

    payloads = _run_blocked_pair(
        tmp_path,
        first_operation="save",
        first_kwargs={"message": "injected failure"},
        second_operation="save",
        second_kwargs={"message": "successful retry"},
        fail_first_snapshot=True,
    )

    saves = sorted(
        (item for item in payloads if item["operation"] == "save"),
        key=lambda item: bool(item["result"].get("ok")),
    )
    assert saves[0]["result"] == {
        "ok": False,
        "error": "injected snapshot failure",
    }
    assert saves[1]["result"]["created"] is True
    assert _git(tmp_path, "log", "--format=%s").strip() == "successful retry"
    _assert_repository_integrity(tmp_path)


@pytest.mark.parametrize(
    ("rule_operation", "rule", "expected_path"),
    [
        ("add_exclude", "scratch/", ".localhist/info/exclude"),
        (
            "add_force_include",
            "generated.txt",
            ".onetool/state/localhist/force-include",
        ),
    ],
)
def test_rule_mutations_serialize_with_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rule_operation: str,
    rule: str,
    expected_path: str,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    if rule_operation == "add_force_include":
        _write(tmp_path / ".gitignore", "generated.txt\n")
    _write(tmp_path / "a.txt", "base\n")
    assert localhist.save(message="baseline")["created"] is True
    _write(tmp_path / "a.txt", "changed\n")
    if rule_operation == "add_force_include":
        _write(tmp_path / "generated.txt", "generated\n")

    payloads = _run_blocked_pair(
        tmp_path,
        first_operation=rule_operation,
        first_kwargs={"rule": rule},
        second_operation="save",
        second_kwargs={"message": f"save after {rule_operation}"},
    )

    mutation = _result_for(payloads, rule_operation)
    saved = _result_for(payloads, "save")
    assert mutation["result"]["added"] == 1
    assert mutation["acquisitions"] == 1
    assert saved["result"]["created"] is True
    assert rule in (tmp_path / expected_path).read_text().splitlines()
    assert _git(tmp_path, "show", "HEAD:a.txt") == "changed\n"
    _assert_repository_integrity(tmp_path)


def test_different_projects_progress_under_independent_locks(
    tmp_path: Path,
) -> None:
    first_project = tmp_path / "first"
    second_project = tmp_path / "second"
    first_project.mkdir()
    second_project.mkdir()
    _write(first_project / "a.txt", "first\n")
    _write(second_project / "a.txt", "second\n")

    context = _spawn_context()
    first_entered = context.Event()
    first_release = context.Event()
    second_entered = context.Event()
    second_release = context.Event()
    second_release.set()
    active = context.Value("i", 0)
    max_active = context.Value("i", 0)
    results = context.Queue()

    first = _start_worker(
        context,
        project=first_project,
        operation="save",
        kwargs={"message": "first project"},
        entered=first_entered,
        release=first_release,
        active=active,
        max_active=max_active,
        results=results,
    )
    assert first_entered.wait(timeout=15)
    second = _start_worker(
        context,
        project=second_project,
        operation="save",
        kwargs={"message": "second project"},
        entered=second_entered,
        release=second_release,
        active=active,
        max_active=max_active,
        results=results,
    )
    assert second_entered.wait(timeout=15)
    second.join(timeout=20)
    assert second.exitcode == 0
    assert max_active.value == 2
    first_release.set()
    first.join(timeout=20)
    assert first.exitcode == 0

    assert _git(first_project, "show", "HEAD:a.txt") == "first\n"
    assert _git(second_project, "show", "HEAD:a.txt") == "second\n"
    _assert_repository_integrity(first_project)
    _assert_repository_integrity(second_project)
