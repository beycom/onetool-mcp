# ot-harness Terminal-Bench Comparison Request

## User Request

Run a real ot-harness / Harbor comparison on a very challenging Terminal-Bench task:

- Variant A: base Codex, no OneTool MCP.
- Variant B: Codex with OneTool MCP over HTTP.
- Compare speed and token usage.
- The OneTool MCP variant should receive focused directions to use specific tools, not discover them during the run.
- The prompt should include exact OneTool command shapes and target arguments for:
  - `ground.search`
  - `ground.search_batch`
  - `ground.dev`
  - `ground.docs`
  - `context7.search`
  - `context7.doc`
  - `file.slice`
  - `file.slice_batch`
- Research the chosen Terminal-Bench scenario first so the MCP prompt is focused and avoids tool-discovery overhead.

The user specifically wants to eliminate the discovery part of using OneTool MCP.

## Current Harness State

Recent implementation changed ot-harness to use OneTool MCP over HTTP, not stdio.

Important files:

- `packages/ot-harness/src/ot_harness/config.py`
  - `OneToolMcpConfig` is HTTP-only.
  - Fields are `config_path`, `server_name`, `url`.
  - Rejects non-HTTP URLs and rejects old stdio-style extra fields.
- `packages/ot-harness/src/ot_harness/harbor/plan.py`
  - Emits Harbor `agent.mcp_servers` entries with `transport: http`.
  - Supports MCP on both `codex-onetool-mcp` and `codex-skills` variants.
- `packages/ot-harness/src/ot_harness/results.py`
  - Normalizes Harbor job-level and trial-level `result.json`.
  - Prefers per-trial results when both job summary and child trial result exist.
  - Extracts reward, wall time, token count, and cost from Harbor output.
- `packages/ot-harness/mcp/onetool-http.toml`
  - Points at `http://host.docker.internal:8768/mcp`.
- `packages/ot-harness/variants/codex-onetool-mcp.yaml`
  - HTTP MCP variant.
- `packages/ot-harness/variants/codex-skills-smoke-onetool-mcp.yaml`
  - Combined skills + HTTP MCP variant.

Useful prior validation:

- `uv run pytest packages/ot-harness/tests/unit -q` passed with 21 tests.
- `uv run ruff check packages/ot-harness/src packages/ot-harness/tests` passed.
- `uv run pytest -m smoke -q` passed with 39 tests.
- Real Harbor trial for `fix-git` using `codex-skills-smoke-onetool-mcp` passed with reward `1.0`.
- `uv run ot-harness report tmp/harness/harbor/terminal-bench-codex-smoke/fix-git/codex-skills-smoke-onetool-mcp/rep-001` reported one normalized trial, 100% pass rate, complete token/cost telemetry.

Known unrelated issue:

- `just lint` currently fails on an unrelated existing lint issue:
  - `src/onetool/cli.py:215`
  - `ARG001 Unused function argument: ot_dir`

## MCP Lifecycle Decision

Use a harness-owned OneTool HTTP MCP server for benchmark tests.

- Do not reuse the shared interactive `__run` MCP server.
- Do not stop shared OneTool processes.
- The test command should start its own HTTP MCP server, run the harness, and stop only the child process it started.
- The dedicated harness-owned port is `18768`.
- Docker containers should use `http://host.docker.internal:18768/mcp`.

Use:

```bash
just test-harness-owned-mcp
```

The recipe is backed by:

- `scripts/run_ot_harness_owned_mcp.sh`
- `packages/ot-harness/experiments/terminal-bench-owned-mcp/experiment.yaml`
- `packages/ot-harness/mcp/onetool-owned-http.toml`
- `packages/ot-harness/variants/codex-skills-smoke-owned-onetool-mcp.yaml`

The script should:

- fail if port `18768` is already occupied,
- start `uv run onetool serve ... --transport http --port 18768 --path /mcp`,
- wait for a real FastMCP `ot.status()` call to succeed,
- run `uv run ot-harness validate ...`,
- run `uv run ot-harness run ...`,
- stop only the child PID it started via shell trap cleanup.

## Exact OneTool Tool Forms

The MCP call shape is:

```python
ground.search(query='...', context='...', focus='documentation', max_sources=5, output_format='text_only')
ground.search_batch(queries=[('query text', 'label')], context='...', focus='code', max_sources=3, output_format='text_only')
ground.dev(query='...', language='Python', framework='FastAPI', max_sources=5, output_format='text_only')
ground.docs(query='...', technology='React', max_sources=5, output_format='text_only')
context7.search(query='...', library_name='react', output_format='str')
context7.doc(library_id='/vercel/next.js', query='middleware matcher app router')
file.slice(path='...', start='...', end='...')
file.slice_batch(requests=[{'path': '...', 'start': '...', 'end': '...'}])
```

Need to verify exact `file.slice` and `file.slice_batch` signatures before using them in the final prompt:

```bash
sed -n '1524,1705p' src/otutil/tools/file.py
```

Known signatures already inspected:

- `ground.search`:
  - `query: str`
  - `context: str = ''`
  - `focus: 'general' | 'code' | 'documentation' | 'troubleshooting' = 'general'`
  - `model: str | None = None`
  - `timeout: float | None = None`
  - `max_sources: int | None = None`
  - `output_format: 'full' | 'text_only' | 'sources_only' = 'full'`
  - `extract_schema: dict | None = None`
  - `return_provenance: bool = False`
- `ground.search_batch`:
  - `queries: list[tuple[str, str] | str]`
  - same `context`, `focus`, `model`, `timeout`, `max_sources`, `output_format`
  - `retries: int = 0`
  - `retry_delay_ms: int = 250`
- `ground.dev`:
  - `query`, `language`, `framework`, `timeout`, `max_sources`, `output_format`
- `ground.docs`:
  - `query`, `technology`, `timeout`, `max_sources`, `output_format`
- `context7.search`:
  - `query`, `library_name`, `output_format='str'`
- `context7.doc`:
  - `library_id`, `query`

## Next-Session Plan

1. Use `just test-harness-owned-mcp` for benchmark execution.
2. Do not manually start or stop shared OneTool MCP processes.
3. Choose a difficult Terminal-Bench task:
   - Prefer one with modern framework/library docs where `ground` and `context7` should help.
   - Research task metadata before running.
   - Use Harbor/Terminal-Bench cache or download commands to inspect task README/instructions without solving it.
4. Write a focused benchmark skill/instruction file for the OneTool MCP variant.
   - Include exact tool calls and specific library IDs/search args.
   - Tell Codex not to run `ot.help` / `ot.tool_info` unless a provided call fails.
   - Prefer `file.slice` / `file.slice_batch` for large-file inspection instead of shell `sed`.
5. Create a dedicated two-variant experiment:
   - `codex-base`
   - focused `codex-onetool-mcp` or `codex-skills-...-onetool-mcp`
6. Run both Harbor trials.
7. Generate report and compare:
   - reward/pass
   - wall time
   - input tokens
   - output tokens
   - total tokens
   - cost
   - evidence that MCP was available and whether it was actually used.

## Candidate Files To Add

Likely add these files rather than modifying the smoke experiment:

- `packages/ot-harness/experiments/terminal-bench-focused-mcp/experiment.yaml`
- `packages/ot-harness/experiments/terminal-bench-focused-mcp/tasks.yaml`
- `packages/ot-harness/variants/codex-onetool-mcp-focused.yaml`
- `packages/ot-harness/skills/focused-mcp/<task-name>/SKILL.md`

Whether to use `codex-onetool-mcp` plus `skill_paths`, or `codex-skills-*` plus `mcp`, depends on the cleanest existing config pattern. The current harness supports MCP on `codex-skills` variants, which is probably best for injecting the focused prompt.

## Important Caveat

Do not claim the agent used OneTool MCP unless the Harbor trajectory/logs prove actual MCP calls. Previous validation proved MCP availability and Docker reachability, but the `fix-git` run solved the task via shell and did not prove tool usage.

## 2026-05-29 Owned-Server Smoke Result

Command run:

```bash
just test-harness-owned-mcp
```

Lifecycle result:

- Started harness-owned OneTool HTTP MCP on `http://127.0.0.1:18768/mcp`.
- Verified readiness with a real FastMCP `ot.status()` call.
- Ran both Harbor variants.
- Stopped the harness-owned child server after completion.
- Confirmed no listener remained on port `18768`.
- Confirmed shared interactive `__run ot.status()` still worked after the test.

Benchmark result for `fix-git`:

| Variant | Reward | Wall time | Tokens | Cost |
|---|---:|---:|---:|---:|
| `codex-base` | `0.0` | `342.298s` | `812724` | `$0.3407236` |
| `codex-skills-smoke-owned-onetool-mcp` | `1.0` | `268.214s` | `520219` | `$0.26311775` |

Report command:

```bash
uv run ot-harness report tmp/harness/harbor/terminal-bench-owned-mcp-smoke --json
```

## 2026-05-29 `pypi-server` Focused MCP Trial

Changed the owned-MCP experiment to run `pypi-server` instead of `fix-git`.

Files changed for the trial:

- `packages/ot-harness/experiments/terminal-bench-owned-mcp/experiment.yaml`
  - Experiment name: `terminal-bench-owned-mcp-pypi`
  - Variants: `codex-base`, `codex-skills-pypi-owned-onetool-mcp`
- `packages/ot-harness/experiments/terminal-bench-owned-mcp/tasks.yaml`
  - Task: `pypi-server`
- `packages/ot-harness/variants/codex-skills-pypi-owned-onetool-mcp.yaml`
  - Focused skill plus harness-owned OneTool HTTP MCP.
- `packages/ot-harness/skills/focused/pypi-server/SKILL.md`
  - Instructs the agent to call:
    - `package.pypi(...)`
    - `ground.search(...)`
    - `ground.docs(...)`
    - `context7.search(...)`
    - `file.slice_batch(...)`

Command run:

```bash
just test-harness-owned-mcp
```

Lifecycle result:

- Started harness-owned OneTool HTTP MCP on `http://127.0.0.1:18768/mcp`.
- Verified readiness with `ot.status()`.
- Ran both Harbor variants.
- The wrapper exited and cleaned up the owned server.
- Confirmed no listener remained on port `18768`.

Benchmark result:

| Variant | Reward | Wall time | Tokens | Cost |
|---|---:|---:|---:|---:|
| `codex-base` | `0.0` | `310.554s` | `546021` | `$0.2798579` |
| `codex-skills-pypi-owned-onetool-mcp` | `0.0` | `328.885s` | `539387` | `$0.2661211` |

Report command:

```bash
uv run ot-harness report tmp/harness/harbor/terminal-bench-owned-mcp-pypi --json
```

Important evidence:

- Harbor config included the MCP server:
  - `tmp/harness/harbor/terminal-bench-owned-mcp-pypi/pypi-server/codex-skills-pypi-owned-onetool-mcp/rep-001/harbor-run.yaml`
  - `mcp_servers: [{name: onetool, transport: http, url: http://host.docker.internal:18768/mcp}]`
- Harbor copied skills into the task container:
  - trial log contains `mkdir -p $HOME/.agents/skills && cp -r /harbor/skills/* $HOME/.agents/skills/`
- The agent read the focused skill:
  - `agent/codex.txt` contains `sed -n '1,200p' /root/.agents/skills/pypi-server/SKILL.md`
- OneTool MCP was actually used:
  - `agent/codex.txt` includes `mcp_tool_call` entries for server `onetool`, tool `run`.
  - `.onetool/runtime/stats/stats.jsonl` for owned server PID `34276` includes calls at `2026-05-29T10:38:56Z` through `10:39:40Z`:
    - `package.pypi`
    - `ground.search`
    - `ground.docs`
    - `context7.search`
    - `file.slice_batch`

Why both variants failed:

- Both agents created a package and self-verified `pip install --index-url http://localhost:8080/simple vectorops==0.1.0` during their own run.
- Both stopped the package server before Harbor's verifier ran.
- The next focused prompt should require a detached process that remains alive after the agent exits, for example:

```bash
nohup python /app/pypi_server.py > /tmp/pypi-server.log 2>&1 &
```

Additional note:

- The `file.slice_batch` OneTool call used `/app/...` paths. The harness-owned OneTool server runs on the host, so those container paths are not visible to OneTool and the call returned `Path not found`. For container task files, use shell reads from inside the task container or make the harness expose/mount task files to the owned MCP server before asking OneTool `file.*` to inspect them.

## 2026-05-29 `pypi-server` Workspace-Mounted MCP Result

Implemented the best solution for file-pack access:

- Each Harbor trial can now get a clean host workspace bind-mounted into the Docker task container.
- The owned OneTool HTTP MCP server starts per MCP trial with `OT_CWD` set to that host workspace.
- The task container sees the same files at `/app`, while OneTool file tools see them through their host path.
- The shared interactive OneTool server is not used and is not stopped.

The focused `pypi-server` skill was also tightened so the agent must leave a detached package server running for Harbor's verifier. The key fix was to make server lifetime part of the task, and to prefer a static PEP 503 simple index served by a detached `python -m http.server` process.

Command run:

```bash
just test-harness-owned-mcp
```

Validation:

```bash
uv run pytest packages/ot-harness/tests/unit -q
uv run ruff check packages/ot-harness/src packages/ot-harness/tests
bash -n scripts/run_ot_harness_owned_mcp.sh
uv run ot-harness report tmp/harness/harbor/terminal-bench-owned-mcp-pypi --json
```

Benchmark result after the fix:

| Variant | Reward | Wall time | Tokens | Cost |
|---|---:|---:|---:|---:|
| `codex-base` | `0.0` | `222.701s` | `372179` | `$0.1558515` |
| `codex-skills-pypi-owned-onetool-mcp` | `1.0` | `328.416s` | `787632` | `$0.30477615` |

Important evidence:

- Owned OneTool readiness reported `cwd` as the trial workspace:
  - `tmp/harness/harbor/workspaces/terminal-bench-owned-mcp-pypi/pypi-server/codex-skills-pypi-owned-onetool-mcp/rep-001`
- The generated Harbor config bind-mounted that workspace into `/app`:
  - `tmp/harness/harbor/terminal-bench-owned-mcp-pypi/pypi-server/codex-skills-pypi-owned-onetool-mcp/rep-001/harbor-run.yaml`
- The MCP trial trajectory contains a real OneTool call:
  - `agent/codex.txt` includes `mcp_tool_call` for server `onetool`, tool `run`.
- OneTool runtime stats for owned server PID `48274` include:
  - `package.pypi`
  - `ground.search`
  - `ground.docs`
  - `context7.search`
  - `file.tree`
- The agent ultimately started the package server with a detached session and left it running for the verifier:
  - `setsid python -m http.server 8080 --directory /app/pypi --bind :: > /tmp/pypi-server.log 2>&1 < /dev/null &`

Conclusion:

- The original `pypi-server` failure was agent solution behavior: the server was stopped before Harbor's verifier.
- The harness did have a separate access flaw for OneTool file tools: host-running OneTool could not see Docker-only `/app` paths.
- The current harness fix addresses the file-pack/CWD mapping problem; the focused skill fix addresses server lifetime.
