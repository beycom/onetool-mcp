"""OneTool Local History snapshots backed by Git."""

from __future__ import annotations

pack = "localhist"
pack_aliases = ("lh",)

__all__ = [
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

__ot_requires__: dict[str, list[tuple[str, str]]] = {}

from otpack import LogSpan

from otdev.tools._localhist.autosave import (
    autosave_list_project,
    autosave_start_project,
    autosave_stop_project,
)
from otdev.tools._localhist.config import Config as _Config
from otdev.tools._localhist.core import (
    append_exclude_rules,
    append_force_include_rules,
    diff_snapshot,
    info_repository,
    init_repository,
    list_history,
    list_log,
    restore_paths,
    save_snapshot,
    show_file,
    status_repository,
)

SnapshotKind = str


class Config(_Config):
    """Pack configuration discovered by the registry."""


def init() -> dict[str, object]:
    """Initialize the project-local history repository.

    Returns:
        Structured initialization status, resolved paths, and inspection command.
    """

    with LogSpan(span="localhist.init") as span:
        result = init_repository()
        span.add(ok=result.get("ok"), created=result.get("created"))
        return result


def status(
    *,
    path: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    """Inspect local-history working tree status.

    Args:
        path: Optional project-relative path to inspect.
        status: Optional status category filter.
        limit: Optional maximum number of file entries to return.

    Returns:
        Git-like file status with dirty counts.
    """

    with LogSpan(span="localhist.status", path=path, status=status, limit=limit) as span:
        result = status_repository(path=path, status=status, limit=limit)
        span.add(ok=result.get("ok"), initialized=result.get("initialized"))
        return result


def info() -> dict[str, object]:
    """Inspect local-history initialization, config, paths, and current head.

    Returns:
        Structured repository metadata and localhist-specific ignore files.
    """

    with LogSpan(span="localhist.info") as span:
        result = info_repository()
        span.add(ok=result.get("ok"), initialized=result.get("initialized"))
        return result


def add_exclude(*, rule: str | list[str]) -> dict[str, object]:
    """Append localhist-only exclude rules idempotently.

    Args:
        rule: One rule or a list of rules to append to `.localhist/info/exclude`.

    Returns:
        Structured result with added count and effective rules.
    """

    rules = [rule] if isinstance(rule, str) else rule
    with LogSpan(span="localhist.add_exclude", ruleCount=len(rules)) as span:
        result = append_exclude_rules(rules=rules)
        span.add(ok=result.get("ok"), added=result.get("added"))
        return result


def add_force_include(*, rule: str | list[str]) -> dict[str, object]:
    """Append localhist force-include pathspec rules idempotently.

    Args:
        rule: One rule or a list of rules to append to `.onetool/state/localhist/force-include`.

    Returns:
        Structured result with added count and effective rules.
    """

    rules = [rule] if isinstance(rule, str) else rule
    with LogSpan(span="localhist.add_force_include", ruleCount=len(rules)) as span:
        result = append_force_include_rules(rules=rules)
        span.add(ok=result.get("ok"), added=result.get("added"))
        return result


def save(*, message: str, kind: SnapshotKind = "") -> dict[str, object]:
    """Create a local-history snapshot.

    Args:
        message: Commit message for the snapshot.
        kind: Free-form snapshot kind metadata.

    Returns:
        Structured snapshot result with commit details or no-change status.
    """

    with LogSpan(span="localhist.save", kind=kind) as span:
        result = save_snapshot(message=message, kind=kind)
        span.add(ok=result.get("ok"), created=result.get("created"))
        return result


def autosave_start(*, path: str | None = None) -> dict[str, object]:
    """Start or reuse the shared localhist autosave watcher.

    Args:
        path: Optional project directory to watch. Defaults to the effective project cwd.

    Returns:
        Structured watcher status and active project details.
    """

    with LogSpan(span="localhist.autosave_start", path=path) as span:
        result = autosave_start_project(path=path)
        span.add(ok=result.get("ok"), started=result.get("started"))
        return result


def autosave_list() -> dict[str, object]:
    """List the shared localhist autosave watcher state.

    Returns:
        Structured active, stale, heartbeat, and last-save information.
    """

    with LogSpan(span="localhist.autosave_list") as span:
        result = autosave_list_project()
        span.add(ok=result.get("ok"), active=result.get("active"), stale=result.get("stale"))
        return result


def autosave_stop(*, path: str | None = None) -> dict[str, object]:
    """Stop the shared localhist autosave watcher.

    Args:
        path: Optional project directory. When supplied, the watcher is stopped only
            when it is watching that resolved project.

    Returns:
        Structured stop result.
    """

    with LogSpan(span="localhist.autosave_stop", path=path) as span:
        result = autosave_stop_project(path=path)
        span.add(ok=result.get("ok"), stopped=result.get("stopped"))
        return result


def log(*, limit: int = 20, date_format: str = "%Y-%m-%d %H:%M:%S %Z") -> dict[str, object]:
    """List local-history snapshots.

    Args:
        limit: Maximum commits to return.
        date_format: `strftime` format for each entry's local date.

    Returns:
        Structured log entries, or an empty list when no commits exist.
    """

    with LogSpan(span="localhist.log", limit=limit) as span:
        result = list_log(limit=limit, date_format=date_format)
        span.add(ok=result.get("ok"), count=len(result.get("entries", [])))
        return result


def history(
    *,
    path: str,
    limit: int = 20,
    follow: bool = True,
    date_format: str = "%Y-%m-%d %H:%M:%S %Z",
) -> dict[str, object]:
    """List snapshots that touched a project-relative path.

    Args:
        path: Project-relative path to inspect.
        limit: Maximum commits to return.
        follow: Whether Git should follow renames for a single file path.
        date_format: `strftime` format for each entry's local date.

    Returns:
        Structured path-scoped history entries.
    """

    with LogSpan(span="localhist.history", path=path, limit=limit, follow=follow) as span:
        result = list_history(path=path, limit=limit, follow=follow, date_format=date_format)
        span.add(ok=result.get("ok"), count=len(result.get("entries", [])))
        return result


def diff(
    *,
    ref: str = "HEAD",
    against: str | None = None,
    path: str | None = None,
) -> dict[str, object]:
    """Return a patch for a local-history snapshot.

    Args:
        ref: Commit ref to inspect.
        against: Optional commit ref to compare against, or `worktree`.
        path: Optional project-relative path to limit the diff.

    Returns:
        Structured diff result or a clear ref/path error.
    """

    with LogSpan(span="localhist.diff", ref=ref, against=against, path=path) as span:
        result = diff_snapshot(ref=ref, against=against, path=path)
        span.add(ok=result.get("ok"))
        return result


def show(
    *,
    ref: str,
    path: str,
    offset: int = 1,
    limit: int | None = None,
    tail: int | None = None,
) -> dict[str, object]:
    """Return file content from a local-history snapshot.

    Args:
        ref: Commit ref to inspect.
        path: Project-relative file path.
        offset: One-based first line to return.
        limit: Maximum number of lines to return.
        tail: Return the last N lines instead of using offset/limit.

    Returns:
        Structured file content result or a clear ref/path error.
    """

    with LogSpan(span="localhist.show", ref=ref, path=path) as span:
        result = show_file(ref=ref, path=path, offset=offset, limit=limit, tail=tail)
        span.add(ok=result.get("ok"))
        return result


def restore(
    *,
    ref: str,
    paths: list[str],
    dry_run: bool = True,
) -> dict[str, object]:
    """Restore selected paths from a local-history snapshot.

    Args:
        ref: Snapshot ref to restore from.
        paths: Explicit project-relative paths to restore.
        dry_run: When true, report changes without modifying files.

    Returns:
        Structured dry-run or applied restore result.
    """

    with LogSpan(span="localhist.restore", ref=ref, pathCount=len(paths), dryRun=dry_run) as span:
        result = restore_paths(ref=ref, paths=paths, dry_run=dry_run)
        span.add(ok=result.get("ok"), dryRun=result.get("dry_run"))
        return result
