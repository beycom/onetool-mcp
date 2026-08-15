"""Mechanical Local Changes, Console, and History lifecycle helpers."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import ValidationError

from ottools._worker.models import ConsoleRecord, HistoryRecord, LocalChange

if TYPE_CHECKING:
    from collections.abc import Mapping

_EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".onetool",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "tmp",
    "venv",
}


class ObservationError(OSError):
    """A project-tree or Console observation could not complete."""


class HistoryError(OSError):
    """A strict worker History operation failed."""


@dataclass(frozen=True)
class FileFingerprint:
    """Content-sensitive fingerprint for one regular project file."""

    digest: str
    size: int
    mode: int


def project_fingerprint(project_root: Path) -> dict[str, FileFingerprint]:
    """Return a stable VCS-independent fingerprint of regular project files."""
    root = project_root.resolve()
    if not root.is_dir():
        raise ObservationError(f"project root is not a directory: {root}")
    result: dict[str, FileFingerprint] = {}
    try:
        for current, dirnames, filenames in os.walk(
            root, topdown=True, followlinks=False
        ):
            current_path = Path(current)
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in _EXCLUDED_DIR_NAMES
                and not (current_path / name).is_symlink()
            )
            for filename in sorted(filenames):
                path = current_path / filename
                if path.is_symlink() or not path.is_file():
                    continue
                relative = path.relative_to(root).as_posix()
                stat_result = path.stat()
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
                result[relative] = FileFingerprint(
                    digest=digest.hexdigest(),
                    size=stat_result.st_size,
                    mode=stat_result.st_mode,
                )
    except OSError as exc:
        raise ObservationError(f"could not fingerprint project tree: {exc}") from exc
    return result


def classify_changes(
    before: Mapping[str, FileFingerprint],
    after: Mapping[str, FileFingerprint],
) -> list[LocalChange]:
    """Classify created, modified, and deleted paths in stable path order."""
    result: list[LocalChange] = []
    for path in sorted(set(before) | set(after)):
        classification: Literal["created", "modified", "deleted"]
        if path not in before:
            classification = "created"
        elif path not in after:
            classification = "deleted"
        elif before[path] != after[path]:
            classification = "modified"
        else:
            continue
        result.append(LocalChange(path=path, classification=classification))
    return result


class ConsoleObserver:
    """Capture body-free identifiers for Console messages created in an episode."""

    def __init__(self, *, project_root: Path) -> None:
        self._instances_root = (
            project_root.resolve() / ".onetool" / "state" / "console" / "instances"
        )
        self._before: dict[tuple[str, str], ConsoleRecord] = {}
        self._latest: dict[tuple[str, str], ConsoleRecord] = {}
        self.warning: str | None = None

    def capture_before(self) -> None:
        """Capture the message set before worker startup."""
        self._before = self._scan()
        self._latest = dict(self._before)

    def capture_current(self) -> None:
        """Capture messages while the child runtime is still alive."""
        try:
            self._latest.update(self._scan())
        except ObservationError:
            self.warning = "console_observation_failed"

    def created(self) -> list[ConsoleRecord]:
        """Return new body-free message metadata in stable identifier order."""
        keys = sorted(set(self._latest) - set(self._before))
        return [self._latest[key] for key in keys]

    def _scan(self) -> dict[tuple[str, str], ConsoleRecord]:
        if not self._instances_root.exists():
            return {}
        if self._instances_root.is_symlink() or not self._instances_root.is_dir():
            raise ObservationError("Console instances root is not a directory")
        result: dict[tuple[str, str], ConsoleRecord] = {}
        try:
            for instance in sorted(
                self._instances_root.iterdir(), key=lambda path: path.name
            ):
                messages = instance / "messages"
                if (
                    instance.is_symlink()
                    or not messages.is_dir()
                    or messages.is_symlink()
                ):
                    continue
                for path in sorted(messages.glob("*.json"), key=lambda item: item.name):
                    if path.is_symlink() or not path.is_file():
                        continue
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    metadata = raw.get("metadata") if isinstance(raw, dict) else None
                    if not isinstance(metadata, dict):
                        raise ObservationError(f"invalid Console metadata file: {path}")
                    message_id = metadata.get("id")
                    kind = metadata.get("kind")
                    if not isinstance(message_id, str) or not isinstance(kind, str):
                        raise ObservationError(f"invalid Console metadata file: {path}")
                    result[(instance.name, message_id)] = ConsoleRecord(
                        id=message_id,
                        kind=kind,
                    )
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
            raise ObservationError(
                f"could not observe Console metadata: {exc}"
            ) from exc
        return result


class HistoryStore:
    """Append and strictly read project-scoped mechanical History records."""

    def __init__(self, *, state_root: Path) -> None:
        self._path = state_root / "history.jsonl"

    @property
    def path(self) -> Path:
        """Return the History journal path."""
        return self._path

    def append(self, record: HistoryRecord) -> None:
        """Canonically append and durably flush one complete JSON line."""
        encoded = (
            json.dumps(
                record.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                self._path,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o600,
            )
            try:
                written = os.write(descriptor, encoded)
                if written != len(encoded):
                    raise HistoryError("incomplete History append")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as exc:
            raise HistoryError(f"could not append worker History: {exc}") from exc

    def read(self) -> list[HistoryRecord]:
        """Read a strict valid prefix, ignoring only one malformed final line."""
        if not self._path.exists():
            return []
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise HistoryError(f"could not read worker History: {exc}") from exc
        result: list[HistoryRecord] = []
        for index, line in enumerate(lines):
            try:
                result.append(HistoryRecord.model_validate_json(line))
            except (ValidationError, ValueError) as exc:
                if index == len(lines) - 1 and result:
                    break
                raise HistoryError(
                    f"invalid worker History line {index + 1}: {exc}"
                ) from exc
        return result


__all__ = [
    "ConsoleObserver",
    "FileFingerprint",
    "HistoryError",
    "HistoryStore",
    "ObservationError",
    "classify_changes",
    "project_fingerprint",
]
