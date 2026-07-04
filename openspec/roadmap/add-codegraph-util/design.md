## Context

OneTool already supports external MCP servers as Python namespaces, and the
`chrome_util` / `play_util` packs demonstrate a useful companion pattern: a local
OneTool pack adds ergonomic helpers around a separately configured MCP server.
CodeGraph fits the same model, but its value is code structure rather than
browser annotation.

CodeGraph itself is a Node/TypeScript static-analysis product that owns Tree-sitter
parsing, `.codegraph/codegraph.db`, file watching, daemon sharing, and MCP output
formatting. Vendoring those responsibilities would add a large second runtime and
make OneTool responsible for upstream schema, parser, and freshness behavior. The
companion pack should therefore consume CodeGraph outputs rather than replace them.

### Validated behaviors (live testing, 2026-07-04)

Tested against upstream `@colbymchenry/codegraph` proxied through OneTool with
`tool_prefix: "codegraph_"` (verified working) and
`env.CODEGRAPH_MCP_TOOLS: "explore,search,node,status,files,callers,callees,impact"`
(all eight tools connect; upstream hides seven by default to save raw-client
context, which is irrelevant behind OneTool's lazy tool discovery):

- `projectPath` can be omitted when the server runs from the project root —
  guidance for agents should say "omit it" rather than teach path resolution.
- Query matching is lexical (FTS over symbol names). Bags of symbol/file names
  work well; natural-language phrasing with generic verbs ("how is X resolved")
  matches the wrong symbols.
- `node()` defaults `includeCode=false` (locations only); agents forget this.
  Ambiguous names return a candidate list plus a re-query hint — good behavior
  worth mirroring in `cg.*` ambiguity results.
- Unknown symbols return clean error strings; `impact()` reliably surfaces the
  test functions covering a symbol.
- Live schema confirmed: `nodes`, `edges`, `files`, `unresolved_refs`, plus
  `schema_versions` (use for version validation) and `project_metadata`.
  `files` carries `content_hash`, `modified_at`, `indexed_at`, and `errors`
  (JSON) — staleness and parse-error reporting are simple column reads.

## Goals / Non-Goals

**Goals:**

- Provide a `[dev]` `codegraph_util` pack with `cg` as a short alias.
- Make CodeGraph useful in OneTool scripts through structured, read-only graph
  analytics.
- Keep CodeGraph installation, indexing, watching, and upstream source exploration
  owned by the upstream `codegraph` CLI/MCP server.
- Allow users to point the pack at a project path and have it resolve the nearest
  `.codegraph/codegraph.db`.
- Provide actionable outputs for common engineering workflows: health checks,
  symbol lookup, neighborhoods, flow paths, hotspots, and git-diff impact.
- Add a disabled shared MCP server template for `codegraph serve --mcp` so users
  can proxy upstream `codegraph_explore` through OneTool when desired.

**Non-Goals:**

- Do not vendor CodeGraph source, grammars, database migrations, or CLI code.
- Do not create or update `.codegraph/` indexes.
- Do not mutate CodeGraph SQLite data.
- Do not guarantee compatibility with arbitrary future CodeGraph schema versions
  beyond clear validation and error reporting.
- Do not replace upstream `codegraph_explore`; source-heavy exploration remains
  the responsibility of the proxied CodeGraph MCP server.

## Decisions

1. **Use a companion pack, not a vendored engine.**

   The pack will live under `src/otdev/tools/` and expose `pack = "codegraph_util"`
   plus `pack_aliases = ("cg",)`. This matches existing developer utility packs
   and avoids adding a new runtime boundary inside OneTool.

   Alternative considered: vendor CodeGraph or reimplement indexing in Python.
   Rejected because CodeGraph's complexity is in parsing, sync, daemon sharing,
   and schema evolution, not in a small MCP wrapper.

2. **Read `.codegraph/codegraph.db` directly for structured analytics.**

   The pack will open the database in SQLite read-only mode and set query-only
   behavior. It will resolve a `project_path` by walking upward to the nearest
   `.codegraph/codegraph.db`, matching CodeGraph's user model. Results should be
   native Python dictionaries/lists, not serialized JSON strings.

   Alternative considered: call CodeGraph CLI subcommands for every helper.
   Rejected for the first version because CLI output is less stable and less
   composable than the database for analytic summaries.

3. **Keep upstream MCP exploration available through OneTool proxy.**

   The shared server template will define a disabled `codegraph` stdio server
   using `codegraph serve --mcp` and `tool_prefix: "codegraph_"`, so
   `codegraph_explore` can be called as `codegraph.explore(...)`.
   The template SHALL also set
   `env.CODEGRAPH_MCP_TOOLS: "explore,search,node,status,files,callers,callees,impact"`
   — upstream hides seven of its eight tools by default to conserve raw-client
   context, a cost OneTool's lazy tool discovery does not pay — and an
   `instructions` block teaching the verified gotchas (see Decision 6).
   The companion pack may provide guidance/status around this, but it should not
   depend on the upstream MCP server being connected for database-only helpers.

   Alternative considered: make every `codegraph_util` function proxy through the
   CodeGraph MCP server. Rejected because the useful OneTool-specific value is
   structured graph data that composes inside Python runs.

4. **Start with high-signal read-only tools.**

   Initial public functions should be:

   - `status(project_path=".")`
   - `symbols(query, project_path=".", kind=None, language=None, limit=20)`
   - `neighborhood(symbol, project_path=".", depth=1, direction="both", limit=100)`
   - `flow(source, target, project_path=".", max_depth=6, limit=50)`
   - `hotspots(project_path=".", by="fan_in", limit=20)`
   - `diff_impact(project_path=".", ref="HEAD", limit=100)`

   These cover both immediate diagnostics and workflows that benefit from
   combining CodeGraph with OneTool's shell, git, test, and LLM tools.

5. **Degrade clearly when CodeGraph is absent or unsupported.**

   Missing `codegraph` CLI should not break database-only helpers. Missing
   `.codegraph/codegraph.db` should return an error string telling the caller that
   the project is not indexed and that the user can run `codegraph init`.
   Schema validation should check the `schema_versions` table first and report
   the found version; unknown or incomplete schemas should return an error naming
   the missing required tables or columns.

6. **Design every surface for agents that have never seen CodeGraph.**

   Weaker models will use this pack knowing nothing beyond what OneTool shows
   them at call time. Four concrete measures:

   - **Teaching errors.** Every error string names the next call to make, not
     just the failure: "project is not indexed — run `codegraph init` from the
     project root", "3 symbols match 'run' — pass file= to pin one, e.g.
     cg.neighborhood(symbol='run', file='src/ot/executor/runner.py')". This
     mirrors upstream's ambiguity hint, which tested well.
   - **Docstring examples.** Every `cg.*` function docstring carries an
     `Example:` section (the existing pack convention), because
     `ot.tools(info='signatures')` and `ot.help()` are the only documentation a
     mid-task agent sees. Examples use symbol-name queries, never
     natural-language phrasing.
   - **Snippets for canned workflows.** Server-side snippets so weak models can
     invoke whole workflows with one short line: `:cg_impact symbol=X` (impact +
     covering tests), `:cg_find q=X` (symbols + top neighborhood), `:cg_health`
     (status + staleness). Snippet mode needs no Python fluency.
   - **Query cookbook in docs.** The docs page leads with "prefer bags of
     symbol/file names; generic natural-language verbs match the wrong symbols"
     and a table of task → right call (read a file body → proxied
     `codegraph.node(file=..., includeCode=True)`; structured fan-in →
     `cg.hotspots`; blast radius before an edit → `cg.diff_impact`).

   The proxied `instructions` block carries the same two highest-value rules
   (includeCode default, symbol-name queries) so raw-proxy users get them even
   without the pack installed.

## Risks / Trade-offs

- **CodeGraph schema changes** -> Validate required tables/columns before running
  queries and return clear unsupported-schema errors.
- **Static graph false positives/negatives** -> Use names like `dead_candidates`
  only if added later; for initial impact/flow outputs, include edge kinds and
  provenance where available so callers can judge confidence.
- **Database locking** -> Open read-only, keep queries bounded, avoid long write
  transactions, and do not run migrations or PRAGMA changes that mutate the DB.
- **Git diff mapping can be approximate** -> Map changed line ranges to containing
  symbols when possible and include unmatched changed files separately.
- **Two CodeGraph entrypoints may confuse users** -> Documentation should explain:
  use proxied `codegraph.explore(...)` for source context, use `cg.*` for
  structured analytics.
