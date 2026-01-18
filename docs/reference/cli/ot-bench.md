# ot-bench

**Measure what matters. Tokens, cost, accuracy.**

Real LLM + MCP testing. Define tasks in YAML, get objective metrics: token counts, costs, accuracy scores, timing.

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

## Configuration

Configuration file: `config/ot-bench.yaml` or `.onetool/ot-bench.yaml`

| Variable | Description |
|----------|-------------|
| `OT_BENCH_CONFIG` | Config file path override |

## Output

Benchmarks produce:
- Token counts (input, output, total)
- Cost estimates (USD)
- Timing information
- Evaluation scores

## Related

- [Testing Strategy](../../extending/testing.md) - Test markers and organization
- [Examples](../../examples/index.md) - Demo benchmarks
