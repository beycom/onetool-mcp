## 1. Pack Skeleton

- [ ] 1.1 Create `src/otdev/tools/codegraph_util.py` with `pack = "codegraph_util"`, `pack_aliases = ("cg",)`, and exported functions `status`, `symbols`, `neighborhood`, `flow`, `hotspots`, and `diff_impact`.
- [ ] 1.2 Add shared helpers to resolve `project_path` to the nearest `.codegraph/codegraph.db` without mutating the filesystem.
- [ ] 1.3 Add read-only SQLite connection helpers that validate required CodeGraph tables and columns before running queries.
- [ ] 1.4 Add `LogSpan` coverage for each public tool function.

## 2. Core Graph Queries

- [ ] 2.1 Implement `status()` with counts for files, nodes, edges, unresolved references, languages, node kinds, edge kinds, resolved project path, and database path.
- [ ] 2.2 Implement `symbols()` with query, optional kind/language filters, bounded limit, and compact symbol records.
- [ ] 2.3 Implement symbol resolution shared by `neighborhood()` and `flow()`, including explicit ambiguity results instead of silent selection.
- [ ] 2.4 Implement `neighborhood()` with bounded depth, direction filtering, adjacent symbols, and edge metadata.
- [ ] 2.5 Implement `flow()` with bounded path search between selected source and target symbols.
- [ ] 2.6 Implement `hotspots()` for at least `fan_in` and `fan_out` ordering modes.
- [ ] 2.7 Implement `diff_impact()` by reading git diff line ranges, mapping changed ranges to containing CodeGraph symbols, and walking inbound edges to impacted symbols.

## 3. Proxy Template and Documentation

- [ ] 3.1 Add a disabled shared `codegraph` MCP server template using `codegraph serve --mcp` and `tool_prefix: "codegraph_"`.
- [ ] 3.2 Add `codegraph_util` to tool documentation metadata and generated tool-index inputs.
- [ ] 3.3 Add a user-facing `docs/reference/tools/codegraph-util.md` page explaining `cg.*` structured analytics and proxied `codegraph.explore(...)` source exploration.
- [ ] 3.4 Update any reference indexes that list `[dev]` packs so `codegraph_util` appears consistently.

## 4. Tests

- [ ] 4.1 Add unit fixtures that create a minimal CodeGraph-like SQLite database with `nodes`, `edges`, `files`, and `unresolved_refs`.
- [ ] 4.2 Add unit tests for project resolution, missing index errors, schema validation errors, and read-only behavior.
- [ ] 4.3 Add unit tests for `status()`, `symbols()`, `neighborhood()`, `flow()`, and `hotspots()` against the fixture database.
- [ ] 4.4 Add unit tests for `diff_impact()` using a temporary git repository and fixture CodeGraph database.
- [ ] 4.5 Add tests or config validation coverage for the shared `codegraph` MCP server template.

## 5. Verification

- [ ] 5.1 Run targeted `uv run pytest` tests for the new `codegraph_util` coverage.
- [ ] 5.2 Run `just check`.
- [ ] 5.3 Update this task list as implementation tasks complete.
