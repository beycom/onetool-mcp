# Plan: Harbor-Based `ot-harness` Benchmark Package

## Purpose

Create a new permanent benchmark harness package named `ot-harness` that uses
Harbor as the core execution engine for measuring Codex harness variants.

This plan is intended to be self-contained input for the `$openspec-ff-change`
skill. Do not run that skill from this note alone unless the user explicitly
requests it.

Recommended OpenSpec change name:

```text
add-ot-harness-harbor-benchmarks
```

## Goal

Replace the long-term role of the stale internal `ot-bench` harness with a new
Harbor-first package, while leaving `packages/onetool-bench/` in place during
the migration.

The new package should let OneTool measure whether Codex performs better with:

1. base harness only;
2. base harness plus OneTool MCP;
3. base harness plus skills, with skill variants.

The first supported agent is Codex. The design can use generic vocabulary such
as experiment, scenario, variant, trial, and result, but implementation should
avoid premature support for non-Codex agents.

## Background

`packages/onetool-bench/` exists today as an internal benchmark harness. It can
run YAML-defined direct MCP and OpenAI-compatible agent tasks, capture API usage
from model responses, calculate costs, and report timing/evaluation scores.

That harness is not sufficient for the new benchmark goal because it does not
run real Codex CLI sessions. It therefore cannot measure the actual Codex
harness behavior, including Codex prompts, skill loading, command execution,
MCP configuration, session logs, and Codex token/cost accounting.

Harbor is the preferred foundation because it already supports agent execution,
Docker-backed tasks, Terminal-Bench datasets, verifier execution, trajectories,
logs, timing fields, token/cost fields, MCP server configuration, skill
directory injection, job/trial results, and aggregate job statistics.

The new work should add a clean Harbor-based package rather than rewriting
`packages/onetool-bench/` immediately. `packages/onetool-bench/` remains
legacy/reference until `ot-harness` can produce useful benchmark evidence.

## Package Location

Permanent source/config/test package:

```text
packages/ot-harness/
```

Legacy package left unchanged initially:

```text
packages/onetool-bench/
```

Generated temporary runtime artifacts:

```text
tmp/harness/harbor/
```

Use `harbor`, not `harbour`, because the framework name is Harbor.

Do not put generated Harbor jobs, raw logs, copied task environments, or scratch
outputs inside `packages/ot-harness/`. Those artifacts can become large and may
contain prompts, trajectories, local paths, environment details, or sensitive
configuration.

Curated benchmark summaries may live in:

```text
packages/ot-harness/reports/
```

Later, release-quality evidence can move to project docs if needed.

## Proposed Package Shape

```text
packages/ot-harness/
  pyproject.toml
  README.md
  src/ot_harness/
    __init__.py
    cli.py
    config.py
    paths.py
    harbor/
      __init__.py
      experiments.py
      variants.py
      commands.py
      results.py
      reports.py
  experiments/
    terminal-bench-codex/
      experiment.yaml
      tasks.txt
  variants/
    codex-base/
      variant.yaml
    codex-onetool-mcp/
      variant.yaml
    codex-skills/
      variant.yaml
  skills/
    README.md
  mcp/
    onetool-local.toml
  reports/
    README.md
  tests/
```

The exact module split can be adjusted during implementation, but the package
must keep Harbor-specific logic under `ot_harness.harbor` and avoid coupling the
core vocabulary to the old `bench` package internals.

## Runtime Output Shape

Generated output should default to:

```text
tmp/harness/harbor/
  jobs/
  raw-results/
  scratch/
  logs/
```

The output root should be configurable, but `tmp/harness/harbor/` should be the
default for local runs.

## Initial Experiment Scope

Initial public benchmark substrate:

```text
Terminal-Bench via Harbor
```

The implementation must not hard-code an outdated dataset name. Harbor examples
and versions may use names such as:

```text
terminal-bench@2.0
terminal-bench/terminal-bench-2
terminal-bench/terminal-bench-2-1
```

The CLI or documentation must instruct the user to confirm the installed Harbor
dataset identifier with:

```bash
harbor datasets list
harbor run --help
```

The first experiment should use a curated fixed task slice, not the full
dataset. Prefer 10 to 20 Terminal-Bench tasks for a meaningful spike, with a
smaller 3 to 5 task smoke run.

Recommended task categories:

- code repair;
- security remediation;
- large text or repository navigation;
- build/test debugging;
- git or filesystem recovery;
- CLI or service configuration.

Example candidate Terminal-Bench-style tasks from prior local inspection:

- `fix-code-vulnerability`
- `git-leak-recovery`
- `sanitize-git-repo`
- `large-scale-text-editing`
- `filter-js-from-html`
- `configure-git-webserver`
- `fix-git`
- `classifier-debug`
- `debug-long-program`
- `security-celery-redis-rce`

The task list must be fixed and reused across all variants in the same
experiment.

## Required Variants

### `codex-base`

Purpose: establish the Codex-only baseline.

Configuration:

- Harbor agent: Codex.
- Model: same as all variants in the experiment.
- MCP servers: none.
- Skills: none, unless Harbor/Codex requires a neutral empty skill directory.
- OneTool: unavailable.

### `codex-onetool-mcp`

Purpose: isolate the value of OneTool MCP.

Configuration:

- Harbor agent: same Codex agent as `codex-base`.
- Model: same as `codex-base`.
- MCP servers: OneTool MCP configured.
- Skills: no skill, or only a neutral OneTool availability instruction if
  needed to make Codex aware of the MCP server.
- Handoff: not encouraged and not a required measurement in the first spike.

Conceptual local MCP config:

```toml
[mcp_servers.onetool]
command = "uv"
args = ["run", "onetool", "mcp"]
```

If Harbor runs from outside the OneTool repository root or inside a container
where relative paths are unreliable, use a wrapper script that changes directory
to this repo and starts OneTool:

```bash
#!/usr/bin/env bash
cd /absolute/path/to/onetool-mcp
exec uv run onetool mcp
```

### `codex-skills-*`

Purpose: compare skill variants under the same benchmark tasks.

Configuration:

- Harbor agent: same Codex agent as the other variants.
- Model: same as the other variants.
- MCP servers: configurable per experiment; initial skill-only track may run
  without OneTool MCP to isolate skill impact.
- Skills: Harbor `skills_dir` points to the specific skill variant directory.

Skill variants should be treated as experiment artifacts. Each run should
record at least:

- skill variant id;
- skill file path;
- skill text hash;
- skill metadata if available.

Initial examples may include variants such as:

- no skill baseline;
- current `ot-ref`;
- current `ot-handoff` only in a later handoff experiment;
- candidate revised skill variants.

## Deferred Variant

`codex-onetool-mcp-handoff` is valuable but should not be mandatory for the
first implementation.

Handoff depends on the Codex app-server path and OneTool handoff tools being
available and stable. Add it after base, MCP, and skill variants have reliable
telemetry.

When added later, the handoff variant should verify that OneTool exposes:

- `handoff.submit`
- `handoff.check`
- `handoff.read_index`
- `handoff.search_index`
- `handoff.cancel`
- `handoff.clear`

## Experiment Model

Use this vocabulary:

- experiment: the complete benchmark matrix and metadata;
- scenario or task: one benchmark task;
- variant: one agent/configuration condition;
- repetition: repeat index for the same task and variant;
- trial: one run of one task under one variant and repetition;
- result: measured trial output;
- report: aggregated comparison.

Harbor's native vocabulary includes task, trial, job, agent, dataset, reward,
rollout, and trajectory. `ot-harness` should use `variant` as the OneTool-level
comparison unit and compile variants into Harbor jobs/trials.

## Initial Config Expectations

The first implementation should support a compact experiment definition. A
representative shape:

```yaml
name: terminal-bench-codex
description: Compare Codex base, OneTool MCP, and skill variants on a curated Terminal-Bench slice.

harbor:
  dataset: terminal-bench@2.0
  agent: codex
  model: gpt-5.3-codex
  output_root: tmp/harness/harbor
  n_concurrent: 1

tasks:
  file: tasks.txt

run:
  repetitions: 1
  agent_timeout_sec: 1800
  verifier_timeout_sec: 600

variants:
  - id: codex-base
    path: ../../variants/codex-base/variant.yaml
  - id: codex-onetool-mcp
    path: ../../variants/codex-onetool-mcp/variant.yaml
  - id: codex-skills
    path: ../../variants/codex-skills/variant.yaml

metrics:
  require_accuracy: true
  require_time: true
  require_tokens: true
  require_cost: true
```

Representative variant shape:

```yaml
id: codex-onetool-mcp
label: Codex + OneTool MCP
agent: codex
mcp:
  - name: onetool
    transport: stdio
    command: uv
    args: ["run", "onetool", "mcp"]
skills_dir: null
metadata:
  isolates: onetool-mcp
```

Exact schema can be refined during OpenSpec artifact creation, but the initial
implementation must avoid backward-compatibility shims for old `bench` YAML.
This is a new package and should fail clearly on invalid config.

## Required Measurements

Every useful trial result should capture:

- task id;
- variant id;
- repetition number;
- pass/fail or reward;
- numeric verifier score when Harbor exposes it;
- accuracy label: `pass`, `fail`, `partial`, or `invalid`;
- short accuracy notes;
- wall time;
- agent setup time when available;
- agent execution time;
- verifier execution time;
- input tokens;
- cached input tokens when available;
- output tokens;
- reasoning output tokens when available;
- total tokens;
- estimated cost;
- tool call count when available;
- MCP call count when available;
- OneTool call count when available;
- final answer or artifact path;
- logs path;
- Harbor result JSON path.

If verifier output is missing, the trial is invalid for accuracy comparison.

If token or cost fields are missing, the trial can still be usable for
accuracy-only analysis, but the report must mark cost/token telemetry as
partial or unavailable.

Do not count setup/tooling failures as model accuracy failures unless the
failure would also affect a real user of that variant. Report setup failures as
invalid/tooling failures.

## Aggregated Report Requirements

Reports should aggregate by variant:

- task count;
- repetition count;
- trial count;
- pass rate;
- partial rate;
- invalid rate;
- mean reward or score;
- mean wall time;
- median wall time;
- mean input tokens;
- mean cached input tokens when available;
- mean output tokens;
- mean total tokens;
- mean cost;
- total cost;
- mean tool calls when available;
- OneTool call rate when available;
- tooling failure rate.

Final comparison table should include at least:

```text
Metric | codex-base | codex-onetool-mcp | codex-skills-*
```

## CLI Expectations

The first CLI should be minimal and implementation-oriented.

Suggested command name:

```bash
ot-harness
```

Suggested commands:

```bash
ot-harness validate <experiment.yaml>
ot-harness run <experiment.yaml>
ot-harness report <run-output-dir>
```

`validate` should parse configs, resolve paths, check variant/task references,
and verify required local files exist.

`run` should orchestrate Harbor for the experiment matrix and write generated
outputs under `tmp/harness/harbor/` by default.

`report` should parse Harbor trial/job results and produce a concise Markdown
and/or JSON summary.

The CLI may call Harbor as a subprocess for the first implementation. Direct
Harbor Python API integration can come later if needed.

## Verification and Test Plan

Unit tests:

- parse valid experiment config;
- reject invalid experiment config;
- parse valid variant config;
- reject unknown/invalid variant fields;
- resolve paths relative to the experiment file;
- generate the expected Harbor command/config shape for each variant;
- normalize representative Harbor `result.json` files;
- aggregate normalized trial results by variant;
- mark missing verifier output as invalid;
- mark missing token/cost telemetry as partial rather than silently zero;
- keep generated output paths under `tmp/harness/harbor/` by default.

Smoke/diagnostic checks:

```bash
harbor --help
harbor run --help
harbor datasets list
codex --version
docker --version
```

OneTool MCP diagnostic before benchmark runs:

- run a minimal Harbor/Codex task with OneTool MCP configured;
- verify Codex can see the MCP server;
- verify Codex can invoke a simple OneTool help/status call.

Skill diagnostic before skill benchmark runs:

- run a minimal Harbor/Codex task with `skills_dir` configured;
- verify Harbor copies skills into Codex's skill location;
- verify logs/trajectory show the skill was available or used.

Benchmark stages:

- smoke: 3 to 5 curated tasks, 1 repetition, all initial variants;
- spike: 10 to 20 curated tasks, 3 repetitions, all initial variants;
- later evidence run: larger curated subset or full dataset, 3 to 5 repetitions.

Project checks should use `just`, consistent with repo guidance:

```bash
just check
just test
just lint
```

Package-specific tests should use `uv run pytest`, not bare `pytest`.

## Documentation Requirements

Add a README under `packages/ot-harness/` that explains:

- what `ot-harness` is;
- why Harbor is the core harness engine;
- relationship to legacy `packages/onetool-bench/`;
- how to install/run local dependencies;
- how to validate Harbor/Codex/Docker availability;
- how to run the smoke experiment;
- where generated artifacts go;
- how to read the report;
- known limitations.

Document that raw generated artifacts belong under:

```text
tmp/harness/harbor/
```

Document that curated summaries may be committed under:

```text
packages/ot-harness/reports/
```

## OpenSpec Notes

This likely needs OpenSpec because it adds a new package and benchmark CLI and
defines new user-facing benchmark workflow/config behavior.

The OpenSpec artifacts should define:

- the new `ot-harness` package;
- the minimal CLI commands;
- the config concepts and validation behavior;
- the Harbor-based execution boundary;
- the generated artifact location;
- the required metrics and reporting behavior;
- the relationship to legacy `packages/onetool-bench/`;
- initial Codex-only scope;
- deferred handoff scope.

Do not include backward-compatible aliases or old `bench` config support unless
the user explicitly asks for compatibility.

## Non-Goals for First Implementation

- Do not delete or rewrite `packages/onetool-bench/`.
- Do not implement a custom warm Codex app-server Harbor agent.
- Do not make handoff a required variant.
- Do not support Claude Code, OpenHands, or other agents beyond schema-neutral
  naming.
- Do not build Promptfoo integration.
- Do not integrate the `feature/chat-ops` branch.
- Do not make benchmark results part of release claims until telemetry and
  scoring are verified.
- Do not store raw Harbor runtime artifacts inside `packages/ot-harness/`.

## Acceptance Criteria

The first implementation is successful when:

- `packages/ot-harness/` exists as a standalone workspace package;
- `packages/onetool-bench/` is left intact;
- experiment and variant configs can be validated;
- Harbor commands/configs can be generated or executed for all required
  variants;
- generated outputs default to `tmp/harness/harbor/`;
- result parsing can produce per-trial normalized metrics;
- reporting can compare `codex-base`, `codex-onetool-mcp`, and at least one
  `codex-skills-*` variant;
- tests cover config parsing, path resolution, command/config generation,
  result normalization, and aggregation;
- README documents setup, smoke run, artifact locations, and limitations.

## Key Design Decisions Already Made

- Use Harbor as the `ot-harness` execution engine, not as a temporary spike.
- Put permanent source in `packages/ot-harness/`.
- Leave `packages/onetool-bench/` alone during the initial migration.
- Put generated artifacts in `tmp/harness/harbor/`.
- Use Codex as the initial and only required agent.
- Start with base, OneTool MCP, and skills variants.
- Treat handoff as a later optional variant.
- Use a curated Terminal-Bench task slice first.
- Require accuracy, speed, tokens, and cost in reports.

