"""Project-scoped interprocess locking for local-history mutations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from filelock import FileLock

if TYPE_CHECKING:
    from otdev.tools._localhist.config import Paths

REPOSITORY_LOCK_FILE = "repository.lock"


def repository_lock(paths: Paths) -> FileLock:
    """Return the deterministic lock covering one project's Git mutations.

    Callers that also hold the autosave watcher-state lock must acquire that
    state lock first. Public mutation entry points acquire this lock exactly
    once and call non-locking helpers for nested initialization and snapshots.
    """

    paths.state_dir.mkdir(parents=True, exist_ok=True)
    return FileLock(str(paths.state_dir / REPOSITORY_LOCK_FILE))


__all__ = ["REPOSITORY_LOCK_FILE", "repository_lock"]
