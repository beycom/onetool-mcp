# Chat Ops

Chat telemetry ingest, annotation capture, and structured reporting via the `chat_ops` (`co`) pack.

## Highlights

- Ingests provider rollout events into a local SQLite telemetry database
- Uses pluggable provider parsers configured in `onetool.yaml`
- Captures structured annotations with `chat_ops.note(...)` (`co.note(...)`)
- Exports raw report tabs to Excel with `chat_ops.report_excel(...)` (`co.report_excel(...)`)
- Runs ingest/report_excel synchronously and returns final result payloads

## Functions

| Function | Description |
|----------|-------------|
| `chat_ops.ingest(...)` (`co.ingest(...)`) | Ingest configured provider logs and return final counters |
| `chat_ops.report_excel(...)` (`co.report_excel(...)`) | Generate Excel report (`.xlsx`) with raw tabs only |
| `chat_ops.report_summary(...)` (`co.report_summary(...)`) | Generate YAML session summary report with deterministic evidence and coaching |
| `chat_ops.report_llm(...)` (`co.report_llm(...)`) | Generate YAML narrative report from structured summary payload |
| `chat_ops.note(type, message, ...)` (`co.note(...)`) | Persist annotation rows (`note`, `title`, `summary`) |
| `chat_ops.rebuild(...)` (`co.rebuild(...)`) | Rebuild derived projection tables from raw events |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `report` | list[str] | Optional raw mode list for `report_excel`: `commands`, `invocations`, `files`, `signals`, `raw`, `sessions`, `annotations`, `usage`, `turns` |
| `output_dir` | str | Optional Excel report output directory. Defaults to `tools.chat_ops.reporting.output_dir`. |
| `output_name` | str | Optional report output filename. `.xlsx` for `report_excel`; `.yaml/.yml` for summary/llm reports (extension auto-added when omitted). |
| `projects` | str \| list[str] | Optional project filter list for `report_excel` (comma-separated string or list). |
| `session_ids` | str \| list[str] | Optional session_id filter list for `report_excel`. |
| `models` | str \| list[str] | Optional model filter list for `report_excel`. |
| `start` / `end` | str | Optional ISO-8601 session date window for `report_excel`. |
| `limit` | int | Optional per-tab cap for `report_excel`. If omitted, exports all rows in each raw tab. |
| `type` | str | Annotation type: `note`, `title`, `summary` |
| `message` | str | Annotation value text (non-empty) |

## Requires

- None — no secrets required.
- `openpyxl` for Excel report generation.

## Configuration

### Required

None — chat_ops uses built-in defaults when `tools.chat_ops` is omitted.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.chat_ops.storage.db` | str | `chat-ops/chat-ops.db` | SQLite database path relative to `.onetool/` unless absolute. |
| `tools.chat_ops.providers` | map | `{codex: ...}` | Provider parser settings and roots. |
| `tools.chat_ops.providers.<name>.provider_dir` | str | `${HOME}/.codex/sessions` | Provider session directory (env vars expanded). |
| `tools.chat_ops.providers.<name>.parser_file` | str | `builtin:codex_parser` | Python parser module file or builtin parser alias. |
| `tools.chat_ops.analysis.default_category` | str | `GENERAL` | Fallback category if no category rule matches. |
| `tools.chat_ops.analysis.categories` | list | built-in list | Ordered regex category rules (`first-match-wins`). |
| `tools.chat_ops.analysis.signals` | list | built-in list | Ordered regex signal rules. |
| `tools.chat_ops.reporting.output_dir` | str | `chat-ops/reports` | Default directory for saved report artifacts. |

```yaml
tools:
  chat_ops:
    storage:
      db: chat-ops/chat-ops.db
    providers:
      codex:
        provider_dir: "${HOME}/.codex/sessions"
        parser_file: "builtin:codex_parser"
      claude:
        provider_dir: "${HOME}/.claude/projects"
        parser_file: "./parsers/claude_parser.py"
    analysis:
      default_category: GENERAL
      categories: []
      signals: []
```

### Defaults

- If `tools.chat_ops.storage.db` is omitted, chat_ops stores data in `.onetool/chat-ops/chat-ops.db`.
- If `tools.chat_ops.providers` is omitted, chat_ops scans `${HOME}/.codex/sessions` with the built-in Codex parser.
- If `tools.chat_ops.analysis` is omitted, chat_ops uses built-in category and signal regex rules.
- If `tools.chat_ops.reporting.output_dir` is omitted, Excel reports are written under `chat-ops/reports` relative to the current project.

## Examples

```python
# Ingest all configured providers and rebuild projections before returning.
chat_ops.ingest(rebuild=True)

# Rescan Codex logs from scratch and return final ingest counters.
chat_ops.ingest(providers="codex", force_rescan=True, rebuild=True)

# Export all raw report tabs to an .xlsx workbook.
chat_ops.report_excel(output_name="chat-ops-full.xlsx")

# Export selected report tabs for one project.
chat_ops.report_excel(projects="onetool-mcp", report=["sessions", "commands", "usage"])

# Add a structured summary annotation.
chat_ops.note(type="summary", message="Finished synchronous chat-ops ingest refactor")
```

## Parser Customization

Each provider can point to a parser module via `parser_file`. This makes parser fixes and provider-specific enrichment immediate in your repo, without waiting for a package release.

Parser module contract:

```python
def parse_line(
    line: str,
    source_file: str | None = None,
    line_no: int | None = None,
) -> dict | None:
    ...
```

- Return `dict` for a parsed event payload.
- Return `None` to skip unknown/invalid lines.

Reference parser to copy and extend:

- `src/onetool/chat_ops/codex_parser.py`

## Schema

Default DB path: `.onetool/chat-ops/chat-ops.db`

For full schema details (table purposes, keys/indexes, and key columns), see:

- [Chat Ops Schema](chat_ops_schema.md)

## Direct Queries

```python
db_url = "sqlite:///.onetool/chat-ops/chat-ops.db"

db.query(sql="""
SELECT signal_type, COUNT(*) AS n
FROM event_signals
GROUP BY signal_type
ORDER BY n DESC
""", db_url=db_url)
```

## report_excel

`chat_ops.report_excel(...)` exports `.xlsx` only (no `json/csv/md/yaml` format switch for this tool).

- Output: one workbook with one tab per raw mode
- Raw modes: `commands`, `invocations`, `files`, `signals`, `raw`, `sessions`, `annotations`, `usage`, `turns`
- Default: exports all raw tabs when `report` is omitted
- Row count: exports full raw tabs by default; pass `limit` to cap rows per tab
- Canonical leading columns on each tab: `project`, `session_id`, `model`, `date` (session-level date)


## report_summary

`chat_ops.report_summary(...)` writes a YAML artifact (default `report-summary.yaml`) with:
- Chronological sessions (`started_at` ascending)
- Deterministic metrics/evidence per session
- Intent classification, health scoring, and coaching blocks
- Lightweight recognizability fields (`session_story`, `llm_session_summary`) with auditable sampling metadata
- Aggregate rollup across matching sessions

## report_llm

`chat_ops.report_llm(...)` consumes the same structured summary payload and writes a richer YAML narrative artifact (default `report-llm.yaml`).

If no LLM model is configured (`llm_model` argument or `tools.chat_ops.reporting.llm_model`), `report_llm(...)` fails with a clear actionable error.
