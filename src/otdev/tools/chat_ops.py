"""Chat telemetry ingest, annotation capture, and structured reporting tools.

This pack exposes chat-ops workflows as MCP tools (no CLI dependency):
- synchronous ingest
- synchronous report_excel export (xlsx raw tabs)
- explicit annotation writes via note(type=..., message=...)
- projection rebuild
"""

from __future__ import annotations

pack = "chat_ops"

__all__ = ["ingest", "note", "rebuild", "report_excel", "report_llm", "report_summary"]

__ot_requires__ = {
    "lib": [("openpyxl", "pip install openpyxl")],
}

import importlib.util
import inspect
import json
import os
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from otpack import LogSpan, get_tool_config
from pydantic import BaseModel, ConfigDict, Field

from onetool.chat_ops import configure_analysis_rules
from onetool.chat_ops.codex_parser import parse_line as builtin_codex_parse_line
from onetool.chat_ops.pipeline import (
    IngestOptions,
    ensure_schema,
    rebuild_projections,
)
from onetool.chat_ops.pipeline import (
    ingest as pipeline_ingest,
)
from ot.meta import resolve_ot_path
from ot.paths import resolve_cwd_path
from otutil.tools._chat_ops.excel import (
    ExcelRequest,
    export_excel_report,
    normalize_filter_values,
    normalize_modes,
    resolve_excel_output_path,
)
from otutil.tools._chat_ops.session_payload import MessageFilterConfig, SummaryLlmConfig
from otutil.tools._chat_ops.summary import (
    SummaryRequest,
    run_report_llm,
    run_report_summary,
)

if TYPE_CHECKING:
    from pathlib import Path

NoteType = Literal["note", "title", "summary"]
ParseLineFn = Callable[[str, str, int], dict[str, Any] | None]


class StorageConfig(BaseModel):
    """Storage defaults for chat ops."""

    db: str = Field(
        default="chat-ops/chat-ops.db",
        description="SQLite DB path relative to .onetool/ unless absolute.",
    )


class ProviderConfig(BaseModel):
    """Provider root and parser config."""

    model_config = ConfigDict(extra="forbid")

    provider_dir: str = Field(
        default="${HOME}/.codex/sessions",
        description="Directory to scan for rollout-*.jsonl files.",
    )
    parser_file: str = Field(
        default="builtin:codex_parser",
        description=(
            "Python parser module path (or builtin:codex_parser). "
            "Module must expose parse_line(...)."
        ),
    )


class CategoryRuleConfig(BaseModel):
    """Regex category rule."""

    name: str = Field(default="", description="Rule name.")
    category: str = Field(..., description="Assigned category for a match.")
    pattern: str = Field(..., description="Regex pattern.")


class SignalRuleConfig(BaseModel):
    """Regex signal rule."""

    name: str = Field(default="", description="Rule name.")
    signal_type: str = Field(..., description="Signal type label.")
    pattern: str = Field(..., description="Regex pattern.")


def _default_category_rules() -> list[CategoryRuleConfig]:
    return [
        CategoryRuleConfig(
            name="planning_tools",
            category="PLANNING",
            pattern=r"\b(?:HAS_PLAN_MODE|enterplanmode|taskcreate|taskupdate|taskget|tasklist|taskoutput|taskstop|todowrite|update_plan|request_user_input)\b",
        ),
        CategoryRuleConfig(
            name="delegation_tools",
            category="DELEGATION",
            pattern=r"\b(?:HAS_AGENT_SPAWN|spawn_agent|send_input|wait_agent|close_agent|resume_agent)\b",
        ),
        CategoryRuleConfig(
            name="testing_cmd",
            category="TESTING",
            pattern=r"\b(?:pytest|vitest|jest|mocha|npm\s+test|npx\s+vitest|npx\s+jest|coverage|spec)\b",
        ),
        CategoryRuleConfig(
            name="version_control_cmd",
            category="VERSION_CONTROL",
            pattern=r"\bgit\s+(?:push|pull|commit|merge|rebase|checkout|branch|stash|log|diff|status|add|reset|cherry-pick|tag)\b",
        ),
        CategoryRuleConfig(
            name="build_deploy_cmd",
            category="BUILD_AND_DEPLOYMENT",
            pattern=r"\b(?:npm\s+run\s+build|npm\s+publish|pip\s+install|docker|deploy|make\s+build|npm\s+run\s+dev|npm\s+start|pm2|systemctl|brew|cargo\s+build|npm\s+install|apt\s+install|cargo\s+add)\b",
        ),
        CategoryRuleConfig(
            name="debugging_keywords",
            category="DEBUGGING",
            pattern=r"\b(?:fix|bug|error|broken|failing|crash|issue|debug|traceback|exception|stack\s*trace|not\s+working|wrong|unexpected|status\s+code|404|500|401|403)\b",
        ),
        CategoryRuleConfig(
            name="refactoring_keywords",
            category="REFACTORING",
            pattern=r"\b(?:refactor|clean\s*up|rename|reorganize|simplify|extract|restructure|move|migrate|split)\b",
        ),
        CategoryRuleConfig(
            name="feature_dev_keywords",
            category="FEATURE_DEVELOPMENT",
            pattern=r"\b(?:add|create|implement|new|build|feature|introduce|set\s*up|scaffold|generate|make\s+(?:a|me|the)|write\s+(?:a|me|the))\b",
        ),
        CategoryRuleConfig(
            name="brainstorming_keywords",
            category="BRAINSTORMING",
            pattern=r"\b(?:brainstorm|idea|what\s+if|explore|think\s+about|approach|strategy|design|consider|how\s+should|what\s+would|opinion|suggest|recommend)\b",
        ),
        CategoryRuleConfig(
            name="exploration_tools",
            category="EXPLORATION",
            pattern=r"\b(?:HAS_SEARCH_TOOL|HAS_MCP_TOOL|HAS_READ|search|webfetch|websearch|toolsearch|grep|rg|read|open|view|cat|research|investigate|look\s+into|find\s+out|check|analyze|review|understand|explain|https?://)\b",
        ),
        CategoryRuleConfig(
            name="coding_from_edits",
            category="CODING",
            pattern=r"\b(?:HAS_EDIT|apply_patch|edit|write|replace|create_file|update_file)\b",
        ),
        CategoryRuleConfig(
            name="conversation_text_only",
            category="CONVERSATION",
            pattern=r"\b(?:TEXT_ONLY)\b",
        ),
        CategoryRuleConfig(
            name="general_skill_uncategorized",
            category="GENERAL",
            pattern=r"\b(?:HAS_SKILL_TOOL|GENERAL_FALLBACK)\b",
        ),
    ]


def _default_signal_rules() -> list[SignalRuleConfig]:
    return [
        SignalRuleConfig(
            name="failure_signal",
            signal_type="FAILURE",
            pattern=r"\b(?:error|failed|exception|traceback)\b",
        ),
        SignalRuleConfig(
            name="retry_signal",
            signal_type="RETRY",
            pattern=r"\b(?:retry|again)\b",
        ),
        SignalRuleConfig(
            name="patch_summary_signal",
            signal_type="PATCH_SUMMARY",
            pattern=r"(?:\*\*\*\s*begin\s*patch|update\s+file:)",
        ),
    ]


class AnalysisConfig(BaseModel):
    """Configurable regex analysis rules."""

    default_category: str = Field(default="GENERAL", description="Fallback category.")
    categories: list[CategoryRuleConfig] = Field(default_factory=_default_category_rules)
    signals: list[SignalRuleConfig] = Field(default_factory=_default_signal_rules)


class ReportingConfig(BaseModel):
    """Report defaults."""

    output_dir: str = Field(
        default="chat-ops/reports",
        description="Default output directory for saved report artifacts.",
    )
    llm_model: str | None = Field(default=None, description="Optional default LLM model.")
    max_input_chars_per_session: int = Field(default=4000)
    sample_start_messages: int = Field(default=4)
    sample_end_messages: int = Field(default=6)
    top_n: int = Field(default=10)
    temperature: float | None = Field(default=None)
    summary_message_filters_exclude_regex: list[str] = Field(default_factory=list)
    summary_message_filters_include_regex: list[str] = Field(default_factory=list)


class Config(BaseModel):
    """chat_ops pack configuration."""

    storage: StorageConfig = Field(default_factory=StorageConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)


_ALLOWED_NOTE_TYPES: set[str] = {"note", "title", "summary"}

_SQLITE_BUSY_TIMEOUT_MS = 30_000
_SQLITE_TIMEOUT_S = _SQLITE_BUSY_TIMEOUT_MS / 1000.0


def _get_config() -> Config:
    return get_tool_config("chat_ops", Config)


def _resolve_db_path(cfg: Config) -> Path:
    db_path = resolve_ot_path(cfg.storage.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _open_sqlite_connection(db_path: Path) -> sqlite3.Connection:
    """Open a chat_ops SQLite connection with consistent pragmas."""
    conn = sqlite3.connect(db_path, timeout=_SQLITE_TIMEOUT_S)
    conn.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _resolve_provider_map(cfg: Config) -> dict[str, ProviderConfig]:
    if cfg.providers:
        return cfg.providers
    return {
        "codex": ProviderConfig(),
    }


def _apply_analysis_rules(cfg: Config) -> None:
    category_rules = [
        (rule.name or f"category_{idx}", rule.category, rule.pattern)
        for idx, rule in enumerate(cfg.analysis.categories, start=1)
    ]
    signal_rules = [
        (rule.name or f"signal_{idx}", rule.signal_type, rule.pattern)
        for idx, rule in enumerate(cfg.analysis.signals, start=1)
    ]
    configure_analysis_rules(
        default_category=cfg.analysis.default_category,
        category_rules=category_rules,
        signal_rules=signal_rules,
    )


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _parse_since(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _resolve_provider_dir(provider_name: str, provider_cfg: ProviderConfig) -> Path:
    raw = provider_cfg.provider_dir.strip()
    if not raw:
        raise ValueError(
            f"provider_dir must be non-empty for provider '{provider_name}'"
        )
    expanded = os.path.expandvars(raw)
    return resolve_cwd_path(expanded)


def _wrap_parse_line_callable(
    *,
    provider_name: str,
    source: str,
    fn: Any,
) -> ParseLineFn:
    if not callable(fn):
        raise ValueError(
            f"parser_file '{source}' for provider '{provider_name}' must define callable parse_line"
        )

    sig = inspect.signature(fn)
    positional = [
        param
        for param in sig.parameters.values()
        if param.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    argc = len(positional)
    if argc < 1:
        raise ValueError(
            f"parser_file '{source}' for provider '{provider_name}' parse_line must accept at least one positional argument"
        )

    if argc == 1:

        def _call(line: str, source_file: str, line_no: int) -> dict[str, Any] | None:
            del source_file, line_no
            parsed = fn(line)
            return parsed if isinstance(parsed, dict) else None

        return _call

    if argc == 2:

        def _call(line: str, source_file: str, line_no: int) -> dict[str, Any] | None:
            del line_no
            parsed = fn(line, source_file)
            return parsed if isinstance(parsed, dict) else None

        return _call

    def _call(line: str, source_file: str, line_no: int) -> dict[str, Any] | None:
        parsed = fn(line, source_file, line_no)
        return parsed if isinstance(parsed, dict) else None

    return _call


def _load_parser_from_file(*, provider_name: str, parser_path: Path) -> ParseLineFn:
    module_name = f"chat_ops_parser_{provider_name}_{uuid.uuid4().hex[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, parser_path)
    if spec is None or spec.loader is None:
        raise ValueError(
            f"unable to load parser_file for provider '{provider_name}': {parser_path}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parse_line = getattr(module, "parse_line", None)
    return _wrap_parse_line_callable(
        provider_name=provider_name,
        source=str(parser_path),
        fn=parse_line,
    )


def _resolve_provider_parser(provider_name: str, provider_cfg: ProviderConfig) -> ParseLineFn:
    parser_file = provider_cfg.parser_file.strip()
    if not parser_file:
        raise ValueError(
            f"parser_file must be non-empty for provider '{provider_name}'"
        )

    if parser_file == "builtin:codex_parser":
        return _wrap_parse_line_callable(
            provider_name=provider_name,
            source=parser_file,
            fn=builtin_codex_parse_line,
        )

    parser_path = resolve_cwd_path(os.path.expandvars(parser_file))
    if not parser_path.exists():
        raise ValueError(
            f"parser_file does not exist for provider '{provider_name}': {parser_path}"
        )
    if parser_path.suffix.lower() != ".py":
        raise ValueError(
            f"parser_file must point to a .py file for provider '{provider_name}': {parser_path}"
        )
    return _load_parser_from_file(provider_name=provider_name, parser_path=parser_path)


def _run_report_excel_job(
    *,
    db_path: Path,
    req: ExcelRequest,
    output_path: Path,
) -> dict[str, Any]:
    conn = _open_sqlite_connection(db_path)
    try:
        ensure_schema(conn)
        return export_excel_report(conn, req=req, output_path=output_path)
    finally:
        conn.close()


def ingest(
    *,
    providers: str | list[str] | None = None,
    since: str | None = None,
    rebuild: bool = False,
    force_rescan: bool = False,
    parse_version: int = 1,
) -> dict[str, Any] | str:
    """Ingest configured provider logs into the chat_ops database.

    Args:
        providers: Provider key or keys from tools.chat_ops.providers. If omitted,
            all configured providers are ingested.
        since: Optional ISO-8601 lower timestamp bound.
        rebuild: Rebuild projections after ingest.
        force_rescan: Ignore offsets and rescan all files.
        parse_version: Parse version for state invalidation.

    Returns:
        Ingest summary dict, or error string.
    """
    with LogSpan(span="chat_ops.ingest", providers=providers, forceRescan=force_rescan) as s:
        try:
            cfg = _get_config()
            db_path = _resolve_db_path(cfg)
            provider_map = _resolve_provider_map(cfg)
            _apply_analysis_rules(cfg)

            if providers is None:
                selected = list(provider_map.keys())
            elif isinstance(providers, str):
                selected = [providers]
            else:
                selected = [str(item) for item in providers]

            if not selected:
                return "Error: no providers selected"

            for name in selected:
                if name not in provider_map:
                    return (
                        f"Error: unsupported provider '{name}'. "
                        f"Configured providers: {', '.join(sorted(provider_map.keys()))}"
                    )

            parsed_since = _parse_since(since)

            results: list[dict[str, Any]] = []
            for name in selected:
                provider_cfg = provider_map[name]
                provider_dir = _resolve_provider_dir(name, provider_cfg)
                parser_fn = _resolve_provider_parser(name, provider_cfg)
                if not provider_dir.exists():
                    raise ValueError(
                        f"provider_dir does not exist for '{name}': {provider_dir}"
                    )
                ingest_result = pipeline_ingest(
                    IngestOptions(
                        db_path=db_path,
                        provider_dir=provider_dir,
                        provider=name,
                        since=parsed_since,
                        rebuild_projections=rebuild,
                        force_rescan=force_rescan,
                        parse_version=parse_version,
                        parse_line=parser_fn,
                    )
                )
                results.append(
                    {
                        "provider": name,
                        "run_id": ingest_result.run_id,
                        "scanned": ingest_result.scanned,
                        "inserted": ingest_result.inserted,
                        "duplicates": ingest_result.duplicates,
                        "skipped": ingest_result.skipped,
                        "errors": ingest_result.errors,
                    }
                )

            s.add(providerCount=len(results))
            return {"db": str(db_path), "providers": results}
        except Exception as exc:
            s.add(error=str(exc))
            return f"Error: {exc}"


def report_excel(
    *,
    projects: str | list[str] | None = None,
    session_ids: str | list[str] | None = None,
    models: str | list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    report: list[str] | None = None,
    limit: int | None = None,
    output_dir: str | None = None,
    output_name: str | None = None,
) -> dict[str, Any] | str:
    """Export an xlsx report over raw modes.

    Args:
        projects: Optional project filter list (CSV string or list).
        session_ids: Optional session_id filter list (CSV string or list).
        models: Optional model filter list (CSV string or list).
        start: Optional ISO-8601 start timestamp (session-level).
        end: Optional ISO-8601 end timestamp (session-level).
        report: Optional raw mode list. Defaults to all raw modes.
        limit: Optional row limit per sheet before filter shaping. When omitted,
            all rows for each raw tab are exported.
        output_dir: Optional output directory.
        output_name: Optional output filename (`.xlsx`).

    Returns:
        Excel export summary dict, or error string.
    """
    with LogSpan(span="chat_ops.report_excel") as s:
        try:
            cfg = _get_config()
            _apply_analysis_rules(cfg)
            db_path = _resolve_db_path(cfg)
            if not db_path.exists():
                return f"Error: database does not exist: {db_path}"

            modes = normalize_modes(report)
            projects_norm = normalize_filter_values(projects)
            session_ids_norm = normalize_filter_values(session_ids)
            models_norm = normalize_filter_values(models)

            output_dir_raw = output_dir or cfg.reporting.output_dir
            output_root = resolve_cwd_path(os.path.expandvars(output_dir_raw))
            output_path = resolve_excel_output_path(
                output_dir=output_root,
                output_name=output_name,
            )
            req = ExcelRequest(
                modes=modes,
                projects=projects_norm,
                session_ids=session_ids_norm,
                models=models_norm,
                start=start,
                end=end,
                limit=limit,
            )

            result = _run_report_excel_job(
                db_path=db_path,
                req=req,
                output_path=output_path,
            )
            s.add(modes=",".join(modes), outputPath=str(output_path))
            return result
        except Exception as exc:
            s.add(error=str(exc))
            return f"Error: {exc}"


def _summary_llm_cfg(
    *,
    cfg: Config,
    llm_model: str | None,
    max_input_chars_per_session: int | None,
    sample_start_messages: int,
    sample_end_messages: int,
    top_n: int,
    temperature: float | None,
    require_llm: bool,
) -> SummaryLlmConfig:
    return SummaryLlmConfig(
        enabled=True,
        required=require_llm,
        llm_model=llm_model or cfg.reporting.llm_model,
        max_input_chars_per_session=max_input_chars_per_session
        or cfg.reporting.max_input_chars_per_session,
        sample_start_messages=sample_start_messages,
        sample_end_messages=sample_end_messages,
        top_n=top_n,
        temperature=temperature if temperature is not None else cfg.reporting.temperature,
        message_filters=MessageFilterConfig(
            exclude_regex=list(cfg.reporting.summary_message_filters_exclude_regex),
            include_regex=list(cfg.reporting.summary_message_filters_include_regex),
        ),
    )


def report_summary(
    *,
    projects: str | list[str] | None = None,
    session_ids: str | list[str] | None = None,
    models: str | list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
    output_dir: str | None = None,
    output_name: str | None = None,
    llm_model: str | None = None,
    max_input_chars_per_session: int | None = None,
    sample_start_messages: int = 4,
    sample_end_messages: int = 6,
    top_n: int = 10,
    temperature: float | None = None,
) -> dict[str, Any] | str:
    with LogSpan(span="chat_ops.report_summary") as s:
        try:
            cfg = _get_config()
            _apply_analysis_rules(cfg)
            db_path = _resolve_db_path(cfg)
            if not db_path.exists():
                return f"Error: database does not exist: {db_path}"
            req = SummaryRequest(
                projects=normalize_filter_values(projects),
                session_ids=normalize_filter_values(session_ids),
                models=normalize_filter_values(models),
                start=start,
                end=end,
                limit=limit,
                output_dir=resolve_cwd_path(os.path.expandvars(output_dir or cfg.reporting.output_dir)),
                output_name=output_name,
                llm=_summary_llm_cfg(
                    cfg=cfg,
                    llm_model=llm_model,
                    max_input_chars_per_session=max_input_chars_per_session,
                    sample_start_messages=sample_start_messages,
                    sample_end_messages=sample_end_messages,
                    top_n=top_n,
                    temperature=temperature,
                    require_llm=False,
                ),
            )
            conn = _open_sqlite_connection(db_path)
            try:
                ensure_schema(conn)
                return run_report_summary(conn, req=req)
            finally:
                conn.close()
        except Exception as exc:
            s.add(error=str(exc))
            return f"Error: {exc}"


def report_llm(
    *,
    projects: str | list[str] | None = None,
    session_ids: str | list[str] | None = None,
    models: str | list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
    output_dir: str | None = None,
    output_name: str | None = None,
    llm_model: str | None = None,
    max_input_chars_per_session: int | None = None,
    top_n: int = 10,
    temperature: float | None = None,
) -> dict[str, Any] | str:
    with LogSpan(span="chat_ops.report_llm") as s:
        try:
            cfg = _get_config()
            _apply_analysis_rules(cfg)
            db_path = _resolve_db_path(cfg)
            if not db_path.exists():
                return f"Error: database does not exist: {db_path}"
            req = SummaryRequest(
                projects=normalize_filter_values(projects),
                session_ids=normalize_filter_values(session_ids),
                models=normalize_filter_values(models),
                start=start,
                end=end,
                limit=limit,
                output_dir=resolve_cwd_path(os.path.expandvars(output_dir or cfg.reporting.output_dir)),
                output_name=output_name,
                llm=_summary_llm_cfg(
                    cfg=cfg,
                    llm_model=llm_model,
                    max_input_chars_per_session=max_input_chars_per_session,
                    sample_start_messages=cfg.reporting.sample_start_messages,
                    sample_end_messages=cfg.reporting.sample_end_messages,
                    top_n=top_n,
                    temperature=temperature,
                    require_llm=True,
                ),
            )
            conn = _open_sqlite_connection(db_path)
            try:
                ensure_schema(conn)
                return run_report_llm(conn, req=req)
            finally:
                conn.close()
        except Exception as exc:
            s.add(error=str(exc))
            return f"Error: {exc}"


def rebuild(*, provider: str = "codex") -> dict[str, Any] | str:
    """Rebuild derived projection tables synchronously.

    Args:
        provider: Provider label to include in response.

    Returns:
        Rebuild summary or error string.
    """
    with LogSpan(span="chat_ops.rebuild", provider=provider) as s:
        try:
            cfg = _get_config()
            db_path = _resolve_db_path(cfg)
            if not db_path.exists():
                return f"Error: database does not exist: {db_path}"
            _apply_analysis_rules(cfg)
            conn = _open_sqlite_connection(db_path)
            try:
                rebuild_projections(conn)
                conn.commit()
            finally:
                conn.close()
            return {
                "ok": True,
                "db": str(db_path),
                "provider": provider,
                "rebuild_at": _now_iso(),
            }
        except Exception as exc:
            s.add(error=str(exc))
            return f"Error: {exc}"


def note(
    *,
    type: NoteType,
    message: str,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> dict[str, Any] | str:
    """Write a chat annotation row.

    Args:
        type: Annotation type (`note`, `title`, `summary`).
        message: Annotation text (required, non-empty).
        session_id: Optional session identifier.
        turn_id: Optional turn identifier.

    Returns:
        Inserted annotation metadata or error string.
    """
    with LogSpan(span="chat_ops.note", annotationType=type) as s:
        conn: sqlite3.Connection | None = None
        try:
            annotation_type = str(type).strip().lower()
            if annotation_type not in _ALLOWED_NOTE_TYPES:
                return (
                    f"Error: invalid type '{type}'. "
                    f"Allowed: {', '.join(sorted(_ALLOWED_NOTE_TYPES))}"
                )
            annotation_value = message.strip()
            if not annotation_value:
                return "Error: message must be non-empty"

            cfg = _get_config()
            db_path = _resolve_db_path(cfg)
            conn = _open_sqlite_connection(db_path)
            ensure_schema(conn)

            event_id = f"co-note-{uuid.uuid4().hex}"
            canonical_payload = json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "co.note",
                        "arguments": {
                            "type": annotation_type,
                            "message": annotation_value,
                        },
                    },
                },
                ensure_ascii=True,
                sort_keys=True,
            )
            sid_raw = (session_id or "").strip()
            sid = sid_raw or str(uuid.uuid5(uuid.NAMESPACE_URL, "chat_ops:manual"))
            tid_raw = (turn_id or "").strip()
            tid = tid_raw or str(uuid.uuid5(uuid.NAMESPACE_URL, f"chat_ops:{sid}:manual-note"))
            now = _now_iso()
            session_name = annotation_value if annotation_type == "title" else None
            first_user_message = annotation_value if annotation_type == "note" else None
            conn.execute(
                """
                INSERT INTO sessions(
                    session_id, provider, provider_session_id, rollout_id,
                    project, session_name, first_user_message, started_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    session_name = COALESCE(excluded.session_name, sessions.session_name),
                    first_user_message = COALESCE(sessions.first_user_message, excluded.first_user_message),
                    updated_at = COALESCE(excluded.updated_at, sessions.updated_at)
                """,
                (
                    sid,
                    "co",
                    sid_raw or None,
                    "co.note",
                    None,
                    session_name,
                    first_user_message,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO turns(
                    turn_id, session_id, provider_turn_id, turn_kind,
                    turn_id_source, started_at, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(turn_id) DO UPDATE SET
                    ended_at = COALESCE(excluded.ended_at, turns.ended_at)
                """,
                (
                    tid,
                    sid,
                    tid_raw or None,
                    "synthetic",
                    "ingest_synthetic",
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO events(
                    event_id, session_id, turn_id, provider,
                    provider_event_uuid, provider_parent_event_uuid, provider_logical_parent_event_uuid,
                    event_type, payload_type, rollout_item_type,
                    event_scope, event_source_kind, is_sidechain,
                    agent_id, request_id, prompt_id, trace_id,
                    event_ts, source_file, line_no, byte_offset, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    sid,
                    tid,
                    "co",
                    None,
                    None,
                    None,
                    "response_item",
                    "function_call",
                    "response_item",
                    "metadata",
                    "always",
                    0,
                    None,
                    None,
                    None,
                    None,
                    now,
                    "co.note",
                    1,
                    0,
                    canonical_payload,
                ),
            )
            cur = conn.execute(
                """
                INSERT INTO event_annotations(
                    event_id, annotation_type, annotation_value, source, raw_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    annotation_type,
                    annotation_value,
                    "tool_call",
                    "co.note",
                ),
            )
            conn.commit()
            annotation_id = int(cur.lastrowid)

            result = {
                "ok": True,
                "id": annotation_id,
                "event_id": event_id,
                "session_id": sid,
                "turn_id": tid,
                "annotation_type": annotation_type,
                "annotation_value": annotation_value,
                "source": "tool_call",
                "db": str(db_path),
            }
            s.add(annotationId=annotation_id)
            return result
        except Exception as exc:
            s.add(error=str(exc))
            return f"Error: {exc}"
        finally:
            if conn is not None:
                conn.close()
