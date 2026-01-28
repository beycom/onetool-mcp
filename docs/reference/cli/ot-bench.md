# ot-bench

**Measure what matters. Tokens, cost, accuracy.**

Real agent + MCP testing. Define tasks in YAML, get objective metrics: token counts, costs, accuracy scores, timing.

## Usage

```bash
ot-bench [COMMAND] [OPTIONS]
```

## Commands

### run

Run benchmark tasks from a YAML file.

```bash
ot-bench run FILE [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--tui` | Interactive TUI for selecting benchmark files |
| `--csv` | Export results to CSV in `tmp/result-YYYYMMDD-HHMM.csv` |
| `--scenario NAME` | Run only scenarios matching NAME |
| `--task NAME` | Run only tasks matching NAME |
| `--tag TAG` | Run only tasks with matching tag |
| `--verbose` | Show detailed per-call metrics |

## Task Types

| Type | Description |
|------|-------------|
| `type: direct` | Direct MCP tool invocation (no LLM) |
| `type: harness` | LLM benchmark with MCP servers (default) |

## Examples

```bash
# Run feature benchmarks
OT_CWD=demo ot-bench run demo/bench/features.yaml

# Run specific tool benchmark
OT_CWD=demo ot-bench run demo/bench/tool_brave_search.yaml
```

## Benchmark File Structure

```yaml
defaults:
  timeout: 60
  model: openai/gpt-5-mini

evaluators:
  accuracy:
    model: openai/gpt-5-mini
    prompt: |
      Evaluate this response.
      Response: {response}
      Return JSON: {"score": <0-100>, "reason": "<explanation>"}

scenarios:
  - name: Search Test
    tasks:
      - name: "search:base"
        server:              # No server = baseline
        evaluate: accuracy
        prompt: "Search for AI news"

      - name: "search:onetool"
        server: onetool
        evaluate: accuracy
        prompt: |
          __ot `brave.search(query="AI news")`

servers:
  onetool:
    type: stdio
    command: uv
    args: ["run", "ot-serve"]
```

### Multi-Prompt Tasks

Use `---PROMPT---` delimiter to split a task into sequential prompts. Each prompt completes its agentic loop before the next begins, with conversation history accumulating.

```yaml
- name: multi-step-task
  server: onetool
  prompt: |
    __ot
    ```python
    npm = package.version(registry="npm", packages={"express": "4.0.0"})
    ```
    Return the latest version.
    ---PROMPT---
    __ot
    ```python
    pypi = package.version(registry="pypi", packages={"httpx": "0.20.0"})
    ```
    Return the latest version.
    ---PROMPT---
    Summarize both versions as: "express: [version], httpx: [version]"
```

## Configuration

Configuration file: `.onetool/config/ot-bench.yaml` (project) or `~/.onetool/ot-bench.yaml` (global)

| Variable | Description |
|----------|-------------|
| `OT_BENCH_CONFIG` | Config file path override |

## Output

Benchmarks produce:
- Token counts (input, output, total)
- Cost estimates (USD)
- Timing information
- Evaluation scores