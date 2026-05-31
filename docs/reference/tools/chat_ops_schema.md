# Chat Ops Schema

Schema reference for the `chat_ops` (`co`) telemetry database.

Default DB path: `.onetool/chat-ops/chat-ops.db`

## Core Contract (v3)

- Backbone: `sessions -> turns -> events`
- Every `events` row references both `session_id` and `turn_id`
- Sparse event detail is stored in `event_*` composition tables
- Report-facing aggregates are materialized in `mv_turn_metrics` and `mv_session_metrics`
- Rollout is clean-break: no migration or legacy compatibility layer

## Table Groups

### Ingest tracking

- `ingest_state`: per-source file offsets/versions for incremental ingest
- `ingest_runs`: run-level counters (`scanned`, `inserted`, `duplicates`, `skipped`, `errors`)

### Backbone tables

- `sessions`
  - Canonical key: `session_id`
  - Provider identity passthrough: `provider_session_id`
  - Session metadata: `project`, `session_name`, `first_user_message`, timestamps
- `turns`
  - Canonical key: `turn_id`
  - Parent: `session_id`
  - Turn source: `turn_id_source` (`turn_context`, `event_payload`, `ingest_synthetic`)
- `events`
  - Canonical key: `event_id`
  - Parents: `session_id`, `turn_id`
  - Envelope metadata: `event_type`, `payload_type`, `rollout_item_type`, `event_scope`, `event_source_kind`
  - Full raw payload: `payload_json`

### Composition tables (`event_*`)

- `event_usage`: token and rate-limit details from usage/token_count payloads
- `event_commands`: shell/command execution rows (`raw_command`, `status`, `duration_ms`, outputs), including synthesized shell-wrapper rows when command-end events are missing
- `event_file_ops`: read/write file operation rows with churn estimate
- `event_invocations`: intent-layer invocation rows (`slash`, `dollar`)
- `event_tool_calls`: canonical executed non-shell tool-call rows (one row per logical `call_id`/`tool_use_id`, with start metadata + terminal outcome, plus canonical total `duration_ms`)
- `event_patch_ops`: patch apply outcomes and patch metadata
- `event_signals`: extracted signal rows with evidence JSON
- `event_annotations`: explicit annotation rows from note tool calls
- `event_session_meta`: extracted session metadata (originator, cli_version, cwd, git fields)
- `event_turn_context`: extracted turn context (model, approval, sandbox, collaboration, effort)
- `event_content_blocks`: normalized assistant/user content blocks
- `event_edges`: parent/logical-parent/tool-result relationships between events

### Projection tables (`mv_*`)

- `mv_turn_metrics`: per-turn aggregates (commands, file ops, invocations, logical tool calls, tokens)
- `mv_session_metrics`: per-session aggregates (turn counts, command/tool counts, tokens)

## Key Guarantees

- `sessions.session_id` is canonical; upstream thread/session identity is preserved in `sessions.provider_session_id`
- `events.event_scope` is constrained to: `transcript`, `metadata`, `queue`, `system`, `ephemeral`
- `events.event_source_kind` is constrained to: `limited`, `extended`, `always`, `unknown`
- Tool-call correlation links `assistant_event_id` and `result_event_id` by `call_id`/`tool_use_id`
- `event_edges` enforces unique `(from_event_id, to_event_id, edge_type)` links
- Usage/rate-limit rows are sparse: `event_usage` exists only when usage payload data is present

## Reporting Surface

- Canonical entrypoint: `chat_ops.report_excel(...)` / `co.report_excel(...)`
- Report queries read v3 `event_*` and `mv_*` tables
- Legacy report entrypoints are intentionally unsupported
