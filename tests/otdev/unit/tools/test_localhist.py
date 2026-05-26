from __future__ import annotations

import inspect
import json
import subprocess
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from otdev.tools import localhist
from otdev.tools._localhist import autosave as autosave_runtime
from otdev.tools._localhist.autosave import run_once
from otdev.tools._localhist.config import Config, resolve_paths, validate_project_path
from otdev.tools._localhist.git import GitRunner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.tools]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_pack_metadata_and_public_signatures() -> None:
    assert localhist.pack == "localhist"
    assert localhist.pack_aliases == ("lh",)
    assert localhist.__all__ == [
        "add_exclude",
        "add_force_include",
        "autosave_list",
        "autosave_start",
        "autosave_stop",
        "diff",
        "history",
        "info",
        "init",
        "log",
        "restore",
        "save",
        "show",
        "status",
    ]
    assert localhist.__ot_requires__ == {}
    for name in localhist.__all__:
        signature = inspect.signature(getattr(localhist, name))
        for param in signature.parameters.values():
            assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_config_defaults_and_path_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    config = Config()
    paths = resolve_paths(config)
    assert paths.git_dir == tmp_path / ".localhist"
    assert paths.work_tree == tmp_path
    assert paths.state_dir == tmp_path / ".onetool" / "state" / "localhist"
    assert paths.force_include_file == paths.state_dir / "force-include"
    assert Config().autosave.poll_interval_seconds == 30.0
    assert Config().autosave.quiet_period_seconds == 30.0
    assert Config().autosave.min_save_interval_seconds == 120.0
    assert Config().autosave.heartbeat_timeout_seconds == 120.0
    assert Config().autosave.message_prefix == "autosave"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Config(excludes=["build/"])
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Config(autosave={"unknown": True})
    with pytest.raises(ValueError, match="escapes"):
        validate_project_path("../outside.txt", paths)
    global_paths = resolve_paths(Config(git_dir=str(tmp_path / "global" / "{project_id}")))
    assert global_paths.git_dir.parent == tmp_path / "global"
    assert tmp_path.name in global_paths.git_dir.name
    with pytest.raises(ValueError, match="absolute git_dir requires"):
        resolve_paths(Config(git_dir=str(tmp_path / "global-no-token")))


def test_git_runner_uses_explicit_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    paths = resolve_paths(Config())
    calls: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls["args"] = args
        calls["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("otdev.tools._localhist.git.subprocess.run", fake_run)
    assert GitRunner(paths).run("status") == "ok"
    assert calls["args"] == ["git", "status"]
    kwargs = calls["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["cwd"] == tmp_path
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    env = kwargs["env"]
    assert isinstance(env, dict)
    assert env["GIT_DIR"] == str(tmp_path / ".localhist")
    assert env["GIT_WORK_TREE"] == str(tmp_path)


def test_init_info_status_save_log_and_gitignore(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "notes.txt", "one\n")
    _write(tmp_path / ".gitignore", "ignored/\n*.tmp\n")
    _write(tmp_path / "ignored" / "local.txt", "ignored\n")
    _write(tmp_path / "scratch.tmp", "ignored\n")
    init_result = localhist.init()
    assert init_result["ok"] is True
    assert init_result["created"] is True
    gitignore_lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert ".localhist/" in gitignore_lines
    exclude_lines = (tmp_path / ".localhist" / "info" / "exclude").read_text().splitlines()
    assert ".git/" in exclude_lines
    assert ".onetool/state/localhist/" in exclude_lines
    assert (tmp_path / ".onetool" / "state" / "localhist" / "force-include").exists()
    assert not (tmp_path / ".localhist" / "info" / "force-include").exists()
    assert localhist.init()["already_initialized"] is True

    status_result = localhist.status()
    assert status_result["initialized"] is True
    assert status_result["has_commits"] is False
    assert {entry["path"] for entry in status_result["files"]} == {".gitignore", "notes.txt"}
    assert "eligible_count" not in status_result
    assert "skipped" not in status_result

    info_result = localhist.info()
    assert info_result["initialized"] is True
    assert info_result["exclude_rules"] == [".git/", ".onetool/state/localhist/"]
    assert info_result["force_include_rules"] == []
    assert info_result["config"]["git_dir"] == ".localhist"

    save_result = localhist.save(message="first")
    assert save_result["created"] is True
    assert save_result["commit"]["kind"] == "manual"
    assert localhist.save(message="no changes")["created"] is False
    assert len(localhist.log(limit=5)["entries"]) == 1


def test_exclude_and_force_include_rules_are_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / ".gitignore", "*.secret\n")
    _write(tmp_path / "public.txt", "public\n")
    _write(tmp_path / "keep.secret", "secret\n")

    assert localhist.add_exclude(rule=["build/", "build/"])["added"] == 1
    force = localhist.add_force_include(rule=["keep.secret", "keep.secret"])
    assert force["added"] == 1
    assert force["added_rules"] == ["keep.secret"]
    assert force["unchanged_rules"] == ["keep.secret"]
    assert force["config_file"] == str(tmp_path / ".onetool" / "state" / "localhist" / "force-include")
    assert force["rules"] == ["keep.secret"]
    assert force["force_include_file"] == str(tmp_path / ".onetool" / "state" / "localhist" / "force-include")

    save_result = localhist.save(message="force include")
    assert save_result["created"] is True
    assert "secret" in localhist.show(ref="HEAD", path="keep.secret")["content"]


def test_save_accepts_free_form_kind_and_rejects_empty_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "one\n")

    assert localhist.save(message="", kind="manual") == {"ok": False, "error": "message is required"}
    result = localhist.save(message="custom", kind="agent-custom")

    assert result["created"] is True
    assert result["commit"]["kind"] == "agent-custom"
    assert localhist.log(limit=1)["entries"][0]["kind"] == "agent-custom"


def test_autosave_run_once_creates_auto_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "one\n")
    localhist.init()
    state_file = tmp_path / ".onetool" / "state" / "localhist" / "autosave-state.json"
    first_state = run_once(project_root=tmp_path)
    first_state["last_event_at"] = 0
    first_state["last_save"] = None
    state_file.write_text(json.dumps(first_state))

    state = run_once(project_root=tmp_path)

    assert state["last_save"]["result"]["created"] is True
    assert state["last_save"]["result"]["commit"]["kind"] == "auto"
    assert localhist.log(limit=5)["entries"][0]["subject"].startswith("autosave:")


def test_autosave_start_list_stop_and_stale_takeover(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    start = localhist.autosave_start()
    assert start["ok"] is True
    assert start["started"] is True
    assert start["config"]["autosave"]["message_prefix"] == "autosave"
    pid = start["state"]["pid"]

    reused = localhist.autosave_start()
    assert reused["reused"] is True
    assert reused["config"]["autosave"]["poll_interval_seconds"] == 30.0
    assert reused["state"]["pid"] == pid

    listed = localhist.autosave_list()
    assert listed["active"] is True
    assert listed["stale"] is False
    assert listed["active_project"] == str(tmp_path)
    assert listed["config"]["autosave"]["heartbeat_timeout_seconds"] == 120.0

    state_file = tmp_path / ".onetool" / "state" / "localhist" / "autosave-state.json"
    data = state_file.read_text()
    payload = json.loads(data)
    payload["heartbeat_at"] = -1_000_000
    state_file.write_text(json.dumps(payload))
    stale = localhist.autosave_list()
    assert stale["stale"] is True
    assert stale["config"]["autosave"]["quiet_period_seconds"] == 30.0
    takeover = localhist.autosave_start()
    assert takeover["started"] is True
    assert takeover["config"]["autosave"]["min_save_interval_seconds"] == 120.0
    assert takeover["state"]["pid"] != pid

    stopped = localhist.autosave_stop(path=str(tmp_path))
    assert stopped["stopped"] is True


def test_autosave_refreshes_quiet_timer_when_dirty_signature_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "one\n")
    localhist.init()
    state_file = tmp_path / ".onetool" / "state" / "localhist" / "autosave-state.json"
    state_file.write_text(
        json.dumps(
            {
                "status": "running",
                "pid": None,
                "project_root": str(tmp_path),
                "heartbeat_at": 0,
                "last_event_at": 0,
                "last_dirty_signature": "previous",
                "last_save": None,
                "recent_errors": [],
                "stop_requested": False,
                "heartbeat_timeout_seconds": 120.0,
            }
        )
    )
    monkeypatch.setattr(autosave_runtime, "_now", lambda: 100.0)

    state = run_once(project_root=tmp_path)

    assert state["last_event_at"] == 100.0
    assert state["last_save"] is None
    state["last_event_at"] = 0
    state_file.write_text(json.dumps(state))

    saved = run_once(project_root=tmp_path)

    assert saved["last_save"]["result"]["created"] is True


def test_autosave_stop_path_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    active = tmp_path / "active"
    other = tmp_path / "other"
    active.mkdir()
    other.mkdir()
    monkeypatch.setenv("OT_CWD", str(active))

    assert localhist.autosave_start()["started"] is True
    result = localhist.autosave_stop(path=str(other))

    assert result["stopped"] is False
    assert result["reason"] == "active_project_mismatch"
    assert localhist.autosave_stop()["stopped"] is True


def test_autosave_start_explicit_path_switches_from_current_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    current = tmp_path / "current"
    explicit = tmp_path / "explicit"
    current.mkdir()
    explicit.mkdir()
    monkeypatch.setenv("OT_CWD", str(current))

    first = localhist.autosave_start()
    switched = localhist.autosave_start(path=str(explicit))

    assert first["started"] is True
    assert switched["started"] is True
    current_state = json.loads(
        (current / ".onetool" / "state" / "localhist" / "autosave-state.json").read_text()
    )
    assert current_state["stop_requested"] is True
    explicit_state = json.loads(
        (explicit / ".onetool" / "state" / "localhist" / "autosave-state.json").read_text()
    )
    assert explicit_state["project_root"] == str(explicit)
    assert localhist.autosave_stop(path=str(explicit))["stopped"] is True


def test_log_rejects_invalid_limit_before_and_after_commits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))

    assert localhist.log(limit=0) == {"ok": False, "error": "limit must be >= 1"}
    assert localhist.log(limit=-1) == {"ok": False, "error": "limit must be >= 1"}
    _write(tmp_path / "a.txt", "one\n")
    assert localhist.save(message="first")["created"] is True
    assert localhist.log(limit=0) == {"ok": False, "error": "limit must be >= 1"}
    assert localhist.log(limit=-1) == {"ok": False, "error": "limit must be >= 1"}


def test_status_log_history_diff_and_show_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "one\n")
    _write(tmp_path / "sub" / "b.txt", "b1\n")
    localhist.save(message="first")
    _write(tmp_path / "a.txt", "one\ntwo\nthree\n")
    _write(tmp_path / "sub" / "b.txt", "b2\n")
    localhist.save(message="second", kind="manual")
    _write(tmp_path / "sub" / "c.txt", "new\n")

    status = localhist.status(path="sub", status="untracked", limit=1)
    assert status["total_files"] == 1
    assert status["truncated"] is False
    assert status["files"][0]["path"] == "sub/c.txt"

    entry = localhist.log(limit=1, date_format="%Y-%m-%d")["entries"][0]
    assert entry["date"]
    assert entry["kind"] == "manual"

    history = localhist.history(path="a.txt", limit=5)
    assert history["path"] == "a.txt"
    assert len(history["entries"]) == 2
    assert history["entries"][0]["follow"] is True

    assert localhist.diff(ref="HEAD~1", against="HEAD", path="a.txt")["mode"] == "ref"
    assert localhist.diff(ref="HEAD", against="worktree", path="sub/c.txt")["mode"] == "worktree"

    shown = localhist.show(ref="HEAD", path="a.txt", offset=2, limit=1)
    assert shown["content"] == "two\n"
    assert shown["total_lines"] == 3
    assert shown["returned_lines"] == 1
    assert shown["has_more"] is True
    assert localhist.show(ref="HEAD", path="a.txt", tail=1)["content"] == "three\n"
    assert shown["truncated"] is False
    assert shown["bytes_returned"] == len(b"two\n")


def test_symlink_path_can_be_inspected_when_target_escapes_worktree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("secret\n")
    (tmp_path / "link-out").symlink_to(outside)

    assert localhist.save(message="symlink outside")["created"] is True
    shown = localhist.show(ref="HEAD", path="link-out")

    assert shown["ok"] is True
    assert shown["content"].strip() == str(outside)


def test_diff_show_restore(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "one\n")
    localhist.save(message="first")
    _write(tmp_path / "a.txt", "two\n")
    localhist.save(message="second")

    assert "one" in localhist.show(ref="HEAD~1", path="a.txt")["content"]
    assert localhist.diff(ref="HEAD")["ok"] is True
    assert localhist.diff(ref="HEAD~20")["ok"] is False
    assert localhist.show(ref="HEAD", path="../bad")["ok"] is False

    dry_run = localhist.restore(ref="HEAD~1", paths=["a.txt"])
    assert dry_run["dry_run"] is True
    assert (tmp_path / "a.txt").read_text() == "two\n"

    applied = localhist.restore(ref="HEAD~1", paths=["a.txt"], dry_run=False)
    assert applied["ok"] is True
    assert (tmp_path / "a.txt").read_text() == "one\n"
    assert localhist.restore(ref="HEAD", paths=[])["ok"] is False


def test_diff_and_show_report_truncation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    monkeypatch.setattr("otdev.tools._localhist.core.MAX_DIFF_BYTES", 100)
    monkeypatch.setattr("otdev.tools._localhist.core.MAX_SHOW_BYTES", 100)
    _write(tmp_path / "large.txt", "baseline\n")
    assert localhist.save(message="baseline")["created"] is True
    _write(tmp_path / "large.txt", ("a" * 100 + "\n") * 12_000)
    assert localhist.save(message="large")["created"] is True

    diff = localhist.diff(ref="HEAD")
    assert diff["truncated"] is True
    assert diff["bytes_returned"] <= diff["max_bytes"]

    shown = localhist.show(ref="HEAD", path="large.txt")
    assert shown["truncated"] is True
    assert shown["bytes_returned"] <= shown["max_bytes"]


def test_restore_relative_ref_is_resolved_before_safety_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OT_CWD", str(tmp_path))
    _write(tmp_path / "a.txt", "one\n")
    localhist.save(message="baseline")
    _write(tmp_path / "a.txt", "two\n")
    localhist.save(message="change")
    _write(tmp_path / "a.txt", "three unsaved\n")

    applied = localhist.restore(ref="HEAD~1", paths=["a.txt"], dry_run=False)

    assert applied["ok"] is True
    assert applied["requested_ref"] == "HEAD~1"
    assert (tmp_path / "a.txt").read_text() == "one\n"
    assert applied["pre_restore_snapshot"]["created"] is True
