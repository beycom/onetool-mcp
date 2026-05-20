# ot-harness

`ot-harness` is a Harbor-backed benchmark package for comparing real Codex runs across OneTool variants. It is separate from `packages/onetool-bench/`, which remains the legacy internal harness and is not changed by this package.

Harbor is the execution engine. `ot-harness` validates a strict experiment matrix, generates Harbor run configs for each task, variant, and repetition, invokes `harbor run`, then normalizes available Harbor result JSON into concise reports.

## Setup Diagnostics

Run these before benchmark runs:

```bash
harbor --help
harbor run --help
harbor datasets list
codex --version
docker --version
uv run onetool --help
```

For OneTool MCP variants, inspect `mcp/onetool-local.toml` and confirm the configured command starts the intended local server. For skills variants, confirm the configured `skills_dir` contains the expected `SKILL.md` files before running the matrix.

## Smoke Workflow

Validate the checked-in smoke experiment:

```bash
uv run ot-harness validate packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml
```

Generate Harbor configs without executing Harbor:

```bash
uv run ot-harness run packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml --dry-run
```

Execute the matrix:

```bash
uv run ot-harness run packages/ot-harness/experiments/terminal-bench-codex/experiment.yaml
```

Report on a completed or partial run:

```bash
uv run ot-harness report tmp/harness/harbor/terminal-bench-codex-smoke
uv run ot-harness report tmp/harness/harbor/terminal-bench-codex-smoke --json
```

## Artifacts

By default, generated Harbor configs, raw results, logs, trajectories, copied task environments, and scratch artifacts go under `tmp/harness/harbor/`. Experiment configs may override `output_root`, but validation rejects any path that resolves inside `packages/ot-harness/`.

Curated summaries may be checked into `packages/ot-harness/reports/`; raw runtime artifacts should not be stored in the package.

## Reports

Reports aggregate normalized trials by variant. Missing verifier output is marked invalid and excluded from model accuracy failures. Missing token or cost telemetry is marked partial or unavailable instead of being coerced to zero.

## Limitations

The first implementation targets Codex-only variants: base Codex, Codex with OneTool MCP, and Codex with skill directories. Handoff-specific benchmarks and non-Codex first-class agents are deferred until the base Harbor telemetry loop is reliable.
