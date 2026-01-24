# CLI Reference

**Two CLIs. Serve and benchmark.**

| CLI | Purpose |
|-----|---------|
| [`ot-serve`](ot-serve.md) | MCP server |
| [`ot-bench`](ot-bench.md) | Benchmark harness |

## Configuration

All CLIs follow a consistent configuration pattern:

| CLI | Env Var | Default Path | Fallback |
|-----|---------|--------------|----------|
| `ot-serve` | `OT_SERVE_CONFIG` | `.onetool/ot-serve.yaml` | `~/.onetool/ot-serve.yaml`, then defaults |
| `ot-bench` | `OT_BENCH_CONFIG` | `.onetool/ot-bench.yaml` | Task file config |

**Resolution order:**

1. CLI flags (if provided)
2. Environment variable (if set and file exists)
3. `.onetool/<tool>.yaml` (project config)
4. `~/.onetool/<tool>.yaml` (global config)
5. Built-in defaults

## Common Options

All CLIs support:

- `-v, --version` - Show version and exit
- `--json` - Output as JSON (where applicable)
