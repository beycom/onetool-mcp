# Harness Tasks for OneTool MCP Benchmarking

## Context

This note recommends a first Terminal-Bench 2.1 slice for benchmarking plain
`ot-harness` against `ot-harness + onetool-mcp`.

The task set is biased toward common agentic engineering and coding work:
repository repair, dependency/build failures, migrations, backend services,
async bugs, database/debugging, config/ops, packaging, and large-file editing.
It deliberately avoids tasks where the result mostly measures niche science,
cryptanalysis, QEMU stamina, or ML infrastructure.

## Public TB 2.1 Evidence

The public Terminal-Bench 2.1 leaderboard page for Codex CLI 0.125.0 with
GPT-5.5 at OpenAI reports:

- Agent: Codex CLI
- Agent version: `0.125.0`
- Model: `gpt-5.5@openai`
- Date: 2026-05-01
- Overall TB 2.1 accuracy: `83.4% ± 2.2`
- Rank on the TB 2.1 page: `1`
- Detail page shape: 89 tasks, 5 trials per task, with per-task successes and
  resolution rate.

Source pages:

- https://www.tbench.ai/leaderboard/terminal-bench/2.1
- https://www.tbench.ai/leaderboard/terminal-bench/2.1/codex/0.125.0/gpt-5.5%40openai
- https://hub.harborframework.com/datasets/terminal-bench/terminal-bench-2-1/6
- https://github.com/harbor-framework/terminal-bench-2/pull/53
- https://huggingface.co/datasets/zai-org/terminal-bench-2-verified

The T-Bench detail page gives task-level trials/successes, not token/cost/time
columns. Harbor Hub job pages can expose timing and reward for individual public
trials, and Harbor result JSON supports token/cost/time fields, but the T-Bench
agent detail page itself is best treated as task outcome evidence.

## Top 10 Recommended TB 2.1 Tasks

| Rank | Task | Codex 0.125.0 / GPT-5.5 Result | Why It Represents Common Engineering | Packs to Leverage |
|---:|---|---:|---|---|
| 1 | `fix-git` | 5/5, 100% | Broken repository state, git diagnosis, careful repair. Good fast smoke test. | `file`, `ripgrep`, `ot`, `ot_context`, `handoff` |
| 2 | `build-cython-ext` | 5/5, 100% | Dependency/build failure with package compatibility and native extension debugging. | `package`, `context7`, `ripgrep`, `file`, `ground`, `tavily`, `brave` |
| 3 | `modernize-scientific-stack` | 5/5, 100% | Real migration/refactor with dependency and API drift, but still normal coding work. | `package`, `context7`, `ripgrep`, `file`, `webfetch`, `ground`, `ot_caveman` |
| 4 | `kv-store-grpc` | 3/5, 60% | Backend service implementation/debugging with interface and tests. | `ripgrep`, `file`, `context7`, `ground`, `handoff`, `ot_context` |
| 5 | `cancel-async-tasks` | 5/5, 100% | Async correctness bug, cancellation semantics, targeted code inspection. | `context7`, `ripgrep`, `file`, `ground`, `tavily` |
| 6 | `git-multibranch` | 5/5, 100% | Multi-branch repo reasoning, history inspection, integration and conflict handling. | `file`, `ripgrep`, `handoff`, `ot_context`, `ot_timer` |
| 7 | `sqlite-db-truncate` | 5/5, 100% | Practical data/debugging task involving local files and database state. | `db`, `file`, `ripgrep`, `ot_context`, `handoff` |
| 8 | `nginx-request-logging` | 5/5, 100% | Config/ops-adjacent engineering with service behavior verification. | `ground`, `tavily`, `webfetch`, `file`, `ripgrep`, `context7` |
| 9 | `pypi-server` | 3/5, 60% | Package server setup, dependency behavior, config and test workflow. | `package`, `context7`, `ground`, `file`, `ripgrep`, `webfetch` |
| 10 | `large-scale-text-editing` | 5/5, 100% | Bulk repository/file transformation where search and batch reads should reduce context cost. | `ripgrep`, `file`, `ot_caveman`, `ot_context`, `handoff` |

Interpretation: this slice is mostly solvable for a frontier coding agent, but
not fully saturated. `kv-store-grpc` and `pypi-server` are the useful challenge
anchors because Codex solved only 3/5 public trials. The 100% tasks remain useful
for measuring token/cost/time reduction, trace quality, and whether OneTool can
maintain pass rate with less context overhead.

## Per-Task Notes

### 1. `fix-git`

Use this as the first canary because it is easy to explain, usually cheap to
run, and representative of coding agents operating in a dirty repository.
Plain harness should inspect git state and repair directly. OneTool should help
by using `file` and `ripgrep` for scoped inspection, `ot_context` for storing
larger command output, and `handoff` on the feature branch for parallel diagnosis
of branch/history anomalies.

### 2. `build-cython-ext`

This is a strong OneTool task because build failures often require reading
source, checking current package versions, and looking up compatibility notes.
Use `package` for PyPI version checks, `context7` for library docs, `ground` or
`tavily` for current compatibility evidence, and `ripgrep`/`file` for targeted
code inspection.

### 3. `modernize-scientific-stack`

This represents realistic migration work: deprecated APIs, dependency changes,
and small refactors. OneTool can reduce token load by searching only relevant
symbols with `ripgrep`, consulting docs with `context7`, and compacting long
release-note or error-output material with `ot_caveman`.

### 4. `kv-store-grpc`

This is backend implementation/debugging rather than a puzzle. It should expose
differences in how agents inspect service interfaces, tests, generated files,
and failure logs. Because the public Codex result is only 3/5, this should be
one of the primary tasks for measuring pass-rate lift, not just token savings.
`handoff` can be tested as an optional feature-branch variant by delegating
API-shape review while the main agent debugs tests.

### 5. `cancel-async-tasks`

Async cancellation bugs are common in real code. OneTool search should help find
call sites and task lifecycle code quickly. `context7`, `ground`, and `tavily`
are useful when the agent needs precise runtime/library behavior.

### 6. `git-multibranch`

This tests repository reasoning under more complexity than `fix-git`. It is a
good handoff candidate because one worker can inspect branch intent or history
while the primary agent reasons about the final merge/repair path.

### 7. `sqlite-db-truncate`

This task tests local debugging and structured data inspection. `db` is the
obvious OneTool advantage if SQLite access is wired through the task environment;
otherwise `file`, `ripgrep`, and shell execution remain useful for locating and
understanding the database workflow.

### 8. `nginx-request-logging`

This is representative ops/config work. It is not purely coding, but it matches
common engineering tasks where agents must read docs, edit config, and verify
service behavior. `ground`, `tavily`, or native web search can help when config
syntax or logging directives are uncertain.

### 9. `pypi-server`

This tests packaging and server setup. Because the public Codex result is 3/5,
it is a second pass-rate challenge anchor. `package` helps with Python package
versions and vulnerability checks, `context7`/`webfetch` help with
documentation, and `file`/`ripgrep` reduce repository inspection cost.

### 10. `large-scale-text-editing`

This is one of the best tasks for showing OneTool's context advantage. The agent
should not paste large files into the conversation when it can use `ripgrep`,
`file.read_batch`, `file.slice`, and `ot_context` to inspect only the relevant
parts. `ot_caveman` can compact long intermediate summaries.

## Search Tools

| Tool | Role in Benchmark | Best Use |
|---|---|---|
| `ground` | Current web search with Google grounding and citations. | Official docs, current package/API behavior, troubleshooting with source provenance. |
| `tavily` | LLM-oriented search, extraction, and deeper research. | Clean web results, extracting docs/articles, multi-source research when the task permits internet. |
| `brave` | Fast web/news/image/video search. | Lightweight search, broad web discovery, batch search with simple source lists. |
| Native web search | Non-MCP baseline comparison. | Measure whether OneTool search packs reduce context, cost, and tool-call clutter versus built-in host browsing. |
| `webfetch` | Fetch and extract known URLs. | When the agent already knows the documentation URL and needs content extraction rather than discovery. |
| `context7` | Library documentation lookup. | Current library/API documentation without broad web search. |

Recommendation: include search-enabled and search-disabled variants when the
task permits internet. That separates "better because it searched" from "better
because OneTool lowered tool/context overhead."

## Special Tools

### `handoff` Feature-Branch Variant

`handoff` should be included only in a feature-branch benchmark profile, not the
default comparison. It changes agent capability by adding Codex worker
delegation, so it is not a pure tool-tax comparison.

Use it for:

- Parallel branch/history inspection in `git-multibranch`.
- Independent build-failure triage in `build-cython-ext`.
- API/test review in `kv-store-grpc`.
- Large edit planning in `large-scale-text-editing`.

Measure:

- Accuracy impact.
- Wall-clock impact.
- Token and cost impact.
- Whether delegated work is actually used or just adds overhead.

### OT Caveman Pack and `/ot-cm` Skill

`ot_caveman` / `cm` is useful for compacting long logs, summaries, docs, and
intermediate findings while preserving protected content such as code blocks,
paths, commands, URLs, version numbers, errors, and security warnings.

Benchmark uses:

- Compact long build/test logs before the next model turn.
- Compact release-note or troubleshooting summaries.
- Compare baseline context growth against compacted OneTool output.
- Use `cm.input()` only for explicit command-queue workflows, not normal TB task
  execution.

The `/ot-cm` skill is different from the pack: it changes assistant response
style for the session. Include it in notes as a possible human/operator mode,
but do not treat it as a normal MCP tool benchmark dimension unless the benchmark
explicitly tests response compaction.

## OneTool MCP Pack Deep Dive

| Pack | Benchmark Role | Default Profile |
|---|---|---|
| `arch` | Architecture model ingest/validate/generate/export. Useful later for architecture-design benchmarks, not this TB slice. | Optional |
| `aws` | AWS service utilities and role activation. Disable unless a task explicitly needs AWS credentials/services. | Disabled |
| `brave` | Fast web/news/image/video search. Useful for docs and troubleshooting discovery. | Search profile |
| `ot_caveman` | Compaction/expansion with token stats; strong for logs, docs, and long summaries. | Enabled if model/API available |
| `chrome_util` | Chrome DevTools visual annotation. Not relevant to terminal-only tasks. | Disabled |
| `context7` | Library documentation lookup. Strong for package/API/async/server tasks. | Enabled in `[dev,util]` |
| `convert` | Convert PDF/Word/PPTX/Excel to Markdown. Useful for document-heavy tasks later. | Optional |
| `db` | SQL query/schema/sample inspection. Strong for `sqlite-db-truncate`. | DB profile |
| `diagram` | Diagram generation. Useful for reporting, not solving this slice. | Disabled |
| `excel` | Spreadsheet operations. Not needed in this slice. | Disabled |
| `file` | Read/search/list/tree/slice/batch/edit files. Core to every coding task. | Enabled |
| `ground` | Google-grounded web search with citations and docs/dev modes. | Search profile |
| `handoff` | Codex worker delegation with file-backed results. Capability-changing, feature-branch only. | Feature branch |
| `ide` | Read-only VS Code state. Usually not exposed inside TB containers. | Disabled |
| `knowledge` | Portable indexed knowledge bases. Useful only if pre-indexing is controlled across profiles. | Optional |
| `mem` | Persistent memory. Avoid for strict task isolation unless explicitly testing memory. | Disabled |
| `ot_context` | Store/query large outputs outside main context. Strong for logs and bulk editing. | Enabled |
| `ot` | Core introspection, health, tools, stats, server state. Useful for diagnostics. | Enabled |
| `ot_forge` | Extension scaffolding/validation. Not needed unless task is to create tools. | Disabled |
| `ot_image` | Vision over images. Save for `code-from-image` style variants. | Disabled |
| `ot_llm` | Nested LLM transformation. Use cautiously because it changes evaluation target. | Optional/disabled |
| `ot_secrets` | Secret management. Not relevant unless task requires secret setup. | Disabled |
| `ot_servers` | Enable/disable/restart/status external MCP proxy servers. Useful for harness setup. | Harness ops |
| `package` | NPM/PyPI versions, audits, model lookup. Strong for build/migration/package tasks. | Enabled in `[dev,util]` |
| `play_util` | Playwright visual annotation. Not needed in terminal-only slice. | Disabled |
| `ripgrep` | Fast repo/file search. One of the most important packs for coding benchmarks. | Enabled |
| `tavily` | Search, extraction, batch search, deep research. Useful with internet-enabled docs tasks. | Search profile |
| `ot_timer` | Named timers. Harness already measures time, but useful for agent-side instrumentation. | Optional |
| `whiteboard` | Excalidraw drawing. Not relevant to TB terminal tasks. | Disabled |
| `webfetch` | Fetch/extract known URLs after search identifies docs. | Enabled if internet allowed |

## Recommended Benchmark Matrix

| Scenario | Baseline | OneTool Main | Optional Variant |
|---|---|---|---|
| `fix-git` | Plain agent | `file`, `ripgrep`, `ot_context` | `handoff` |
| `build-cython-ext` | Plain agent | `package`, `context7`, `file`, `ripgrep` | `ground`/`tavily`/`brave` search |
| `modernize-scientific-stack` | Plain agent | `package`, `context7`, `ripgrep`, `ot_caveman` | `webfetch`, `ground` |
| `kv-store-grpc` | Plain agent | `file`, `ripgrep`, `context7` | `handoff` |
| `cancel-async-tasks` | Plain agent | `context7`, `ripgrep`, `file` | `ground` |
| `git-multibranch` | Plain agent | `file`, `ripgrep`, `ot_context` | `handoff` |
| `sqlite-db-truncate` | Plain agent | `db`, `file`, `ripgrep` | `handoff` |
| `nginx-request-logging` | Plain agent | `file`, `ripgrep`, `ground` | `tavily`, native web search |
| `pypi-server` | Plain agent | `package`, `context7`, `file`, `ripgrep` | `webfetch`, `ground` |
| `large-scale-text-editing` | Plain agent | `ripgrep`, `file`, `ot_context`, `ot_caveman` | `handoff` |

## Measurement Plan

Track these per task and per profile:

- Pass/fail or verifier reward.
- Total input tokens.
- Total cache tokens where available.
- Total output tokens.
- LLM call count.
- Tool call count.
- Agent execution time.
- Verifier time.
- End-to-end wall-clock duration.
- Estimated cost.
- Base context size and average context growth.
- Search-enabled vs search-disabled delta where applicable.
- Handoff overhead and usefulness in the feature-branch profile.

Use the public Codex/TB 2.1 page as a calibration baseline for expected pass
rates. Use local Harbor or `ot-harness` results for token/cost/time because the
T-Bench leaderboard detail page does not expose those metrics directly.

The main success signal for OneTool is not only higher pass rate. For common
engineering tasks, the expected advantage is equal or better pass rate with
lower context growth, lower total input tokens, cleaner tool use, and better
debugging traceability.
