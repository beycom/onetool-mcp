"""Deterministic episodic context normalization and persistence."""

from __future__ import annotations

import os
import re
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from yaml.events import AliasEvent

from ot.paths import get_effective_cwd, get_project_state_dir
from ottools._worker.models import CommittedContext, WorkerContext

_SESSION_RE = re.compile(r"^ep-[0-9a-f]{32}$")


class ContextError(ValueError):
    """A deterministic context validation or persistence failure."""


class _CanonicalDumper(yaml.SafeDumper):
    """YAML dumper with stable scalar style and no aliases."""

    def ignore_aliases(self, _data: Any) -> bool:
        return True


def _represent_string(dumper: _CanonicalDumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_CanonicalDumper.add_representer(str, _represent_string)


def _normalize_text(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip(" \t") for line in lines]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _dedupe_strings(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_value(value)
        if isinstance(normalized, str):
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
        result.append(normalized)
    return result


def _normalize_path(value: str) -> str:
    parts = [part for part in value.replace("\\", "/").split("/") if part not in {"", "."}]
    prefix = "/" if value.startswith(("/", "\\")) else ""
    return prefix + "/".join(parts)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, list):
        return _dedupe_strings(value)
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    return value


def normalize_context(value: object) -> WorkerContext:
    """Normalize allowed mechanical forms and validate the strict context."""
    if not isinstance(value, dict):
        raise ContextError("context must be an object")
    normalized = _normalize_value(value)
    references = normalized.get("references")
    if isinstance(references, list):
        for reference in references:
            if isinstance(reference, dict) and isinstance(reference.get("path"), str):
                reference["path"] = _normalize_path(reference["path"])

    for key, fields in (("knowledge", ("kind", "text")), ("references", ("path", "purpose"))):
        entries = normalized.get(key)
        if not isinstance(entries, list):
            continue
        unique: list[Any] = []
        seen: set[tuple[Any, ...]] = set()
        for entry in entries:
            identity = tuple(entry.get(field) for field in fields) if isinstance(entry, dict) else (id(entry),)
            if identity in seen:
                continue
            seen.add(identity)
            unique.append(entry)
        normalized[key] = unique

    try:
        return WorkerContext.model_validate(normalized)
    except ValidationError as exc:
        raise ContextError(str(exc)) from exc


def render_context(context: CommittedContext) -> str:
    """Render canonical YAML with fixed model field order and one final newline."""
    data = context.model_dump(mode="python")
    ordered = {
        "schema_version": data["schema_version"],
        "revision": data["revision"],
        "goal": data["goal"],
        "work": data["work"],
        "knowledge": data["knowledge"],
        "questions": data["questions"],
        "references": data["references"],
    }
    rendered = yaml.dump(
        ordered,
        Dumper=_CanonicalDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=10_000,
    )
    return rendered.rstrip("\n") + "\n"


@dataclass(frozen=True)
class LoadedContext:
    """Validated episode-start context and the revision used for commit checks."""

    revision: int
    value: dict[str, Any]


class ContextStore:
    """Store one canonical context file per opaque project-local session."""

    def __init__(
        self,
        *,
        context_max_kb: int,
        state_root: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._max_bytes = context_max_kb * 1024
        self._state_root = state_root or get_project_state_dir("episodic-context")
        self._project_root = (project_root or get_effective_cwd()).resolve()

    def create_session(self) -> str:
        """Create and return a new opaque session directory."""
        self._state_root.mkdir(parents=True, exist_ok=True)
        for _attempt in range(10):
            session_id = f"ep-{secrets.token_hex(16)}"
            try:
                self._session_dir(session_id).mkdir()
            except FileExistsError:
                continue
            return session_id
        raise ContextError("could not allocate a unique session ID")

    def require_session(self, session_id: str) -> None:
        """Require an existing session under this project's state root."""
        session_dir = self._session_dir(session_id)
        if session_dir.is_symlink() or not session_dir.is_dir():
            raise ContextError(f"session_id does not exist in this project: {session_id}")

    def preflight(self, session_id: str) -> LoadedContext:
        """Safely load, validate, canonicalize, and size-check stored context."""
        self.require_session(session_id)
        return self._load(session_id, rewrite=True)

    def commit(
        self,
        *,
        session_id: str,
        loaded_revision: int,
        context: WorkerContext,
    ) -> CommittedContext:
        """Atomically commit terminal context if the loaded revision is current."""
        current = self._load(session_id, rewrite=False)
        if current.revision != loaded_revision:
            raise ContextError(
                "context revision changed during episode: "
                f"expected {loaded_revision}, found {current.revision}"
            )
        committed = CommittedContext(
            schema_version=1,
            revision=loaded_revision + 1,
            **context.model_dump(mode="python"),
        )
        self._validate_references(committed)
        rendered = render_context(committed)
        self._validate_size(rendered)
        self._write_atomic(self._context_path(session_id), rendered)
        return committed

    def _load(self, session_id: str, *, rewrite: bool) -> LoadedContext:
        path = self._context_path(session_id)
        if path.is_symlink():
            raise ContextError(f"context path is not a regular file: {path}")
        if not path.exists():
            return LoadedContext(
                revision=0,
                value={"schema_version": 1, "revision": 0, "context": None},
            )
        if not path.is_file():
            raise ContextError(f"context path is not a regular file: {path}")
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ContextError(f"could not read context file {path}: {exc}") from exc
        try:
            if any(isinstance(event, AliasEvent) for event in yaml.parse(original)):
                raise yaml.YAMLError("YAML aliases are not allowed")
            raw = yaml.safe_load(original)
        except yaml.YAMLError as exc:
            raise ContextError(f"invalid YAML in {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ContextError(f"context file must contain an object: {path}")

        worker_raw = {
            key: value
            for key, value in raw.items()
            if key not in {"schema_version", "revision"}
        }
        worker = normalize_context(worker_raw)
        try:
            committed = CommittedContext.model_validate(
                {
                    "schema_version": raw.get("schema_version"),
                    "revision": raw.get("revision"),
                    **worker.model_dump(mode="python"),
                }
            )
        except ValidationError as exc:
            raise ContextError(str(exc)) from exc
        unknown_runtime = set(raw) - set(type(committed).model_fields)
        if unknown_runtime:
            raise ContextError(f"unknown context fields: {sorted(unknown_runtime)}")

        self._validate_references(committed)
        rendered = render_context(committed)
        self._validate_size(rendered)
        if rewrite and original != rendered:
            self._write_atomic(path, rendered)
        return LoadedContext(
            revision=committed.revision,
            value=committed.model_dump(mode="json"),
        )

    def _validate_references(self, context: WorkerContext) -> None:
        for index, reference in enumerate(context.references):
            candidate = (self._project_root / reference.path).resolve()
            if not candidate.is_relative_to(self._project_root):
                raise ContextError(f"references.{index}.path escapes project: {reference.path}")
            if not candidate.is_file():
                raise ContextError(
                    f"references.{index}.path is not an existing regular file: "
                    f"{reference.path}"
                )

    def _validate_size(self, rendered: str) -> None:
        actual = len(rendered.encode("utf-8"))
        if actual > self._max_bytes:
            configured_kb = self._max_bytes // 1024
            raise ContextError(
                f"canonical context is {actual} bytes; limit is {configured_kb} KB "
                f"({self._max_bytes} bytes)"
            )

    def _session_dir(self, session_id: str) -> Path:
        if not _SESSION_RE.fullmatch(session_id):
            raise ContextError(f"invalid session_id: {session_id}")
        return self._state_root / session_id

    def _context_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "context.yaml"

    @staticmethod
    def _write_atomic(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=".context-", dir=path.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            temp_path.replace(path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise


__all__ = [
    "ContextError",
    "ContextStore",
    "LoadedContext",
    "normalize_context",
    "render_context",
]
