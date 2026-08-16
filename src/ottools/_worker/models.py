"""Strict data contracts for named-Context worker execution."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves this runtime type.
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    TypeAdapter,
)

STATUS_MAX_BYTES = 1024
NEXT_ACTION_MAX_BYTES = 1024
CONTEXT_DESCRIPTION_MAX_BYTES = 512
CONTEXT_TAG_MAX_BYTES = 64
CONTEXT_TAGS_MAX_ITEMS = 16
ARTIFACT_LABEL_MAX_BYTES = 256

if TYPE_CHECKING:
    from collections.abc import Callable


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


def _bounded_utf8(*, label: str, maximum: int) -> Callable[[str], str]:
    def validate(value: str) -> str:
        size = len(value.encode("utf-8"))
        if size > maximum:
            raise ValueError(f"{label} must not exceed {maximum} UTF-8 bytes")
        return value

    return validate


def _require_non_question_action(value: str) -> str:
    if value.rstrip().endswith("?"):
        raise ValueError("next_action must be autonomous work, not a user question")
    return value


NonBlank = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=1),
    AfterValidator(_require_nonblank),
]
ModelId = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=1, max_length=512),
    AfterValidator(_require_nonblank),
]
StatusMessage = Annotated[
    NonBlank,
    AfterValidator(_bounded_utf8(label="message", maximum=STATUS_MAX_BYTES)),
]
NextAction = Annotated[
    NonBlank,
    AfterValidator(
        _bounded_utf8(label="next_action", maximum=NEXT_ACTION_MAX_BYTES)
    ),
    AfterValidator(_require_non_question_action),
]
ContextDescription = Annotated[
    str,
    AfterValidator(
        _bounded_utf8(label="description", maximum=CONTEXT_DESCRIPTION_MAX_BYTES)
    ),
]
ContextTag = Annotated[
    NonBlank,
    AfterValidator(_bounded_utf8(label="tag", maximum=CONTEXT_TAG_MAX_BYTES)),
]
ArtifactLabel = Annotated[
    NonBlank,
    AfterValidator(_bounded_utf8(label="label", maximum=ARTIFACT_LABEL_MAX_BYTES)),
]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields and coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ContextMetadata(StrictModel):
    """Strict discoverable frontmatter for one named Context."""

    schema_version: Literal[1] = 1
    revision: Annotated[StrictInt, Field(ge=1)]
    status: Literal["active", "archived"]
    description: ContextDescription
    tags: Annotated[list[ContextTag], Field(max_length=CONTEXT_TAGS_MAX_ITEMS)]


class ContextListItem(ContextMetadata):
    """Body-free metadata returned by ``worker.ctx_list``."""

    name: NonBlank


class ArtifactMetadata(StrictModel):
    """Strict metadata for one immutable Context-owned artifact."""

    schema_version: Literal[1] = 1
    id: Annotated[
        str,
        StringConstraints(pattern=r"^artifact-[0-9a-f]{32}$"),
    ]
    label: ArtifactLabel
    kind: Literal["text", "binary"]
    media_type: Annotated[str, StringConstraints(min_length=3, max_length=255)]
    byte_length: Annotated[StrictInt, Field(ge=0, le=8 * 1024 * 1024)]
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    created_at: datetime
    status: Literal["ready"] = "ready"


class InternalCompletedOutput(StrictModel):
    """Strict successful app-server output before Context processing."""

    status: Literal["completed"]
    message: StatusMessage
    context: str | None = None


class InternalNeedsInputOutput(StrictModel):
    """Strict required-input app-server output before Context processing."""

    status: Literal["needs_input"]
    message: StatusMessage
    context: str | None = None


class InternalContinueOutput(StrictModel):
    """Strict internal-only request for another turn in the same episode."""

    status: Literal["continue"]
    next_action: NextAction


InternalPublicTerminalOutput = InternalCompletedOutput | InternalNeedsInputOutput
InternalTerminalOutput = Annotated[
    InternalCompletedOutput | InternalNeedsInputOutput | InternalContinueOutput,
    Field(discriminator="status"),
]
INTERNAL_TERMINAL_OUTPUT_ADAPTER: TypeAdapter[InternalTerminalOutput] = TypeAdapter(
    InternalTerminalOutput
)


class PublicWorkerResult(StrictModel):
    """The exact public result returned by ``worker.run``."""

    context: NonBlank
    status: Literal["completed", "needs_input", "failed", "interrupted"]
    message: StatusMessage


class ConsoleRecord(StrictModel):
    """Body-free Console publication recorded in worker History."""

    id: NonBlank
    kind: NonBlank


class LocalChange(StrictModel):
    """One mechanically observed project path classification."""

    path: NonBlank
    classification: Literal["created", "modified", "deleted"]


class HistoryRecord(StrictModel):
    """One project-scoped mechanical worker episode record."""

    schema_version: Literal[1] = 1
    episode_id: NonBlank
    context: NonBlank
    started_at: datetime
    finished_at: datetime
    status: Literal["completed", "needs_input", "failed", "interrupted"]
    turn_count: Annotated[StrictInt, Field(ge=0)]
    context_revision_before: Annotated[StrictInt, Field(ge=1)]
    context_revision_after: Annotated[StrictInt, Field(ge=1)]
    console: list[ConsoleRecord]
    local_changes: list[LocalChange]
    failure: NonBlank | None = None
    warnings: list[NonBlank]


__all__ = [
    "ARTIFACT_LABEL_MAX_BYTES",
    "CONTEXT_DESCRIPTION_MAX_BYTES",
    "CONTEXT_TAGS_MAX_ITEMS",
    "CONTEXT_TAG_MAX_BYTES",
    "INTERNAL_TERMINAL_OUTPUT_ADAPTER",
    "NEXT_ACTION_MAX_BYTES",
    "STATUS_MAX_BYTES",
    "ArtifactLabel",
    "ArtifactMetadata",
    "ConsoleRecord",
    "ContextDescription",
    "ContextListItem",
    "ContextMetadata",
    "ContextTag",
    "HistoryRecord",
    "InternalCompletedOutput",
    "InternalContinueOutput",
    "InternalNeedsInputOutput",
    "InternalPublicTerminalOutput",
    "InternalTerminalOutput",
    "LocalChange",
    "ModelId",
    "NextAction",
    "NonBlank",
    "PublicWorkerResult",
    "StatusMessage",
]
