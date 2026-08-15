# Worker Warm-Runtime Baseline

Measured on 2026-08-16 with Codex CLI 0.147.0 on macOS 26.5.2 arm64. The
benchmark starts and deletes a fresh thread without starting a model turn, so it
isolates app-server initialization, the first protocol event, thread start, and
total pre-turn duration. Run it with:

```bash
uv run python dev/benchmarks/worker_warm_runtime.py --iterations 5 --project .
```

## Baseline

| Project | Cold initialization | Cold first event | Cold thread start | Cold pre-turn | Warm median pre-turn | Improvement |
|---|---:|---:|---:|---:|---:|---:|
| OneTool worktree | 119 ms | 57 ms | 109 ms | 429 ms | 191 ms | 55.4% |
| Minimal temporary project | 110 ms | 46 ms | 94 ms | 295 ms | 159 ms | 46.0% |

The acceptance target was at least a 30% median pre-turn reduction on both
representative project shapes. Both samples clear it, so warm reuse is the
default. Explicit disabled mode remains available for cold comparison and
debugging.

## Reusable boundary

The reusable unit is one initialized Codex app-server process and the eligible
thread-independent transports it owns. Every probe and real episode still starts
and deletes a distinct thread. Per-episode thread state, Chat, Context, developer
input, tool results, and reasoning are ineligible for reuse. Disabled mode and
isolation-key changes reconnect by starting a new process.

The isolation key covers the canonical project, inherited execution boundary,
exact environment identity, and content identities for effective Codex/MCP and
credential configuration without retaining secret values.
