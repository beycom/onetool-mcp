"""Strict Context-owned worker artifact persistence."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex
from typing import Any, Literal

from pydantic import ValidationError

from ot.paths import get_effective_cwd
from ottools._worker.context import ContextError, ContextStore, validate_context_name
from ottools._worker.models import ArtifactMetadata

ARTIFACT_MAX_BYTES = 8 * 1024 * 1024
ARTIFACT_MAX_ITEMS = 64
ARTIFACT_TOTAL_MAX_BYTES = 64 * 1024 * 1024
ARTIFACT_LIST_MAX_ITEMS = 64
ORPHAN_WARNING_MAX_ITEMS = 16

_ARTIFACT_ID_RE = re.compile(r"^artifact-[0-9a-f]{32}$")
_MEDIA_TYPE_RE = re.compile(
    r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$"
)
_BODY_NAME = "body"
_METADATA_NAME = "metadata.json"
_TRANSIENT_PREFIXES = (".staging-", ".deleting-")
_STORE_LOCK = threading.Lock()


class ArtifactError(ValueError):
    """A deterministic artifact validation or persistence failure."""


@dataclass(frozen=True)
class LoadedArtifact:
    """One fully validated immutable artifact."""

    metadata: ArtifactMetadata
    body: bytes


@dataclass(frozen=True)
class ArtifactPage:
    """One bounded stable metadata-only artifact page."""

    items: list[ArtifactMetadata]
    total: int
    limit: int
    offset: int
    warnings: list[str]

    @property
    def has_more(self) -> bool:
        """Return whether another oldest-first page exists."""
        return self.offset + len(self.items) < self.total


def decode_content(*, content: str, kind: Literal["text", "binary"]) -> bytes:
    """Decode public artifact content according to its strict kind."""
    if not isinstance(content, str):
        raise ArtifactError("artifact content must be a string")
    if kind == "text":
        return content.encode("utf-8")
    if kind != "binary":
        raise ArtifactError("artifact kind must be text or binary")
    try:
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ArtifactError("binary artifact content must be strict base64") from exc


def encode_content(artifact: LoadedArtifact) -> str:
    """Encode validated artifact bytes for the public tool result."""
    if artifact.metadata.kind == "binary":
        return base64.b64encode(artifact.body).decode("ascii")
    try:
        return artifact.body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactError("text artifact body is not valid UTF-8") from exc


class ArtifactStore:
    """Persist immutable artifacts under one existing named Context."""

    def __init__(
        self,
        *,
        context_store: ContextStore,
        project_root: Path | None = None,
    ) -> None:
        self._context_store = context_store
        self._state_root = context_store.state_root.absolute()
        self._project_root = (project_root or get_effective_cwd()).resolve()
        if not self._state_root.is_relative_to(self._project_root):
            raise ArtifactError("worker artifact state root escapes the project")
        self._artifacts_root = self._state_root / "artifacts"

    def create(
        self,
        *,
        context: str,
        content: str,
        kind: Literal["text", "binary"],
        media_type: str,
        label: str,
    ) -> tuple[ArtifactMetadata, list[str]]:
        """Atomically create one immutable artifact for an active Context."""
        body = decode_content(content=content, kind=kind)
        if len(body) > ARTIFACT_MAX_BYTES:
            raise ArtifactError(
                f"artifact body is {len(body)} bytes; limit is {ARTIFACT_MAX_BYTES} bytes"
            )
        _validate_media_type(media_type)
        _validate_label(label)
        context_name = self._load_owner(context, require_active=True)

        with _STORE_LOCK:
            root = self._context_root(context_name, create=True)
            if root is None:  # pragma: no cover - create=True guarantees a root
                raise ArtifactError("could not create the Context artifact root")
            ready, warnings = self._scan(root)
            if len(ready) >= ARTIFACT_MAX_ITEMS:
                raise ArtifactError(
                    f"Context already has the maximum {ARTIFACT_MAX_ITEMS} ready artifacts"
                )
            total = sum(item.metadata.byte_length for item in ready)
            if total + len(body) > ARTIFACT_TOTAL_MAX_BYTES:
                raise ArtifactError(
                    "artifact would exceed the Context total body limit of "
                    f"{ARTIFACT_TOTAL_MAX_BYTES} bytes"
                )

            artifact_id = self._new_id(root)
            metadata = ArtifactMetadata(
                id=artifact_id,
                label=label,
                kind=kind,
                media_type=media_type,
                byte_length=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                created_at=datetime.now(UTC),
            )
            self._publish(root=root, metadata=metadata, body=body)
            return metadata, warnings

    def open(
        self,
        *,
        context: str,
        artifact_id: str,
    ) -> tuple[LoadedArtifact, list[str]]:
        """Return one fully validated artifact and any bounded orphan warnings."""
        context_name = self._load_owner(context, require_active=False)
        checked_id = _validate_artifact_id(artifact_id)
        with _STORE_LOCK:
            root = self._context_root(context_name, create=False)
            if root is None:
                raise ArtifactError(f"artifact does not exist: {checked_id}")
            ready, warnings = self._scan(root)
            for artifact in ready:
                if artifact.metadata.id == checked_id:
                    return artifact, warnings
            if (root / checked_id).exists() or (root / checked_id).is_symlink():
                raise ArtifactError(
                    f"artifact is inconsistent and quarantined: {checked_id}"
                )
            raise ArtifactError(f"artifact does not exist: {checked_id}")

    def list_artifacts(
        self,
        *,
        context: str,
        limit: int,
        offset: int,
    ) -> ArtifactPage:
        """List a bounded stable oldest-first page of artifact metadata."""
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ArtifactError("artifact list limit must be an integer")
        if limit < 1 or limit > ARTIFACT_LIST_MAX_ITEMS:
            raise ArtifactError(
                f"artifact list limit must be between 1 and {ARTIFACT_LIST_MAX_ITEMS}"
            )
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ArtifactError("artifact list offset must be an integer")
        if offset < 0:
            raise ArtifactError("artifact list offset must be greater than or equal to 0")
        context_name = self._load_owner(context, require_active=False)
        with _STORE_LOCK:
            root = self._context_root(context_name, create=False)
            if root is None:
                return ArtifactPage([], 0, limit, offset, [])
            ready, warnings = self._scan(root)
            ready.sort(key=lambda item: (item.metadata.created_at, item.metadata.id))
            items = [item.metadata for item in ready[offset : offset + limit]]
            return ArtifactPage(items, len(ready), limit, offset, warnings)

    def delete(
        self,
        *,
        context: str,
        artifact_id: str,
    ) -> list[str]:
        """Atomically remove one existing ready artifact from its owner."""
        context_name = self._load_owner(context, require_active=False)
        checked_id = _validate_artifact_id(artifact_id)
        with _STORE_LOCK:
            root = self._context_root(context_name, create=False)
            if root is None:
                raise ArtifactError(f"artifact does not exist: {checked_id}")
            ready, warnings = self._scan(root)
            if not any(item.metadata.id == checked_id for item in ready):
                if (root / checked_id).exists() or (root / checked_id).is_symlink():
                    raise ArtifactError(
                        f"artifact is inconsistent and quarantined: {checked_id}"
                    )
                raise ArtifactError(f"artifact does not exist: {checked_id}")
            final_path = root / checked_id
            deleting = root / f".deleting-{checked_id}-{token_hex(6)}"
            final_path.rename(deleting)
            _fsync_directory(root)
            shutil.rmtree(deleting)
            _fsync_directory(root)
            return warnings

    def _load_owner(self, context: str, *, require_active: bool) -> str:
        try:
            loaded, _ = self._context_store.load(
                context,
                create=False,
                require_active=require_active,
            )
        except ContextError as exc:
            raise ArtifactError(str(exc)) from exc
        return loaded.name

    def _context_root(self, context: str, *, create: bool) -> Path | None:
        context_name = validate_context_name(context)
        root = self._artifacts_root / context_name
        if not root.is_relative_to(self._artifacts_root):
            raise ArtifactError("artifact root escapes worker state")
        exists = self._ensure_directory(root, create=create)
        return root if exists else None

    def _ensure_directory(self, path: Path, *, create: bool) -> bool:
        current = self._project_root
        for part in path.relative_to(self._project_root).parts:
            current /= part
            if current.is_symlink():
                raise ArtifactError(f"artifact state component is a symlink: {part}")
            if current.exists():
                if not current.is_dir():
                    raise ArtifactError(
                        f"artifact state component is not a directory: {part}"
                    )
                continue
            if not create:
                return False
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                if current.is_symlink() or not current.is_dir():
                    raise ArtifactError(
                        f"artifact state component is not a safe directory: {part}"
                    ) from None
        return True

    def _scan(self, root: Path) -> tuple[list[LoadedArtifact], list[str]]:
        warnings: list[str] = []
        self._cleanup_transients(root, warnings)
        ready: list[LoadedArtifact] = []
        for path in sorted(root.iterdir(), key=lambda item: item.name):
            if path.name.startswith(_TRANSIENT_PREFIXES):
                continue
            if not _ARTIFACT_ID_RE.fullmatch(path.name):
                _add_warning(warnings, "orphan:invalid-entry")
                continue
            try:
                ready.append(self._load_final(path, expected_id=path.name))
            except ArtifactError:
                _add_warning(warnings, f"orphan:{path.name}")
        return ready, warnings

    def _cleanup_transients(self, root: Path, warnings: list[str]) -> None:
        for path in sorted(root.iterdir(), key=lambda item: item.name):
            if not path.name.startswith(_TRANSIENT_PREFIXES):
                continue
            if path.is_symlink() or not path.is_dir():
                _add_warning(warnings, "orphan:invalid-transient")
                continue
            shutil.rmtree(path)
            _fsync_directory(root)

    @staticmethod
    def _load_final(path: Path, *, expected_id: str) -> LoadedArtifact:
        if path.is_symlink() or not path.is_dir():
            raise ArtifactError("artifact path is not a safe directory")
        entries = {entry.name: entry for entry in path.iterdir()}
        if set(entries) != {_BODY_NAME, _METADATA_NAME}:
            raise ArtifactError("artifact directory has an invalid layout")
        body_path = entries[_BODY_NAME]
        metadata_path = entries[_METADATA_NAME]
        if (
            body_path.is_symlink()
            or metadata_path.is_symlink()
            or not body_path.is_file()
            or not metadata_path.is_file()
        ):
            raise ArtifactError("artifact files are not safe regular files")
        metadata = _read_metadata(metadata_path)
        if metadata.id != expected_id:
            raise ArtifactError("artifact metadata owner does not match its directory")
        stat_size = body_path.stat().st_size
        if stat_size != metadata.byte_length or stat_size > ARTIFACT_MAX_BYTES:
            raise ArtifactError("artifact body size does not match metadata")
        body = body_path.read_bytes()
        if len(body) != metadata.byte_length:
            raise ArtifactError("artifact body length changed while reading")
        if hashlib.sha256(body).hexdigest() != metadata.sha256:
            raise ArtifactError("artifact body digest does not match metadata")
        if metadata.kind == "text":
            try:
                body.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ArtifactError("text artifact body is not valid UTF-8") from exc
        return LoadedArtifact(metadata=metadata, body=body)

    @staticmethod
    def _new_id(root: Path) -> str:
        for _attempt in range(32):
            artifact_id = f"artifact-{token_hex(16)}"
            if not (root / artifact_id).exists() and not (root / artifact_id).is_symlink():
                return artifact_id
        raise ArtifactError("could not allocate a collision-free artifact ID")

    @staticmethod
    def _publish(
        *,
        root: Path,
        metadata: ArtifactMetadata,
        body: bytes,
    ) -> None:
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=root))
        final_path = root / metadata.id
        try:
            _write_synced(staging / _BODY_NAME, body)
            encoded_metadata = (
                json.dumps(
                    metadata.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                + b"\n"
            )
            _write_synced(staging / _METADATA_NAME, encoded_metadata)
            _fsync_directory(staging)
            if final_path.exists() or final_path.is_symlink():
                raise ArtifactError(f"artifact ID collision: {metadata.id}")
            staging.rename(final_path)
            _fsync_directory(root)
        except Exception:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)
            raise


def _validate_artifact_id(value: str) -> str:
    if not isinstance(value, str) or not _ARTIFACT_ID_RE.fullmatch(value):
        raise ArtifactError("artifact ID must use the opaque artifact-<32 hex> form")
    return value


def _validate_media_type(value: str) -> None:
    if not isinstance(value, str) or not _MEDIA_TYPE_RE.fullmatch(value):
        raise ArtifactError("media_type must be a lowercase type/subtype without parameters")


def _validate_label(value: str) -> None:
    if not isinstance(value, str):
        raise ArtifactError("artifact label must be a string")
    if any(ord(character) < 0x20 for character in value):
        raise ArtifactError("artifact label must not contain control characters")
    try:
        ArtifactMetadata(
            id="artifact-00000000000000000000000000000000",
            label=value,
            kind="text",
            media_type="text/plain",
            byte_length=0,
            sha256="0" * 64,
            created_at=datetime.now(UTC),
        )
    except ValidationError as exc:
        raise ArtifactError(str(exc)) from exc


def _read_metadata(path: Path) -> ArtifactMetadata:
    try:
        data = path.read_bytes()
        if len(data) > 16 * 1024:
            raise ArtifactError("artifact metadata exceeds 16384 bytes")
        text = data.decode("utf-8")
        raw = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_raise_json_constant(value)),
        )
        if not isinstance(raw, dict):
            raise ArtifactError("artifact metadata must be a JSON object")
        created_at = raw.get("created_at")
        if not isinstance(created_at, str):
            raise ArtifactError("artifact created_at must be an ISO timestamp")
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ArtifactError("artifact created_at must include a timezone")
        raw["created_at"] = parsed.astimezone(UTC)
        metadata = ArtifactMetadata.model_validate(raw)
        _validate_media_type(metadata.media_type)
        _validate_label(metadata.label)
        return metadata
    except (
        ArtifactError,
        ValidationError,
        UnicodeError,
        json.JSONDecodeError,
        OSError,
        ValueError,
    ) as exc:
        if isinstance(exc, ArtifactError):
            raise
        raise ArtifactError(f"invalid artifact metadata: {exc}") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactError(f"duplicate artifact metadata field: {key}")
        result[key] = value
    return result


def _raise_json_constant(value: str) -> Any:
    raise ArtifactError(f"invalid JSON constant in artifact metadata: {value}")


def _write_synced(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _add_warning(warnings: list[str], warning: str) -> None:
    if len(warnings) < ORPHAN_WARNING_MAX_ITEMS and warning not in warnings:
        warnings.append(warning)


__all__ = [
    "ARTIFACT_LIST_MAX_ITEMS",
    "ARTIFACT_MAX_BYTES",
    "ARTIFACT_MAX_ITEMS",
    "ARTIFACT_TOTAL_MAX_BYTES",
    "ArtifactError",
    "ArtifactPage",
    "ArtifactStore",
    "LoadedArtifact",
    "decode_content",
    "encode_content",
]
