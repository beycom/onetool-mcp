# OneTool Harness WIP

This branch is a work in progress for comparing Terminal-Bench runs that use
plain Codex against runs that use a focused skill plus OneTool MCP over HTTP.

## Document Map

Use this file as the resume entry point. The supporting notes are kept under
`harbor/references/` so they can be committed with the WIP branch instead of
remaining in ignored `wip/` paths.

- `harbor/references/test-harness.md`
  - Chronological execution log for the owned-MCP harness work, including
    previous failed runs, MCP evidence, workspace-mount evidence, and the final
    passing `pypi-server` run.
- `harbor/references/skill-harness-evals-notes.md`
  - Earlier consultation notes on skill/harness evaluation architecture,
    Harbor suitability, Codex runner tradeoffs, and experiment vocabulary.
- `harbor/references/plan-harness-tests.md`
  - Original implementation plan for a Harbor-based `ot-harness` package.
- `harbor/references/harness-tasks.md`
  - Terminal-Bench task selection notes and recommended task slice for broader
    benchmark runs.
- `harbor/references/onetool-bench-rec.md`
  - Benchmark recommendation memo comparing base Codex, OneTool MCP, and
    handoff-capable variants.
- `harbor/references/canary/`
  - Early ignored canary experiment files and the first smoke error log. These
    are historical references, not the current runnable experiment.

## What Changed

- Added HTTP-only OneTool MCP configuration for harness variants.
- Added support for a clean per-trial host workspace bind-mounted into the
  Harbor Docker task container.
- Updated the owned-MCP runner so it starts its own OneTool HTTP MCP server per
  MCP trial, sets `OT_CWD` to the trial workspace, and stops only that owned
  child server after the trial.
- Enabled an owned-MCP `pypi-server` experiment with the workspace mounted at
  `/app`.
- Added focused `pypi-server` skill guidance that removes tool discovery and
  makes package-server lifetime explicit.
- Added unit coverage for workspace mount config and generated Harbor mounts.
- Updated harness notes with the latest benchmark evidence.

## Important Files

- `scripts/run_ot_harness_owned_mcp.sh`
  - Validates the experiment, regenerates trial configs, starts an owned
    OneTool HTTP MCP server only for MCP variants, waits for readiness through
    a real FastMCP call, runs Harbor, and cleans up the owned server.
- `packages/ot-harness/src/ot_harness/config.py`
  - Defines `workspace_mount` and HTTP MCP URL validation.
- `packages/ot-harness/src/ot_harness/harbor/plan.py`
  - Emits Harbor Docker bind mounts and trial metadata for the host workspace.
- `packages/ot-harness/experiments/terminal-bench-owned-mcp/experiment.yaml`
  - Current comparison experiment: base vs focused pypi OneTool MCP.
- `packages/ot-harness/skills/focused/pypi-server/SKILL.md`
  - Focused instructions for `pypi-server`, including OneTool calls and the
    detached package server requirement.

## Latest Result

Command:

```bash
just test-harness-owned-mcp
```

Result:

| Variant | Reward | Wall Time | Tokens | Cost |
|---|---:|---:|---:|---:|
| `codex-base` | `0.0` | `222.701s` | `372179` | `$0.1558515` |
| `codex-skills-pypi-owned-onetool-mcp` | `1.0` | `328.416s` | `787632` | `$0.30477615` |

OneTool MCP usage was confirmed in `.onetool/runtime/stats/stats.jsonl` for the
owned server PID `48274`:

- `package.pypi`
- `ground.search`
- `ground.docs`
- `context7.search`
- `file.tree`

The generated Harbor config mounted the host trial workspace into the container
at `/app`, and the owned OneTool readiness response reported `cwd` as the host
trial workspace. No listener remained on port `18768` after cleanup.

## What The Result Means

The original `pypi-server` failure had two separate causes:

- Agent solution behavior: the agent self-verified while the package server was
  alive, then stopped or lost the server before Harbor's verifier ran.
- Harness ergonomics: a host-running OneTool server could not see Docker-only
  `/app` paths, so file-pack access needed a host workspace mapped into Docker.

The current WIP fixes the harness mapping problem and gives the `pypi-server`
agent focused instructions that require a detached server to remain live.

This does not yet prove OneTool itself was the decisive factor. The successful
run likely came from the focused skill/prompt as much as from MCP access.

## Validation Run

```bash
uv run pytest packages/ot-harness/tests/unit -q
uv run ruff check packages/ot-harness/src packages/ot-harness/tests
bash -n scripts/run_ot_harness_owned_mcp.sh
uv run ot-harness report tmp/harness/harbor/terminal-bench-owned-mcp-pypi --json
```

Observed:

- Unit tests: `24 passed`
- Ruff: passed
- Shell syntax: passed
- Report command: passed

## Next Work

Run the clean control experiment:

- `codex-base`
- `codex-base` plus the same focused `pypi-server` skill but without OneTool MCP
- `codex-skills-pypi-owned-onetool-mcp`

That will separate the value of focused prompting from the value of OneTool MCP.
If base plus the same skill passes, the current benchmark is evidence for prompt
quality and harness wiring, not a strong OneTool advantage.

Useful follow-up improvements:

- Replace the shell runner's `jq` dependency with a small Python metadata reader.
- Add a report field that counts actual OneTool calls from runtime stats.
- Add a focused-skill-only variant for direct A/B/C comparisons.
- Decide whether `pypi-server` should use `setsid` instead of `nohup` in the
  canonical focused skill example, because the successful agent switched to
  `setsid` after `nohup` did not survive in the task environment.

## Ignored Files Brought Into This WIP

These were intentionally moved out of ignored paths so the branch can be resumed
from git alone:

- `wip/consult/1-new/harness/*` -> `harbor/references/`
- `wip/notes/test-harness.md` -> `harbor/references/test-harness.md`
- `tmp/harness/canary/*` -> `harbor/references/canary/`
- `tmp/harness/onetool-http-codex-smoke.jsonl` ->
  `harbor/references/canary/onetool-http-codex-smoke-error.jsonl`

Ignored runtime outputs, caches, generated Harbor jobs, and
`tmp/harness/secrets/` were left out.
