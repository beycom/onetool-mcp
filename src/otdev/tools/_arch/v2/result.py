"""Common schema-v2 operation result and diagnostic envelope."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .models import Identifier, SourceLocation, StrictModel

OperationName = Literal[
    "init",
    "validate",
    "convert",
    "resolve",
    "diff",
    "generate",
    "export",
    "bundle",
]


class IssueIdentity(StrictModel):
    """Applicable canonical identities retained by an issue."""

    roadmap: Identifier | None = None
    order: int | None = None
    change: Identifier | None = None
    operation: Identifier | None = None
    state: Identifier | None = None
    view: Identifier | None = None
    entity: Identifier | None = None
    interface: Identifier | None = None
    diagram: Identifier | None = None
    artifact: Identifier | None = None


class Issue(StrictModel):
    """Stable source-complete diagnostic."""

    code: Identifier
    severity: Literal["error", "warning"]
    message: str
    identity: IssueIdentity = Field(default_factory=IssueIdentity)
    locations: list[SourceLocation] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class IssueCollection(StrictModel):
    """Separated error and warning arrays."""

    errors: list[Issue] = Field(default_factory=list)
    warnings: list[Issue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_severity_buckets(self) -> IssueCollection:
        """Keep issue severity and containing bucket coherent."""
        if any(issue.severity != "error" for issue in self.errors):
            raise ValueError("issues.errors may contain only error diagnostics")
        if any(issue.severity != "warning" for issue in self.warnings):
            raise ValueError("issues.warnings may contain only warning diagnostics")
        return self


class ArtifactOutcome(StrictModel):
    """One requested generated, reused, skipped, failed, or removed artifact."""

    id: Identifier
    path: str
    status: Literal["generated", "reused", "skipped", "failed", "removed_stale"]
    format: str | None = None
    content_hash: str | None = None
    selection_id: Identifier | None = None
    fidelity: list[str] = Field(default_factory=list)


class ResultSummary(StrictModel):
    """Counts reconciled with issues and artifact outcomes."""

    errors: int = Field(default=0, ge=0)
    warnings: int = Field(default=0, ge=0)
    requested: int = Field(default=0, ge=0)
    generated: int = Field(default=0, ge=0)
    reused: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    removed_stale: int = Field(default=0, ge=0)


class OperationResult(StrictModel):
    """Common result envelope returned by every public architecture operation."""

    ok: bool
    operation: OperationName
    valid: bool | None = None
    partial: bool = False
    issues: IssueCollection = Field(default_factory=IssueCollection)
    summary: ResultSummary = Field(default_factory=ResultSummary)
    selections: list[Identifier] = Field(default_factory=list)
    artifacts: list[ArtifactOutcome] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reconcile_counts(self) -> OperationResult:
        """Require summary counts and status flags to match returned content."""
        expected = {
            "errors": len(self.issues.errors),
            "warnings": len(self.issues.warnings),
            "generated": sum(item.status == "generated" for item in self.artifacts),
            "reused": sum(item.status == "reused" for item in self.artifacts),
            "skipped": sum(item.status == "skipped" for item in self.artifacts),
            "failed": sum(item.status == "failed" for item in self.artifacts),
            "removed_stale": sum(item.status == "removed_stale" for item in self.artifacts),
        }
        for field, count in expected.items():
            if getattr(self.summary, field) != count:
                raise ValueError(
                    f"summary.{field}={getattr(self.summary, field)} does not match {count} outcomes"
                )
        if self.ok and self.issues.errors:
            raise ValueError("ok cannot be true when errors are present")
        if self.valid is True and self.issues.errors:
            raise ValueError("valid cannot be true when errors are present")
        return self


def result_payload(result: OperationResult) -> dict[str, Any]:
    """Serialize an operation result as a native tool payload."""
    return result.model_dump(mode="json", exclude_none=True)


def unimplemented_result(*, operation: OperationName) -> dict[str, Any]:
    """Return a stable error while a dependency-ordered operation is unfinished."""
    issue = Issue(
        code="arch.operation_not_implemented",
        severity="error",
        message=f"arch.{operation} is not implemented yet",
    )
    return result_payload(
        OperationResult(
            ok=False,
            operation=operation,
            valid=False if operation == "validate" else None,
            issues=IssueCollection(errors=[issue]),
            summary=ResultSummary(errors=1),
        )
    )
