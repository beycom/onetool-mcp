# Skill Harness Evaluation Notes

## Context

OneTool needs a repeatable way to evaluate agent configurations against realistic work. The target comparisons include base agents versus agents using handoff, caveman-style compression, context tooling, and evolving skill instructions. The desired loop is iterative: test a skill, tweak it, retest it, compare against prior runs, and keep doing that with a full harness and MCP tools enabled.

The main use case is not prompt-only evaluation. It is realistic coding work on large codebases, where the agent may inspect files, use MCP tools, edit code, run tests, and produce a diff. The benchmark must therefore measure correctness, speed, token usage, cost, tool behavior, and validation outcomes under conditions close to a real agent session.

The consultation stayed read-only except for this requested notes file.

## Questions Discussed

1. Which Python libraries or frameworks can evaluate skills, MCPs, and agents in their actual harness?

2. Whether it makes sense to build on the Codex harness or worker code to measure speed, token usage, and accuracy.

3. How to accurately measure token cost, especially for Codex or Claude-style harness runs where usage may be available only through session logs.

4. How Promptfoo and similar tools fit into the design.

5. Whether repeated skill testing should be driven by log analysis, Promptfoo Python providers, or a custom OneTool benchmark harness.

6. How this changes when the benchmark target is realistic coding tasks on a large codebase.

7. Whether Harbor should be used as the basis for a separate live-harness benchmark repo.

## Key Findings

OneTool already has a useful benchmark foundation in `packages/onetool-bench`. It can run direct MCP tool tasks and OpenAI-compatible agentic harness tasks, capture model usage from API responses, record per-call metrics, and calculate costs. This is a good measurement spine for controlled MCP/tool experiments.

The current `onetool-bench` harness is not enough by itself for Codex/Claude harness comparisons. It runs its own OpenAI-chat loop, so it does not capture the full behavior of a real Codex CLI or Claude Code session, including harness prompts, skill loading, worker behavior, command execution, and session-level usage accounting.

The `feature/chat-ops` branch appears highly relevant. It adds parsing and storage for session events, usage records, command events, tool calls, and materialized turn/session metrics. For Codex-harness benchmarking, this should be treated as the measurement backend or truth source where possible.

The handoff worker code is a good execution shortcut because it already maintains a warm `codex app-server --listen stdio://` process and can submit tasks into ephemeral Codex threads. This is promising for quickly running a range of benchmark tasks without paying full CLI startup cost each time.

The current handoff runtime should not be used as-is as the benchmark model. It is optimized for compact delegated worker tasks, not controlled experiments. Its default worker prompt, read-only sandbox, dedupe/queue semantics, and summary-oriented result files would distort skill benchmark results unless separated from the reusable runner layer.

The cleaner design is to extract or generalize the Codex app-server runner into a shared internal `CodexHarnessRunner`, with `handoff` as one consumer and `onetool-bench` as another. Benchmark mode should control the skill body/path, MCP config, model, effort, sandbox mode, cwd/worktree, timeout, and run metadata.

An experiment variant is one test condition. Examples include `baseline` with no skill, `candidate` with the current edited skill, `previous` with the last known good skill, `handoff`, `context`, or `caveman`. Every variant runs the same task suite so metrics can be compared.

For iterative skill testing, the skill body should be treated as the experiment artifact. Each run should snapshot the skill hash and metadata so results can be tied to the exact skill text that was tested. This enables a loop such as test skill, tweak, retest, compare with baseline or last passing run.

Promptfoo is useful as an outer eval loop and reporting layer. It can define test matrices, providers, assertions, pass/fail criteria, and comparisons. It should not replace OneTool's harness and log analysis layer for accurate Codex-harness metrics.

Promptfoo Python providers can call custom Python code, run the real harness, and return `output`, `tokenUsage`, `cost`, and metadata. In this architecture, a Promptfoo provider would call the OneTool/Codex harness runner, parse logs via `chat-ops`, and return the final answer plus accurate metrics to Promptfoo.

Log analysis and Promptfoo are complementary, not alternatives. Promptfoo can orchestrate and score test cases, while `chat-ops` or an equivalent parser provides authoritative measurement from the real session logs.

For realistic coding tasks on large codebases, runs should happen in isolated git worktrees or temporary repository copies. The harness should allow file edits, capture the resulting diff, run validation commands, and score the result using tests, static checks, diff assertions, and optionally LLM-based judging as a secondary signal.

Harbor is the strongest external basis investigated so far for a separate repository. It is Python, open source, and already implements much of the desired outer harness: agent adapters, Docker-backed live execution, tasks/datasets, verifier scripts, trajectory capture, timing fields, token/cost fields, MCP server configuration, skill directory injection, job/trial results, and aggregate job statistics.

Harbor's built-in agent abstraction already takes both `mcp_servers` and `skills_dir`, and its docstrings explicitly frame those as setup/run responsibilities for agents. This means skills and MCPs are not an afterthought in Harbor's model; they are first-class inputs that can be passed into Codex, Claude Code, or custom agents.

Harbor's built-in Codex agent copies a configured skills directory into Codex's skill location and writes MCP server configuration into `CODEX_HOME/config.toml`. Its built-in Claude Code agent similarly copies skills into Claude's config directory and writes user-scoped MCP server config. That makes Harbor immediately relevant for testing skill and MCP variants without writing a full harness from scratch.

Harbor's trial lifecycle matches the desired benchmark flow: create/start an environment, set up the agent, execute the agent with timing, download agent logs, populate token/cost metrics from trajectory/session logs, run a verifier, collect artifacts, and write `result.json`. This is close to the architecture previously sketched for a OneTool-specific benchmark repo.

Harbor's result model already includes `AgentContext` fields for input tokens, cache tokens, output tokens, and cost. It also records phase timing for environment setup, agent setup, agent execution, and verifier execution, and aggregates token/cost totals into job-level statistics. This reduces the amount of custom measurement infrastructure needed.

The main Harbor caveat is that its built-in Codex path uses `codex exec`, not the warm `codex app-server` worker path from OneTool handoff. That is simpler and likely more reproducible, but it may be slower for repeated small skill tests. If maximum iteration speed matters, a custom Harbor agent could wrap OneTool's warm app-server runner or implement a Harbor-native app-server runner.

Another Harbor caveat is that skill/MCP configuration is currently task/environment-level. For clean variant comparisons, the benchmark repo should probably generate per-variant Harbor job configs rather than mutating tasks in place. Each variant should still carry explicit metadata such as skill hash, prompt hash, MCP config hash, agent, model, and harness version.

The revised direction is to prototype the separate repo as a Harbor-based benchmark package rather than starting from a blank custom harness. OneTool-specific code can live in custom Harbor agents, task generators, result post-processors, or `chat-ops` enrichment steps.

The first implementation should use Codex CLI only, while keeping the project vocabulary generic enough to support other harnesses later. The core schema should talk about experiments, scenarios, variants, trials, and results. Codex-specific logic should live behind a `codex-cli` harness adapter rather than leaking into every file name and schema field.

The term "variant" should replace "arm" as the canonical comparison unit. A variant is one benchmark configuration, such as `codex-baseline`, `codex-onetool-mcp`, `codex-skill-v1`, `codex-skill-v2`, or `codex-skill-v3`. An experiment is the product of scenarios, variants, and repetitions.

Harbor does not appear to use "arm" or "variant" as a primary concept. Its main concepts are task, trial, job, agent, dataset, reward, rollout, and trajectory. OneTool Harness can use "variant" as its higher-level comparison layer and compile each scenario/variant/repetition into Harbor trials.

Terminal-Bench should be treated as a ready-made public benchmark layer that Harbor can run with Codex CLI. It can validate that skills and MCP configuration do not regress general terminal-task performance, but it is not sufficient by itself to prove OneTool-specific lift because many Terminal-Bench tasks are not designed around MCP-aware code navigation or tool selection.

There are two primary evaluation goals. First, measure the impact of adding OneTool MCP to Codex CLI versus base Codex CLI. Second, support fast iteration on skills, comparing skill variants such as `ot_ref`, `ot_ref_v1`, `ot_ref_v2`, and `ot_ref_v3` against base Codex CLI and against each other.

These goals should be kept as separate experiment tracks initially. Track A should compare `codex-base` against `codex-onetool-mcp` to isolate MCP/tooling impact. Track B should compare `codex-base` against skill variants to isolate skill impact. A later Track C can test combined impact, such as `codex-onetool-mcp` plus the best-performing skill.

Custom large-codebase scenarios should be written in Harbor/Terminal-Bench-style task format where possible: an instruction, pinned repository/environment, verifier, reward output, and optional reference solution. This avoids inventing a separate task format while still letting OneTool Harness generate Harbor jobs across variants.

The Terminal-Bench repository was cloned locally to `scratch/terminal-bench` for inspection. The main study area is `scratch/terminal-bench/original-tasks/`, where tasks typically include `task.yaml`, `Dockerfile`, `docker-compose.yaml`, `run-tests.sh`, and `solution.sh`. Useful starting examples for OneTool Harness scenario design include `fix-code-vulnerability`, `git-leak-recovery`, `sanitize-git-repo`, `large-scale-text-editing`, `filter-js-from-html`, and `configure-git-webserver`.

FastMCP is a strong flagship external repo for realistic scenarios because it is MCP-native and has relevant surfaces around servers, clients, auth, transports, tool/resource registration, request context, and examples. However, open-ended "review FastMCP for unknown security issues" is hard to score repeatably. The first FastMCP scenarios should use pinned commits with either seeded vulnerabilities or historical fixed issues.

Good repeatable scenario categories include seeded security review, security remediation, MCP tool-selection/navigation, historical bug reproduction, dependency/API migration, and small feature additions in a large codebase. Each should be pinned to a repository commit and verified by deterministic tests or explicit report checks.

## Evidence and Code References

The existing benchmark runner records per-call timing around LLM calls in `packages/onetool-bench/src/bench/harness/runner.py:534`.

The benchmark runner reads provider usage from `response.usage` in `packages/onetool-bench/src/bench/harness/runner.py:550` and accumulates input/output token counts in `packages/onetool-bench/src/bench/harness/runner.py:559`.

The runner records tool calls and tool results inside the agentic loop in `packages/onetool-bench/src/bench/harness/runner.py:610`.

Task duration and cost are computed near task completion in `packages/onetool-bench/src/bench/harness/runner.py:727`.

Benchmark cost calculation currently uses OpenRouter pricing fetched in `packages/onetool-bench/src/bench/harness/metrics.py:24` and calculated in `packages/onetool-bench/src/bench/harness/metrics.py:61`.

Per-call benchmark metrics are represented by `LLMCallMetrics` in `packages/onetool-bench/src/bench/harness/metrics.py:87`.

The handoff Codex runner owns a long-lived Codex app-server process in `src/ot/handoff/codex_runner.py:56`, which is valuable for repeated benchmark execution.

The handoff runner starts ephemeral Codex threads in `src/ot/handoff/codex_runner.py:394` and starts turns with the benchmark prompt in `src/ot/handoff/codex_runner.py:414`.

The handoff runtime wires MCP child proxy settings into the runner in `src/ot/handoff/runtime.py:153`.

Handoff result files already include timing-related fields such as submit-to-start and run seconds in `src/ot/handoff/results.py:70`.

The handoff configuration currently defaults to a worker-specific prompt in `src/ot/handoff/models.py:49`, which is useful for handoff but would contaminate skill evaluation unless made configurable or bypassed.

The `feature/chat-ops` branch includes an `event_usage` table with input, output, cached input, reasoning, total tokens, model, service tier, speed, and related usage fields in `src/onetool/chat_ops/pipeline.py:166`.

The same branch includes materialized turn metrics such as command counts, retry counts, file reads/writes, edit churn, tool calls, input/output/cached/reasoning tokens, and total tokens in `src/onetool/chat_ops/pipeline.py:412`.

OpenAI Agents SDK has explicit usage tracking across model calls, including tool calls and handoffs, and exposes aggregated usage after a run. This makes it a strong candidate when the benchmark can run inside OpenAI Agents SDK, but it does not directly measure the Codex CLI harness.

Braintrust, Phoenix/OpenInference/OpenTelemetry, LangSmith/AgentEvals, DeepEval, and MCPEval-style trajectory evaluation are all useful references. None fully replace the need for OneTool-specific harness execution and log-derived metrics when testing Codex/Claude-style coding agents.

Promptfoo supports Python providers/assertions and can be used as an outer orchestration layer. A Python provider can call a real harness and return output, token usage, cost, and metadata for Promptfoo assertions and reports.

Harbor was cloned into `scratch/harbor` for local inspection.

Harbor's base agent stores `mcp_servers` and `skills_dir` in `scratch/harbor/src/harbor/agents/base.py:27`, and its setup/run docstrings explicitly say agents can register MCP servers and copy skills in `scratch/harbor/src/harbor/agents/base.py:96` and `scratch/harbor/src/harbor/agents/base.py:112`.

Harbor task environment config exposes `mcp_servers` and `skills_dir` in `scratch/harbor/src/harbor/models/task/config.py:118`.

Harbor's trial constructor passes task-level MCP servers and skills directory into the created agent in `scratch/harbor/src/harbor/trial/trial.py:190`.

Harbor's trial runner records agent execution timing in `scratch/harbor/src/harbor/trial/trial.py:370`, runs verifier timing in `scratch/harbor/src/harbor/trial/trial.py:393`, downloads logs and populates agent context after execution in `scratch/harbor/src/harbor/trial/trial.py:1242`, and writes trial `result.json` in `scratch/harbor/src/harbor/trial/trial.py:448`.

Harbor's Codex agent populates `AgentContext` from converted trajectory final metrics in `scratch/harbor/src/harbor/agents/installed/codex.py:641`.

Harbor's Codex agent copies skills into `$HOME/.agents/skills` in `scratch/harbor/src/harbor/agents/installed/codex.py:648`, writes MCP server config to `CODEX_HOME/config.toml` in `scratch/harbor/src/harbor/agents/installed/codex.py:658`, and runs `codex exec` with JSON output in `scratch/harbor/src/harbor/agents/installed/codex.py:704`.

Harbor's Claude Code agent populates `AgentContext` from trajectory final metrics in `scratch/harbor/src/harbor/agents/installed/claude_code.py:942`.

Harbor's Claude Code agent copies skills into `$CLAUDE_CONFIG_DIR/skills` in `scratch/harbor/src/harbor/agents/installed/claude_code.py:949`, writes MCP config into `.claude.json` in `scratch/harbor/src/harbor/agents/installed/claude_code.py:978`, and runs Claude Code with stream JSON output in `scratch/harbor/src/harbor/agents/installed/claude_code.py:1015`.

Harbor's `AgentContext` has input tokens, cache tokens, output tokens, cost, rollout details, and metadata in `scratch/harbor/src/harbor/models/agent/context.py:8`.

Harbor's `TrialResult` records task/trial identity, agent/verifier results, exceptions, and phase timings in `scratch/harbor/src/harbor/models/trial/result.py:69`.

Harbor aggregates token/cost totals from trial results in `scratch/harbor/src/harbor/models/trial/result.py:90`, and job stats include aggregate token and cost fields in `scratch/harbor/src/harbor/models/job/result.py:35`.

Terminal-Bench was cloned into `scratch/terminal-bench`. Its README describes Terminal-Bench as a dataset of tasks plus an execution harness, where each task includes an English instruction, a test script, and an oracle/reference solution in `scratch/terminal-bench/README.md`.

Terminal-Bench's legacy task folders live under `scratch/terminal-bench/original-tasks/`. The local clone contains task folders such as `fix-code-vulnerability`, `git-leak-recovery`, `sanitize-git-repo`, `large-scale-text-editing`, `filter-js-from-html`, and `configure-git-webserver`.

## Open Questions

Should support for non-Codex harnesses be limited to schema shape in v0, or should the repository include placeholder adapters for future Claude Code/OpenHands support?

Should skill injection initially mean simple system-prompt injection, or should it immediately support harness-native skill installation directories?

Should coding-task benchmark worktrees be created from local git commits, fixture repositories, or external repositories?

How strict should validation be for realistic coding tasks: tests only, deterministic diff assertions, tool trajectory assertions, LLM judge, or a weighted combination?

Should Promptfoo be a first-class integration, or should OneTool first expose a Python provider/adapter that Promptfoo can call without becoming part of the core benchmark path?

How should costs account for cached input tokens, reasoning tokens, provider-specific billing, and models whose pricing comes from multiple sources?

Should the reusable Codex runner live under `src/ot/harness/`, `packages/onetool-bench/src/bench/harness/`, or another shared internal module so it can be consumed by both handoff and benchmark code without coupling benchmark behavior to the handoff tool?

Should the separate repo be implemented as a Harbor benchmark package from the start, with custom OneTool/skill agents layered on top, rather than building a new task runner?

Should Harbor's existing `codex exec` agent be enough for the first spike, or should the first implementation include a custom warm `codex app-server` Harbor agent for faster repeated skill testing?

How should OneTool-specific `chat-ops` metrics be integrated with Harbor results: as a post-processing command, a custom Harbor agent's `populate_context_post_run`, a job hook, or a separate results-enrichment step?

Should skill and MCP variants be represented as separate Harbor job configs, generated datasets, custom agent kwargs, or a thin OneTool wrapper that expands a higher-level experiment file into Harbor configs?

Which first FastMCP scenarios should be selected: seeded vulnerabilities for deterministic scoring, historical bugs for realism, or open-ended review for demonstration value?

Should Terminal-Bench be used only as a smoke/regression benchmark, or should OneTool Harness maintain a curated Terminal-Bench subset focused on coding/security/navigation tasks?

For the two initial experiment tracks, should the baseline be shared exactly between Track A and Track B, or should each track run its own contemporaneous baseline to control for model/runtime variance?

## Agreements and Decisions

Promptfoo and log analysis should not be treated as alternatives. The likely architecture is Promptfoo as an optional orchestration/reporting layer, with OneTool harness execution and `chat-ops` log parsing as the source of accurate measurements.

The handoff worker path is worth reusing for fast repeated runs because it already keeps Codex app-server warm and supports MCP configuration. It should be factored into a benchmark-oriented runner rather than driving skill evaluation through handoff's public task API.

The first implementation should use Codex CLI only. The schema should allow future harnesses, but v0 should implement a single concrete `codex-cli` adapter and avoid premature multi-harness complexity.

Use "variant" instead of "arm" everywhere. Recommended concepts are `Experiment` for the whole benchmark, `Scenario` for one task/challenge, `Variant` for one comparison configuration, `Trial` for one run of one scenario under one variant, and `Result` for the measured outcome.

For iterative skill testing, each run should snapshot the skill text or hash and compare repeated runs against fixed variants such as baseline, candidate, previous, handoff, context, and caveman.

For realistic large-codebase tasks, each benchmark run should execute in an isolated worktree or temp repository copy, capture the diff, run validation commands, and parse raw session logs for token/cost/tool metrics.

Harbor should be treated as the leading candidate for the separate repo foundation. The first spike should use Harbor's existing Codex agent with one local coding task, two variants, a skills directory, and a OneTool MCP server config, then inspect `result.json`, `agent/trajectory.json`, verifier output, token counts, cost, and timings.

If Harbor's built-in metrics are accurate enough for the initial use case, OneTool can avoid building a full runner. If they are incomplete, the next layer should be custom Harbor agents or `chat-ops` result enrichment rather than replacing Harbor's task/environment/verifier/job machinery.

The next likely project step is still an OpenSpec change if this moves back into OneTool itself. If the work is a separate repo, the first milestone should be a Harbor spike and a minimal experiment schema for skills, prompts, MCP configs, variants, and result comparison.

The separate `onetool-harness` repo should compile a higher-level experiment matrix into Harbor jobs. The v0 layout should probably include `experiments/`, `variants/`, `scenarios/`, `skills/`, `mcp/`, and `src/onetool_harness/`, with Codex-specific logic isolated under a harness adapter such as `src/onetool_harness/harnesses/codex_cli.py`.

Terminal-Bench should be used as Tier 1: a broad public benchmark to check whether Codex skills or MCP configuration help, hurt, or stay neutral on general terminal tasks. OneTool/FastMCP scenarios should be Tier 2 and Tier 3: targeted MCP-aware and security-review benchmarks designed to show the lift from skills and OneTool MCP.

The first custom scenarios should favor deterministic scoring. Recommended starters are `fastmcp-security-review-seeded`, `fastmcp-security-fix-seeded`, `fastmcp-auth-boundary-map`, `fastmcp-historical-session-context-fix`, `onetool-mcp-tool-routing-fix`, and `onetool-mcp-large-codebase-navigation`.

Initial experiments should be split into two tracks. Track A isolates OneTool MCP impact with `codex-base` versus `codex-onetool-mcp`. Track B isolates skill impact with `codex-base` versus `ot_ref`, `ot_ref_v1`, `ot_ref_v2`, and `ot_ref_v3`. Combined variants should wait until those two tracks produce clear enough signal.
