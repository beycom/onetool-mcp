# Review: Does CodeGraph Deliver, and Does This Pack Add Value?

Assessment from live testing (2026-07-04) against upstream
`@colbymchenry/codegraph` proxied through OneTool on this repository
(437 files, 8,673 nodes, 21,250 edges). Guidance for scoping and
prioritizing this change going forward.

## Does CodeGraph deliver real benefit?

**Yes, but narrower than its branding suggests.**

### Where it is genuinely good

- **Relationship queries beat grep decisively.** `callers()` and `impact()`
  returned exact, resolved answers in milliseconds. A grep for a common name
  like `restart` returns hundreds of false hits; the graph disambiguates by
  symbol identity, not string match. This is the core value and it is real.
- **Test discovery via `impact` is a killer feature.** `impact('restart')`
  named the exact 4 test functions covering the symbol — precisely what a fix
  workflow needs, and something grep cannot do without reading files.
- **Token economics favor it for weaker models.** One bounded call replaces
  the iterative grep -> read -> refine loop that weak models drive poorly.
  `node(file=...)` returning Read-equivalent output plus blast radius is
  strictly better than Read for indexed source files.

### Where it is oversold

- **"Semantic" is really lexical.** A natural-language query ("how are pack
  aliases resolved and injected") matched the wrong symbols entirely
  (`file.resolve()`, `ot.aliases()`), and `explore` missed the actual
  mechanism (`tool_loader.py` collection site) that a competent grep session
  finds. The "usually the only call you need" claim did not hold under test.
  Bags of symbol/file names work; generic verbs do not.
- **Static analysis is blind to dynamic dispatch.** OneTool's core mechanism —
  injecting pack proxies into an execution namespace at runtime — produces
  call edges no tree-sitter parse can see. The graph structurally understates
  this repo's most important coupling. This generalizes to any
  decorator/registry/DI-heavy Python project and should be permanently
  attached as a caveat to impact/flow outputs.
- **Marginal for strong models in familiar repos.** A capable model with
  repo memory answers structural questions faster than the explore loop.

**Net:** real benefit for relationship, impact, and test-coverage queries; in
unfamiliar large repos; and disproportionately for weaker models. Not a
replacement for text search or model reasoning.

## Does the OneTool extension add value?

Split verdict.

### Proxy configuration: unambiguously yes (already validated live)

`tool_prefix: "codegraph_"` + `env.CODEGRAPH_MCP_TOOLS` exposing all eight
tools + an `instructions` block cost three lines of YAML and transformed the
experience from one lexically-fragile explore tool into a usable toolkit.
Upstream hides seven of eight tools to save raw-client context — a cost
OneTool's lazy tool discovery does not pay. Highest ROI item in the change;
the template work (task 3.1) should be treated as the non-negotiable core.

### The `cg` pack: yes, but only for its differentiated half

With all eight upstream tools exposed through the proxy, `symbols()`,
`neighborhood()`, and `flow()` mostly re-deliver upstream
`search`/`callers`/`callees`/`explore` with nicer return types. Structured
dicts are worth something for composition inside `run()`, but not three
tools' worth of implementation and maintenance.

The parts upstream **cannot** do, because they require git or trust auditing:

1. **`status()` with staleness + parse errors** — the DB-direct approach
   reads whatever is on disk; without staleness detection it silently serves
   stale answers. `files.content_hash` / `modified_at` / `indexed_at` /
   `errors` make this a column read. Nothing upstream answers "can I trust
   this graph right now?"
2. **`hotspots(by="risk")` (churn x fan-in)** — needs git history joined to
   graph fan-in; the DB alone can never produce it. File-level churn only
   (symbol-level churn across renames is the too-complex version).
3. **`diff_impact()` / `affected_tests()`** — diff-scoped impact needs git;
   upstream `impact` is symbol-scoped only. Changed-lines -> symbols ->
   inbound edges -> covering tests is the flagship agent workflow.

### Scoping guidance for v3

- **Core (build first):** server template upgrades; `status()` with trust
  signals; `diff_impact()`; `hotspots()` including `by="risk"`; the agent
  guidance surfaces (teaching errors, docstring examples, snippets, query
  cookbook) — weaker models only ever see signatures and error strings.
- **Demote to thin conveniences or a later wave:** `symbols()`,
  `neighborhood()`, `flow()`. Keep them only if they stay thin wrappers over
  simple queries; do not invest in ranking or traversal sophistication that
  duplicates upstream.
- **The defensible claim** for this pack is not "better CodeGraph queries" —
  it is "CodeGraph joined with git and trust signals, composable in one
  `run()` call." Scope decisions should be tested against that sentence.

## Operational notes from testing

- `projectPath` can be omitted when the server runs from the project root;
  guidance should say "omit it."
- Config edits to `servers.yaml` require `ot.reload()` before
  `ot_servers.restart()` — restart alone reuses stale in-memory config (filed
  as `wip/issues/1-new/server-restart-uses-stale-config.md`).
- Ambiguous `node()` calls return a candidate list plus a re-query hint —
  good behavior worth mirroring in `cg.*` ambiguity results.
- Live schema confirmed: `nodes`, `edges`, `files`, `unresolved_refs`,
  `schema_versions`, `project_metadata`. Validate via `schema_versions`
  first; copy the real DDL into test fixtures.
