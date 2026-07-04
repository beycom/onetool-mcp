## Why

CodeGraph can provide high-value codebase structure, but OneTool users currently have to call the upstream MCP surface directly or query its SQLite database by hand. A small `codegraph_util` companion pack can make CodeGraph useful inside OneTool workflows without vendoring CodeGraph or taking ownership of its indexing engine.

## What Changes

- Add a new `[dev]` `codegraph_util` tool pack, similar in role to `chrome_util` and `play_util`, that complements a configured CodeGraph MCP server.
- Provide structured, read-only helpers for CodeGraph-backed developer workflows such as index health, symbol search, graph neighborhoods, flow paths, hotspots, and git-diff impact.
- Use existing CodeGraph artifacts only: the upstream MCP server for source-oriented exploration and `.codegraph/codegraph.db` for local read-only graph analytics.
- Add an optional shared CodeGraph MCP server template so users can proxy `codegraph serve --mcp` through OneTool.
- Do not vendor CodeGraph, reimplement indexing, or mutate `.codegraph/` data.

## Capabilities

### New Capabilities
- `otdev/tool-codegraph-util`: Defines the `codegraph_util` (`cg`) developer pack for read-only CodeGraph companion queries and upstream CodeGraph MCP integration guidance.

### Modified Capabilities

None.

## Impact

- Adds a new optional `[dev]` tool pack under `src/otdev/tools/`.
- Adds tests under `tests/otdev/` using fixture SQLite data rather than a vendored CodeGraph checkout.
- Adds user-facing tool reference documentation and tool-index metadata for the new pack.
- Adds or updates shared MCP server configuration templates to include a disabled CodeGraph server entry.
- Depends on users installing and initializing upstream CodeGraph separately; OneTool does not bundle CodeGraph.
