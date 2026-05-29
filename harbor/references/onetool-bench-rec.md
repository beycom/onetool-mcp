# OneTool Benchmark Recommendation

## Purpose

Use Terminal-Bench 2.1 through Harbor to test whether OneTool MCP improves Codex results, and whether OneTool MCP plus the new handoff tool improves results further.

The benchmark should compare three Codex variants on the same Terminal-Bench 2.1 task set:

1. `codex-base`
2. `codex-onetool-mcp`
3. `codex-onetool-mcp-handoff`

The goal is not to create a new benchmark task. The goal is to use an existing public benchmark, Terminal-Bench 2.1, as the evaluation substrate and measure the lift from adding OneTool capabilities.

The test must measure four mandatory dimensions for every variant:

- accuracy;
- token usage;
- elapsed time;
- estimated cost.

A run that only reports resource usage is incomplete, and a run that only reports pass/fail or reward is also incomplete. Accuracy, token, time, and cost measurements are all required to decide whether OneTool or handoff improves results efficiently enough to justify the added tooling.

## Recommendation

Build the first spike as a Harbor-based benchmark run against Terminal-Bench 2.1.

Harbor is the right starting point because it already supports agent execution, Docker-backed benchmark environments, task/trial/job results, verifier execution, logs, timing, token fields, cost fields, MCP server configuration, and skill directory injection. Terminal-Bench 2.1 is already exposed through Harbor as a dataset.

The comparison should use Harbor's Terminal-Bench 2.1 dataset:

```bash
harbor run -d terminal-bench/terminal-bench-2-1
```

Use Codex as the agent for all variants. Keep the model, timeout, task selection, repetitions, and execution environment identical across variants. Only change the availability and instruction of OneTool MCP and handoff.

Every variant must produce comparable accuracy, token, timing, and cost data. If Harbor's built-in result files do not contain complete scoring or usage data, the implementation must add verifier parsing, log parsing, or post-processing before treating the benchmark as complete.

## Variants

### Variant 1: `codex-base`

Purpose: Establish the baseline.

Configuration:

- Agent: Codex CLI through Harbor.
- Model: use the same model as the other variants, for example `gpt-5.3-codex` or the current target Codex model.
- MCP servers: none.
- Skills: none, unless Harbor/Codex requires a minimal neutral skill directory. Do not include OneTool-specific instructions.
- Handoff: unavailable.

This variant answers: how well does Codex solve Terminal-Bench 2.1 without OneTool?

### Variant 2: `codex-onetool-mcp`

Purpose: Isolate the value of OneTool MCP.

Configuration:

- Agent: same Codex CLI agent as `codex-base`.
- Model: identical to `codex-base`.
- MCP servers: configure OneTool MCP.
- Skills: either no skill, or a minimal skill that tells the agent OneTool MCP is available and should be used when helpful.
- Handoff: do not explicitly encourage use of handoff. If the handoff tool is available as part of OneTool, the instructions should not bias the agent toward it in this variant.

This variant answers: does adding OneTool MCP improve Terminal-Bench 2.1 pass rate, cost, or time versus Codex alone?

### Variant 3: `codex-onetool-mcp-handoff`

Purpose: Test the added value of the new handoff tool.

Configuration:

- Agent: same Codex CLI agent as the other variants.
- Model: identical to the other variants.
- MCP servers: configure OneTool MCP.
- Skills: include an explicit handoff-aware instruction or skill.
- Handoff: available and encouraged only for bounded parallel subwork.

The handoff instruction should say:

```text
Use OneTool MCP when it helps with codebase navigation, file inspection, command discovery, or structured tool calls.

You may use the handoff tool for bounded side work that can run independently while you continue the main task. Good handoff tasks include focused codebase inspection, test-gap review, log inspection, or summarizing a specific subsystem. Do not use handoff for the immediate next step if your progress is blocked on that result.

When using handoff:
- submit focused tasks with enough context to work independently;
- record returned task ids;
- poll only while ids are outstanding;
- remove completed ids after reading results;
- use result files or summaries as evidence;
- stop polling when all tracked ids are complete.
```

This variant answers: does OneTool MCP plus handoff outperform OneTool MCP alone and Codex alone?

## Experimental Design

### Initial Task Slice

Start with a small, fixed Terminal-Bench 2.1 slice before running the full benchmark.

Recommended first slice:

- 10 to 20 tasks.
- Prefer tasks that involve code navigation, debugging, file edits, tests, repo inspection, or multi-step terminal work.
- Avoid tasks that are dominated by external downloads, GPU requirements, unusually long builds, or flaky network behavior for the first spike.

The task list must be fixed and reused for all variants.

Example selection categories:

- code repair;
- security remediation;
- large text or repository navigation;
- build/test debugging;
- git or filesystem recovery;
- CLI or service configuration.

The first spike should not optimize task selection to favor OneTool. The purpose is to establish whether OneTool helps on realistic terminal tasks without inventing custom scenarios.

### Repetitions

Run at least 3 repetitions per task per variant for the first useful signal.

For a cheap smoke run:

- 5 tasks;
- 1 repetition;
- all three variants.

For a meaningful spike:

- 10 to 20 tasks;
- 3 repetitions;
- all three variants.

For a publishable internal result:

- larger Terminal-Bench 2.1 subset or full dataset;
- 3 to 5 repetitions;
- all three variants;
- confidence intervals.

### Controlled Variables

These must stay identical across variants:

- Terminal-Bench dataset version: `terminal-bench/terminal-bench-2-1`.
- Task ids.
- Number of repetitions.
- Codex model.
- Reasoning/effort setting, if configurable.
- Agent timeout.
- Verifier timeout.
- Docker image/environment version.
- Harbor version.
- Host machine class, if possible.
- Date/time window, if possible.

Only these should vary:

- OneTool MCP availability.
- OneTool skill/instruction availability.
- Handoff-specific instruction availability.

## Harbor Command Shape

The public dataset command shape is:

```bash
harbor run -d terminal-bench/terminal-bench-2-1 -a codex -m gpt-5.3-codex
```

Confirm the exact agent name and model flag in the installed Harbor version before running. Some Harbor versions may use names such as `codex`, `codex-cli`, or another installed agent identifier.

The implementation agent should first run Harbor help:

```bash
harbor --help
harbor run --help
```

Then confirm that Terminal-Bench 2.1 resolves:

```bash
harbor run -d terminal-bench/terminal-bench-2-1 --help
```

If Harbor requires `uvx`, use:

```bash
uvx harbor run -d terminal-bench/terminal-bench-2-1 -a codex -m gpt-5.3-codex
```

## OneTool MCP Configuration

The OneTool MCP variant needs Codex to see OneTool as an MCP server inside the Harbor trial environment.

The exact config location is Harbor/Codex-version dependent, but the intended Codex MCP config should point to the local OneTool server command.

Example conceptual MCP server config:

```toml
[mcp_servers.onetool]
command = "uv"
args = ["run", "onetool", "mcp"]
```

If the benchmark runs from a separate repository, use an absolute path or a wrapper script that starts OneTool from the OneTool repository.

Example wrapper script concept:

```bash
#!/usr/bin/env bash
cd /absolute/path/to/onetool-mcp
exec uv run onetool mcp
```

Then configure Codex/Harbor MCP with:

```toml
[mcp_servers.onetool]
command = "/absolute/path/to/run-onetool-mcp.sh"
args = []
```

The implementation must verify that Codex can see OneTool before running the benchmark slice.

Minimum verification task:

```text
Ask the Codex agent to list available MCP tools and call OneTool help.
Expected: OneTool exposes a run-style MCP tool, and the agent can execute a simple `ot.help()` or equivalent OneTool call.
```

## Handoff Configuration

The handoff variant requires OneTool MCP to expose the handoff pack.

Before running Terminal-Bench tasks, verify:

```python
ot.tools(pattern="handoff", info="full")
```

Expected tools:

- `handoff.submit`
- `handoff.check`
- `handoff.read_index`
- `handoff.search_index`
- `handoff.cancel`
- `handoff.clear`

Handoff also depends on the local Codex CLI being installed and authenticated. If handoff uses a Codex app-server child runner, verify that the root OneTool process supports the required direct child access. If the handoff tool reports that child access is unavailable, record this as a blocker for the handoff variant.

Do not use public handoff as the benchmark harness itself. Use Harbor as the benchmark harness. Handoff should be a tool available to the agent inside the benchmark variant.

## Metrics To Collect

Accuracy, token usage, elapsed time, and estimated cost are mandatory. The benchmark report must include them per trial and aggregated by variant.

Collect these metrics per trial:

- task id;
- variant id;
- repetition number;
- pass/fail or reward;
- verifier score;
- accuracy label;
- accuracy notes;
- wall time;
- agent setup time;
- agent execution time;
- verifier execution time;
- input tokens;
- cached input tokens;
- noncached input tokens, if available;
- output tokens;
- reasoning output tokens, if available;
- total tokens;
- estimated cost;
- number of tool calls;
- number of MCP calls;
- number of OneTool calls;
- number of handoff submissions;
- number of completed handoff tasks;
- number of failed handoff tasks;
- final answer or diff artifact path;
- logs path;
- result JSON path.

Minimum required per-trial measurement fields:

| Field | Required? | Notes |
| :--- | :---: | :--- |
| pass/fail | yes | Primary Terminal-Bench verifier outcome |
| reward or score | yes | Numeric task score when Harbor/Terminal-Bench exposes it |
| accuracy label | yes | `pass`, `fail`, `partial`, or `invalid` |
| accuracy notes | yes | Short reason for failures, partials, or invalid trials |
| wall time | yes | Total trial elapsed time |
| agent execution time | yes | Time spent running Codex, separate from setup/verifier when available |
| verifier execution time | yes | Time spent scoring the task |
| input tokens | yes | Include cached and noncached breakdown when available |
| cached input tokens | yes | Record `0` only if provider reports zero; otherwise use `not available` |
| output tokens | yes | Completion/output tokens |
| reasoning output tokens | yes | Required when provider exposes it; otherwise `not available` |
| total tokens | yes | Sum or provider-reported total |
| estimated cost | yes | Must use the token fields and current pricing for the model/provider |

If any required accuracy field is unavailable, the trial is invalid for benchmark comparison. If any required token or cost field is unavailable, the trial is still usable for accuracy-only analysis, but the benchmark status must be marked `partial` until the missing telemetry path is fixed.

Collect these aggregate metrics per variant:

| Metric | Meaning |
| :--- | :--- |
| pass rate | Fraction of trials that pass verifier |
| partial rate | Fraction of trials with partial credit or partial verifier success |
| invalid rate | Fraction of trials invalidated by setup/tooling/telemetry errors |
| mean reward | Average Harbor/Terminal-Bench reward |
| mean wall time | Average total trial time |
| median wall time | Median total trial time |
| mean cost | Average estimated trial cost |
| total cost | Sum cost across trials |
| mean input tokens | Average input tokens |
| mean cached input tokens | Average cached input tokens |
| mean output tokens | Average output tokens |
| mean total tokens | Average total tokens |
| mean tool calls | Average tool calls |
| handoff use rate | Fraction of handoff-variant trials that used handoff |
| handoff completion rate | Completed handoff tasks / submitted handoff tasks |
| tooling failure rate | Fraction of failures caused by MCP/handoff/tool setup |

Final comparison table:

| Metric | `codex-base` | `codex-onetool-mcp` | `codex-onetool-mcp-handoff` |
| :--- | ---: | ---: | ---: |
| tasks | | | |
| repetitions | | | |
| trials | | | |
| pass rate | | | |
| partial rate | | | |
| invalid rate | | | |
| mean reward | | | |
| mean wall time | | | |
| median wall time | | | |
| total cost | | | |
| mean cost | | | |
| mean input tokens | | | |
| mean cached input tokens | | | |
| mean output tokens | | | |
| mean total tokens | | | |
| mean tool calls | | | |
| handoff submissions | n/a | n/a | |
| handoff completed | n/a | n/a | |
| tooling failures | | | |

## Accuracy And Telemetry Requirements

The benchmark implementation must verify accuracy scoring and telemetry before running the main spike.

For each variant, run one smoke trial and confirm that the result artifacts contain:

- Terminal-Bench verifier pass/fail;
- numeric reward or score when exposed;
- enough verifier output to explain failures;
- elapsed wall time;
- agent execution time or enough timestamps to compute it;
- verifier execution time or enough timestamps to compute it;
- input tokens;
- cached input tokens, when exposed by the provider;
- output tokens;
- reasoning output tokens, when exposed by the provider;
- total tokens;
- estimated cost or enough token/pricing data to compute cost.

Cost calculation must use the actual model used in the run. Cached input tokens must be priced separately from noncached input tokens when the provider exposes cached token usage. If current pricing is not already stored in the benchmark repo, fetch or record pricing before the run and save it with the result metadata.

The final report must clearly distinguish:

- verifier-measured accuracy;
- invalid trials caused by environment, MCP, handoff, or harness setup;
- measured values from Harbor result files;
- values computed by post-processing logs;
- values that were unavailable.

Do not count invalid setup/tooling trials as model accuracy failures unless the failure would also occur for a real user of that variant. Report them separately as invalid trials or tooling failures.

Do not compare variants on accuracy if any variant lacks verifier output for the same task set. Do not compare variants on cost or token efficiency if any variant lacks the corresponding telemetry.

## Success Criteria

The benchmark is useful if it can answer these questions:

1. Does `codex-onetool-mcp` improve pass rate or reward over `codex-base`?
2. Does `codex-onetool-mcp-handoff` improve pass rate or reward over both other variants?
3. Does either OneTool variant reduce wall time?
4. Does either OneTool variant increase cost, and if so, is the quality improvement worth it?
5. Does handoff actually get used in tasks where it helps?
6. Are failures due to benchmark task difficulty, Codex behavior, OneTool MCP setup, or handoff instability?
7. What token, time, and cost tradeoff does each improvement require?
8. Are any accuracy gains statistically or practically meaningful across tasks and repetitions?

Interpretation guidelines:

- If pass rate improves and cost/time are reasonable, OneTool is valuable.
- If pass rate is flat but time or cost improves, OneTool may still be valuable.
- If pass rate improves only with handoff but time/cost increase sharply, handoff may be useful for hard tasks but not default use.
- If handoff is rarely used, the skill/instruction may need improvement before judging the tool.
- If MCP/handoff setup causes failures, fix the integration before drawing model-quality conclusions.
- If token, time, or cost telemetry is missing, fix telemetry before making efficiency claims.
- If accuracy scoring is missing or verifier output is ambiguous, fix scoring before making quality claims.

## Implementation Plan

### Step 1: Prepare Harbor

1. Install or use Harbor.
2. Confirm Harbor can run a trivial Terminal-Bench 2.1 task with Codex.
3. Record Harbor version and Codex CLI version.
4. Confirm Docker is available.

Commands:

```bash
harbor --help
harbor run --help
codex --version
docker --version
```

### Step 2: Select Task Slice

Choose a fixed list of Terminal-Bench 2.1 task ids.

Write the list to a config file such as:

```text
experiments/tbench-2-1-slice/tasks.txt
```

The task list must be reused unchanged across all variants.

### Step 3: Define Variants

Create one config directory per variant:

```text
variants/codex-base/
variants/codex-onetool-mcp/
variants/codex-onetool-mcp-handoff/
```

Each variant directory should contain:

```text
variant.yaml
skills/
mcp/
README.md
```

For `codex-base`, `skills/` and `mcp/` can be empty.

For `codex-onetool-mcp`, include the OneTool MCP config and a neutral OneTool instruction.

For `codex-onetool-mcp-handoff`, include the OneTool MCP config and a handoff-aware instruction.

### Step 4: Verify OneTool MCP Variant

Run a short smoke task or diagnostic prompt that proves Codex can call OneTool.

Expected evidence:

- Codex sees the OneTool MCP server.
- Codex can invoke OneTool help.
- The result includes available OneTool tools.

Do this before running expensive Terminal-Bench tasks.

### Step 5: Verify Handoff Variant

Run a short diagnostic prompt that proves:

- `handoff` tools are discoverable;
- a tiny handoff task can be submitted;
- the result can be checked;
- the handoff task completes or produces a clear failure.

If this fails, do not run the full handoff benchmark. Fix the setup first.

### Step 6: Run Smoke Benchmark

Run:

- 5 Terminal-Bench 2.1 tasks;
- 1 repetition;
- all three variants.

Purpose:

- verify Harbor config;
- verify logs and result files;
- verify verifier pass/fail and reward extraction;
- verify cost/token extraction;
- verify elapsed-time extraction;
- identify obvious setup failures.

### Step 7: Run Main Spike

Run:

- 10 to 20 Terminal-Bench 2.1 tasks;
- 3 repetitions;
- all three variants.

Keep all run settings identical except variant config.

### Step 8: Aggregate Results

Write a result aggregation script that reads Harbor trial results and produces:

```text
results/tbench-2-1/summary.csv
results/tbench-2-1/summary.md
results/tbench-2-1/by-task.csv
results/tbench-2-1/by-variant.csv
```

The script should calculate pass rates, means, medians, totals, and tooling failure counts.

The aggregation script must fail loudly or mark the benchmark `partial` if accuracy, token, time, or cost fields are missing for any variant.

### Step 9: Analyze Handoff Usage

For the handoff variant, inspect logs and count:

- `handoff.submit` calls;
- `handoff.check` calls;
- completed handoff task ids;
- failed handoff task ids;
- trials where handoff was available but not used.

This matters because a weak result may mean the agent did not use handoff, not that handoff has no value.

### Step 10: Write Final Report

The final report should include:

- benchmark setup;
- Harbor version;
- Codex version;
- OneTool commit;
- Terminal-Bench dataset id;
- task list;
- variant definitions;
- result tables;
- accuracy analysis;
- token usage analysis;
- elapsed-time analysis;
- cost analysis;
- handoff usage analysis;
- tooling failures;
- conclusion and next recommended experiment.

## Suggested Output Layout

Use this layout for the benchmark project or experiment directory:

```text
experiments/
  tbench-2-1-onetool/
    README.md
    tasks.txt
    run-smoke.sh
    run-main.sh
    aggregate.py
    variants/
      codex-base/
        variant.yaml
        README.md
      codex-onetool-mcp/
        variant.yaml
        README.md
        mcp/
          codex-config.toml
        skills/
          onetool-mcp/SKILL.md
      codex-onetool-mcp-handoff/
        variant.yaml
        README.md
        mcp/
          codex-config.toml
        skills/
          onetool-mcp-handoff/SKILL.md
    results/
      smoke/
      main/
      summary.md
      summary.csv
```

## Risk Register

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| Harbor agent name or flags differ by version | Run commands fail | Start with `harbor --help` and document exact command syntax |
| Terminal-Bench 2.1 task resolution changes | Non-reproducible results | Record dataset id/version and task ids |
| OneTool MCP is not visible inside Codex | OneTool variant invalid | Add a diagnostic smoke check before benchmark runs |
| Handoff child runtime unavailable | Handoff variant invalid | Verify `handoff.submit/check` before full run |
| Handoff is available but not used | Cannot judge handoff value | Add explicit handoff-aware skill instructions and count usage |
| Tooling increases token cost | Pass rate may improve at high cost | Report quality, time, and cost together |
| Accuracy scoring missing | Cannot compare result quality | Require verifier output validation before the main spike |
| Token/time/cost telemetry missing | Cannot answer the efficiency part of the benchmark question | Require telemetry validation before the main spike |
| Small sample noise | Misleading conclusion | Use smoke only for setup; use 10 to 20 tasks x 3 reps for signal |
| Task selection bias | Overstates OneTool value | Use a fixed, documented task slice and later expand to a broader subset |

## Non-Goals

Do not build custom benchmark tasks for the first spike.

Do not use the handoff public API as the benchmark harness.

Do not compare different Codex models across variants.

Do not tune prompts separately per task.

Do not draw conclusions from a run where OneTool MCP or handoff setup failed.

Do not draw accuracy conclusions from a run that lacks verifier pass/fail, reward, or score data.

Do not draw efficiency conclusions from a run that lacks token usage, elapsed time, or cost measurements.

## Bottom Line

Use Terminal-Bench 2.1 as the benchmark and Harbor as the execution harness. Compare `codex-base`, `codex-onetool-mcp`, and `codex-onetool-mcp-handoff` under identical task/model/runtime settings. Treat OneTool MCP and handoff as benchmark variants, not as new tasks or a replacement harness. The first useful result is a 10 to 20 task, 3 repetition spike with accuracy, pass rate, token usage, elapsed time, cost, tool-call, and handoff-usage metrics. Accuracy, token usage, time, and cost are required measurements, not optional nice-to-have fields.
