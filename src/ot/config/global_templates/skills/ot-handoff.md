---
name: ot-handoff
description: Optional OneTool handoff loop - delegate focused Codex worker tasks, track outstanding ids, poll compact results, and inspect file-backed handoff output
tags: [reference, delegation, codex]
---

# OneTool Handoff

`ot-handoff` is optional. Use it when the user explicitly wants OneTool/Codex
handoff delegation, parallel background investigation, or a workflow that starts
focused worker tasks and checks results later.

## Preconditions

- Handoff requires the `handoff` pack to be available in OneTool.
- The local Codex CLI must be installed and authenticated.
- Root OneTool MCP must expose the direct API; otherwise `handoff.submit(...)`
  returns a clear child runtime error.
- Workers may inspect or edit according to the delegated task. Keep ownership
  narrow and explicit when assigning edits.

## Delegation Boundary

Use handoff for bounded side work:

- independent codebase inspection;
- targeted risk or test-gap review;
- summarizing a specific file, feature, or subsystem;
- checking docs/spec alignment while the main agent keeps working.

Keep work local when the next step is blocked on the result, the task needs
tight interactive judgment, or the worker would need broad ownership of edits.

## Submit First

Submit one focused worker task with enough context to work independently:

```python
handoff.submit(
    task="Inspect src/ot/config for strict validation gaps and report file:line evidence",
    context="Focus on current implementation only. Return compact findings for the main agent.",
)
```

Record returned `id` values as the active outstanding queue. Track them in
conversation context. If resume/compaction durability matters, persist a small
local state file such as `tmp/handoff-active.json`.

Expected submit shape:

```python
{
  "id": "hf-abc123",
  "status": "submitted",
  "deduped": False,
  "remaining_count": 1,
  "remaining_ids": ["hf-abc123"],
  "queue_empty": False,
  "index_path": ".../runtime/handoff/index.jsonl",
}
```

If `deduped` is true, reuse the returned existing id instead of submitting the
same task again.

## Poll Only While Outstanding

Continue the user's current work after submitting. Check only while at least one
handoff id is outstanding:

```python
handoff.check(wait=False)
```

Use non-blocking checks by default. Use a short wait only when the user asks to
wait or a natural pause already exists:

```python
handoff.check(ids=["hf-abc123"], wait=True, timeout=5)
```

After every check:

1. Read `ready[]`.
2. Remove any returned ready ids from the outstanding list.
3. Keep polling only if `remaining_count > 0` or your tracked outstanding list is
   non-empty.
4. Stop polling when the outstanding list is empty or the user tells you to stop.

Do not repeatedly call `check()` with an empty outstanding list.

## Result Handling

`check()` returns compact summaries and paths. Treat the result file as the
authoritative worker output when details matter:

```python
result = handoff.check(wait=False)
# Then inspect result["ready"][0]["result_path"] with normal file tools if needed.
```

Prefer these inspection tools before asking the user:

```python
handoff.read_index(status="completed", limit=10)
handoff.search_index(query="auth", status="completed")
```

Index and result files live under OneTool-owned runtime storage, commonly:

```text
runtime/handoff/index.jsonl
runtime/handoff/results/<task-id>.md
runtime/handoff/raw/<task-id>.log
```

Use summaries for routing decisions. Open result files only when the worker's
evidence or full answer affects the final response or next edit.

## Recovery Loop

If a handoff call fails:

1. Inspect the tool once with `ot.tool_info(name='handoff.submit')` or the
   failing function name.
2. If the pack is missing, check `ot.tools(pattern='handoff')`.
3. If the child runtime is unavailable, continue locally and report that handoff
   needs root OneTool direct API enabled.
4. Retry once only after correcting a concrete issue. Do not guess through
   repeated submissions.

If the session resumes after compaction:

1. Restore outstanding ids from context or `tmp/handoff-active.json` if present.
2. Call `handoff.check(ids=[...], wait=False)` only when restored ids exist.
3. Use `handoff.read_index(limit=20)` or `handoff.search_index(...)` to recover
   completed work whose ids were lost.

## Cancellation And Cleanup

Cancel outstanding work when the user redirects, the result is no longer useful,
or the queue is blocking better work:

```python
handoff.cancel(ids=["hf-abc123"])
```

Clear transient state after a handoff experiment:

```python
handoff.clear()
```

Use `include_logs=True` only when the user explicitly wants handoff artifacts
deleted:

```python
handoff.clear(include_logs=True)
```

## Prompt Quality

Worker tasks should be narrow and evidence-oriented:

- include the exact files, subsystem, or question;
- request file paths, line references, commands, or URLs only when useful;
- state output shape when needed, such as "return findings only" or "return
  no-issue summary plus residual risk";
- avoid assigning broad implementation, planning, or review ownership to one
  worker.

Good:

```python
handoff.submit(
    task="Review src/ot/handoff/runtime.py cancellation behavior against docs/reference/tools/handoff.md",
    context="Return only mismatches with file:line evidence and likely user impact.",
)
```

Poor:

```python
handoff.submit(task="Review the whole repo and fix problems")
```

## Stop Rule

Stop handoff polling when either:

- the tracked outstanding id list is empty;
- the user explicitly says to stop checking;
- a handoff precondition fails and one recovery attempt does not fix it.
