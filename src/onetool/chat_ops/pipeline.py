"""Chat ops ingestion and projection pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


@dataclass(slots=True)
class IngestOptions:
    """Options for ingest execution."""

    db_path: Path
    provider_dir: Path
    provider: str
    since: datetime | None
    rebuild_projections: bool
    force_rescan: bool
    parse_version: int
    parse_line: Callable[[str, str, int], dict[str, Any] | None]


@dataclass(slots=True)
class IngestResult:
    """Counters for an ingest run."""

    run_id: int
    scanned: int = 0
    inserted: int = 0
    duplicates: int = 0
    skipped: int = 0
    errors: int = 0


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ingest_state (
    source_file TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    offset INTEGER NOT NULL,
    line_no INTEGER NOT NULL,
    parse_version INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingest_state_provider ON ingest_state(provider);
CREATE INDEX IF NOT EXISTS idx_ingest_state_updated_at ON ingest_state(updated_at);

CREATE TABLE IF NOT EXISTS ingest_runs (
    ingest_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    provider TEXT NOT NULL,
    parse_version INTEGER NOT NULL,
    scanned INTEGER NOT NULL DEFAULT 0,
    inserted INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ingest_runs_provider_started_at
    ON ingest_runs(provider, started_at);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_completed_at ON ingest_runs(completed_at);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_session_id TEXT,
    rollout_id TEXT NOT NULL,
    project TEXT,
    session_name TEXT,
    first_user_message TEXT,
    started_at TEXT,
    updated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_provider_provider_session_id
    ON sessions(provider, provider_session_id)
    WHERE provider_session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sessions_provider ON sessions(provider);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);

CREATE TABLE IF NOT EXISTS turns (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    provider_turn_id TEXT,
    turn_kind TEXT NOT NULL,
    turn_id_source TEXT,
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(turn_kind IN ('explicit', 'synthetic')),
    CHECK(turn_id_source IN ('turn_context', 'event_payload', 'ingest_synthetic') OR turn_id_source IS NULL),
    UNIQUE(session_id, turn_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_turns_session_provider_turn
    ON turns(session_id, provider_turn_id)
    WHERE provider_turn_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_turns_started_at ON turns(started_at);
CREATE INDEX IF NOT EXISTS idx_turns_kind ON turns(turn_kind);
CREATE INDEX IF NOT EXISTS idx_turns_source ON turns(turn_id_source);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_event_uuid TEXT,
    provider_parent_event_uuid TEXT,
    provider_logical_parent_event_uuid TEXT,
    event_type TEXT NOT NULL,
    payload_type TEXT,
    rollout_item_type TEXT,
    event_scope TEXT NOT NULL DEFAULT 'transcript',
    event_source_kind TEXT NOT NULL DEFAULT 'unknown',
    is_sidechain INTEGER NOT NULL DEFAULT 0,
    agent_id TEXT,
    request_id TEXT,
    prompt_id TEXT,
    trace_id TEXT,
    event_ts TEXT,
    source_file TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    byte_offset INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(session_id, turn_id) REFERENCES turns(session_id, turn_id) ON DELETE CASCADE,
    CHECK(event_scope IN ('transcript', 'metadata', 'queue', 'system', 'ephemeral')),
    CHECK(event_source_kind IN ('limited', 'extended', 'always', 'unknown')),
    CHECK(is_sidechain IN (0,1))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_events_provider_source_loc
    ON events(provider, source_file, line_no, byte_offset);
CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_turn_id ON events(turn_id);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_payload_type ON events(payload_type);
CREATE INDEX IF NOT EXISTS idx_events_type_payload_ts ON events(event_type, payload_type, event_ts);
CREATE INDEX IF NOT EXISTS idx_events_provider_ts ON events(provider, event_ts);
CREATE INDEX IF NOT EXISTS idx_events_scope ON events(event_scope);
CREATE INDEX IF NOT EXISTS idx_events_sidechain ON events(is_sidechain);
CREATE INDEX IF NOT EXISTS idx_events_provider_event_uuid ON events(provider, provider_event_uuid);
CREATE INDEX IF NOT EXISTS idx_events_provider_parent_uuid ON events(provider, provider_parent_event_uuid);
CREATE INDEX IF NOT EXISTS idx_events_trace_id ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_request_id ON events(request_id);
CREATE INDEX IF NOT EXISTS idx_events_rollout_item_type ON events(rollout_item_type);
CREATE INDEX IF NOT EXISTS idx_events_source_kind ON events(event_source_kind);

CREATE TABLE IF NOT EXISTS event_usage (
    event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cached_input_tokens INTEGER,
    reasoning_tokens INTEGER,
    uncached_input_tokens INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    model TEXT,
    model_context_window INTEGER,
    last_input_tokens INTEGER,
    last_cached_input_tokens INTEGER,
    last_output_tokens INTEGER,
    last_reasoning_output_tokens INTEGER,
    last_total_tokens INTEGER,
    cache_read_input_tokens INTEGER,
    cache_creation_input_tokens INTEGER,
    web_search_requests INTEGER,
    web_fetch_requests INTEGER,
    service_tier TEXT,
    speed TEXT,
    plan_type TEXT,
    iterations_json TEXT,
    rate_limit_id TEXT,
    rate_limit_name TEXT,
    rate_primary_used_percent REAL,
    rate_primary_window_minutes INTEGER,
    rate_primary_resets_at INTEGER,
    rate_secondary_used_percent REAL,
    rate_secondary_window_minutes INTEGER,
    rate_secondary_resets_at INTEGER,
    credits_has_credits INTEGER,
    credits_unlimited INTEGER,
    credits_balance TEXT,
    rate_limit_reached_type TEXT,
    CHECK(credits_has_credits IN (0,1) OR credits_has_credits IS NULL),
    CHECK(credits_unlimited IN (0,1) OR credits_unlimited IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_event_usage_model ON event_usage(model);
CREATE INDEX IF NOT EXISTS idx_event_usage_service_tier ON event_usage(service_tier);
CREATE INDEX IF NOT EXISTS idx_event_usage_speed ON event_usage(speed);
CREATE INDEX IF NOT EXISTS idx_event_usage_plan_type ON event_usage(plan_type);
CREATE INDEX IF NOT EXISTS idx_event_usage_rate_limit_reached ON event_usage(rate_limit_reached_type);

CREATE TABLE IF NOT EXISTS event_commands (
    event_command_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    call_id TEXT,
    process_id TEXT,
    provider_turn_id TEXT,
    raw_command TEXT NOT NULL,
    family TEXT,
    base_cmd TEXT,
    subcommand TEXT,
    status TEXT,
    exit_code INTEGER,
    duration_ms REAL,
    completed_at_ms INTEGER,
    stdout TEXT,
    stderr TEXT,
    aggregated_output TEXT,
    formatted_output TEXT,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_commands_event_id ON event_commands(event_id);
CREATE INDEX IF NOT EXISTS idx_event_commands_call_id ON event_commands(call_id);
CREATE INDEX IF NOT EXISTS idx_event_commands_base_cmd ON event_commands(base_cmd);
CREATE INDEX IF NOT EXISTS idx_event_commands_status ON event_commands(status);
CREATE INDEX IF NOT EXISTS idx_event_commands_provider_turn_id ON event_commands(provider_turn_id);

CREATE TABLE IF NOT EXISTS event_file_ops (
    event_file_op_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    op TEXT NOT NULL,
    churn INTEGER NOT NULL DEFAULT 0,
    CHECK(op IN ('read', 'write'))
);

CREATE INDEX IF NOT EXISTS idx_event_file_ops_event_id ON event_file_ops(event_id);
CREATE INDEX IF NOT EXISTS idx_event_file_ops_file_path ON event_file_ops(file_path);
CREATE INDEX IF NOT EXISTS idx_event_file_ops_op ON event_file_ops(op);

CREATE TABLE IF NOT EXISTS event_invocations (
    event_invocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    invocation_type TEXT NOT NULL,
    invocation_text TEXT NOT NULL,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_invocations_event_id ON event_invocations(event_id);
CREATE INDEX IF NOT EXISTS idx_event_invocations_type ON event_invocations(invocation_type);

CREATE TABLE IF NOT EXISTS event_tool_calls (
    event_tool_call_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    call_id TEXT,
    tool_use_id TEXT,
    provider_turn_id TEXT,
    assistant_event_id TEXT REFERENCES events(event_id) ON DELETE SET NULL,
    result_event_id TEXT REFERENCES events(event_id) ON DELETE SET NULL,
    server TEXT,
    tool_name TEXT NOT NULL,
    arguments_json TEXT,
    duration_ms REAL,
    is_error INTEGER,
    status TEXT,
    result_json TEXT,
    error_text TEXT,
    source TEXT,
    CHECK(is_error IN (0,1) OR is_error IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_event_tool_calls_event_id ON event_tool_calls(event_id);
CREATE INDEX IF NOT EXISTS idx_event_tool_calls_call_id ON event_tool_calls(call_id);
CREATE INDEX IF NOT EXISTS idx_event_tool_calls_tool_use_id ON event_tool_calls(tool_use_id);
CREATE INDEX IF NOT EXISTS idx_event_tool_calls_assistant_event_id ON event_tool_calls(assistant_event_id);
CREATE INDEX IF NOT EXISTS idx_event_tool_calls_result_event_id ON event_tool_calls(result_event_id);
CREATE INDEX IF NOT EXISTS idx_event_tool_calls_provider_turn_id ON event_tool_calls(provider_turn_id);
CREATE INDEX IF NOT EXISTS idx_event_tool_calls_server_tool ON event_tool_calls(server, tool_name);

CREATE TABLE IF NOT EXISTS event_patch_ops (
    event_patch_op_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    call_id TEXT NOT NULL,
    provider_turn_id TEXT,
    status TEXT,
    success INTEGER,
    auto_approved INTEGER,
    stdout TEXT,
    stderr TEXT,
    changes_json TEXT,
    CHECK(success IN (0,1) OR success IS NULL),
    CHECK(auto_approved IN (0,1) OR auto_approved IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_event_patch_ops_event_id ON event_patch_ops(event_id);
CREATE INDEX IF NOT EXISTS idx_event_patch_ops_call_id ON event_patch_ops(call_id);
CREATE INDEX IF NOT EXISTS idx_event_patch_ops_provider_turn_id ON event_patch_ops(provider_turn_id);

CREATE TABLE IF NOT EXISTS event_signals (
    event_signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,
    content TEXT NOT NULL,
    evidence_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_signals_event_id ON event_signals(event_id);
CREATE INDEX IF NOT EXISTS idx_event_signals_signal_type ON event_signals(signal_type);

CREATE TABLE IF NOT EXISTS event_annotations (
    event_annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    annotation_type TEXT NOT NULL,
    annotation_value TEXT NOT NULL,
    source TEXT,
    raw_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_annotations_event_id ON event_annotations(event_id);
CREATE INDEX IF NOT EXISTS idx_event_annotations_type ON event_annotations(annotation_type);

CREATE TABLE IF NOT EXISTS event_session_meta (
    event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
    provider_thread_id TEXT,
    forked_from_thread_id TEXT,
    source TEXT,
    originator TEXT,
    cli_version TEXT,
    cwd TEXT,
    agent_nickname TEXT,
    agent_role TEXT,
    agent_path TEXT,
    model_provider TEXT,
    memory_mode TEXT,
    git_sha TEXT,
    git_branch TEXT,
    git_origin_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_session_meta_provider_thread_id
    ON event_session_meta(provider_thread_id);

CREATE TABLE IF NOT EXISTS event_turn_context (
    event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
    provider_turn_id TEXT,
    trace_id TEXT,
    cwd TEXT,
    timezone TEXT,
    current_date TEXT,
    model TEXT,
    approval_policy TEXT,
    sandbox_policy TEXT,
    permission_profile_json TEXT,
    collaboration_mode TEXT,
    realtime_active INTEGER,
    reasoning_effort TEXT,
    CHECK(realtime_active IN (0,1) OR realtime_active IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_event_turn_context_provider_turn_id
    ON event_turn_context(provider_turn_id);
CREATE INDEX IF NOT EXISTS idx_event_turn_context_trace_id
    ON event_turn_context(trace_id);

CREATE TABLE IF NOT EXISTS event_content_blocks (
    event_content_block_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    block_index INTEGER NOT NULL,
    block_type TEXT NOT NULL,
    role TEXT,
    tool_use_id TEXT,
    tool_name TEXT,
    call_id TEXT,
    is_error INTEGER,
    text_content TEXT,
    block_json TEXT NOT NULL,
    CHECK(is_error IN (0,1) OR is_error IS NULL),
    UNIQUE(event_id, block_index)
);

CREATE INDEX IF NOT EXISTS idx_event_content_blocks_event_id ON event_content_blocks(event_id);
CREATE INDEX IF NOT EXISTS idx_event_content_blocks_type ON event_content_blocks(block_type);
CREATE INDEX IF NOT EXISTS idx_event_content_blocks_tool_use_id ON event_content_blocks(tool_use_id);
CREATE INDEX IF NOT EXISTS idx_event_content_blocks_tool_name ON event_content_blocks(tool_name);

CREATE TABLE IF NOT EXISTS event_edges (
    event_edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    to_event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    provider_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_edges_from ON event_edges(from_event_id);
CREATE INDEX IF NOT EXISTS idx_event_edges_to ON event_edges(to_event_id);
CREATE INDEX IF NOT EXISTS idx_event_edges_type ON event_edges(edge_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_event_edges_unique_link
    ON event_edges(from_event_id, to_event_id, edge_type);

CREATE TABLE IF NOT EXISTS mv_turn_metrics (
    turn_id TEXT PRIMARY KEY REFERENCES turns(turn_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    turn_kind TEXT NOT NULL,
    turn_started_at TEXT,
    model TEXT,
    project TEXT,
    task_category TEXT NOT NULL,
    commands_count INTEGER NOT NULL,
    failed_commands_count INTEGER NOT NULL,
    successful_commands_count INTEGER NOT NULL,
    retry_count INTEGER NOT NULL,
    one_shot_success INTEGER NOT NULL,
    file_reads_count INTEGER NOT NULL,
    files_read_unique INTEGER NOT NULL,
    file_writes_count INTEGER NOT NULL,
    files_written_unique INTEGER NOT NULL,
    edit_churn INTEGER NOT NULL,
    invocations_count INTEGER NOT NULL,
    tool_calls_count INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER NOT NULL,
    reasoning_tokens INTEGER NOT NULL,
    uncached_input_tokens INTEGER NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mv_turn_metrics_session_id ON mv_turn_metrics(session_id);
CREATE INDEX IF NOT EXISTS idx_mv_turn_metrics_project ON mv_turn_metrics(project);
CREATE INDEX IF NOT EXISTS idx_mv_turn_metrics_model ON mv_turn_metrics(model);
CREATE INDEX IF NOT EXISTS idx_mv_turn_metrics_category ON mv_turn_metrics(task_category);
CREATE INDEX IF NOT EXISTS idx_mv_turn_metrics_started_at ON mv_turn_metrics(turn_started_at);

CREATE TABLE IF NOT EXISTS mv_session_metrics (
    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    provider_session_id TEXT,
    rollout_id TEXT NOT NULL,
    project TEXT,
    session_name TEXT,
    first_user_message TEXT,
    started_at TEXT,
    updated_at TEXT,
    turns_count INTEGER NOT NULL,
    commands_count INTEGER NOT NULL,
    tool_calls_count INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mv_session_metrics_provider ON mv_session_metrics(provider);
CREATE INDEX IF NOT EXISTS idx_mv_session_metrics_project ON mv_session_metrics(project);
CREATE INDEX IF NOT EXISTS idx_mv_session_metrics_updated_at ON mv_session_metrics(updated_at);
"""

_COMMAND_KEYS = {
    "command",
    "cmd",
    "raw_command",
    "shell_command",
    "command_text",
    "input",
}

_FILE_KEYS = {"path", "file", "filepath", "target_file", "filename"}

_READ_HINTS = ("read", "open", "view", "cat", "grep", "rg", "search")
_WRITE_HINTS = (
    "write",
    "edit",
    "patch",
    "update",
    "create",
    "delete",
    "apply",
    "replace",
)
_USER_MESSAGE_BEGIN = "## My request for Codex:"
_ANNOTATION_KEYS = {"title", "summary", "note"}

_CATEGORY_RULES: list[tuple[str, str, re.Pattern[str]]] = []
_SIGNAL_RULES: list[tuple[str, str, re.Pattern[str]]] = []
_DEFAULT_SIGNAL_RULES: tuple[tuple[str, str, str], ...] = (
    ("failure_signal", "FAILURE", r"\b(?:error|failed|exception|traceback)\b"),
    ("retry_signal", "RETRY", r"\b(?:retry|again)\b"),
    ("patch_summary_signal", "PATCH_SUMMARY", r"(?:\*\*\*\s*begin\s*patch|update\s+file:)"),
)
_DEFAULT_CATEGORY = "GENERAL"
_SQLITE_BUSY_TIMEOUT_MS = 30_000
_SQLITE_TIMEOUT_S = _SQLITE_BUSY_TIMEOUT_MS / 1000.0
_SESSION_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class _TurnResolutionSource:
    TURN_CONTEXT = "turn_context"
    EVENT_PAYLOAD = "event_payload"
    ACTIVE = "active"
    SYNTHETIC = "ingest_synthetic"


def _open_sqlite_connection(db_path: Path) -> sqlite3.Connection:
    """Open a chat_ops pipeline connection with consistent pragmas."""
    conn = sqlite3.connect(db_path, timeout=_SQLITE_TIMEOUT_S)
    conn.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure chat_ops schema exists."""
    conn.executescript(_SCHEMA_SQL)


def configure_analysis_rules(
    *,
    default_category: str | None = None,
    category_rules: list[tuple[str, str, str]] | None = None,
    signal_rules: list[tuple[str, str, str]] | None = None,
) -> None:
    """Configure regex-based category/signal rules for projections."""
    global _CATEGORY_RULES, _SIGNAL_RULES, _DEFAULT_CATEGORY

    compiled_categories: list[tuple[str, str, re.Pattern[str]]] = []
    for name, category, pattern in (category_rules or []):
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(
                f"Invalid category regex rule '{name}' pattern '{pattern}': {exc}"
            ) from exc
        compiled_categories.append((name, category, compiled))

    compiled_signals: list[tuple[str, str, re.Pattern[str]]] = []
    for name, signal_type, pattern in (signal_rules or []):
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(
                f"Invalid signal regex rule '{name}' pattern '{pattern}': {exc}"
            ) from exc
        compiled_signals.append((name, signal_type, compiled))

    _CATEGORY_RULES = compiled_categories
    _SIGNAL_RULES = compiled_signals
    if default_category is not None and default_category.strip():
        _DEFAULT_CATEGORY = default_category.strip()


def _ensure_default_signal_rules() -> None:
    """Apply baseline signal rules when ingest is used without tool-level config."""
    global _SIGNAL_RULES
    if _SIGNAL_RULES:
        return
    compiled: list[tuple[str, str, re.Pattern[str]]] = []
    for name, signal_type, pattern in _DEFAULT_SIGNAL_RULES:
        compiled.append((name, signal_type, re.compile(pattern, re.IGNORECASE)))
    _SIGNAL_RULES = compiled


def ingest(options: IngestOptions) -> IngestResult:
    """Ingest rollout logs and project telemetry tables."""
    options.db_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_default_signal_rules()
    conn = _open_sqlite_connection(options.db_path)
    ensure_schema(conn)

    started_at = _now_iso()
    cur = conn.execute(
        "INSERT INTO ingest_runs(started_at, provider, parse_version) VALUES (?, ?, ?)",
        (started_at, options.provider, options.parse_version),
    )
    run_id = int(cur.lastrowid)
    result = IngestResult(run_id=run_id)

    try:
        for source_file in _discover_rollouts(options.provider_dir):
            result.scanned += 1
            file_result = _ingest_file(
                conn=conn, source_file=source_file, options=options
            )
            result.inserted += file_result["inserted"]
            result.duplicates += file_result["duplicates"]
            result.skipped += file_result["skipped"]
            result.errors += file_result["errors"]
        if options.rebuild_projections or result.inserted > 0:
            rebuild_projections(conn)

        conn.execute(
            """
            UPDATE ingest_runs
            SET completed_at = ?, scanned = ?, inserted = ?, duplicates = ?, skipped = ?, errors = ?
            WHERE ingest_run_id = ?
            """,
            (
                _now_iso(),
                result.scanned,
                result.inserted,
                result.duplicates,
                result.skipped,
                result.errors,
                run_id,
            ),
        )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rebuild_projections(conn: sqlite3.Connection) -> None:
    """Rebuild composition and projection tables from canonical events."""
    ensure_schema(conn)
    conn.execute("DELETE FROM event_usage")
    conn.execute("DELETE FROM event_commands")
    conn.execute("DELETE FROM event_file_ops")
    conn.execute("DELETE FROM event_invocations")
    conn.execute("DELETE FROM event_tool_calls")
    conn.execute("DELETE FROM event_patch_ops")
    conn.execute("DELETE FROM event_signals")
    conn.execute("DELETE FROM event_annotations")
    conn.execute("DELETE FROM event_session_meta")
    conn.execute("DELETE FROM event_turn_context")
    conn.execute("DELETE FROM event_content_blocks")
    conn.execute("DELETE FROM event_edges")
    conn.execute("DELETE FROM mv_turn_metrics")
    conn.execute("DELETE FROM mv_session_metrics")

    rows = query_rows(
        conn,
        sql="""
            SELECT
                e.event_id,
                e.session_id,
                e.turn_id,
                e.provider,
                e.event_type,
                e.payload_type,
                e.provider_event_uuid,
                e.provider_parent_event_uuid,
                e.provider_logical_parent_event_uuid,
                e.event_ts,
                e.source_file,
                e.line_no,
                e.payload_json,
                t.turn_kind,
                t.provider_turn_id,
                s.project,
                s.provider_session_id,
                s.rollout_id
            FROM events e
            JOIN turns t ON t.turn_id = e.turn_id
            JOIN sessions s ON s.session_id = e.session_id
            ORDER BY e.source_file, e.line_no
        """,
        params={},
    )

    by_turn: dict[str, dict[str, Any]] = {}
    event_uuid_map: dict[tuple[str, str], str] = {}

    for row in rows:
        event_id = str(row["event_id"])
        session_id = str(row["session_id"])
        turn_id = str(row["turn_id"])
        provider = _as_str(row.get("provider")) or "(unknown)"
        source_file = _as_str(row.get("source_file")) or ""
        line_no = _as_int(row.get("line_no")) or 0
        payload_raw = _as_str(row.get("payload_json")) or "{}"
        event_ts = _as_str(row.get("event_ts"))
        payload = _safe_json_load(payload_raw)
        if not isinstance(payload, dict):
            continue

        provider_event_uuid = _as_str(row.get("provider_event_uuid"))
        if provider_event_uuid:
            event_uuid_map[(provider, provider_event_uuid)] = event_id

        turn_state = by_turn.setdefault(
            turn_id,
            {
                "turn_id": turn_id,
                "session_id": session_id,
                "turn_kind": _as_str(row.get("turn_kind")) or "synthetic",
                "turn_started_at": None,
                "model": None,
                "project": _as_str(row.get("project")),
                "commands": [],
                "tool_names": [],
                "invocation_items": [],
                "user_messages": [],
                "reads": [],
                "writes": [],
                "edit_churn": 0,
                "retry_hits": 0,
                "invocations": 0,
                "tool_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_input_tokens": 0,
                "reasoning_tokens": 0,
                "uncached_input_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "tokens": 0,
            },
        )

        if event_ts:
            current_started = _as_str(turn_state.get("turn_started_at"))
            if current_started is None or event_ts < current_started:
                turn_state["turn_started_at"] = event_ts

        payload_model = _extract_model(payload)
        payload_reasoning = _extract_reasoning_level(payload)
        effective_model = _format_model_label(payload_model, payload_reasoning)
        if effective_model and turn_state.get("model") is None:
            turn_state["model"] = effective_model

        for user_message in _extract_user_message_texts(payload):
            stripped = user_message.strip()
            if stripped:
                turn_state["user_messages"].append(stripped)

        usage = _extract_usage(payload)
        if usage is not None:
            conn.execute(
                """
                INSERT OR REPLACE INTO event_usage(
                    event_id, input_tokens, output_tokens, cached_input_tokens,
                    reasoning_tokens, uncached_input_tokens, prompt_tokens,
                    completion_tokens, total_tokens, model,
                    model_context_window, last_input_tokens, last_cached_input_tokens,
                    last_output_tokens, last_reasoning_output_tokens, last_total_tokens,
                    cache_read_input_tokens, cache_creation_input_tokens,
                    web_search_requests, web_fetch_requests,
                    service_tier, speed, plan_type, iterations_json,
                    rate_limit_id, rate_limit_name,
                    rate_primary_used_percent, rate_primary_window_minutes, rate_primary_resets_at,
                    rate_secondary_used_percent, rate_secondary_window_minutes, rate_secondary_resets_at,
                    credits_has_credits, credits_unlimited, credits_balance, rate_limit_reached_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    usage.get("input_tokens"),
                    usage.get("output_tokens"),
                    usage.get("cached_input_tokens"),
                    usage.get("reasoning_tokens"),
                    usage.get("uncached_input_tokens"),
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    usage.get("total_tokens"),
                    usage.get("model"),
                    usage.get("model_context_window"),
                    usage.get("last_input_tokens"),
                    usage.get("last_cached_input_tokens"),
                    usage.get("last_output_tokens"),
                    usage.get("last_reasoning_output_tokens"),
                    usage.get("last_total_tokens"),
                    usage.get("cache_read_input_tokens"),
                    usage.get("cache_creation_input_tokens"),
                    usage.get("web_search_requests"),
                    usage.get("web_fetch_requests"),
                    usage.get("service_tier"),
                    usage.get("speed"),
                    usage.get("plan_type"),
                    usage.get("iterations_json"),
                    usage.get("rate_limit_id"),
                    usage.get("rate_limit_name"),
                    usage.get("rate_primary_used_percent"),
                    usage.get("rate_primary_window_minutes"),
                    usage.get("rate_primary_resets_at"),
                    usage.get("rate_secondary_used_percent"),
                    usage.get("rate_secondary_window_minutes"),
                    usage.get("rate_secondary_resets_at"),
                    usage.get("credits_has_credits"),
                    usage.get("credits_unlimited"),
                    usage.get("credits_balance"),
                    usage.get("rate_limit_reached_type"),
                ),
            )
            turn_state["input_tokens"] += int(usage.get("input_tokens") or 0)
            turn_state["output_tokens"] += int(usage.get("output_tokens") or 0)
            turn_state["cached_input_tokens"] += int(usage.get("cached_input_tokens") or 0)
            turn_state["reasoning_tokens"] += int(usage.get("reasoning_tokens") or 0)
            turn_state["uncached_input_tokens"] += int(usage.get("uncached_input_tokens") or 0)
            turn_state["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            turn_state["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            turn_state["tokens"] += int(usage.get("total_tokens") or 0)
            if turn_state.get("model") is None and usage.get("model"):
                turn_state["model"] = usage["model"]

        for command in _extract_commands(payload):
            conn.execute(
                """
                INSERT INTO event_commands(
                    event_id, call_id, process_id, provider_turn_id,
                    raw_command, family, base_cmd, subcommand, status,
                    exit_code, duration_ms, completed_at_ms, stdout, stderr,
                    aggregated_output, formatted_output, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    command.get("call_id"),
                    command.get("process_id"),
                    command.get("provider_turn_id"),
                    command["raw_command"],
                    command.get("family"),
                    command.get("base_cmd"),
                    command.get("subcommand"),
                    command.get("status"),
                    command.get("exit_code"),
                    command.get("duration_ms"),
                    command.get("completed_at_ms"),
                    command.get("stdout"),
                    command.get("stderr"),
                    command.get("aggregated_output"),
                    command.get("formatted_output"),
                    command.get("source"),
                ),
            )
            turn_state["commands"].append(command)

        for file_event in _extract_file_events(payload):
            conn.execute(
                """
                INSERT INTO event_file_ops(event_id, file_path, op, churn)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event_id,
                    file_event["file_path"],
                    file_event["op"],
                    file_event["churn"],
                ),
            )
            if file_event["op"] == "read":
                turn_state["reads"].append(file_event["file_path"])
            else:
                turn_state["writes"].append(file_event["file_path"])
                turn_state["edit_churn"] += int(file_event["churn"])

        for inv in _extract_invocations(payload):
            conn.execute(
                """
                INSERT INTO event_invocations(event_id, invocation_type, invocation_text, source)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event_id,
                    inv["invocation_type"],
                    inv["invocation_text"],
                    inv["source"],
                ),
            )
            turn_state["invocations"] += 1
            turn_state["invocation_items"].append(inv)

        for annotation in _extract_chat_annotations(payload):
            conn.execute(
                """
                INSERT INTO event_annotations(
                    event_id, annotation_type, annotation_value, source, raw_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    annotation["annotation_type"],
                    annotation["annotation_value"],
                    annotation.get("source"),
                    annotation.get("raw_text"),
                ),
            )

        for tool in _extract_tool_calls(payload):
            conn.execute(
                """
                INSERT INTO event_tool_calls(
                    event_id, call_id, tool_use_id, provider_turn_id,
                    assistant_event_id, result_event_id,
                    server, tool_name, arguments_json,
                    duration_ms, is_error, status,
                    result_json, error_text, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    tool.get("call_id"),
                    tool.get("tool_use_id"),
                    tool.get("provider_turn_id"),
                    tool.get("assistant_event_id"),
                    tool.get("result_event_id"),
                    tool.get("server"),
                    tool["tool_name"],
                    tool.get("arguments_json"),
                    tool.get("duration_ms"),
                    tool.get("is_error"),
                    tool.get("status"),
                    tool.get("result_json"),
                    tool.get("error_text"),
                    tool.get("source"),
                ),
            )
            turn_state["tool_calls"] += 1
            turn_state["tool_names"].append(tool["tool_name"])

        for patch in _extract_patch_ops(payload):
            conn.execute(
                """
                INSERT INTO event_patch_ops(
                    event_id, call_id, provider_turn_id, status,
                    success, auto_approved, stdout, stderr, changes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    patch["call_id"],
                    patch.get("provider_turn_id"),
                    patch.get("status"),
                    patch.get("success"),
                    patch.get("auto_approved"),
                    patch.get("stdout"),
                    patch.get("stderr"),
                    patch.get("changes_json"),
                ),
            )

        for signal in _extract_signals(
            payload, source_file=source_file, line_no=line_no, event_id=event_id
        ):
            conn.execute(
                """
                INSERT INTO event_signals(event_id, signal_type, content, evidence_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event_id,
                    signal["signal_type"],
                    signal["content"],
                    json.dumps(signal["evidence"], ensure_ascii=True),
                ),
            )
            if str(signal["signal_type"]).upper() == "RETRY":
                turn_state["retry_hits"] += 1

        session_meta = _extract_session_meta(payload)
        if session_meta is not None:
            conn.execute(
                """
                INSERT OR REPLACE INTO event_session_meta(
                    event_id, provider_thread_id, forked_from_thread_id, source,
                    originator, cli_version, cwd, agent_nickname, agent_role,
                    agent_path, model_provider, memory_mode, git_sha, git_branch,
                    git_origin_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    session_meta.get("provider_thread_id"),
                    session_meta.get("forked_from_thread_id"),
                    session_meta.get("source"),
                    session_meta.get("originator"),
                    session_meta.get("cli_version"),
                    session_meta.get("cwd"),
                    session_meta.get("agent_nickname"),
                    session_meta.get("agent_role"),
                    session_meta.get("agent_path"),
                    session_meta.get("model_provider"),
                    session_meta.get("memory_mode"),
                    session_meta.get("git_sha"),
                    session_meta.get("git_branch"),
                    session_meta.get("git_origin_url"),
                ),
            )

        turn_context = _extract_turn_context(payload)
        if turn_context is not None:
            conn.execute(
                """
                INSERT OR REPLACE INTO event_turn_context(
                    event_id, provider_turn_id, trace_id, cwd, timezone,
                    current_date, model, approval_policy, sandbox_policy,
                    permission_profile_json, collaboration_mode,
                    realtime_active, reasoning_effort
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    turn_context.get("provider_turn_id"),
                    turn_context.get("trace_id"),
                    turn_context.get("cwd"),
                    turn_context.get("timezone"),
                    turn_context.get("current_date"),
                    turn_context.get("model"),
                    turn_context.get("approval_policy"),
                    turn_context.get("sandbox_policy"),
                    turn_context.get("permission_profile_json"),
                    turn_context.get("collaboration_mode"),
                    turn_context.get("realtime_active"),
                    turn_context.get("reasoning_effort"),
                ),
            )

        for block in _extract_content_blocks(payload):
            conn.execute(
                """
                INSERT INTO event_content_blocks(
                    event_id, block_index, block_type, role, tool_use_id,
                    tool_name, call_id, is_error, text_content, block_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    block["block_index"],
                    block["block_type"],
                    block.get("role"),
                    block.get("tool_use_id"),
                    block.get("tool_name"),
                    block.get("call_id"),
                    block.get("is_error"),
                    block.get("text_content"),
                    block["block_json"],
                ),
            )

    _apply_tool_call_correlations(conn)
    _refresh_turn_tool_call_counts(conn, by_turn=by_turn)
    _build_event_edges(conn, event_uuid_map=event_uuid_map)
    _build_turn_metrics(conn, by_turn=by_turn)
    _build_session_metrics(conn)


def _ingest_file(
    *,
    conn: sqlite3.Connection,
    source_file: Path,
    options: IngestOptions,
) -> dict[str, int]:
    stats = {"inserted": 0, "duplicates": 0, "skipped": 0, "errors": 0}
    st = source_file.stat()
    mtime = float(st.st_mtime)
    size = int(st.st_size)

    state_row = conn.execute(
        "SELECT mtime, size, offset, line_no, parse_version FROM ingest_state WHERE source_file = ?",
        (str(source_file),),
    ).fetchone()

    start_offset = 0
    start_line = 0

    if state_row is not None and not options.force_rescan:
        prev_mtime, prev_size, prev_offset, prev_line_no, prev_version = state_row
        if int(prev_version) != options.parse_version:
            start_offset = 0
            start_line = 0
        elif size == int(prev_size) and abs(mtime - float(prev_mtime)) < 0.0001:
            stats["skipped"] += 1
            return stats
        elif size >= int(prev_offset):
            start_offset = int(prev_offset)
            start_line = int(prev_line_no)
        else:
            start_offset = 0
            start_line = 0

    if (
        options.since is not None
        and datetime.fromtimestamp(mtime, tz=UTC) < options.since
        and state_row is None
    ):
        stats["skipped"] += 1
        return stats

    rollout_id = source_file.stem
    fallback_session_id = _canonical_session_from_rollout(
        provider=options.provider,
        source_file=str(source_file),
        rollout_id=rollout_id,
    )

    current_offset = start_offset
    current_line_no = start_line
    active_session_id: str | None = None
    active_provider_session_id: str | None = None
    active_turn_id: str | None = None

    with source_file.open("rb") as handle:
        if start_offset > 0:
            handle.seek(start_offset)
        for raw_line in handle:
            current_line_no += 1
            current_offset += len(raw_line)
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            if options.since is not None:
                maybe_ts = _extract_timestamp_from_line(line)
                if maybe_ts is not None and maybe_ts < options.since:
                    continue

            try:
                payload = options.parse_line(line, str(source_file), current_line_no)
            except Exception:
                stats["errors"] += 1
                continue
            if not isinstance(payload, dict):
                stats["errors"] += 1
                continue

            event_ts = _extract_event_ts(payload)
            provider_session_id = _extract_provider_session_id(payload)
            if provider_session_id:
                active_provider_session_id = provider_session_id
            else:
                provider_session_id = active_provider_session_id

            previous_session_id = active_session_id
            session_id = _resolve_session_id(
                payload=payload,
                provider=options.provider,
                provider_session_id=provider_session_id,
                rollout_id=rollout_id,
                fallback_session_id=fallback_session_id,
                active_session_id=active_session_id,
            )
            if previous_session_id is not None and session_id != previous_session_id:
                # Active turn IDs are session-scoped; drop carried state on session switches.
                active_turn_id = None
            active_session_id = session_id

            project = _extract_project(payload)
            first_user_message = _extract_session_preview(payload)
            session_name = _extract_thread_name_update(payload)
            _upsert_session(
                conn,
                session_id=session_id,
                provider=options.provider,
                provider_session_id=provider_session_id,
                rollout_id=rollout_id,
                project=project,
                session_name=session_name,
                first_user_message=first_user_message,
                event_ts=event_ts,
            )

            turn_resolution = _resolve_turn_for_event(
                conn,
                payload=payload,
                session_id=session_id,
                active_turn_id=active_turn_id,
                event_seed=f"{source_file}:{current_line_no}",
                event_ts=event_ts,
            )
            turn_id = turn_resolution["turn_id"]
            active_turn_id = turn_id

            event_type = _extract_event_type(payload) or "unknown"
            payload_type = _extract_payload_type(payload)
            canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
            event_id = _build_event_id(
                provider=options.provider,
                source_file=source_file,
                line_no=current_line_no,
                canonical_payload=canonical,
            )

            provider_event_uuid = _extract_provider_event_uuid(payload)
            provider_parent_uuid = _extract_provider_parent_event_uuid(payload)
            provider_logical_parent_uuid = _extract_provider_logical_parent_event_uuid(payload)

            cur = conn.execute(
                """
                INSERT INTO events(
                    event_id, session_id, turn_id, provider,
                    provider_event_uuid, provider_parent_event_uuid, provider_logical_parent_event_uuid,
                    event_type, payload_type, rollout_item_type,
                    event_scope, event_source_kind, is_sidechain,
                    agent_id, request_id, prompt_id, trace_id,
                    event_ts, source_file, line_no, byte_offset, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO NOTHING
                """,
                (
                    event_id,
                    session_id,
                    turn_id,
                    options.provider,
                    provider_event_uuid,
                    provider_parent_uuid,
                    provider_logical_parent_uuid,
                    event_type,
                    payload_type,
                    _extract_rollout_item_type(payload),
                    _classify_event_scope(payload),
                    _extract_event_source_kind(payload),
                    _as_sqlite_bool(_extract_is_sidechain(payload)) or 0,
                    _extract_agent_id(payload),
                    _extract_request_id(payload),
                    _extract_prompt_id(payload),
                    _extract_trace_id(payload),
                    event_ts,
                    str(source_file),
                    current_line_no,
                    current_offset,
                    canonical,
                ),
            )

            if cur.rowcount == 1:
                stats["inserted"] += 1
            else:
                stats["duplicates"] += 1

    conn.execute(
        """
        INSERT INTO ingest_state(source_file, provider, mtime, size, offset, line_no, parse_version, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_file) DO UPDATE SET
            provider = excluded.provider,
            mtime = excluded.mtime,
            size = excluded.size,
            offset = excluded.offset,
            line_no = excluded.line_no,
            parse_version = excluded.parse_version,
            updated_at = excluded.updated_at
        """,
        (
            str(source_file),
            options.provider,
            mtime,
            size,
            current_offset,
            current_line_no,
            options.parse_version,
            _now_iso(),
        ),
    )
    return stats


def _discover_rollouts(provider_dir: Path) -> list[Path]:
    files = [p for p in provider_dir.rglob("rollout-*.jsonl") if p.is_file()]
    files.sort()
    return files


def _canonical_session_from_rollout(
    *, provider: str, source_file: str, rollout_id: str
) -> str:
    rollout_uuid = _uuid_from_rollout_id(rollout_id)
    if rollout_uuid:
        return rollout_uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"chatops:{provider}:{source_file}"))


def _resolve_session_id(
    *,
    payload: dict[str, Any],
    provider: str,
    provider_session_id: str | None,
    rollout_id: str,
    fallback_session_id: str,
    active_session_id: str | None,
) -> str:
    direct = _extract_session_id(payload)
    if direct:
        if _SESSION_UUID_RE.fullmatch(direct):
            return direct.lower()
        return str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"chatops:{provider}:provider_session:{direct}",
            )
        )

    if provider_session_id:
        return str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"chatops:{provider}:provider_session:{provider_session_id}",
            )
        )

    if active_session_id:
        return active_session_id

    rollout_uuid = _uuid_from_rollout_id(rollout_id)
    if rollout_uuid:
        return rollout_uuid

    return fallback_session_id


def _upsert_session(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    provider: str,
    provider_session_id: str | None,
    rollout_id: str,
    project: str | None,
    session_name: str | None,
    first_user_message: str | None,
    event_ts: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO sessions(
            session_id, provider, provider_session_id, rollout_id,
            project, session_name, first_user_message, started_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            provider = excluded.provider,
            provider_session_id = COALESCE(sessions.provider_session_id, excluded.provider_session_id),
            rollout_id = excluded.rollout_id,
            project = COALESCE(sessions.project, excluded.project),
            session_name = COALESCE(excluded.session_name, sessions.session_name),
            first_user_message = COALESCE(sessions.first_user_message, excluded.first_user_message),
            started_at =
                CASE
                    WHEN sessions.started_at IS NULL THEN excluded.started_at
                    WHEN excluded.started_at IS NULL THEN sessions.started_at
                    WHEN excluded.started_at < sessions.started_at THEN excluded.started_at
                    ELSE sessions.started_at
                END,
            updated_at =
                CASE
                    WHEN sessions.updated_at IS NULL THEN excluded.updated_at
                    WHEN excluded.updated_at IS NULL THEN sessions.updated_at
                    WHEN excluded.updated_at > sessions.updated_at THEN excluded.updated_at
                    ELSE sessions.updated_at
                END
        """,
        (
            session_id,
            provider,
            provider_session_id,
            rollout_id,
            project,
            session_name,
            first_user_message,
            event_ts,
            event_ts,
        ),
    )


def _resolve_turn_for_event(
    conn: sqlite3.Connection,
    *,
    payload: dict[str, Any],
    session_id: str,
    active_turn_id: str | None,
    event_seed: str,
    event_ts: str | None,
) -> dict[str, str]:
    turn_context_id = _extract_turn_context_id(payload)
    if turn_context_id:
        turn_id = _upsert_turn(
            conn,
            session_id=session_id,
            provider_turn_id=turn_context_id,
            turn_kind="explicit",
            turn_id_source=_TurnResolutionSource.TURN_CONTEXT,
            event_ts=event_ts,
        )
        return {"turn_id": turn_id, "source": _TurnResolutionSource.TURN_CONTEXT}

    payload_turn_id = _extract_turn_id(payload)
    if payload_turn_id:
        turn_id = _upsert_turn(
            conn,
            session_id=session_id,
            provider_turn_id=payload_turn_id,
            turn_kind="explicit",
            turn_id_source=_TurnResolutionSource.EVENT_PAYLOAD,
            event_ts=event_ts,
        )
        return {"turn_id": turn_id, "source": _TurnResolutionSource.EVENT_PAYLOAD}

    if active_turn_id:
        row = conn.execute(
            "SELECT 1 FROM turns WHERE turn_id = ? AND session_id = ?",
            (active_turn_id, session_id),
        ).fetchone()
        if row is not None:
            return {"turn_id": active_turn_id, "source": _TurnResolutionSource.ACTIVE}
        # Stale carried turn state from another session: ignore and create synthetic.

    synthetic_turn_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"chatops:{session_id}:synthetic:{event_seed}"))
    _upsert_turn_with_id(
        conn,
        turn_id=synthetic_turn_id,
        session_id=session_id,
        provider_turn_id=None,
        turn_kind="synthetic",
        turn_id_source=_TurnResolutionSource.SYNTHETIC,
        event_ts=event_ts,
    )
    return {"turn_id": synthetic_turn_id, "source": _TurnResolutionSource.SYNTHETIC}


def _upsert_turn(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    provider_turn_id: str,
    turn_kind: Literal["explicit", "synthetic"],
    turn_id_source: Literal["turn_context", "event_payload", "ingest_synthetic"],
    event_ts: str | None,
) -> str:
    row = conn.execute(
        "SELECT turn_id FROM turns WHERE session_id = ? AND provider_turn_id = ?",
        (session_id, provider_turn_id),
    ).fetchone()
    if row is not None:
        turn_id = str(row[0])
        if event_ts:
            conn.execute(
                """
                UPDATE turns
                SET
                    started_at = CASE
                        WHEN started_at IS NULL THEN ?
                        WHEN ? < started_at THEN ?
                        ELSE started_at
                    END,
                    ended_at = CASE
                        WHEN ended_at IS NULL THEN ?
                        WHEN ? > ended_at THEN ?
                        ELSE ended_at
                    END
                WHERE turn_id = ?
                """,
                (event_ts, event_ts, event_ts, event_ts, event_ts, event_ts, turn_id),
            )
        return turn_id

    turn_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"chatops:{session_id}:provider_turn:{provider_turn_id}",
        )
    )
    _upsert_turn_with_id(
        conn,
        turn_id=turn_id,
        session_id=session_id,
        provider_turn_id=provider_turn_id,
        turn_kind=turn_kind,
        turn_id_source=turn_id_source,
        event_ts=event_ts,
    )
    return turn_id


def _upsert_turn_with_id(
    conn: sqlite3.Connection,
    *,
    turn_id: str,
    session_id: str,
    provider_turn_id: str | None,
    turn_kind: Literal["explicit", "synthetic"],
    turn_id_source: Literal["turn_context", "event_payload", "ingest_synthetic"],
    event_ts: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO turns(
            turn_id, session_id, provider_turn_id, turn_kind,
            turn_id_source, started_at, ended_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(turn_id) DO UPDATE SET
            session_id = excluded.session_id,
            provider_turn_id = COALESCE(turns.provider_turn_id, excluded.provider_turn_id),
            turn_kind = turns.turn_kind,
            turn_id_source = turns.turn_id_source,
            started_at = CASE
                WHEN turns.started_at IS NULL THEN excluded.started_at
                WHEN excluded.started_at IS NULL THEN turns.started_at
                WHEN excluded.started_at < turns.started_at THEN excluded.started_at
                ELSE turns.started_at
            END,
            ended_at = CASE
                WHEN turns.ended_at IS NULL THEN excluded.ended_at
                WHEN excluded.ended_at IS NULL THEN turns.ended_at
                WHEN excluded.ended_at > turns.ended_at THEN excluded.ended_at
                ELSE turns.ended_at
            END
        """,
        (
            turn_id,
            session_id,
            provider_turn_id,
            turn_kind,
            turn_id_source,
            event_ts,
            event_ts,
        ),
    )


def _build_turn_metrics(conn: sqlite3.Connection, *, by_turn: dict[str, dict[str, Any]]) -> None:
    for turn_id, turn_state in by_turn.items():
        commands = turn_state["commands"]
        failed = [c for c in commands if c.get("status") == "failed"]
        succeeded = [c for c in commands if c.get("status") in {"succeeded", "ok"}]
        one_shot = 1 if commands and commands[0].get("status") in {"succeeded", "ok"} else 0
        task_category = _classify_turn_category(turn_state)
        conn.execute(
            """
            INSERT INTO mv_turn_metrics(
                turn_id, session_id, turn_kind, turn_started_at, model, project, task_category,
                commands_count, failed_commands_count, successful_commands_count,
                retry_count, one_shot_success,
                file_reads_count, files_read_unique, file_writes_count, files_written_unique,
                edit_churn, invocations_count, tool_calls_count,
                input_tokens, output_tokens, cached_input_tokens, reasoning_tokens,
                uncached_input_tokens, prompt_tokens, completion_tokens, total_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                turn_id,
                turn_state["session_id"],
                turn_state["turn_kind"],
                turn_state.get("turn_started_at"),
                turn_state.get("model") or "(unknown)",
                turn_state.get("project"),
                task_category,
                len(commands),
                len(failed),
                len(succeeded),
                max(len(failed), int(turn_state["retry_hits"])),
                one_shot,
                len(turn_state["reads"]),
                len(set(turn_state["reads"])),
                len(turn_state["writes"]),
                len(set(turn_state["writes"])),
                int(turn_state["edit_churn"]),
                int(turn_state["invocations"]),
                int(turn_state["tool_calls"]),
                int(turn_state["input_tokens"]),
                int(turn_state["output_tokens"]),
                int(turn_state["cached_input_tokens"]),
                int(turn_state["reasoning_tokens"]),
                int(turn_state["uncached_input_tokens"]),
                int(turn_state["prompt_tokens"]),
                int(turn_state["completion_tokens"]),
                int(turn_state["tokens"]),
            ),
        )


def _build_session_metrics(conn: sqlite3.Connection) -> None:
    rows = query_rows(
        conn,
        sql="""
            SELECT
                s.session_id,
                s.provider,
                s.provider_session_id,
                s.rollout_id,
                s.project,
                s.session_name,
                s.first_user_message,
                s.started_at,
                s.updated_at,
                COUNT(mt.turn_id) AS turns_count,
                COALESCE(SUM(mt.commands_count), 0) AS commands_count,
                COALESCE(SUM(mt.tool_calls_count), 0) AS tool_calls_count,
                COALESCE(SUM(mt.input_tokens), 0) AS input_tokens,
                COALESCE(SUM(mt.output_tokens), 0) AS output_tokens,
                COALESCE(SUM(mt.total_tokens), 0) AS total_tokens
            FROM sessions s
            LEFT JOIN mv_turn_metrics mt
              ON mt.session_id = s.session_id
            GROUP BY
                s.session_id,
                s.provider,
                s.provider_session_id,
                s.rollout_id,
                s.project,
                s.session_name,
                s.first_user_message,
                s.started_at,
                s.updated_at
        """,
        params={},
    )

    for row in rows:
        conn.execute(
            """
            INSERT INTO mv_session_metrics(
                session_id, provider, provider_session_id, rollout_id,
                project, session_name, first_user_message, started_at, updated_at,
                turns_count, commands_count, tool_calls_count,
                input_tokens, output_tokens, total_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("session_id"),
                row.get("provider"),
                row.get("provider_session_id"),
                row.get("rollout_id"),
                row.get("project"),
                row.get("session_name"),
                row.get("first_user_message"),
                row.get("started_at"),
                row.get("updated_at"),
                int(row.get("turns_count") or 0),
                int(row.get("commands_count") or 0),
                int(row.get("tool_calls_count") or 0),
                int(row.get("input_tokens") or 0),
                int(row.get("output_tokens") or 0),
                int(row.get("total_tokens") or 0),
            ),
        )


def _apply_tool_call_correlations(conn: sqlite3.Connection) -> None:
    rows = query_rows(
        conn,
        sql="""
            SELECT
                event_tool_call_id,
                event_id,
                call_id,
                tool_use_id,
                provider_turn_id,
                assistant_event_id,
                result_event_id,
                server,
                tool_name,
                arguments_json,
                duration_ms,
                is_error,
                status,
                result_json,
                error_text,
                source
            FROM event_tool_calls
            ORDER BY event_tool_call_id ASC
        """,
        params={},
    )
    if not rows:
        return

    event_time_rows = query_rows(
        conn,
        sql="""
            SELECT event_id, event_ts
            FROM events
            WHERE event_ts IS NOT NULL
        """,
        params={},
    )
    event_dt_by_id: dict[str, datetime] = {}
    for row in event_time_rows:
        event_id = _as_str(row.get("event_id"))
        event_ts = _as_str(row.get("event_ts"))
        if not event_id or not event_ts:
            continue
        parsed = _parse_since(event_ts)
        if parsed is None:
            continue
        event_dt_by_id[event_id] = parsed

    key_to_indexes: dict[str, list[int]] = {}
    row_keys: list[list[str]] = []
    for idx, row in enumerate(rows):
        keys: list[str] = []
        call_id = _as_str(row.get("call_id"))
        if call_id:
            keys.append(f"call:{call_id}")
        tool_use_id = _as_str(row.get("tool_use_id"))
        if tool_use_id:
            keys.append(f"tool_use:{tool_use_id}")
        row_keys.append(keys)
        for key in keys:
            key_to_indexes.setdefault(key, []).append(idx)

    components: list[list[dict[str, Any]]] = []
    visited: set[int] = set()
    for idx in range(len(rows)):
        if idx in visited:
            continue
        queue = [idx]
        visited.add(idx)
        component: list[dict[str, Any]] = []
        while queue:
            current = queue.pop()
            component.append(rows[current])
            for key in row_keys[current]:
                for linked in key_to_indexes.get(key, []):
                    if linked in visited:
                        continue
                    visited.add(linked)
                    queue.append(linked)
        components.append(component)

    def _derive_duration_ms(start_event_id: str | None, end_event_id: str | None) -> float | None:
        if not start_event_id or not end_event_id:
            return None
        start_dt = event_dt_by_id.get(start_event_id)
        end_dt = event_dt_by_id.get(end_event_id)
        if start_dt is None or end_dt is None:
            return None
        delta_ms = (end_dt - start_dt).total_seconds() * 1000.0
        if delta_ms < 0:
            return None
        return delta_ms

    def _event_sort_key(item: dict[str, Any]) -> tuple[int, datetime, int]:
        event_id = _as_str(item.get("event_id")) or ""
        event_dt = event_dt_by_id.get(event_id)
        if event_dt is not None:
            return (0, event_dt, int(item.get("event_tool_call_id") or 0))
        return (1, datetime.min.replace(tzinfo=UTC), int(item.get("event_tool_call_id") or 0))

    def _first_value(items: list[dict[str, Any]], field: str) -> Any:
        for item in items:
            value = item.get(field)
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            return value
        return None

    canonical_rows: list[dict[str, Any]] = []
    for group in components:
        ordered = sorted(group, key=_event_sort_key)
        starts = [
            item
            for item in ordered
            if (_as_str(item.get("status")) or "").lower() in {"called", "started", "request"}
        ]
        terminals = [
            item
            for item in ordered
            if (_as_str(item.get("status")) or "").lower()
            in {"succeeded", "failed", "completed", "result", "ok", "error"}
        ]

        start_row = starts[0] if starts else ordered[0]
        terminal_row = terminals[-1] if terminals else ordered[-1]
        assistant_event_id = _as_str(start_row.get("event_id"))
        result_event_id = _as_str(terminal_row.get("event_id"))
        if assistant_event_id is None and result_event_id is None:
            continue

        derived_duration_ms = _derive_duration_ms(assistant_event_id, result_event_id)
        canonical_duration_ms = derived_duration_ms
        if canonical_duration_ms is None:
            canonical_duration_ms = _as_float(terminal_row.get("duration_ms"))
        if canonical_duration_ms is None:
            canonical_duration_ms = _as_float(start_row.get("duration_ms"))

        canonical = {
            "event_id": assistant_event_id or result_event_id or _as_str(start_row.get("event_id")),
            "call_id": _first_value([start_row, terminal_row, *ordered], "call_id"),
            "tool_use_id": _first_value([start_row, terminal_row, *ordered], "tool_use_id"),
            "provider_turn_id": _first_value([start_row, terminal_row, *ordered], "provider_turn_id"),
            "assistant_event_id": assistant_event_id,
            "result_event_id": result_event_id,
            "server": _first_value([start_row, terminal_row, *ordered], "server"),
            "tool_name": _first_value([start_row, terminal_row, *ordered], "tool_name"),
            "arguments_json": _first_value([start_row, terminal_row, *ordered], "arguments_json"),
            "duration_ms": canonical_duration_ms,
            "is_error": _first_value([terminal_row, start_row, *ordered], "is_error"),
            "status": _first_value([terminal_row, start_row, *ordered], "status"),
            "result_json": _first_value([terminal_row, start_row, *ordered], "result_json"),
            "error_text": _first_value([terminal_row, start_row, *ordered], "error_text"),
            "source": _first_value([terminal_row, start_row, *ordered], "source"),
        }
        if canonical["tool_name"] is None:
            canonical["tool_name"] = "(unknown)"
        canonical_rows.append(canonical)

    shell_wrapper_rows = [
        row for row in canonical_rows if _is_shell_wrapper_tool_name(_as_str(row.get("tool_name")))
    ]
    non_shell_rows = [
        row
        for row in canonical_rows
        if not _is_shell_wrapper_tool_name(_as_str(row.get("tool_name")))
    ]

    conn.execute("DELETE FROM event_tool_calls")
    for row in non_shell_rows:
        conn.execute(
            """
            INSERT INTO event_tool_calls(
                event_id, call_id, tool_use_id, provider_turn_id,
                assistant_event_id, result_event_id,
                server, tool_name, arguments_json,
                duration_ms, is_error, status,
                result_json, error_text, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("event_id"),
                row.get("call_id"),
                row.get("tool_use_id"),
                row.get("provider_turn_id"),
                row.get("assistant_event_id"),
                row.get("result_event_id"),
                row.get("server"),
                row.get("tool_name"),
                row.get("arguments_json"),
                row.get("duration_ms"),
                row.get("is_error"),
                row.get("status"),
                row.get("result_json"),
                row.get("error_text"),
                row.get("source"),
            ),
        )
    _synthesize_shell_commands_from_tool_calls(conn, shell_wrapper_rows)


def _refresh_turn_tool_call_counts(conn: sqlite3.Connection, *, by_turn: dict[str, dict[str, Any]]) -> None:
    for turn_state in by_turn.values():
        turn_state["tool_calls"] = 0
    rows = query_rows(
        conn,
        sql="""
            SELECT e.turn_id, COUNT(*) AS calls
            FROM event_tool_calls etc
            JOIN events e ON e.event_id = etc.event_id
            GROUP BY e.turn_id
        """,
        params={},
    )
    for row in rows:
        turn_id = _as_str(row.get("turn_id"))
        if not turn_id:
            continue
        turn_state = by_turn.get(turn_id)
        if turn_state is None:
            continue
        turn_state["tool_calls"] = int(row.get("calls") or 0)


def _synthesize_shell_commands_from_tool_calls(
    conn: sqlite3.Connection, rows: list[dict[str, Any]]
) -> None:
    for row in rows:
        call_id = _as_str(row.get("call_id"))
        if call_id:
            exists = conn.execute(
                "SELECT 1 FROM event_commands WHERE call_id = ? LIMIT 1",
                (call_id,),
            ).fetchone()
            if exists is not None:
                continue

        raw_command = _extract_shell_command_from_tool_arguments(row.get("arguments_json"))
        if raw_command is None:
            continue

        status = (_as_str(row.get("status")) or "").strip().lower()
        if status not in {"succeeded", "failed"}:
            status = "failed" if int(row.get("is_error") or 0) == 1 else "succeeded"

        result_text = _extract_shell_result_text(row.get("result_json"))
        error_text = _as_str(row.get("error_text"))
        if status == "failed":
            stderr = error_text or result_text
            stdout = None
            aggregated_output = stderr
            formatted_output = error_text
        else:
            stdout = result_text
            stderr = None
            aggregated_output = stdout
            formatted_output = None

        family, base_cmd, subcommand = _parse_command(raw_command)
        event_id = _as_str(row.get("result_event_id")) or _as_str(row.get("event_id"))
        if not event_id:
            continue
        conn.execute(
            """
            INSERT INTO event_commands(
                event_id, call_id, process_id, provider_turn_id,
                raw_command, family, base_cmd, subcommand, status,
                exit_code, duration_ms, completed_at_ms, stdout, stderr,
                aggregated_output, formatted_output, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                call_id,
                None,
                _as_str(row.get("provider_turn_id")),
                raw_command,
                family,
                base_cmd,
                subcommand,
                status,
                None,
                _as_float(row.get("duration_ms")),
                None,
                stdout,
                stderr,
                aggregated_output,
                formatted_output,
                "tool_call_synth",
            ),
        )


def _extract_shell_command_from_tool_arguments(arguments_json: Any) -> str | None:
    parsed = _decode_json_value(arguments_json)
    if isinstance(parsed, dict):
        raw = _str_or_none(parsed.get("cmd"), parsed.get("command"))
        if raw:
            return raw.strip()
    return None


def _extract_shell_result_text(result_json: Any) -> str | None:
    parsed = _decode_json_value(result_json)
    if parsed is None:
        return None
    return _extract_text_blob(parsed)


def _decode_json_value(value: Any) -> Any:
    current = value
    for _ in range(3):
        if not isinstance(current, str):
            break
        loaded = _safe_json_load(current)
        if loaded is None:
            break
        current = loaded
    return current


def _is_shell_wrapper_tool_name(tool_name: str | None) -> bool:
    if not tool_name:
        return False
    normalized = tool_name.strip().lower()
    return normalized == "exec_command" or normalized.endswith(".exec_command")


def _build_event_edges(
    conn: sqlite3.Connection, *, event_uuid_map: dict[tuple[str, str], str]
) -> None:
    events = query_rows(
        conn,
        sql="""
            SELECT event_id, provider, provider_parent_event_uuid, provider_logical_parent_event_uuid
            FROM events
        """,
        params={},
    )

    for row in events:
        event_id = _as_str(row.get("event_id"))
        provider = _as_str(row.get("provider"))
        if not event_id or not provider:
            continue

        parent_uuid = _as_str(row.get("provider_parent_event_uuid"))
        if parent_uuid:
            parent_event_id = event_uuid_map.get((provider, parent_uuid))
            if parent_event_id:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO event_edges(from_event_id, to_event_id, edge_type, provider_ref)
                    VALUES (?, ?, ?, ?)
                    """,
                    (event_id, parent_event_id, "parent", parent_uuid),
                )

        logical_parent_uuid = _as_str(row.get("provider_logical_parent_event_uuid"))
        if logical_parent_uuid:
            logical_parent_event_id = event_uuid_map.get((provider, logical_parent_uuid))
            if logical_parent_event_id:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO event_edges(from_event_id, to_event_id, edge_type, provider_ref)
                    VALUES (?, ?, ?, ?)
                    """,
                    (event_id, logical_parent_event_id, "logical_parent", logical_parent_uuid),
                )

    tool_rows = query_rows(
        conn,
        sql="""
            SELECT DISTINCT assistant_event_id, result_event_id, call_id, tool_use_id
            FROM event_tool_calls
            WHERE assistant_event_id IS NOT NULL AND result_event_id IS NOT NULL
        """,
        params={},
    )
    for row in tool_rows:
        assistant_event_id = _as_str(row.get("assistant_event_id"))
        result_event_id = _as_str(row.get("result_event_id"))
        if not assistant_event_id or not result_event_id:
            continue
        provider_ref = _as_str(row.get("tool_use_id")) or _as_str(row.get("call_id"))
        conn.execute(
            """
            INSERT OR IGNORE INTO event_edges(from_event_id, to_event_id, edge_type, provider_ref)
            VALUES (?, ?, ?, ?)
            """,
            (result_event_id, assistant_event_id, "tool_result_of", provider_ref),
        )


def _extract_usage(payload: dict[str, Any]) -> dict[str, Any] | None:
    usage_node: dict[str, Any] | None = None
    info_node: dict[str, Any] | None = None
    total_usage_node: dict[str, Any] | None = None
    nested = payload.get("payload")
    if (
        isinstance(nested, dict)
        and _as_str(payload.get("type")) == "event_msg"
        and _as_str(nested.get("type")) == "token_count"
    ):
        maybe_info = nested.get("info")
        if isinstance(maybe_info, dict):
            info_node = maybe_info
            for key in ("last_token_usage", "total_token_usage"):
                token_node = maybe_info.get(key)
                if isinstance(token_node, dict):
                    usage_node = token_node
                    break
            total_candidate = maybe_info.get("total_token_usage")
            if isinstance(total_candidate, dict):
                total_usage_node = total_candidate

    for node in _iter_nodes(payload):
        if usage_node is not None:
            break
        if not isinstance(node, dict):
            continue
        if any(
            key in node
            for key in (
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "reasoning_output_tokens",
                "prompt_tokens",
                "completion_tokens",
            )
        ):
            usage_node = node
            break

    if usage_node is None:
        return None

    prompt = _int_or_none(
        usage_node.get("prompt_tokens"),
        total_usage_node.get("prompt_tokens") if total_usage_node else None,
    )
    completion = _int_or_none(
        usage_node.get("completion_tokens"),
        total_usage_node.get("completion_tokens") if total_usage_node else None,
    )
    input_tokens = _int_or_none(
        usage_node.get("input_tokens"),
        total_usage_node.get("input_tokens") if total_usage_node else None,
    )
    output_tokens = _int_or_none(
        usage_node.get("output_tokens"),
        total_usage_node.get("output_tokens") if total_usage_node else None,
    )
    cached_input = _int_or_none(
        usage_node.get("cached_input_tokens"),
        total_usage_node.get("cached_input_tokens") if total_usage_node else None,
    )
    reasoning = _int_or_none(
        usage_node.get("reasoning_output_tokens"),
        total_usage_node.get("reasoning_output_tokens") if total_usage_node else None,
    )
    total_tokens = _int_or_none(
        usage_node.get("total_tokens"),
        total_usage_node.get("total_tokens") if total_usage_node else None,
    )

    if prompt is None and input_tokens is not None:
        prompt = max(0, input_tokens - int(cached_input or 0))
    if completion is None and output_tokens is not None:
        completion = output_tokens + int(reasoning or 0)

    if total_tokens is None:
        total_tokens = (prompt or 0) + (completion or 0) + int(cached_input or 0)

    rate_limits = _extract_rate_limit_snapshot(payload)

    return {
        "model": _str_or_none(
            usage_node.get("model"),
            usage_node.get("model_name"),
            info_node.get("model") if info_node else None,
            info_node.get("model_name") if info_node else None,
            _extract_model(payload),
        ),
        "input_tokens": input_tokens if input_tokens is not None else prompt,
        "output_tokens": output_tokens if output_tokens is not None else completion,
        "cached_input_tokens": cached_input,
        "reasoning_tokens": reasoning,
        "uncached_input_tokens": prompt,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total_tokens,
        "model_context_window": _int_or_none(
            usage_node.get("model_context_window"),
            info_node.get("model_context_window") if info_node else None,
        ),
        "last_input_tokens": _int_or_none(
            usage_node.get("last_input_tokens"),
            usage_node.get("input_tokens"),
        ),
        "last_cached_input_tokens": _int_or_none(
            usage_node.get("last_cached_input_tokens"),
            usage_node.get("cached_input_tokens"),
        ),
        "last_output_tokens": _int_or_none(
            usage_node.get("last_output_tokens"),
            usage_node.get("output_tokens"),
        ),
        "last_reasoning_output_tokens": _int_or_none(
            usage_node.get("last_reasoning_output_tokens"),
            usage_node.get("reasoning_output_tokens"),
        ),
        "last_total_tokens": _int_or_none(
            usage_node.get("last_total_tokens"),
            usage_node.get("total_tokens"),
        ),
        "cache_read_input_tokens": _as_int(usage_node.get("cache_read_input_tokens")),
        "cache_creation_input_tokens": _as_int(usage_node.get("cache_creation_input_tokens")),
        "web_search_requests": _as_int(usage_node.get("web_search_requests")),
        "web_fetch_requests": _as_int(usage_node.get("web_fetch_requests")),
        "service_tier": _str_or_none(
            usage_node.get("service_tier"),
            info_node.get("service_tier") if info_node else None,
        ),
        "speed": _str_or_none(
            usage_node.get("speed"),
            info_node.get("speed") if info_node else None,
        ),
        "plan_type": _str_or_none(
            usage_node.get("plan_type"),
            info_node.get("plan_type") if info_node else None,
            rate_limits.get("plan_type"),
        ),
        "iterations_json": _json_or_none(
            usage_node.get("iterations")
            if usage_node.get("iterations") is not None
            else (info_node.get("iterations") if info_node else None)
        ),
        "rate_limit_id": rate_limits.get("rate_limit_id"),
        "rate_limit_name": rate_limits.get("rate_limit_name"),
        "rate_primary_used_percent": rate_limits.get("rate_primary_used_percent"),
        "rate_primary_window_minutes": rate_limits.get("rate_primary_window_minutes"),
        "rate_primary_resets_at": rate_limits.get("rate_primary_resets_at"),
        "rate_secondary_used_percent": rate_limits.get("rate_secondary_used_percent"),
        "rate_secondary_window_minutes": rate_limits.get("rate_secondary_window_minutes"),
        "rate_secondary_resets_at": rate_limits.get("rate_secondary_resets_at"),
        "credits_has_credits": rate_limits.get("credits_has_credits"),
        "credits_unlimited": rate_limits.get("credits_unlimited"),
        "credits_balance": rate_limits.get("credits_balance"),
        "rate_limit_reached_type": rate_limits.get("rate_limit_reached_type"),
    }


def _extract_rate_limit_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        rate_limits = node.get("rate_limits")
        if isinstance(rate_limits, dict):
            primary = rate_limits.get("primary") if isinstance(rate_limits.get("primary"), dict) else {}
            secondary = (
                rate_limits.get("secondary") if isinstance(rate_limits.get("secondary"), dict) else {}
            )
            credits = rate_limits.get("credits") if isinstance(rate_limits.get("credits"), dict) else {}
            out["rate_limit_id"] = _str_or_none(rate_limits.get("rate_limit_id"), rate_limits.get("limit_id"))
            out["rate_limit_name"] = _str_or_none(
                rate_limits.get("rate_limit_name"), rate_limits.get("limit_name")
            )
            out["rate_primary_used_percent"] = _as_float(primary.get("used_percent"))
            out["rate_primary_window_minutes"] = _as_int(primary.get("window_minutes"))
            out["rate_primary_resets_at"] = _as_int(primary.get("resets_at"))
            out["rate_secondary_used_percent"] = _as_float(secondary.get("used_percent"))
            out["rate_secondary_window_minutes"] = _as_int(secondary.get("window_minutes"))
            out["rate_secondary_resets_at"] = _as_int(secondary.get("resets_at"))
            out["credits_has_credits"] = _as_sqlite_bool(credits.get("has_credits"))
            out["credits_unlimited"] = _as_sqlite_bool(credits.get("unlimited"))
            out["credits_balance"] = _as_str(credits.get("balance"))
            out["rate_limit_reached_type"] = _as_str(rate_limits.get("rate_limit_reached_type"))
            out["plan_type"] = _as_str(rate_limits.get("plan_type"))
            break

        if "rate_limit_id" in node or "credits_balance" in node:
            out["rate_limit_id"] = _as_str(node.get("rate_limit_id"))
            out["rate_limit_name"] = _as_str(node.get("rate_limit_name"))
            out["rate_primary_used_percent"] = _as_float(node.get("rate_primary_used_percent"))
            out["rate_primary_window_minutes"] = _as_int(node.get("rate_primary_window_minutes"))
            out["rate_primary_resets_at"] = _as_int(node.get("rate_primary_resets_at"))
            out["rate_secondary_used_percent"] = _as_float(node.get("rate_secondary_used_percent"))
            out["rate_secondary_window_minutes"] = _as_int(node.get("rate_secondary_window_minutes"))
            out["rate_secondary_resets_at"] = _as_int(node.get("rate_secondary_resets_at"))
            out["credits_has_credits"] = _as_sqlite_bool(node.get("credits_has_credits"))
            out["credits_unlimited"] = _as_sqlite_bool(node.get("credits_unlimited"))
            out["credits_balance"] = _as_str(node.get("credits_balance"))
            out["rate_limit_reached_type"] = _as_str(node.get("rate_limit_reached_type"))
            out["plan_type"] = _as_str(node.get("plan_type"))
            break
    return out


def _extract_commands(payload: dict[str, Any]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []

    top_type = _as_str(payload.get("type"))
    nested = payload.get("payload")
    if not isinstance(nested, dict):
        return commands

    nested_type = _as_str(nested.get("type"))
    if top_type == "event_msg" and nested_type == "exec_command_end":
        raw = _extract_exec_command_text(nested)
        if raw:
            exit_code = _as_int(nested.get("exit_code"))
            status = "succeeded" if exit_code == 0 else "failed"
            duration_ms = _extract_duration_ms(nested.get("duration"))
            family, base_cmd, subcommand = _parse_command(raw)
            commands.append(
                {
                    "call_id": _as_str(nested.get("call_id")),
                    "process_id": _as_str(nested.get("process_id")),
                    "provider_turn_id": _extract_turn_id(payload),
                    "raw_command": raw,
                    "family": family,
                    "base_cmd": base_cmd,
                    "subcommand": subcommand,
                    "status": status,
                    "exit_code": exit_code,
                    "duration_ms": duration_ms,
                    "completed_at_ms": _as_int(nested.get("completed_at_ms")),
                    "stdout": _as_str(nested.get("stdout")),
                    "stderr": _as_str(nested.get("stderr")),
                    "aggregated_output": _as_str(nested.get("aggregated_output")),
                    "formatted_output": _as_str(nested.get("formatted_output")),
                    "source": "event_msg",
                }
            )

    return commands


def _extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    top_type = _as_str(payload.get("type"))
    nested = payload.get("payload")
    if not isinstance(nested, dict):
        return out

    if top_type == "response_item" and _as_str(nested.get("type")) == "function_call":
        tool_name = _as_str(nested.get("name"))
        if tool_name:
            out.append(
                {
                    "call_id": _as_str(nested.get("call_id")),
                    "tool_use_id": _as_str(nested.get("tool_use_id")) or _as_str(nested.get("id")),
                    "provider_turn_id": _extract_turn_id(payload),
                    "assistant_event_id": None,
                    "result_event_id": None,
                    "server": _as_str(nested.get("server")),
                    "tool_name": tool_name,
                    "arguments_json": _json_or_none(nested.get("arguments")),
                    "duration_ms": _extract_duration_ms(nested.get("duration")),
                    "is_error": _as_sqlite_bool(nested.get("is_error")),
                    "status": _as_str(nested.get("status")) or "called",
                    "result_json": _json_or_none(nested.get("result")),
                    "error_text": _as_str(nested.get("error")),
                    "source": "response_item",
                }
            )

    if top_type == "response_item" and _as_str(nested.get("type")) == "function_call_output":
        call_id = _as_str(nested.get("call_id"))
        if call_id:
            is_error = _as_sqlite_bool(nested.get("is_error"))
            out.append(
                {
                    "call_id": call_id,
                    "tool_use_id": _as_str(nested.get("tool_use_id")) or _as_str(nested.get("id")),
                    "provider_turn_id": _extract_turn_id(payload),
                    "assistant_event_id": None,
                    "result_event_id": None,
                    "server": _as_str(nested.get("server")),
                    "tool_name": _as_str(nested.get("name")) or "(unknown)",
                    "arguments_json": None,
                    "duration_ms": _extract_duration_ms(nested.get("duration")),
                    "is_error": is_error,
                    "status": "failed" if is_error == 1 else "succeeded",
                    "result_json": _json_or_none(nested.get("output")),
                    "error_text": _as_str(nested.get("error")),
                    "source": "response_item_output",
                }
            )

    if top_type == "event_msg" and _as_str(nested.get("type")) == "mcp_tool_call_end":
        invocation = nested.get("invocation")
        if isinstance(invocation, dict):
            out.append(
                {
                    "call_id": _as_str(invocation.get("call_id")) or _as_str(nested.get("call_id")),
                    "tool_use_id": _as_str(invocation.get("tool_use_id")),
                    "provider_turn_id": _extract_turn_id(payload),
                    "assistant_event_id": None,
                    "result_event_id": None,
                    "server": _as_str(invocation.get("server")),
                    "tool_name": _as_str(invocation.get("tool")) or "(unknown)",
                    "arguments_json": _json_or_none(invocation.get("arguments")),
                    "duration_ms": _extract_duration_ms(nested.get("duration")),
                    "is_error": 1 if _mcp_result_is_error(nested.get("result")) else 0,
                    "status": "failed" if _mcp_result_is_error(nested.get("result")) else "succeeded",
                    "result_json": _json_or_none(nested.get("result")),
                    "error_text": _as_str(nested.get("error")),
                    "source": "mcp_tool_call_end",
                }
            )

    return out


def _extract_patch_ops(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    nested = payload.get("payload")
    if not isinstance(nested, dict):
        return out
    if _as_str(payload.get("type")) != "event_msg":
        return out
    if _as_str(nested.get("type")) != "patch_apply_end":
        return out

    out.append(
        {
            "call_id": _as_str(nested.get("call_id")) or "unknown",
            "provider_turn_id": _extract_turn_id(payload),
            "status": _as_str(nested.get("status")),
            "success": _as_sqlite_bool(nested.get("success")),
            "auto_approved": _as_sqlite_bool(nested.get("auto_approved")),
            "stdout": _as_str(nested.get("stdout")),
            "stderr": _as_str(nested.get("stderr")),
            "changes_json": _json_or_none(nested.get("changes")),
        }
    )
    return out


def _extract_file_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        joined = json.dumps(node, ensure_ascii=True).lower()
        for key in _FILE_KEYS:
            file_path = node.get(key)
            if not isinstance(file_path, str):
                continue
            file_path = file_path.strip()
            if not file_path:
                continue

            if any(h in joined for h in _WRITE_HINTS):
                op = "write"
            elif any(h in joined for h in _READ_HINTS):
                op = "read"
            else:
                continue

            churn = _estimate_edit_churn(node)
            dedupe = f"{file_path}|{op}|{churn}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            out.append({"file_path": file_path, "op": op, "churn": churn})
    return out


def _extract_invocations(payload: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    for text in _extract_user_message_texts(payload):
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("`"):
                continue

            slash_match = re.match(r"^/([a-z][a-z0-9:_\-]*)(?:\s|$)", stripped)
            if slash_match is not None:
                invocation = f"/{slash_match.group(1)}"
                key = f"slash|{invocation}"
                if key not in seen:
                    out.append(
                        {
                            "invocation_type": "slash",
                            "invocation_text": invocation,
                            "source": "user_message",
                        }
                    )
                    seen.add(key)

            dollar_match = re.match(r"^\$([a-z][a-z0-9_\-]*)(?:\s|$)", stripped)
            if dollar_match is not None:
                skill_name = dollar_match.group(1)
                dollar_invocation = f"${skill_name}"
                key = f"dollar|{dollar_invocation}"
                if key not in seen:
                    out.append(
                        {
                            "invocation_type": "dollar",
                            "invocation_text": dollar_invocation,
                            "source": "user_message",
                        }
                    )
                    seen.add(key)

    return out


def _extract_chat_annotations(payload: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    payload_type = _as_str(payload.get("type"))
    payload_node = payload.get("payload")
    if payload_type != "response_item" or not isinstance(payload_node, dict):
        return out
    if _as_str(payload_node.get("type")) != "function_call":
        return out

    function_name = (_as_str(payload_node.get("name")) or "").strip().lower()
    if function_name not in {"co.note", "chat_ops.note", "note"}:
        return out

    arguments_node = payload_node.get("arguments")
    parsed_args: dict[str, Any] | None = None
    if isinstance(arguments_node, dict):
        parsed_args = arguments_node
    elif isinstance(arguments_node, str):
        loaded = _safe_json_load(arguments_node)
        if isinstance(loaded, dict):
            parsed_args = loaded

    if not isinstance(parsed_args, dict):
        return out

    annotation_type = (_as_str(parsed_args.get("type")) or "").strip().lower()
    annotation_value = (_as_str(parsed_args.get("message")) or "").strip()
    if annotation_type not in _ANNOTATION_KEYS or not annotation_value:
        return out

    key = f"tool_call|{annotation_type}|{annotation_value}"
    if key in seen:
        return out
    seen.add(key)
    out.append(
        {
            "annotation_type": annotation_type,
            "annotation_value": annotation_value,
            "source": "tool_call",
            "raw_text": json.dumps(parsed_args, ensure_ascii=True, sort_keys=True),
        }
    )

    return out


def _classify_turn_category(turn_state: dict[str, Any]) -> str:
    tools = [_as_str(name) or "" for name in turn_state.get("tool_names", [])]
    tool_names = [name.strip().lower() for name in tools if name.strip()]
    invocations = turn_state.get("invocation_items", [])
    user_messages = [
        _as_str(message) or "" for message in turn_state.get("user_messages", [])
    ]
    user_message = " ".join(msg.strip() for msg in user_messages if msg.strip())
    user_message_lower = user_message.lower()
    command_text = " ; ".join(
        (_as_str(cmd.get("raw_command")) or "")
        for cmd in turn_state.get("commands", [])
        if isinstance(cmd, dict)
    ).lower()
    invocation_text = " ; ".join(
        (_as_str(inv.get("invocation_text")) or "")
        for inv in invocations
        if isinstance(inv, dict)
    ).lower()
    tool_text = " ; ".join(tool_names)

    has_edits = bool(turn_state.get("writes"))
    has_reads = bool(turn_state.get("reads"))
    has_bash = bool(turn_state.get("commands"))
    has_skill_tool = "skill" in tool_names or any(
        isinstance(inv, dict)
        and _as_str(inv.get("invocation_type")) == "skill"
        for inv in invocations
    )
    has_search_tools = any(
        ("search" in name) or ("web_search" in name) for name in tool_names
    )
    has_mcp_tools = any(name.startswith("mcp__") for name in tool_names)
    has_plan_mode = any(
        name
        in {
            "enterplanmode",
            "taskcreate",
            "taskupdate",
            "taskget",
            "tasklist",
            "taskoutput",
            "taskstop",
            "todowrite",
            "update_plan",
            "request_user_input",
        }
        for name in tool_names
    )
    has_agent_spawn = ("spawn_agent" in tool_names) or any(
        isinstance(inv, dict)
        and _as_str(inv.get("invocation_type")) == "agent"
        for inv in invocations
    )

    synthetic_tokens: list[str] = []
    if has_edits:
        synthetic_tokens.append("HAS_EDIT")
    if has_reads:
        synthetic_tokens.append("HAS_READ")
    if has_bash:
        synthetic_tokens.append("HAS_BASH")
    if has_search_tools:
        synthetic_tokens.append("HAS_SEARCH_TOOL")
    if has_mcp_tools:
        synthetic_tokens.append("HAS_MCP_TOOL")
    if has_plan_mode:
        synthetic_tokens.append("HAS_PLAN_MODE")
    if has_agent_spawn:
        synthetic_tokens.append("HAS_AGENT_SPAWN")
    if has_skill_tool:
        synthetic_tokens.append("HAS_SKILL_TOOL")
    if not (
        has_edits
        or has_reads
        or has_bash
        or tool_names
        or invocations
        or turn_state.get("commands")
    ):
        synthetic_tokens.append("TEXT_ONLY")

    category_haystack = " ".join(
        part
        for part in (
            user_message_lower,
            command_text,
            invocation_text,
            tool_text,
            " ".join(synthetic_tokens),
        )
        if part
    )

    for _rule_name, category_name, pattern in _CATEGORY_RULES:
        if pattern.search(category_haystack):
            return category_name
    return _DEFAULT_CATEGORY


def _extract_signals(
    payload: dict[str, Any],
    *,
    source_file: str,
    line_no: int,
    event_id: str,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    text = json.dumps(payload, ensure_ascii=True)
    compact = _compact_text(text)
    seen_keys: set[str] = set()

    for _rule_name, signal_type, pattern in _SIGNAL_RULES:
        if not pattern.search(text):
            continue
        key = f"{signal_type}|{compact}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        signals.append(
            {
                "signal_type": signal_type,
                "content": compact,
                "evidence": {
                    "event_id": event_id,
                    "source_file": source_file,
                    "line_no": line_no,
                },
            }
        )
    return signals


def _extract_session_meta(payload: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    top_type = _as_str(payload.get("type"))
    nested = payload.get("payload")
    if top_type == "session_meta":
        if isinstance(nested, dict):
            candidates.append(nested)
        candidates.append(payload)
    if isinstance(nested, dict) and _as_str(nested.get("type")) == "session_meta":
        inner = nested.get("payload")
        if isinstance(inner, dict):
            candidates.append(inner)
        candidates.append(nested)

    for node in candidates:
        return {
            "provider_thread_id": _as_str(node.get("provider_thread_id"))
            or _as_str(node.get("thread_id"))
            or _as_str(node.get("session_id"))
            or _as_str(node.get("id")),
            "forked_from_thread_id": _as_str(node.get("forked_from_thread_id")),
            "source": _as_str(node.get("source")),
            "originator": _as_str(node.get("originator")),
            "cli_version": _as_str(node.get("cli_version")),
            "cwd": _as_str(node.get("cwd")),
            "agent_nickname": _as_str(node.get("agent_nickname")),
            "agent_role": _as_str(node.get("agent_role")),
            "agent_path": _as_str(node.get("agent_path")),
            "model_provider": _as_str(node.get("model_provider")),
            "memory_mode": _as_str(node.get("memory_mode")),
            "git_sha": _as_str(node.get("git_sha")),
            "git_branch": _as_str(node.get("git_branch")),
            "git_origin_url": _as_str(node.get("git_origin_url")),
        }
    return None


def _extract_turn_context(payload: dict[str, Any]) -> dict[str, Any] | None:
    top_type = _as_str(payload.get("type"))
    nested = payload.get("payload")
    node: dict[str, Any] | None = None
    if top_type == "turn_context":
        node = nested if isinstance(nested, dict) else payload
    elif isinstance(nested, dict) and _as_str(nested.get("type")) == "turn_context":
        inner = nested.get("payload")
        node = inner if isinstance(inner, dict) else nested

    if node is None:
        return None

    permission_profile = node.get("permission_profile")
    collaboration_mode = node.get("collaboration_mode")
    sandbox_policy = node.get("sandbox_policy")
    return {
        "provider_turn_id": _str_or_none(
            node.get("turn_id"),
            node.get("provider_turn_id"),
            node.get("id"),
        ),
        "trace_id": _as_str(node.get("trace_id")),
        "cwd": _as_str(node.get("cwd")),
        "timezone": _as_str(node.get("timezone")),
        "current_date": _as_str(node.get("current_date")),
        "model": _as_str(node.get("model")),
        "approval_policy": _as_str(node.get("approval_policy")),
        "sandbox_policy": _as_str(sandbox_policy) or _json_or_none(sandbox_policy),
        "permission_profile_json": _json_or_none(permission_profile),
        "collaboration_mode": _as_str(collaboration_mode) or _json_or_none(collaboration_mode),
        "realtime_active": _as_sqlite_bool(node.get("realtime_active")),
        "reasoning_effort": _str_or_none(node.get("reasoning_effort"), node.get("effort")),
    }


def _extract_content_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    nested = payload.get("payload")
    if not isinstance(nested, dict):
        return out
    if _as_str(payload.get("type")) != "response_item":
        return out
    if _as_str(nested.get("type")) != "message":
        return out

    role = _as_str(nested.get("role"))
    content = nested.get("content")
    if not isinstance(content, list):
        return out

    for idx, item in enumerate(content):
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "block_index": idx,
                "block_type": _as_str(item.get("type")) or "unknown",
                "role": role,
                "tool_use_id": _as_str(item.get("tool_use_id")) or _as_str(item.get("id")),
                "tool_name": _as_str(item.get("name")) or _as_str(item.get("tool_name")),
                "call_id": _as_str(item.get("call_id")),
                "is_error": _as_sqlite_bool(item.get("is_error")),
                "text_content": _as_str(item.get("text")) or _as_str(item.get("content")),
                "block_json": json.dumps(item, ensure_ascii=True, sort_keys=True),
            }
        )

    return out


def _classify_event_scope(payload: dict[str, Any]) -> str:
    top_type = (_as_str(payload.get("type")) or "").lower()
    nested = payload.get("payload")
    nested_type = ""
    if isinstance(nested, dict):
        nested_type = (_as_str(nested.get("type")) or "").lower()

    if "ephemeral" in top_type or "ephemeral" in nested_type:
        return "ephemeral"
    if top_type in {"session_meta", "turn_context"} or nested_type in {
        "session_meta",
        "turn_context",
        "thread_name_updated",
        "thread_name_update",
    }:
        return "metadata"
    if "queue" in top_type or "queue" in nested_type:
        return "queue"
    if top_type in {"system", "error", "warning", "shutdown", "lifecycle"}:
        return "system"
    if nested_type in {"error", "warning", "turn_started", "turn_completed", "turn_failed"}:
        return "system"
    return "transcript"


def _extract_event_source_kind(payload: dict[str, Any]) -> str:
    valid = {"limited", "extended", "always", "unknown"}

    def _normalize(value: Any) -> str | None:
        candidate = _as_str(value)
        if not candidate:
            return None
        normalized = candidate.strip().lower()
        if normalized in valid:
            return normalized
        return None

    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        for key in (
            "event_source_kind",
            "source_kind",
            "eventSourceKind",
            "sourceKind",
            "source",
            "kind",
            "mode",
        ):
            normalized = _normalize(node.get(key))
            if normalized:
                return normalized

        for key in ("event_source", "eventSource"):
            src_node = node.get(key)
            if not isinstance(src_node, dict):
                continue
            for source_key in ("kind", "source_kind", "event_source_kind", "mode", "type"):
                normalized = _normalize(src_node.get(source_key))
                if normalized:
                    return normalized

    return "unknown"


def _extract_provider_session_id(payload: dict[str, Any]) -> str | None:
    for key in (
        "provider_session_id",
        "thread_id",
        "threadId",
        "session_id",
        "sessionId",
    ):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in (
            "provider_session_id",
            "thread_id",
            "threadId",
            "session_id",
            "sessionId",
        ):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        if _as_str(payload.get("type")) == "session_meta":
            val = nested.get("id")
            if isinstance(val, str) and val.strip():
                return val.strip()
        if _as_str(nested.get("type")) == "session_meta":
            inner = nested.get("payload")
            if isinstance(inner, dict):
                for key in ("id", "provider_session_id", "thread_id", "session_id"):
                    val = inner.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()

    return None


def _extract_session_id(payload: dict[str, Any]) -> str | None:
    for key in ("session_id", "sessionId"):
        sid = payload.get(key)
        if isinstance(sid, str) and sid.strip():
            return sid.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("session_id", "sessionId"):
            sid = nested.get(key)
            if isinstance(sid, str) and sid.strip():
                return sid.strip()
    return None


def _extract_turn_context_id(payload: dict[str, Any]) -> str | None:
    top_type = _as_str(payload.get("type"))
    nested = payload.get("payload")
    if top_type == "turn_context":
        for key in ("turn_id", "provider_turn_id", "id"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        if isinstance(nested, dict):
            for key in ("turn_id", "provider_turn_id", "id"):
                val = nested.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

    if isinstance(nested, dict) and _as_str(nested.get("type")) == "turn_context":
        for key in ("turn_id", "provider_turn_id", "id"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    return None


def _extract_turn_id(payload: dict[str, Any]) -> str | None:
    for key in ("turn_id", "turnId"):
        turn = payload.get(key)
        if isinstance(turn, str) and turn.strip():
            return turn.strip()
        if isinstance(turn, int):
            return str(turn)
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("turn_id", "turnId"):
            turn = nested.get(key)
            if isinstance(turn, str) and turn.strip():
                return turn.strip()
            if isinstance(turn, int):
                return str(turn)
    return None


def _extract_provider_event_uuid(payload: dict[str, Any]) -> str | None:
    for key in ("provider_event_uuid", "event_uuid", "event_id", "id"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("provider_event_uuid", "event_uuid", "event_id", "id"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _extract_provider_parent_event_uuid(payload: dict[str, Any]) -> str | None:
    for key in ("provider_parent_event_uuid", "parent_event_uuid", "parent_event_id", "parent_id"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("provider_parent_event_uuid", "parent_event_uuid", "parent_event_id", "parent_id"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _extract_provider_logical_parent_event_uuid(payload: dict[str, Any]) -> str | None:
    for key in ("provider_logical_parent_event_uuid", "logical_parent_event_uuid", "logical_parent_event_id"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("provider_logical_parent_event_uuid", "logical_parent_event_uuid", "logical_parent_event_id"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _extract_rollout_item_type(payload: dict[str, Any]) -> str | None:
    top = _as_str(payload.get("type"))
    if top:
        return top
    return _extract_payload_type(payload)


def _extract_payload_type(payload: dict[str, Any]) -> str | None:
    nested = payload.get("payload")
    if isinstance(nested, dict):
        val = nested.get("type")
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _extract_is_sidechain(payload: dict[str, Any]) -> bool | None:
    for key in ("is_sidechain", "sidechain", "isSidechain"):
        val = payload.get(key)
        if isinstance(val, bool):
            return val
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("is_sidechain", "sidechain", "isSidechain"):
            val = nested.get(key)
            if isinstance(val, bool):
                return val
    return None


def _extract_agent_id(payload: dict[str, Any]) -> str | None:
    for key in ("agent_id", "agent"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("agent_id", "agent"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _extract_request_id(payload: dict[str, Any]) -> str | None:
    for key in ("request_id", "requestId"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("request_id", "requestId"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _extract_prompt_id(payload: dict[str, Any]) -> str | None:
    for key in ("prompt_id", "promptId"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("prompt_id", "promptId"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _extract_trace_id(payload: dict[str, Any]) -> str | None:
    for key in ("trace_id", "traceId"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("trace_id", "traceId"):
            val = nested.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def _estimate_edit_churn(node: dict[str, Any]) -> int:
    text = json.dumps(node, ensure_ascii=True)
    adds = len(re.findall(r"(^|\\n)\+[^+].*", text))
    dels = len(re.findall(r"(^|\\n)-[^-].*", text))
    explicit = _as_int(node.get("edit_churn"))
    if explicit is not None:
        return max(0, explicit)
    estimate = adds + dels
    return estimate if estimate > 0 else 1


def _iter_nodes(value: Any) -> list[Any]:
    items: list[Any] = []

    def walk(node: Any) -> None:
        items.append(node)
        if isinstance(node, dict):
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return items


def _extract_event_ts(payload: dict[str, Any]) -> str | None:
    for key in ("timestamp", "ts", "time", "created_at"):
        if key not in payload:
            continue
        val = payload.get(key)
        if isinstance(val, str):
            return _normalize_ts_text(val)
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(float(val), tz=UTC).isoformat()
    return None


def _extract_timestamp_from_line(line: str) -> datetime | None:
    payload = _safe_json_load(line)
    if not isinstance(payload, dict):
        return None
    ts = _extract_event_ts(payload)
    if ts is None:
        return None
    return _parse_since(ts)


def _uuid_from_rollout_id(value: str | None) -> str | None:
    text = _as_str(value)
    if text is None:
        return None
    candidate = text[-36:]
    if _SESSION_UUID_RE.fullmatch(candidate):
        return candidate.lower()
    return None


def _extract_model(payload: dict[str, Any]) -> str | None:
    direct = _as_str(payload.get("model")) or _as_str(payload.get("model_name"))
    if direct:
        return direct.strip() or None

    nested = payload.get("payload")
    if isinstance(nested, dict):
        model = _as_str(nested.get("model")) or _as_str(nested.get("model_name"))
        if model:
            return model.strip() or None

        info = nested.get("info")
        if isinstance(info, dict):
            model = _as_str(info.get("model")) or _as_str(info.get("model_name"))
            if model:
                return model.strip() or None

        collaboration_mode = nested.get("collaboration_mode")
        if isinstance(collaboration_mode, dict):
            settings = collaboration_mode.get("settings")
            if isinstance(settings, dict):
                model = _as_str(settings.get("model"))
                if model:
                    return model.strip() or None
    return None


def _extract_project(payload: dict[str, Any]) -> str | None:
    cwd = _as_str(payload.get("cwd"))
    if cwd and cwd.strip():
        return cwd.strip()
    nested = payload.get("payload")
    if isinstance(nested, dict):
        cwd = _as_str(nested.get("cwd"))
        if cwd and cwd.strip():
            return cwd.strip()
    return None


def _extract_reasoning_level(payload: dict[str, Any]) -> str | None:
    direct = _as_str(payload.get("reasoning_effort")) or _as_str(payload.get("effort"))
    if direct and direct.strip():
        return direct.strip().lower()

    nested = payload.get("payload")
    if isinstance(nested, dict):
        effort = _as_str(nested.get("reasoning_effort")) or _as_str(
            nested.get("effort")
        )
        if effort and effort.strip():
            return effort.strip().lower()

        collaboration_mode = nested.get("collaboration_mode")
        if isinstance(collaboration_mode, dict):
            settings = collaboration_mode.get("settings")
            if isinstance(settings, dict):
                effort = _as_str(settings.get("reasoning_effort"))
                if effort and effort.strip():
                    return effort.strip().lower()

    return None


def _format_model_label(model: str | None, reasoning: str | None) -> str | None:
    if not model:
        return None
    model_text = model.strip()
    if not model_text:
        return None
    if not reasoning:
        return model_text
    level = reasoning.strip().lower()
    if not level:
        return model_text
    return f"{model_text} [{level}]"


def _extract_user_message_texts(payload: dict[str, Any]) -> list[str]:
    return _extract_message_texts(payload, roles={"user"})


def _extract_message_texts(
    payload: dict[str, Any], *, roles: set[str] | None = None
) -> list[str]:
    payload_node = payload.get("payload")
    if not isinstance(payload_node, dict):
        return []

    event_type = _as_str(payload.get("type"))
    if event_type == "response_item":
        if _as_str(payload_node.get("type")) != "message":
            return []
        role = (_as_str(payload_node.get("role")) or "").strip().lower()
        if roles is not None and role not in roles:
            return []
        return _extract_message_content_texts(payload_node.get("content"))

    if event_type == "event_msg":
        nested_type = (_as_str(payload_node.get("type")) or "").strip().lower()
        if nested_type == "user_message":
            if roles is not None and "user" not in roles:
                return []
        elif nested_type == "agent_message":
            if roles is not None and "assistant" not in roles:
                return []
        else:
            return []

        direct_message = _as_str(payload_node.get("message"))
        if direct_message and direct_message.strip():
            return [direct_message]
        return _extract_message_content_texts(payload_node.get("content"))

    return []


def _extract_message_content_texts(content: Any) -> list[str]:
    if isinstance(content, str):
        stripped = content.strip()
        return [content] if stripped else []
    if not isinstance(content, list):
        return []

    out: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = _as_str(item.get("text")) or _as_str(item.get("content"))
        if text and text.strip():
            out.append(text)
    return out


def _extract_session_preview(payload: dict[str, Any]) -> str | None:
    fallback_preview: str | None = None
    for text in _extract_user_message_texts(payload):
        stripped = _strip_user_message_prefix(text)
        if not stripped:
            continue
        if fallback_preview is None:
            fallback_preview = stripped
        if not _looks_like_non_preview_message(stripped):
            return stripped

    def _final_fallback() -> str | None:
        if fallback_preview and not _looks_like_non_preview_message(fallback_preview):
            return fallback_preview
        return None

    payload_node = payload.get("payload")
    if not isinstance(payload_node, dict):
        return _final_fallback()
    if _as_str(payload.get("type")) != "event_msg":
        return _final_fallback()
    if _as_str(payload_node.get("type")) != "user_message":
        return _final_fallback()
    message = _as_str(payload_node.get("message"))
    if not message:
        return _final_fallback()
    stripped = _strip_user_message_prefix(message)
    if stripped and not _looks_like_non_preview_message(stripped):
        return stripped
    return _final_fallback()


def _strip_user_message_prefix(text: str) -> str:
    idx = text.find(_USER_MESSAGE_BEGIN)
    if idx >= 0:
        return text[idx + len(_USER_MESSAGE_BEGIN) :].strip()
    return text.strip()


def _looks_like_non_preview_message(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    if stripped.startswith("# AGENTS.md instructions for "):
        return True
    if stripped.startswith("<environment_context>"):
        return True
    return "agents.md instructions for " in lowered and "<instructions>" in lowered


def _extract_thread_name_update(payload: dict[str, Any]) -> str | None:
    payload_node = payload.get("payload")
    if not isinstance(payload_node, dict):
        return None
    if _as_str(payload.get("type")) != "event_msg":
        return None
    payload_type = _as_str(payload_node.get("type"))
    if payload_type not in {"thread_name_updated", "thread_name_update"}:
        return None

    for key in ("thread_name", "name", "title"):
        candidate = _as_str(payload_node.get(key))
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def _extract_tool_name(node: dict[str, Any]) -> str | None:
    if _as_str(node.get("type")) == "function_call":
        function_name = _as_str(node.get("name"))
        if function_name and function_name.strip():
            return function_name.strip()

    direct = _as_str(node.get("tool")) or _as_str(node.get("tool_name"))
    if direct and direct.strip():
        return direct.strip()
    return None


def _extract_skill_name(node: dict[str, Any]) -> str | None:
    tool_name = _extract_tool_name(node)
    if not isinstance(tool_name, str) or tool_name.strip().lower() != "skill":
        return None

    for candidate in (
        _extract_skill_name_from_input(node.get("input")),
        _extract_skill_name_from_input(node.get("arguments")),
        _extract_skill_name_from_input(node.get("payload")),
    ):
        if candidate:
            return candidate
    return None


def _extract_skill_name_from_input(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        parsed = _safe_json_load(text)
        if isinstance(parsed, dict):
            return _extract_skill_name_from_input(parsed)
        return None

    if not isinstance(value, dict):
        return None

    for key in ("skill", "name"):
        raw = _as_str(value.get(key))
        if not raw:
            continue
        cleaned = raw.strip()
        if cleaned.startswith("$"):
            cleaned = cleaned[1:].strip()
        if cleaned and cleaned.lower() != "skill":
            return cleaned
    return None


def _extract_exec_command_text(node: dict[str, Any]) -> str | None:
    command = node.get("command")
    if isinstance(command, str):
        value = command.strip()
        return value or None
    if isinstance(command, list):
        if len(command) >= 3 and isinstance(command[-1], str):
            value = command[-1].strip()
            return value or None
        parts = [part for part in command if isinstance(part, str) and part.strip()]
        if parts:
            return " ".join(parts)
    parsed = node.get("parsed_cmd")
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            cmd = _as_str(item.get("cmd"))
            if cmd and cmd.strip():
                return cmd.strip()
    return None


def _extract_duration_ms(duration_node: Any) -> float | None:
    if not isinstance(duration_node, dict):
        return None
    secs = _as_float(duration_node.get("secs")) or 0.0
    nanos = _as_float(duration_node.get("nanos")) or 0.0
    return (secs * 1000.0) + (nanos / 1_000_000.0)


def _mcp_result_is_error(result_node: Any) -> bool:
    if not isinstance(result_node, dict):
        return False
    if "Err" in result_node:
        return True
    ok = result_node.get("Ok")
    if isinstance(ok, dict):
        is_error = ok.get("isError")
        if isinstance(is_error, bool):
            return is_error
    return False


def _extract_mcp_result_text(result_node: Any) -> str | None:
    if not isinstance(result_node, dict):
        return None
    err = result_node.get("Err")
    if err is not None:
        return _extract_text_blob(err)
    ok = result_node.get("Ok")
    if isinstance(ok, dict):
        content = ok.get("content")
        if content is not None:
            text = _extract_text_blob(content)
            if text:
                return text
    return None


def _extract_text_blob(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            item_text = _extract_text_blob(item)
            if item_text:
                parts.append(item_text)
        if parts:
            return "\n".join(parts)
        return None
    if isinstance(value, dict):
        for key in ("text", "message", "content", "detail", "error"):
            text = _extract_text_blob(value.get(key))
            if text:
                return text
    return None


def _extract_event_type(payload: dict[str, Any]) -> str | None:
    for key in ("type", "event", "event_type", "kind"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None


def _build_event_id(
    *,
    provider: str,
    source_file: Path,
    line_no: int,
    canonical_payload: str,
) -> str:
    digest = hashlib.sha256(
        f"{provider}|{source_file}|{line_no}|{canonical_payload}".encode()
    ).hexdigest()
    return digest


def _parse_command(raw: str) -> tuple[str | None, str | None, str | None]:
    try:
        parts = shlex.split(raw)
    except ValueError:
        return None, None, None

    if not parts:
        return None, None, None

    base = parts[0]
    subcommand = None
    for token in parts[1:]:
        if token.startswith("-"):
            continue
        subcommand = token
        break

    if base in {"git", "uv", "python", "pytest", "just", "npm", "node", "cargo", "go"}:
        family = base
    elif base in {"cat", "rg", "grep", "ls", "sed", "find"}:
        family = "shell"
    else:
        family = "other"

    return family, base, subcommand


def query_rows(
    conn: Any,
    *,
    sql: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    cur = conn.execute(sql, dict(params))
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({key: row[idx] for idx, key in enumerate(cols)})
    return out


def _safe_json_load(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _int_or_none(*values: Any) -> int | None:
    for value in values:
        parsed = _as_int(value)
        if parsed is not None:
            return parsed
    return None


def _str_or_none(*values: Any) -> str | None:
    for value in values:
        parsed = _as_str(value)
        if parsed and parsed.strip():
            return parsed.strip()
    return None


def _as_sqlite_bool(value: Any) -> int | None:
    if isinstance(value, bool):
        return 1 if value else 0
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return 1 if value else 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return 1
        if normalized in {"0", "false", "no", "n", "off"}:
            return 0
    return None


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except TypeError:
        return None


def _compact_text(value: str, limit: int = 280) -> str:
    collapsed = re.sub(r"\s+", " ", value).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def _parse_since(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None

    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _normalize_ts_text(value: str) -> str | None:
    dt = _parse_since(value)
    if dt is None:
        return None
    return dt.isoformat()


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


__all__ = [
    "IngestOptions",
    "IngestResult",
    "ingest",
    "rebuild_projections",
]
