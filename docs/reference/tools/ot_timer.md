# OT Timer

Named stopwatch timers for performance measurement across tool calls.

Short alias: `tmr`

## Highlights

- Persistent timers across multiple tool calls
- Lap timing support (`elapsed()` keeps timer running)
- Human-readable duration formatting (ms, seconds, minutes)
- Store multiple timing results for comparison

## Functions

| Function | Description |
|----------|-------------|
| `ot_timer.start(name)` | Start or restart a named timer |
| `ot_timer.elapsed(name, store_as)` | Get elapsed time (lap behavior) |
| `ot_timer.stop(name, store_as)` | Stop a timer and optionally store its final result |
| `ot_timer.list()` | Show all stored results and active timers |
| `ot_timer.clear(results)` | Clear running timers; optionally clear stored results |

## Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | `"_default"` | Timer name for identifying multiple timers |
| `store_as` | str | `None` | Optional key to store elapsed result for later retrieval |
| `results` | bool | `False` | If True, `clear()` also removes stored results |

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `core`.

No additional runtime requirements are declared.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Configuration

### Required

- No required `tools.ot_timer` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.ot_timer`.

### Defaults

- OneTool uses the built-in defaults for timer names, storage, and formatting.

## Examples

### Basic timing

```python
ot_timer.start(name="api_call")
# ... make API call ...
ot_timer.elapsed(name="api_call")
# {name: "api_call", elapsed_seconds: 1.234, elapsed_formatted: "1.234s", started_at: "..."}
```

### Lap timing

```python
ot_timer.start(name="workflow")
ot_timer.elapsed(name="workflow", store_as="step1")
# ... more work ...
ot_timer.elapsed(name="workflow", store_as="step2")
ot_timer.stop(name="workflow", store_as="total")
ot_timer.list()  # shows stored results + active timers
```

## Notes

- Timers persist across tool calls (useful for multi-step workflows)
- Uses `perf_counter()` for accurate elapsed time
- `elapsed()` keeps timer running (lap behavior)
- `stop()` returns the final elapsed time and removes the active timer
- `clear()` removes timers but preserves stored results by default
- Results stored via `store_as` remain until session ends
