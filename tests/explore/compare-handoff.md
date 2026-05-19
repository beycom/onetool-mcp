# Handoff Comparison

Compare a large repo-review task done by the main agent directly versus done through the
`$ot-handoff` skill with `gpt-5.3-codex` workers. Measure time, token usage where available,
and answer quality.

The goal is to quantify whether delegating focused repo-review work reduces main-agent
cost/time while preserving useful findings.

All repo inspection in both approaches must use the OneTool MCP `__run` tool. Do not use
plain shell/file-reading tools for the review work. The direct/main approach must call
OneTool through `__run`; handoff workers must also call OneTool through their available
`__run`/child OneTool access. Non-review bookkeeping, such as writing final test-output
files, may use normal filesystem tools.

The worker approach must follow the `$ot-handoff` skill workflow: submit focused handoff
tasks through OneTool, record returned ids, poll only while ids are outstanding, inspect
result files when detail matters, and stop polling when all tracked ids are complete.

---

## Task

Review consistency between tool implementation, tool reference docs, and developer guide
rules for three packs:

- `handoff`
- `ot_caveman`
- `ctx`

Use these source areas:

- `src/ottools/`
- `docs/reference/tools/`
- `dev/project/guides/tool-development.md`
- `dev/project/guides/index.md`
- `dev/agents/hints.md`

Review for:

- Missing or stale tool docs.
- Tool names or `__all__` mismatches between implementation and docs.
- Public tool functions that violate guide expectations: keyword-only args, type hints,
  Google-style docstrings, realistic examples, `LogSpan` usage where appropriate.
- Inconsistent naming, descriptions, examples, or pack/tool counts.
- Issues that would affect a user trying to call these tools through OneTool.

Do not edit product code. File issues only if the test runner determines a real code/docs
bug exists.

OneTool usage requirements:

- Start each approach with `ot.help()` through `__run`.
- Use `ot.tools(...)`, `ripgrep`/file tools exposed by OneTool, or other OneTool pack
  calls through `__run` for discovery and source inspection.
- Do not inspect the review target files with shell commands, direct filesystem reads,
  or editor reads outside `__run`.
- If a needed OneTool pack is unavailable, record the missing pack/tool as a test blocker
  instead of falling back to non-OneTool inspection.

---

## Expected Output Shape

Both approaches must produce the same structure:

```markdown
## Findings

| ID | Pack | Severity | File/Line | Finding | Evidence | Suggested fix |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |

## Non-Issues Checked

| Pack | Check | Evidence |
| :--- | :--- | :--- |

## Confidence

Short note on confidence, blind spots, and any files not inspected.
```

Severity values:

- `high`: likely broken user-facing behavior.
- `medium`: stale or misleading docs, discoverability issue, or guide violation.
- `low`: consistency polish.

---

## Measurement Pattern

IMPORTANT: Each numbered step that starts or stops a timer, runs the main-agent review, or
submits/checks handoff work must execute in its own subagent/worker turn when the harness
supports that. This mirrors `tests/explore/compare-vision.md` and gives each measured segment
a separate trace/log opportunity.

Run Approach A first, then Approach B.

If a timer tool is available, use it. Otherwise record wall-clock elapsed time manually with
`date +%s` or equivalent before and after each approach.

For token usage:

- Main-agent/direct token usage may only be available from the harness trace. If unavailable,
  record `not available` and note why.
- Handoff worker token usage should be extracted from each completed raw log by searching for
  `thread/tokenUsage/updated` and taking the final event per worker.
- Report cached input separately from noncached input when available.

---

## Approach A - Main Agent Direct Review

Run the review without using `handoff.submit`.

Suggested steps:

```text
1. [subagent] Start timer named "handoff-compare-main".
2. [subagent] Perform the review directly through OneTool MCP `__run` calls only.
              Start with `ot.help()` and use OneTool tools to inspect the source/docs/guides.
              Produce the required output shape.
              Do not use handoff.
3. [subagent] Stop timer named "handoff-compare-main".
4. [subagent] Capture token usage for the direct review turn if the harness exposes it.
```

Save the raw direct-review answer to:

```text
wip/test-output/compare-handoff-main.md
```

---

## Approach B - `$ot-handoff` Worker Review

Use the `$ot-handoff` skill with `gpt-5.3-codex` workers. Split the work into focused
tasks that can run concurrently.

Before running this approach, load and follow the `$ot-handoff` skill instructions. In
particular:

- Check that the handoff pack is available.
- Submit narrow, evidence-oriented tasks.
- Record every returned `id`.
- Poll with `handoff.check(ids=[...])` only while tracked ids are outstanding.
- Remove completed ids after reading `ready[]`.
- Treat result files as authoritative when synthesizing the final worker answer.
- Do not repeatedly call `handoff.check()` with an empty outstanding id list.

Before starting, call:

```python
ot.tools(pattern="handoff", info="full")
```

This call must be made through OneTool MCP `__run` as part of the `$ot-handoff` precheck.

Suggested steps:

```text
1. [subagent] Start timer named "handoff-compare-workers".
2. [subagent] Submit three focused handoff tasks in one turn:
              A. Review implementation/docs consistency for handoff.
              B. Review implementation/docs consistency for ot_caveman.
              C. Review implementation/docs consistency for ctx.
              Use model="gpt-5.3-codex", reasoning_effort="low" or "medium",
              timeout=180, and instruct each worker not to edit files.
              The submit/check calls must be made through OneTool MCP `__run`.
3. [subagent] Check all submitted ids with wait=True until complete or timeout.
4. [subagent] Read result files and synthesize one combined answer in the required output shape.
5. [subagent] Stop timer named "handoff-compare-workers".
6. [subagent] Extract final token usage from each raw handoff log.
```

Recommended worker prompt template:

```text
Review consistency for the {pack} pack only. Inspect implementation under src/ottools/,
reference docs under docs/reference/tools/, and relevant guide expectations in
dev/project/guides/tool-development.md plus dev/agents/hints.md. You must perform all
repo inspection through OneTool MCP __run calls using ot.help(), ot.tools(), and available
OneTool file/search tools. Do not use shell commands or direct filesystem reads for the
review. Report findings in the required table format. Include file/line evidence. Do not
edit files.
```

Save the synthesized handoff answer to:

```text
wip/test-output/compare-handoff-workers.md
```

---

## Accuracy Comparison

After both approaches complete, compare findings by substance, not exact wording.

Create a combined finding inventory:

- Merge duplicate findings across approaches.
- Assign a stable comparison ID: `C1`, `C2`, ...
- Mark which approach found each issue.
- Mark whether each finding is valid after checking the cited files.

Use this table:

| ID | Valid? | Severity | Found by Main | Found by Handoff | Better Evidence | Notes |
| :--- | :---: | :--- | :---: | :---: | :--- | :--- |
| C1 | | | | | | |

Accuracy metrics:

- `valid_findings`: count of findings confirmed against source/docs.
- `false_positives`: count of findings rejected after source/docs check.
- `misses`: valid findings found by one approach but missed by the other.
- `precision`: valid findings / total findings for each approach.
- `relative_recall`: valid findings found by approach / all valid findings found by either approach.

Do not treat a shorter answer as worse if it finds the same valid high/medium issues.

---

## Measurements

Fill this table:

| Metric | Main Direct | Handoff Workers |
| :--- | ---: | ---: |
| Wall time (s) | | |
| Submit overhead (s) | n/a | |
| Worker run time max (s) | n/a | |
| Worker run time sum (s) | n/a | |
| Input tokens | | |
| Cached input tokens | | |
| Noncached input tokens | | |
| Output tokens | | |
| Reasoning output tokens | | |
| Total tokens | | |
| Valid findings | | |
| False positives | | |
| Precision | | |
| Relative recall | | |

If exact direct-review token usage is unavailable, provide:

- `not available` in the table.
- A note explaining what telemetry was missing.
- Handoff worker token totals from raw logs if available.

---

## Cost Comparison

If token usage is available, estimate cost using current pricing. If pricing is not already
known in the session, look up current official OpenAI pricing before calculating.

Report:

- Main direct estimated cost using the main model under test.
- Handoff worker estimated cost using `gpt-5.3-codex`.
- Main-agent overhead for submit/check/synthesis if measurable.
- Savings percentage.
- Break-even point in tokens for when handoff becomes cheaper.

Use cached input pricing separately from noncached input pricing.

---

## Output Files

Write:

- `wip/test-output/compare-handoff-main.md`
- `wip/test-output/compare-handoff-workers.md`
- `wip/test-output/compare-handoff-{yyyymmdd}.md`

The final comparison file must include:

- Direct answer.
- Handoff synthesized answer.
- Accuracy comparison table.
- Measurement table.
- Cost estimate.
- Notes on telemetry gaps.

Update:

- `wip/test-results/compare-handoff-test-report.yaml`

Use status:

- `pass`: both approaches completed and comparison was produced.
- `partial`: one approach completed or token telemetry was partially unavailable.
- `fail`: neither approach completed or the comparison could not be produced.

File issues under `wip/issues/1-new/` only for confirmed product code/docs bugs, not for
expected telemetry gaps in the harness.
