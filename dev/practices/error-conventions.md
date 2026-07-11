# Pack Error Conventions

How tool-pack functions report failures to callers (agents and scripts).

## The convention

**New packs and new tools return a structured error dict:**

```python
{"ok": False, "error": "<what failed and how to fix it>", "status": "<machine_slug>"}
```

- `error` — human/agent-readable message. Include the failing input and a next step.
- `status` — short machine-checkable slug (e.g. `"file_not_found"`, `"decrypt_failed"`).
- Success payloads from the same tool should be dicts too, so callers branch on
  `result.get("error")` / `result.get("ok")` rather than `isinstance` checks.

This is the localhist/arch style. It was chosen over the alternatives because
programmatic callers (the `run` executor, batch envelopes, other packs) can
branch on it without string sniffing, and it survives serialization.

## Legacy styles (do not extend)

The repo still contains two older styles. Keep them working where they exist,
but migrate a function to the structured dict when you materially rework it —
do not add new functions in these styles:

1. **`"Error: ..."` strings** (ripgrep, db, excel, file): the caller must
   prefix-match on the return value. Tolerable for tools whose success value is
   also a plain string; wrong for anything returning data.
2. **Raises** (console, parts of ctx): exceptions escape the tool boundary and
   surface as tracebacks in agent output. Only acceptable for programmer errors
   (bad argument *types*), never for expected runtime failures (missing file,
   network error, bad input value).

Never mix styles within one module. If you touch a module that mixes them
(e.g. string + dict + silent `[]`), unify on the dict as part of the change.

## Rules of thumb

- Expected failure (missing file, no match, API error) → structured dict, never raise.
- Include the offending value in the message: `f"Sheet '{name}' not found"`.
- Log the failure on the active `LogSpan` (`s.add(error=...)`) with a slug that
  matches `status`.
- Batch tools report per-item failures inside the envelope; the call itself
  still succeeds.
- Don't return bare sentinels (`[]`, `None`, `False`) for failures — silence is
  indistinguishable from an empty result.
