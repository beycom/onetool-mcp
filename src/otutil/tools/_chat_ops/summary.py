"""YAML summary and LLM report helpers for chat_ops."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from otutil.tools._chat_ops.session_payload import (
    SummaryLlmConfig,
    build_summary_payload,
    enrich_with_cheap_llm_summaries,
)


@dataclass(slots=True)
class SummaryRequest:
    projects: list[str] | None
    session_ids: list[str] | None
    models: list[str] | None
    start: str | None
    end: str | None
    limit: int | None
    output_dir: Path
    output_name: str | None
    llm: SummaryLlmConfig


def resolve_yaml_output_path(*, output_dir: Path, output_name: str | None, default_name: str) -> Path:
    raw_name = (output_name or "").strip() or default_name
    out = Path(raw_name)
    if out.name != raw_name:
        raise ValueError("output_name must be a filename, not a path")
    if not out.stem:
        raise ValueError("output_name must be non-empty")
    suffix = out.suffix.lower()
    if suffix and suffix not in {".yaml", ".yml"}:
        raise ValueError("output_name extension must be '.yaml' or '.yml'")
    filename = raw_name if suffix else f"{raw_name}.yaml"
    return output_dir / filename


def run_report_summary(conn: Any, *, req: SummaryRequest) -> dict[str, Any]:
    payload = build_summary_payload(
        conn,
        projects=req.projects,
        session_ids=req.session_ids,
        models=req.models,
        start=req.start,
        end=req.end,
        limit=req.limit,
        top_n=req.llm.top_n,
    )
    enrich_with_cheap_llm_summaries(conn, payload=payload, cfg=req.llm)

    output_path = resolve_yaml_output_path(
        output_dir=req.output_dir,
        output_name=req.output_name,
        default_name="report-summary.yaml",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")

    return {
        "format": "yaml",
        "output_path": str(output_path),
        "sessions": len(payload.get("sessions", [])),
        "date_range": payload.get("aggregate", {}).get("date_range"),
        "filters": payload.get("filters", {}),
    }


def run_report_llm(conn: Any, *, req: SummaryRequest) -> dict[str, Any]:
    payload = build_summary_payload(
        conn,
        projects=req.projects,
        session_ids=req.session_ids,
        models=req.models,
        start=req.start,
        end=req.end,
        limit=req.limit,
        top_n=req.llm.top_n,
    )
    # Phase-8 foundation: consume the structured payload and add richer per-session narrative.
    enrich_with_cheap_llm_summaries(conn, payload=payload, cfg=req.llm, include_narrative=True)

    output_path = resolve_yaml_output_path(
        output_dir=req.output_dir,
        output_name=req.output_name,
        default_name="report-llm.yaml",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")

    return {
        "format": "yaml",
        "output_path": str(output_path),
        "sessions": len(payload.get("sessions", [])),
        "filters": payload.get("filters", {}),
        "prompt_version": req.llm.prompt_version,
    }
