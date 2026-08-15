"""Strict named-Context normalization and project-local persistence."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

import yaml
from pydantic import ValidationError
from yaml.events import AliasEvent

from ot.paths import get_effective_cwd, get_project_state_dir
from ottools._worker.models import ContextListItem, ContextMetadata

CONTEXT_NAME_MAX_CHARS = 64
_CONTEXT_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FRONTMATTER_RE = re.compile(
    r"\A---\n(?P<yaml>.*?)\n---(?:\n(?P<body>.*))?\Z", re.DOTALL
)
_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\((?P<target>[^)]+)\)")


class ContextError(ValueError):
    """A deterministic Context validation or persistence failure."""


class _CanonicalDumper(yaml.SafeDumper):
    """YAML dumper with stable scalar style and no aliases."""

    def ignore_aliases(self, _data: Any) -> bool:
        return True


class _StrictLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_mapping(
    loader: _StrictLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.YAMLError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def validate_context_name(value: str) -> str:
    """Return a valid unambiguous lowercase Context slug."""
    if not isinstance(value, str):
        raise ContextError("context name must be a string")
    if len(value) > CONTEXT_NAME_MAX_CHARS or not _CONTEXT_NAME_RE.fullmatch(value):
        raise ContextError(
            "context name must be a lowercase slug of at most "
            f"{CONTEXT_NAME_MAX_CHARS} characters"
        )
    return value


def normalize_body(value: str) -> str:
    """Normalize permitted line endings and trailing whitespace."""
    if not isinstance(value, str):
        raise ContextError("context body must be a string")
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip(" \t") for line in lines]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _normalize_description(value: str) -> str:
    return normalize_body(value)


def _normalize_tags(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ContextError("tags must contain only strings")
        tag = value.strip()
        if tag in seen:
            raise ContextError(f"tags must be unique: {tag!r}")
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _validate_metadata(value: object) -> ContextMetadata:
    if not isinstance(value, dict):
        raise ContextError("Context frontmatter must contain an object")
    raw = dict(value)
    if isinstance(raw.get("description"), str):
        raw["description"] = _normalize_description(raw["description"])
    if isinstance(raw.get("tags"), list):
        raw["tags"] = _normalize_tags(raw["tags"])
    try:
        return ContextMetadata.model_validate(raw)
    except ValidationError as exc:
        raise ContextError(str(exc)) from exc


def render_context(metadata: ContextMetadata, body: str) -> str:
    """Render one canonical Markdown Context file."""
    normalized_body = normalize_body(body)
    data = metadata.model_dump(mode="python")
    ordered = {
        "schema_version": data["schema_version"],
        "revision": data["revision"],
        "status": data["status"],
        "description": data["description"],
        "tags": data["tags"],
    }
    frontmatter = yaml.dump(
        ordered,
        Dumper=_CanonicalDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=10_000,
    ).rstrip("\n")
    suffix = f"\n\n{normalized_body}\n" if normalized_body else "\n"
    return f"---\n{frontmatter}\n---{suffix}"


def _parse_context(text: str) -> tuple[ContextMetadata, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    match = _FRONTMATTER_RE.fullmatch(normalized)
    if match is None:
        raise ContextError("Context file must contain strict YAML frontmatter")
    frontmatter = match.group("yaml")
    try:
        if any(isinstance(event, AliasEvent) for event in yaml.parse(frontmatter)):
            raise yaml.YAMLError("YAML aliases are not allowed")
        raw = yaml.load(frontmatter, Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise ContextError(f"invalid Context frontmatter YAML: {exc}") from exc
    metadata = _validate_metadata(raw)
    return metadata, normalize_body(match.group("body") or "")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class LoadedContext:
    """One validated complete Context loaded for an operation or episode."""

    name: str
    metadata: ContextMetadata
    body: str
    digest: str

    def list_item(self) -> ContextListItem:
        """Return the body-free public metadata view."""
        return ContextListItem(
            name=self.name,
            **self.metadata.model_dump(mode="python"),
        )


class ContextStore:
    """Store one strict Markdown file per named project-local Context."""

    def __init__(
        self,
        *,
        context_max_kb: int,
        state_root: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._max_bytes = context_max_kb * 1024
        self._state_root = state_root or get_project_state_dir("worker")
        self._contexts_root = self._state_root / "contexts"
        self._project_root = (project_root or get_effective_cwd()).resolve()

    @property
    def state_root(self) -> Path:
        """Return the project-local worker state root."""
        return self._state_root

    def load(
        self,
        name: str,
        *,
        create: bool,
        require_active: bool = True,
    ) -> tuple[LoadedContext, bool]:
        """Load a Context, atomically creating a missing active file if allowed."""
        context_name = validate_context_name(name)
        path = self._context_path(context_name)
        if not path.exists() and create:
            metadata = ContextMetadata(
                revision=1,
                status="active",
                description="",
                tags=[],
            )
            rendered = render_context(metadata, "")
            self._validate_size(rendered)
            created = self._write_new_atomic(path, rendered)
        else:
            created = False
        loaded = self._load_existing(context_name)
        if require_active and loaded.metadata.status != "active":
            raise ContextError(f"Context is archived: {context_name}")
        return loaded, created

    def list_contexts(
        self, *, status: Literal["active", "archived"] | None = None
    ) -> list[ContextListItem]:
        """Return validated body-free metadata in stable name order."""
        if status not in {None, "active", "archived"}:
            raise ContextError("status must be active or archived")
        if not self._contexts_root.exists():
            return []
        if self._contexts_root.is_symlink() or not self._contexts_root.is_dir():
            raise ContextError(
                f"Context root is not a directory: {self._contexts_root}"
            )
        items: list[ContextListItem] = []
        for path in sorted(self._contexts_root.iterdir(), key=lambda item: item.name):
            if path.suffix != ".md":
                raise ContextError(f"unexpected file in Context root: {path.name}")
            name = validate_context_name(path.stem)
            loaded = self._load_existing(name)
            if status is None or loaded.metadata.status == status:
                items.append(loaded.list_item())
        return items

    def update_metadata(
        self,
        name: str,
        *,
        description: str | None,
        tags: list[str] | None,
    ) -> tuple[LoadedContext, bool]:
        """Upsert supplied metadata while preserving the complete body."""
        if description is None and tags is None:
            raise ContextError("description or tags is required")
        context_name = validate_context_name(name)
        path = self._context_path(context_name)
        if not path.exists():
            metadata = _validate_metadata(
                {
                    "schema_version": 1,
                    "revision": 1,
                    "status": "active",
                    "description": description or "",
                    "tags": tags or [],
                }
            )
            rendered = render_context(metadata, "")
            self._validate_size(rendered)
            if self._write_new_atomic(path, rendered):
                return self._load_existing(context_name), True

        loaded = self._load_existing(context_name)
        if loaded.metadata.status != "active":
            raise ContextError(f"Context is archived: {context_name}")
        metadata = _validate_metadata(
            {
                **loaded.metadata.model_dump(mode="python"),
                "revision": loaded.metadata.revision + 1,
                "description": (
                    loaded.metadata.description if description is None else description
                ),
                "tags": loaded.metadata.tags if tags is None else tags,
            }
        )
        return self._replace(loaded, metadata=metadata, body=loaded.body), False

    def archive(self, name: str) -> LoadedContext:
        """Archive one existing active non-default Context without moving it."""
        context_name = validate_context_name(name)
        if context_name == "default":
            raise ContextError("default Context cannot be archived")
        loaded = self._load_existing(context_name)
        if loaded.metadata.status != "active":
            raise ContextError(f"Context is already archived: {context_name}")
        metadata = loaded.metadata.model_copy(
            update={"revision": loaded.metadata.revision + 1, "status": "archived"}
        )
        return self._replace(loaded, metadata=metadata, body=loaded.body)

    def commit_body(
        self,
        *,
        loaded: LoadedContext,
        body: str,
    ) -> LoadedContext:
        """Commit a complete body replacement bound to revision and digest."""
        if loaded.metadata.status != "active":
            raise ContextError(f"Context is archived: {loaded.name}")
        metadata = loaded.metadata.model_copy(
            update={"revision": loaded.metadata.revision + 1}
        )
        return self._replace(loaded, metadata=metadata, body=body)

    def _replace(
        self,
        loaded: LoadedContext,
        *,
        metadata: ContextMetadata,
        body: str,
    ) -> LoadedContext:
        current = self._load_existing(loaded.name)
        if (
            current.metadata.revision != loaded.metadata.revision
            or current.digest != loaded.digest
        ):
            raise ContextError(
                "Context changed during operation: "
                f"expected revision {loaded.metadata.revision} and digest "
                f"{loaded.digest}, found revision {current.metadata.revision} "
                f"and digest {current.digest}"
            )
        normalized_body = normalize_body(body)
        self._validate_references(normalized_body)
        rendered = render_context(metadata, normalized_body)
        self._validate_size(rendered)
        self._write_atomic(self._context_path(loaded.name), rendered)
        return self._load_existing(loaded.name)

    def _load_existing(self, name: str) -> LoadedContext:
        path = self._context_path(name)
        if path.is_symlink() or not path.is_file():
            raise ContextError(f"Context does not exist as a regular file: {name}")
        try:
            data = path.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise ContextError(f"could not read Context {name}: {exc}") from exc
        if len(data) > self._max_bytes:
            self._raise_size(len(data))
        metadata, body = _parse_context(text)
        self._validate_references(body)
        rendered = render_context(metadata, body)
        self._validate_size(rendered)
        return LoadedContext(
            name=name,
            metadata=metadata,
            body=body,
            digest=_digest(data),
        )

    def _validate_references(self, body: str) -> None:
        for match in _MARKDOWN_LINK_RE.finditer(body):
            raw_target = match.group("target").strip()
            if raw_target.startswith("<") and raw_target.endswith(">"):
                raw_target = raw_target[1:-1]
            raw_target = raw_target.split(maxsplit=1)[0]
            parsed = urlsplit(raw_target)
            if (
                parsed.scheme
                or parsed.netloc
                or not parsed.path
                or parsed.path.startswith("#")
            ):
                continue
            decoded = unquote(parsed.path)
            candidate_path = Path(decoded)
            if candidate_path.is_absolute() or ".." in candidate_path.parts:
                raise ContextError(f"Context reference escapes project: {raw_target}")
            candidate = (self._project_root / candidate_path).resolve()
            if not candidate.is_relative_to(self._project_root):
                raise ContextError(f"Context reference escapes project: {raw_target}")
            if not candidate.is_file():
                raise ContextError(
                    f"Context reference is not an existing regular file: {raw_target}"
                )

    def _validate_size(self, rendered: str) -> None:
        actual = len(rendered.encode("utf-8"))
        if actual > self._max_bytes:
            self._raise_size(actual)

    def _raise_size(self, actual: int) -> None:
        configured_kb = self._max_bytes // 1024
        raise ContextError(
            f"complete Context is {actual} bytes; limit is {configured_kb} KB "
            f"({self._max_bytes} bytes)"
        )

    def _context_path(self, name: str) -> Path:
        context_name = validate_context_name(name)
        path = self._contexts_root / f"{context_name}.md"
        if not path.is_relative_to(self._contexts_root):
            raise ContextError(f"Context path escapes project state: {context_name}")
        return path

    @staticmethod
    def _write_new_atomic(path: Path, text: str) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        ContextStore._fsync_directory(path.parent)
        return True

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
            ContextStore._fsync_directory(path.parent)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


__all__ = [
    "CONTEXT_NAME_MAX_CHARS",
    "ContextError",
    "ContextStore",
    "LoadedContext",
    "normalize_body",
    "render_context",
    "validate_context_name",
]
