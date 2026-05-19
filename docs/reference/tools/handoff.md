# Handoff

Codex worker delegation with file-backed result inspection.

## Highlights

- Submit one focused Codex worker task and keep working
- Poll compact summaries while full results are stored as Markdown files
- Read and search a local JSONL task/result index
- Bounded queue, wait, raw-log, dedupe, cleanup, and cancellation behavior

## Functions

| Function | Description |
|----------|-------------|
| `handoff.submit(task, ...)` | Submit one focused Codex worker task |
| `handoff.check(ids, ...)` | Check ready results and outstanding queue state |
| `handoff.read_index(status, ...)` | Read recent task/result index entries |
| `handoff.search_index(query, ...)` | Search the local task/result index |
| `handoff.cancel(ids)` | Request best-effort cancellation |
| `handoff.clear(include_logs)` | Clear in-memory state and optionally delete artifacts |

## Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task` | str | required | Single focused worker request |
| `context` | str | `""` | Extra context rendered into the worker prompt |
| `model` | str | config default | Codex model override |
| `reasoning_effort` | str | config default | Codex reasoning effort override |
| `timeout` | int | config default | Worker task timeout in seconds |
| `ids` | list[str] | `None` | Specific task ids for check or cancel |
| `wait` | bool | `False` | Whether `check()` waits for completions |
| `query` | str | required | Case-insensitive index search text |
| `include_logs` | bool | `False` | Delete result files, index, state, and raw logs during clear |

## Requires

- `codex` CLI installed and authenticated.
- Optional MCP access requires a root OneTool direct API. If unavailable, workers still run and `submit()` returns a warning.

## Configuration

### Required

- No secrets are required.
- The local `codex` CLI must be installed and authenticated.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.handoff.enabled` | bool | `true` | Enables the pack. |
| `tools.handoff.app_server.command` | str | `"codex app-server --listen stdio://"` | Codex app-server command. Must use stdio transport. |
| `tools.handoff.app_server.startup_timeout_seconds` | int | `10` | Startup timeout. Range: `1-120`. |
| `tools.handoff.app_server.ready_check_cache_seconds` | int | `30` | Readiness cache TTL. Range: `0-3600`. |
| `tools.handoff.defaults.model` | str | `"gpt-5.3-codex"` | Default worker model. |
| `tools.handoff.defaults.reasoning_effort` | str | `"low"` | Default worker reasoning effort. |
| `tools.handoff.defaults.timeout_seconds` | int | `60` | Default worker timeout. Range: `1-3600`. |
| `tools.handoff.defaults.worker_prompt` | str | bundled prompt | Worker prompt template with `{task}` and `{context}`. |
| `tools.handoff.limits.max_workers` | int | `1` | Worker pool size for picking up queued tasks. Range: `1-8`. |
| `tools.handoff.limits.max_queue_depth` | int | `10` | Outstanding queue depth. Range: `1-100`. |
| `tools.handoff.limits.max_check_wait_seconds` | int | `10` | Maximum blocking check wait. Range: `0-120`. |
| `tools.handoff.limits.max_raw_log_bytes` | int | `200000` | Per-task raw log buffer cap. Range: `0-10000000`. |
| `tools.handoff.limits.max_remaining_ids_returned` | int | `20` | Returned outstanding id cap. Range: `0-500`. |
| `tools.handoff.runtime.state_path` | str | `"runtime/handoff/state.json"` | State file under OneTool storage. |
| `tools.handoff.runtime.index_path` | str | `"runtime/handoff/index.jsonl"` | JSONL index path under OneTool storage. |
| `tools.handoff.runtime.result_dir` | str | `"runtime/handoff/results"` | Result Markdown directory. |
| `tools.handoff.runtime.raw_log_dir` | str | `"runtime/handoff/raw"` | Raw event log directory. |
| `tools.handoff.runtime.raw_log_enabled` | bool | `true` | Whether raw logs are retained. |
| `tools.handoff.runtime.raw_log_flush` | str | `"on_completion"` | Raw log flush mode; only `on_completion` is supported. |
| `tools.handoff.runtime.dedupe_window_seconds` | int | `30` | Duplicate outstanding suppression window. Range: `0-3600`. |
| `tools.handoff.cleanup.enabled` | bool | `true` | Run age-based cleanup on runtime initialization. |
| `tools.handoff.cleanup.max_age_days` | int | `14` | Terminal artifact retention age. Range: `1-3650`. |

```yaml
tools:
  handoff:
    enabled: true
    app_server:
      command: "codex app-server --listen stdio://"
      startup_timeout_seconds: 10
      ready_check_cache_seconds: 30
    defaults:
      model: "gpt-5.3-codex"
      reasoning_effort: "low"
      timeout_seconds: 60
    limits:
      max_workers: 1
      max_queue_depth: 10
      max_check_wait_seconds: 10
    cleanup:
      enabled: true
      max_age_days: 14
```

### Defaults

- If `tools.handoff` is omitted, handoff uses Codex app-server over stdio, best-effort child OneTool MCP access for `run`, one worker, a 10-item queue, and 14-day cleanup.
- Runtime files are stored under OneTool-owned paths such as `runtime/handoff/index.jsonl` and `runtime/handoff/results/`.
- `check()` returns summaries and paths by default; full worker output lives in the result Markdown file.
- `ot.reload()` resets handoff's in-memory runtime and runner state. File-backed index and result artifacts remain available for inspection.

## Examples

```python
# Submit one focused worker task
handoff.submit(task="Inspect the auth flow and report likely bug locations")

# Submit with extra context and a shorter timeout
handoff.submit(
    task="Review the config loader for strict validation gaps",
    context="Focus on src/ot/config and tests/unit/core.",
    timeout=45,
)

# Poll for completed summaries and file paths
handoff.check(wait=True, timeout=5)

# Inspect recent completed work
handoff.read_index(status="completed", limit=10)

# Search past handoff results locally
handoff.search_index(query="auth", status="completed")

# Cancel outstanding work or clear artifacts
handoff.cancel()
handoff.clear(include_logs=True)
```

## Notes

- Cancellation is best-effort and may return `cancel_requested` or `cancel_unknown`.
- Restart recovery marks prior non-terminal tasks as `abandoned`; it does not resume Codex turns.
- Live Codex app-server integration depends on the local Codex CLI and remains a manual smoke validation target; CI uses fake app-server and fake-runner tests.
