# OneTool Skill Capability Coverage Review

## Outcome

The repository has 28 runtime packs, including beta `console`. The audit also inspected 138 rows
from the non-authoritative historical `features/features.yaml` file as leads only; that file is not
an implementation input and may be removed. The existing 20-skill catalog is too shallow to cover
the verified code-backed runtime surfaces. The proposed `pack-guidance-help-and-setup` change
supplies the right DRY foundation, extended with:

1. a dedicated `ot-runtime` skill;
2. full removal of beta `console` from every distributed skill artifact, including `ot-ref`
   generated references;
3. public read-only proxy resource/prompt operations;
4. the detailed pack-matrix corrections identified below; and
5. correction of stale specification, architecture, documentation, and installation contracts.

No standalone skills are warranted for `otpack`, security, individual research providers, or
knowledge administration. Those concerns fit developer guidance, deterministic help topics, and
their existing owning skills without creating more routing ambiguity.

## Review contract and coverage

- Revision: `528cac463d21f3b510757e106d31ad310591d56b` (dirty only with the session's
  OpenSpec and review artifacts).
- Method: static repository inspection only.
- Dimensions: requirements/spec alignment, documentation/developer experience, architecture
  boundaries, and security/privacy guidance.
- Completed scopes: all 138 feature rows; all stable/beta pack entry points; all 16 bundled
  `otpack` modules; core run/discovery/config/direct/proxy/security/operations surfaces; the current
  skills, router, catalog, validators, generators, and proposed change.
- Excluded: tests, fixtures, generated reference bodies except targeted evidence, archived changes,
  builds, task runners, application execution, package installation, and network services.
- Commands run: static file discovery/search/inspection and Git metadata only.

Coverage is high for public capability surfaces and current signatures. It is medium for
live-service behavior, packaging execution, and test adequacy because those were intentionally not
executed or reviewed.

## Non-authoritative feature-file audit leads

This table records how historical feature-file values led the audit to code surfaces worth
checking. It is evidence from this review only. No implementation, catalog, generator, validator,
test, build, or release process should read this table or `features/features.yaml`.

| Historical value | Rows | Audit lead / verified guidance conclusion |
|---|---:|---|
| `arch` | 6 | `ot-arch` plus workflow/setup/config topics |
| `brave` | 2 | `ot-research` selection plus Brave workflow/setup topics |
| `ground` | 3 | `ot-research` selection plus Ground workflow/setup topics |
| `tavily` | 1 | `ot-research` selection plus Tavily workflow/setup topics |
| `context7` | 2 | `ot-research` selection plus Context7 workflow/setup topics |
| `package` | 2 | `ot-research` selection plus Package workflow topics |
| `webfetch` | 3 | `ot-research` selection plus Webfetch safety/workflow topics |
| `brave/ground/tavily` | 1 | Derived composite of the three research providers; no separate skill |
| `brave/webfetch/tavily/ctx` | 1 | Led to research-selection and `ot-context` output-handling review |
| `chrome_util/play_util` | 3 | `ot-browser-guidance` for annotations and `ot-mcp-proxy` for browser control |
| `play_util` | 1 | Same boundary, including Playwright-only auto-inject |
| `convert` | 2 | `ot-convert` |
| `db` | 2 | `ot-db` |
| `diagram` | 3 | `ot-diagram` plus policy/providers/templates topics |
| `excel` | 2 | `ot-excel` |
| `file` | 7 | `ot-file` |
| `ripgrep` | 3 | Reassign to `ot-file` with fast-search selection guidance |
| `knowledge` | 4 | Expand `ot-knowledge` to cover query plus CLI build/maintenance lifecycle |
| `mem` | 10 | `ot-mem` with complete lifecycle and maintenance topics |
| `localhist` | 2 | `ot-localhist` |
| `whiteboard` | 7 | `ot-whiteboard` plus complete packaged DSL topic |
| `ot_context` | 5 | `ot-context` |
| `ot_context/ot` | 1 | Led to `ot-context` retrieval plus `ot-ref` large-result deflection review |
| `ot_forge` | 1 | `ot-forge`, limited to current extension create/validate behavior |
| `ot_image` | 4 | `ot-image` |
| `ot_llm` | 1 | `ot-llm` |
| `ot_secrets` | 3 | `ot-secrets` |
| `ot_servers` | 1 | Replace `ot-servers` with `ot-mcp-proxy` |
| `ot_timer` | 2 | `ot-ref`; too small for a separate skill |
| `ot` | 5 | `ot-ref` for call/discovery; `ot-runtime` for ongoing diagnostics/operations |
| `core` | 14 | `ot-ref` for execution mechanics; `ot-runtime` for serving/health/operations |
| `cli` | 3 | `ot-setup` for bootstrap/config; `ot-runtime` for serving/transports |
| `config` | 9 | `ot-setup` plus deterministic config topics; runtime-only settings in `ot-runtime` |
| `direct` | 4 | `ot-runtime` plus compact invocation mechanics in `ot-ref`; correct stale rows first |
| `proxy` | 2 | `ot-mcp-proxy` |
| `security` | 3 | Mandatory `ot-ref` safety section/topic; setup diagnostics for config readiness |
| `stats` | 1 | `ot-runtime` operations plus compact `ot-ref` discovery |
| `deploy` | 1 | `ot-runtime`/`ot-setup`; no Docker-only skill |
| `packaging` | 2 | `ot-setup` and developer packaging guidance |
| `skills` | 1 | `ot-ref` distribution plus canonical skill-development/pack-guidance guide |
| `docsgen` | 1 | Developer pack-guidance guide and DRY generators; no runtime skill |
| `testing` | 1 | Developer pack-guidance validation checklist; no runtime skill |
| `logging` | 1 | Pack-development guide; runtime diagnostics in `ot-runtime` |
| `otpack` | 1 | Pack-development guide, setup topics, and owning-pack guidance; no skill |
| `multiple` | 1 | Internal cross-pack maintenance disposition; replace the ambiguous ledger value |
| `console` | 3 | Explicit beta exclusion: public beta docs only, no skill/router/reference projection |

## Pack guidance corrections required

The current OpenSpec matrix has the right shape but still contains or omits material runtime facts.
The implementer should treat the following as required content, not optional examples:

- Forge is `create_ext`/`validate_ext`; validation is static and does not inspect multiple
  templates or behavior.
- Secrets has `init/status/audit/set/get/unset/encrypt/rotate`, no `list`; include forced identity
  replacement, plaintext backup risk, atomic round-trip verification, and protected-file retrieval.
- Brave includes video and structured batch envelopes; Tavily exposes `research`, not `answer`,
  plus search/extract batches and materially different costs.
- Architecture starts with `validate`, not `ingest`; cover Excel↔YAML round-trip, filters/profiles,
  incremental/force behavior, external renderer trust, and bundle verification.
- Whiteboard needs named boards, additive DSL drawing, notes, sync/embedded DSL, state-versus-browser
  operations, exact save/screenshot/share semantics, and clear/close/hard-reset distinctions.
- Memory needs its full batch, history/rollback, file freshness, dump/load, snapshot/restore, decay,
  reindex, background embedding, flush, and dry-run maintenance lifecycle.
- Knowledge must distinguish MCP CRUD/retrieval/synthesis from CLI index/reindex/enrich/scrape,
  including hybrid degradation and graph/citation behavior.
- File needs resolution modes, TOC/slice/batches, dry-run/backup/atomic edit, overwrite/trash, and
  symlink rules; Excel needs full table/workbook and structural mutation coverage.
- Ground needs dev/docs/reddit, batches, extraction/provenance; Context7 `doc` auto-resolves an
  unambiguous library and explicit search is for ambiguity/recovery.
- DB defaults `read_only=False` and uses AUTOCOMMIT; a read-only account is the real boundary.
- Diagram needs public-renderer privacy, source-bearing URLs, async polling, and self-hosted-only
  batch/directory guidance.
- Browser helpers need inject/highlight/scan/clear/guide, plus Playwright-only auto-inject.
- Localhist needs exclude/force-include safety, path-scoped inspection, pre-restore snapshots, and
  destructive prune/GC implications.
- Package is version/staleness lookup, not vulnerability or lockfile analysis; include OpenRouter
  model discovery.
- Webfetch needs raw non-HTML behavior, cache/freshness, extraction tradeoffs, bounded downloads,
  and the fact that private-URL blocking is optional/best-effort.
- Image needs multi-image limits, handle/dedup behavior, clipboard limitations, cached summaries,
  and list/delete/purge lifecycle.
- LLM needs file mutation, untrusted-data framing, lack of retry/input bound, and validation.
- Server enable/disable is session-only; restart rereads only the named on-disk entry.
- Context is also the automatic large-result backend, not only a manual retrieval pack.

## Platform guidance and contract corrections

- Add `ot-runtime` for root server versus outbound proxy, stdio/HTTP serving, safe loopback binding,
  Direct API auth/discovery/readiness, status/debug/reload, statistics, telemetry, logs/results, and
  operational recovery. Root HTTP has no built-in authentication; non-loopback use must require an
  explicitly secured deployment.
- Make `ot-ref` state prominently that the Python execution surface has full builtins and AST
  validation is defense-in-depth, not a sandbox. The trust boundary is the process/user/environment.
- Correct Direct CLI claims: current public CLI has only `onetool direct run`, requires an
  already-running process and explicit port, and uses positional `-` for stdin.
- Add public read-only `ot.resources`, `ot.resource`, `ot.prompts`, and `ot.prompt` operations over
  the manager's existing list/read/list/render behavior.
- Keep Python `[all] = [util,dev]` and explicitly document that `[scrape]` remains separately
  opt-in, so `[all]` does not mean every optional capability.
- Correct root MCP resource detail for proxy tools, stale explicit-config architecture docs, and
  documentation that overstates extension worker isolation.
- Correct MCP discoverability specs from `onetool://...` to current `ot://...` and from
  `destructiveHint=false` to the run tool's actual destructive-capable annotation.

## Historical feature-file observations

The historical file contained stale or free-form material:

- its coverage hash is stale;
- its singular canonical `pack` contract is violated by composite and pseudo-area strings;
- Direct CLI/API rows advertise removed commands and context-sync behavior;
- Webfetch uses a config field as a call kwarg;
- Localhist uses removed `keep_days`;
- Context7 examples omit required `library_name`;
- knowledge CLI examples use removed options;
- several context examples pass arbitrary dictionaries that current `ctx.write` rejects.

These observations were used only to locate authoritative code and public documentation for the
audit. The file SHALL NOT be normalized, parsed, validated, composed with the typed catalog, used
as a test oracle, or made a build/release dependency. The resulting issue draft was rejected after
the user clarified that the file is non-authoritative historical/changelog tracking.

## DRY maintenance model

Use the typed runtime catalog as the relationship source, without any dependency on
`features/features.yaml`:

- runtime pack records declare their skill owner and help topics once;
- generators project skill coverage, router rows, profile membership, pack maps, help inventories,
  and public docs;
- check mode renders in memory and reports exact stale catalog projections;
- generated `ot-ref` artifacts exclude beta `console`, while public beta reference docs may retain
  it. The skill and public-doc indexes therefore come from the same inventory with different
  filters and are not byte-identical.

## Additional skill recommendations

### Recommend adding: `ot-runtime`

Make it user- and model-invocable. It owns the ongoing operational lifecycle after setup:
root serving/transports, Direct API, diagnostics, reload, statistics, telemetry, safe exposure, and
recovery. It hands configuration/install changes to `ot-setup` and outbound MCP server lifecycle to
`ot-mcp-proxy`.

### Do not add: `ot-security`

Security changes every OneTool call rather than forming a separate workflow. Require a semantic
safety section and deterministic security topic in `ot-ref`; reconsider a separate skill only if
that material cannot fit the generous ceiling.

### Do not add: `ot-knowledge-admin`

Indexing, enrichment, scraping, and reindexing are the administrative half of the same configured
knowledge-base lifecycle. Expand `ot-knowledge` with separate “build/maintain” and “query/use”
workflows rather than forcing agents to choose between two owners for one database.

### Do not add: `otpack`, provider-specific, browser-server-specific, Docker-only, or console skills

`otpack` is a pack-author SDK; provider/server details are better supplied by current help/docs;
Docker is one runtime deployment; and beta `console` is explicitly excluded.

## Findings and accounting

- Accepted issues: 0.
- Critical/high/low issues: 0.
- Rejected drafts: 1 feature-ledger validation proposal; the file is intentionally
  non-authoritative and outside implementation architecture.
- No findings does not apply to unexecuted tests/live integrations; those remain not reviewed.

## Approved decisions

1. **Runtime skill**
   - Add user- and model-invocable `ot-runtime`.

2. **Proxy resources and prompts**
   - Add public read-only `ot.resources`, `ot.resource`, `ot.prompts`, and `ot.prompt`, then cover
     their safe use in `ot-mcp-proxy`.

3. **Historical feature tracking**
   - `features/features.yaml` is non-authoritative changelog tracking only. It SHALL NOT be used by
     runtime code, catalogs, generators, validators, tests, builds, or release gates.

4. **Knowledge administration**
   - Keep one `ot-knowledge` skill with distinct build/maintain and query/use workflows.

5. **`[all]` extra**
   - Keep `[all] = [util,dev]`; retain the name but state explicitly that `[scrape]` is separately
     opt-in and `[all]` does not mean every optional capability.
