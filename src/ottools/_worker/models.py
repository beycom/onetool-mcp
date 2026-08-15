"""Strict data contracts for episodic worker execution."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
)


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
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


class StrictModel(BaseModel):
    """Base model that rejects unknown fields and coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)


class Goal(StrictModel):
    """Current objective and independently testable completion conditions."""

    status: Literal["active", "blocked", "complete"]
    objective: NonBlank
    success_criteria: list[NonBlank]


class Work(StrictModel):
    """Current progress and useful next actions."""

    summary: NonBlank
    next_actions: list[NonBlank]
    blockers: list[NonBlank]


class KnowledgeEntry(StrictModel):
    """One durable continuation fact, decision, or constraint."""

    kind: Literal["fact", "decision", "constraint"]
    text: NonBlank


class Reference(StrictModel):
    """A project-relative file reference with its continuation purpose."""

    path: NonBlank
    purpose: NonBlank

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        """Reject absolute and parent-traversing lexical paths."""
        path = Path(value)
        if path.is_absolute() or value.startswith(('/', '\\')):
            raise ValueError("reference path must be project-relative")
        if len(value) >= 2 and value[1] == ":":
            raise ValueError("reference path must be project-relative")
        if ".." in path.parts:
            raise ValueError("reference path must not escape the project")
        return value


class WorkerContext(StrictModel):
    """Complete context authored by one worker for the next episode."""

    goal: Goal
    work: Work
    knowledge: list[KnowledgeEntry]
    questions: list[NonBlank]
    references: list[Reference]


class CommittedContext(WorkerContext):
    """Canonical stored context with MCP-owned version and revision."""

    schema_version: Literal[1] = 1
    revision: Annotated[StrictInt, Field(ge=1)]


class ReadOnlySandboxPolicy(StrictModel):
    """Read-only filesystem access with the parent's network boundary."""

    type: Literal["read-only"]
    network_access: StrictBool


class WorkspaceWriteSandboxPolicy(StrictModel):
    """Workspace writes using the parent's exact roots and network boundary."""

    type: Literal["workspace-write"]
    writable_roots: list[NonBlank]
    network_access: StrictBool
    exclude_slash_tmp: StrictBool
    exclude_tmpdir_env_var: StrictBool


class DangerFullAccessSandboxPolicy(StrictModel):
    """Unrestricted execution matching an unrestricted parent."""

    type: Literal["danger-full-access"]


class ExternalSandboxPolicy(StrictModel):
    """Execution already confined by the parent's external sandbox."""

    type: Literal["external-sandbox"]
    network_access: Literal["restricted", "enabled"]


SandboxPolicy = Annotated[
    ReadOnlySandboxPolicy
    | WorkspaceWriteSandboxPolicy
    | DangerFullAccessSandboxPolicy
    | ExternalSandboxPolicy,
    Field(discriminator="type"),
]


class ExecutionPolicy(StrictModel):
    """Parent-derived non-interactive worker execution policy."""

    cwd: NonBlank
    approval_policy: Literal["never"]
    sandbox: SandboxPolicy


class InternalTerminalOutput(StrictModel):
    """Strict app-server output before the MCP processes context."""

    status: Literal["completed", "needs_input"]
    message: NonBlank
    context: WorkerContext | None = None


class PublicWorkerResult(StrictModel):
    """The exact public result returned by worker.run."""

    session_id: NonBlank
    status: Literal["completed", "needs_input", "failed", "interrupted"]
    message: NonBlank


__all__ = [
    "CommittedContext",
    "DangerFullAccessSandboxPolicy",
    "ExecutionPolicy",
    "ExternalSandboxPolicy",
    "Goal",
    "InternalTerminalOutput",
    "KnowledgeEntry",
    "ModelId",
    "PublicWorkerResult",
    "ReadOnlySandboxPolicy",
    "Reference",
    "SandboxPolicy",
    "Work",
    "WorkerContext",
    "WorkspaceWriteSandboxPolicy",
]
