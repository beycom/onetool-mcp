## Context

OneTool currently has several independently maintained descriptions of the same capability:

- runtime modules declare `pack`, `pack_aliases`, `doc_slug`, `Config`, tool docstrings, and
  heterogeneous `__ot_requires__` values;
- `prompts.yaml` declares one-line pack summaries that are also returned as pack instructions;
- `src/otdev/docsgen/metadata.py` separately maps display names, extras, docs paths, and skill
  owners, while `CURATED_SKILLS` and `PROFILE_SKILLS` repeat derivable membership;
- capability skills repeat availability and advisory text, but omit much of the selection,
  sequencing, configuration, safety, and verification knowledge found in pack code and docs;
- public docs and the `ot-ref` reference are partly generated, but many pack highlights,
  prerequisites, setup instructions, and links remain hand-maintained;
- `ot.help()` can resolve tools, configured packs, servers, snippets, and aliases, but cannot
  address a named topic, expose a pack's config schema, describe generic proxy configuration, or
  compose live setup readiness from the active environment.

The implementation must preserve OneTool's compact-discovery advantage. Skills should teach
judgment; exact current signatures and large references should be pulled only when needed through
`ot.help()` or the generated index. Installed skills may run without a repository checkout, and an
agent connected to a remote OneTool server may not be able to read that server's filesystem.

## Goals / Non-Goals

**Goals:**

- Make the strategic power, safe workflow, and verification path of every stable built-in pack
  clear to an agent without copying its complete API into a skill.
- Declare every non-derivable relationship once and derive all mechanical projections.
- Make `ot.help()` the version-correct, runtime-accessible source for detailed workflows, setup,
  config, DSL, policy, provider, template, and proxy-server guidance.
- Give agents an explicit, safe setup workflow for OneTool packs and arbitrary MCP proxy servers.
- Detect drift among runtime packs, dependencies, config models, skills, generated docs, and
  published links before release.
- Leave an implementation plan detailed enough that an implementer does not need to rediscover
  pack ownership, source boundaries, safety rules, or audited documentation defects.

**Non-Goals:**

- Generate an entire capability skill from metadata. Selection and operating judgment remain
  authored.
- Copy every tool signature or reference page into every skill.
- Add a general-purpose package installer, config mutation MCP tool, or secret-valued diagnostic.
- Automatically install dependencies, start external services, edit config, grant OAuth scopes, or
  add credentials merely because a prerequisite is absent.
- Maintain a OneTool catalog of third-party MCP server presets. Server launch and authentication
  contracts change too quickly; setup must consult current authoritative MCP documentation.
- Create separate static skills for Playwright, Chrome DevTools, Azure, or every proxied server;
  their current native instructions and schemas are discovered live.
- Preserve the old `ot-servers` skill name or heterogeneous `__ot_requires__` declarations.

## Decisions

### 1. Compose facts; do not create a monolithic duplicate

The implementation SHALL use one source for each fact and a composed read model for consumers:

| Fact | Authoritative source |
|---|---|
| Pack/tool identity, signatures, descriptions, aliases | runtime modules and registry |
| Pack config fields, defaults, validation, descriptions | declared Pydantic config model |
| Python/CLI/secret/server/config prerequisites | normalized `__ot_requires__` |
| Distribution extra, display name, default summary, skill owner | typed guidance catalog |
| Skill name, role, invocation policy, Foundation membership | typed skill catalog |
| Help topic names and packaged resource/provider references | typed help-topic catalog |
| User overrides for summaries/server instructions | active OneTool config |
| Proxy transport fields, validation, and defaults | `McpServerConfig` schema |
| Third-party server launch/auth details | current authoritative MCP server documentation |
| Tool/pack operating judgment | authored skill body and packaged help resources |

A runtime-safe catalog package under `src/ot/` SHALL define typed catalog entries without importing
optional pack implementations. `otdev.docsgen` SHALL consume the same package; runtime code SHALL
not import `otdev.docsgen`.

The composed catalog SHALL join static entries to the loaded runtime registry and active config.
It SHALL fail validation on missing/duplicate stable packs, owners, skills, help topics, extras,
docs slugs, or config hooks rather than silently inventing defaults. A beta pack may be excluded
from skill ownership only when its catalog entry records beta status and an explicit exclusion
reason.

Alternative considered: make `prompts.yaml`, Markdown, or `src/otdev/docsgen/metadata.py` the whole
catalog. Rejected because runtime help needs the catalog in installed core environments, Markdown
is not typed, prompt config is user-overridable, and docs-generation code is the wrong runtime
dependency direction.

### 2. Derive skill membership and projections from typed roles

Replace parallel `CURATED_SKILLS`/`PROFILE_SKILLS` declarations with typed `SkillCatalogEntry`
records. At minimum, roles SHALL distinguish:

- shared reference;
- catalog router;
- setup/operations guide;
- pack capability owner;
- cross-pack selection guide.

Profile membership SHALL be derived as:

- Foundation: all entries explicitly marked Foundation;
- Core: Foundation plus owners of core packs and entries explicitly assigned the Core operational
  role;
- Core + `[util]`: Core plus owners of `[util]` packs;
- Core + `[dev]`: Core plus owners of `[dev]` packs;
- `[all]`: every catalog skill.

Tests SHALL validate derivation and externally documented membership, not repeat a second
hard-coded owner map or exact catalog counts.

### 2a. Publish derived installation profiles through the standard skills installer

The former local issue
`wip/issues/1-new/add-onetool-skill-installation-profiles.md` belongs in this change because the
catalog/profile refactor changes the exact memberships it asked documentation to freeze. Its
still-valid acceptance criteria are incorporated here, so no separate issue artifact remains; this
OpenSpec change supersedes its fixed 20-skill/count assumptions.

User documentation SHALL present Foundation, Core, Core + `[util]`, Core + `[dev]`, and skill
`[all]` as derived selection recipes, not native named profiles and not hard-coded counts. It SHALL:

- use the current upstream `npx skills@latest add <OneTool repository>` installation flow;
- document the interactive picker and verified explicit skill-selection syntax;
- recommend `ot-ref` in composed profiles while preserving individual capability installation;
- verify list, discovery, selective install, update, and removal in clean temporary environments
  for supported coding agents;
- prove selective installation adds only requested skills and skill `[all]` adds every current
  catalog skill; and
- keep Claude/Codex plugin packaging, `uvx`, and a OneTool-owned skill installer out of scope.

Upstream command syntax SHALL be verified from current authoritative installer documentation at
implementation time. Public docs may link to that source; installed capability skills SHALL not
depend on browsing it at runtime.

Recommended skill changes:

| Skill | Role / ownership |
|---|---|
| `ot-ref` | shared call/discovery reference; owns `ot` and `ot_timer` |
| `ot-ask` | user-invoked router only |
| `ot-setup` | new Foundation setup/diagnostic workflow |
| `ot-runtime` | new Core root-runtime serving, observability, and recovery workflow |
| `ot-mcp-proxy` | replaces `ot-servers`; owns `ot_servers` and arbitrary proxied servers |
| `ot-file` | owns `file` and `ripgrep`; expands from file mutation to file/search selection |
| `ot-browser-guidance` | owns only `chrome_util`/`play_util` annotation judgment |
| existing remaining skills | retain current pack owners but receive richer guidance |

`ot-setup`, `ot-runtime`, and `ot-mcp-proxy` SHALL permit implicit model invocation and explicit
user invocation. `ot-ask` remains user-only. Other capability skills remain implicitly
model-invoked unless their catalog role says otherwise.

The beta `console` pack SHALL have no owning skill, generated skill coverage, or router route until
it is promoted from beta. Its catalog status and exclusion reason keep validation intentional
without advertising an unstable surface. `ripgrep` moves to `ot-file`; `ot_timer` remains in
`ot-ref` because it is a small instrumentation wrapper that does not justify another skill.
The exclusion applies to every distributed skill file and reference, including the generated
`ot-ref` pack map and skill-side tool index. Console may remain in explicitly beta public product
and tool-reference documentation.

### 3. Normalize the pack requirement contract

Every pack-level requirement SHALL use one typed literal representation. The model SHALL support:

- `lib`: distribution name, import name, install extra, optional flag, and optional activation
  condition;
- `cli`: executable name, platform-aware install guidance or authoritative URL, optional flag,
  and activation condition;
- `secret`: secret name, purpose, optional flag, and activation condition;
- `server`: configured proxy name or compatibility selector, optional flag, and activation
  condition;
- `config`: field path, purpose, and activation condition.

Requirements SHALL identify a OneTool extra such as `util`, `dev`, or `scrape` where that extra is
the supported install route. Free-form `pip install`/`brew install` strings SHALL not be the sole
machine-readable source.

All built-in declarations SHALL migrate in the same change. AST extraction, runtime validation,
dependency checking, docs generation, and extension validation SHALL accept only the new shape.
Old strings, tuples, and ad hoc dictionaries SHALL fail through the current declaration-validation
path; no aliases or transitional parsers SHALL remain.

Optional and conditional requirements SHALL not make a whole pack appear unavailable. For
example, an embedding provider, diagram renderer, or formula engine may be reported as required
only when the relevant configuration or requested workflow activates it.

### 4. Make pack config introspectable explicitly

Packs with typed config SHALL expose an explicit config-model hook in pack metadata. The composed
catalog SHALL use `model_json_schema()` and the active expanded configuration to render field
names, descriptions, defaults, current non-secret values, and validation errors.

The hook is explicit because several packs import or subclass config models from submodules, so
scanning only for a literal module-level `class Config` is incomplete.

Sensitive values SHALL be redacted by schema metadata plus conservative key/value detection.
Diagnostics SHALL report only whether a secret is set, never its value. `${NAME}` references may
show the variable name but not the expansion.

### 5. Extend `ot.help()` with orthogonal topic selection

The public call shape SHALL become:

```python
ot.help(
    query="whiteboard",
    topic="dsl",
    info="default",
    ask="How do I connect grouped nodes?",
    answer_only=True,
)
```

- `query` continues to select a tool, pack, configured server, snippet, alias, or fuzzy subject.
- `topic` selects a named subresource without overloading dotted tool names.
- `ask` remains grounded only in the deterministic, already-narrowed help text.
- `answer_only=False` preserves the current context-plus-answer behavior.
- `answer_only=True` returns only the grounded answer on success.
- If ask mode is unavailable or fails, `answer_only=True` SHALL return an explicit failure plus
  the narrowed deterministic help, never an empty result.
- Passing `answer_only=True` without `ask` SHALL raise `ValueError`.

Topic resolution order SHALL be deterministic:

1. resolve the exact query subject using existing tool/pack/server/snippet/alias rules;
2. if the subject is a configured server, prefer live config/status and combine native MCP
   instructions before configured additions;
3. resolve the requested topic for that subject;
4. only then use fuzzy search over subject and topic names/descriptions.

Topic providers SHALL be read-only. A topic may be:

- a packaged UTF-8 resource;
- a renderer over registry/config/requirement/status data;
- a named existing read-only provider with an explicit adapter.

No help topic may execute a mutating pack operation. Large DSL/policy resources SHALL be returned
through `ot.help()` itself so remote agents do not need server filesystem access.

Standard local-pack topics:

- `overview`: boundary, high-value strengths, tools, docs;
- `workflow`: selection, sequence, safety, verification;
- `setup`: live readiness and exact next steps;
- `config`: schema, defaults, redacted active values, config source.

Pack-specific topics include `dsl`, `policy`, `providers`, `templates`, or similarly reviewed
names. Existing resources such as the whiteboard DSL and diagram policy/providers/templates SHALL
be registered rather than copied.

Standard server topics:

- `overview`/default: status, `call_as`, source, native plus configured instructions, tools;
- `setup`: configured-state availability, transport, requirements, redacted auth/env readiness,
  connection error, persistent config guidance, and validation sequence;
- `config`: redacted active config;
- `resources` and `prompts`: live discovery when connected;
- `workflow`: generic proxy lifecycle plus native and configured server instructions.

For a server that is not yet configured, `ot.help(topic="setup", query="proxy")` SHALL render
generic stdio/HTTP configuration guidance from `McpServerConfig`. Server-specific command,
argument, authentication, and scope details belong to current authoritative MCP documentation and
must not be frozen into the help catalog.

### 6. Separate diagnosis, approval, mutation, and verification

`ot.help(query="<pack-or-server>", topic="setup")` SHALL be read-only. Its internal report model
SHALL distinguish:

- installed and loaded;
- known but missing distribution extra;
- missing library;
- missing executable;
- unset secret;
- missing or invalid config;
- proxy server not configured;
- configured but disabled;
- enabled but connecting/disconnected, including sanitized last error;
- ready.

The `ot-setup` skill SHALL:

1. inspect `ot.status()`, `ot.config()`, and the relevant setup topic;
2. classify the gap;
3. identify the resolved config path and propose exact, minimal changes;
4. stop for explicit approval before installing, editing, starting, connecting, or adding secrets;
5. use the approved environment's package manager/CLI, config editing capability, and
   `ot_secrets` rather than inventing a new privileged runtime tool;
6. run `onetool init validate`, `ot.reload()`, repeat setup help, and use a non-mutating smoke call
   when available.

When the gap is a `servers:` entry, transport, server executable, remote auth, or proxy lifecycle,
`ot-setup` SHALL hand off to `ot-mcp-proxy` rather than duplicate the server workflow.

If the agent cannot modify the OneTool host (for example, remote MCP-only access), the skill SHALL
return the redacted config and commands for the user/operator to apply instead of claiming setup
succeeded.

### 6a. Give ongoing runtime operations one explicit owner

`ot-runtime` SHALL own root-runtime operation after initial setup: choosing and starting stdio or
HTTP serving, distinguishing the root runtime from outbound MCP proxies, using the Direct API,
interpreting status/debug/readiness, reloading config, inspecting statistics and telemetry,
retrieving logs or stored large results, and bounded operational recovery. It SHALL explain that
root HTTP has no built-in authentication and SHALL require an explicitly secured deployment before
recommending a non-loopback bind.

The boundary SHALL remain explicit:

- installation, extras, secrets, and persistent config mutation hand off to `ot-setup`;
- outbound MCP server configuration and connection lifecycle hand off to `ot-mcp-proxy`;
- call syntax and tool discovery remain summarized in `ot-ref`.

### 7. Treat proxy onboarding and proxy use as one lifecycle

`ot-mcp-proxy` SHALL cover:

1. identify the intended MCP server and verify its current authoritative source;
2. choose stdio or HTTP and determine command/URL, arguments, timeout, environment isolation,
   headers, bearer auth, or OAuth scopes;
3. prefer per-server environment entries and secret references; warn before `inherit_env: true`
   or broad OAuth scopes;
4. propose a disabled persistent config entry and request approval;
5. validate config, then enable/restart only the named server;
6. call exact server help and inspect tools, resources, and prompts;
7. use the proxy namespace and exact live signatures rather than static guesses;
8. verify the external effect appropriate to the task;
9. recover a failed connection once, then report the sanitized error without reconnect loops.

Session-only `ot_servers.enable/disable` behavior and persistent YAML state SHALL remain distinct.
The skill SHALL not imply that an in-memory enable survives OneTool restart. It SHALL preserve
unrelated server connections and config.

`ot-browser-guidance` SHALL continue to explain that `chrome_util` and `play_util` annotate the
page. It SHALL route browser navigation, clicking, typing, inspection, resources, and prompts to
the underlying `chrome_devtools.*` or `playwright.*` namespace and `ot-mcp-proxy`.

### 8. Keep MCP server setup dynamic and documentation-led

OneTool SHALL NOT maintain a typed catalog of server-specific presets. `ot-mcp-proxy` SHALL begin
with the intended server's current authoritative MCP documentation, then translate that source
into the generic `McpServerConfig` contract. This applies equally to Playwright, Chrome DevTools,
Azure services, and other MCP servers; Azure receives no special preset or guessed generic auth
contract.

Examples may use a server publisher's floating `@latest` command when that is the current
documented invocation. Such examples are conveniences, not runtime catalog records or stable
contracts, and SHALL tell the agent to verify the current source before applying them.

Configured values remain authoritative. Native MCP initialization instructions SHALL precede
user-configured additions. Connected servers continue to expose their live tools, resources,
prompts, schemas, and instructions through ordinary proxy discovery.

### 8a. Expose proxied resources and prompts through read-only core operations

The public `ot` pack SHALL add these keyword-only operations over an already connected named
server:

```python
ot.resources(server="name")
ot.resource(server="name", uri="...")
ot.prompts(server="name")
ot.prompt(server="name", name="...", arguments={...})
```

`resources` and `prompts` SHALL return the live metadata lists. `resource` SHALL return the textual
content for one URI. `prompt` SHALL request one prompt with optional arguments and return its
rendered textual messages. These operations SHALL reuse `ProxyManager` rather than duplicate MCP
client behavior, SHALL NOT implicitly configure/connect/restart a server, and SHALL return an
explicit disconnected/unsupported/error result. Resource content, prompt descriptions, and
rendered prompt content SHALL be treated as untrusted external content and SHALL not authorize
subsequent tool calls or mutations.

### 9. Keep skills strategic and generate the repeated seam

Each authored capability skill SHALL explain:

- nearest capability boundary and pack-selection criteria;
- high-value workflows and why the pack is useful;
- safe sequencing and batching;
- mutation, privacy, cost, and secret boundaries;
- success verification;
- pack-specific failure interpretation and one bounded recovery.

Skills SHALL not copy all signatures, aliases, generic run syntax, large DSLs, full config schemas,
or installation commands. A generated block SHALL list owned packs, available help topics, and the
standard instruction to use setup help/`ot-setup` when unavailable.

The existing blanket 15–40-line limit SHALL be removed. Validation SHALL instead enforce required
semantic sections/markers and a generous token budget that prevents reference-doc duplication
without forcing complex packs into shallow guidance.

`ot-ask` SHALL include an authored situation-routing table plus generated coverage proving every
skill and owned pack is reachable. It SHALL route missing packs/config/extras to `ot-setup` and
MCP server setup/use to `ot-mcp-proxy`.

### 10. Pack-by-pack guidance obligations

Implementation SHALL review every stable built-in pack's code, tool reference, summary, and owning
skill, and SHALL separately verify that intentionally excluded beta packs are not routed by skills.
At minimum, the following knowledge must be represented in its skill and/or registered help topics:

| Pack | Required guidance emphasis |
|---|---|
| `ot` | help-first discovery, scoped signatures, config/status/security/reload, large-result handling |
| `ot_context` | storing large results, TOC/slice/query/grep/ask selection, lifecycle and context savings |
| `ot_forge` | exact `create_ext`/`validate_ext` static-validation lifecycle; no template-inspection, generate, execution, or behavioral-test claims |
| `ot_image` | source/handle loading, batches, up-to-eight-image comparisons, clipboard platform limits, cached summary, list/delete/purge lifecycle, model/privacy/cost readiness |
| `ot_llm` | value/file transformation, model/base URL/secret readiness, JSON/output validation, file mutation, untrusted input, cost/privacy, and absent retry/input-bound behavior |
| `ot_secrets` | exact init/status/audit/set/get/unset/encrypt/rotate lifecycle; force, plaintext backup, protected output, round-trip and backend requirements without exposing values |
| `ot_servers` | persistent config versus session-only enable/disable, named-entry restart/status, full-reload boundary, and bounded recovery |
| `ot_timer` | exact start/elapsed/stop/list/clear lifecycle, stored results, and meaningful measurement |
| `console` (beta) | no skill ownership or routing; retain only accurate beta pack/reference documentation |
| `brave` | web/news/image/video selection, structured batches/retries, freshness/output modes, citations, API-key/cost |
| `convert` | format-specific conversion, representative-before-batch flow, output/artifact/errors, optional formula support |
| `excel` | full workbook/table introspection, read/write/formula and structural range/row/column mutation, no pivots, recalculation caveat, readback |
| `file` | exact/glob/fuzzy resolution, read/TOC/slice/search/batches, atomic edit/dry-run/backup, copy/move/delete, overwrite/trash/symlink boundaries, verification |
| `ground` | search/dev/docs/reddit, batches, extraction/provenance, citations, Gemini model/config privacy/cost |
| `knowledge` | MCP CRUD/retrieval/synthesis versus CLI index/reindex/enrich/scrape, config, hybrid degradation, graph/citations, embeddings and source targeting |
| `mem` | CRUD/batches, retrieval, history/rollback, file freshness, dump/load versus snapshot/restore, decay/reindex/flush, optional async embeddings and dry-run maintenance |
| `tavily` | search/extract/research selection, search/extract batches, provenance, research polling/models/cost, API-key readiness; no nonexistent answer tool |
| `whiteboard` | named boards, additive graph/note DSL, state/browser lifecycle, sync/layout/style, exact save/screenshot/share semantics, reset distinctions and verification |
| `arch` | validate/generate and Excel↔YAML round-trip/bundle sequencing, filters/profiles, incremental/force behavior, conditional external-renderer trust and output verification |
| `chrome_util` | inject/highlight/scan/clear/guide annotation lifecycle and matching Chrome proxy |
| `context7` | direct doc auto-resolution for unambiguous libraries; explicit search for ambiguity/recovery and version-current selection |
| `db` | tables/schema/sample, parameterized queries, explicit `read_only=False` default, AUTOCOMMIT, account-level boundary and mutation verification |
| `diagram` | provider/backend selection, remote-source/privacy boundary, policy/instructions/templates/output config, async polling, self-hosted batch/directory and render verification |
| `localhist` | init/status, excludes/force-includes, save/log/history/show/diff, autosave, dry-run restore/prune, safety snapshots and history-rewrite/GC consequences |
| `package` | manifest/registry version staleness, npm/PyPI batches, OpenRouter models; no lockfile/vulnerability audit claim |
| `play_util` | inject/highlight/scan/clear/guide plus Playwright-only auto-inject and matching proxy |
| `ripgrep` | regex/literal, globs/types/context/output limits, selection versus `file` search |
| `webfetch` | fetch/extract and batches, non-HTML passthrough, cache/freshness and precision/recall controls, bounded downloads/output, optional best-effort private-URL policy and untrusted content |

The implementer SHALL use current code/signatures as the final authority and correct this table if a
named operation has changed before implementation; it SHALL not preserve a stale claim to satisfy
the plan.

### 11. Keep feature changelog tracking outside the implementation architecture

`features/features.yaml` is non-authoritative historical/changelog tracking and may be removed in
the future. It was useful only as an audit lead for finding surfaces that required verification
against code. No runtime module, typed catalog, documentation generator, skill generator,
validator, test oracle, or build/release gate SHALL import, parse, compose with, or depend on this
file. The change SHALL NOT migrate its schema, generate a feature-coverage report, or treat its
coverage hash, examples, `pack` values, or completeness as an implementation contract.

Current code and validated public interfaces remain authoritative. If maintainers independently
retain or correct the historical file, that documentation maintenance is outside this change and
MUST NOT become a prerequisite for catalog, skill, help, documentation, or release checks.

### 12. Generate projections and validate drift

Extend the existing docs-generation pipeline rather than adding unrelated scripts. One composed
inventory SHALL drive:

- default pack summaries used by runtime discovery;
- public docs tool index plus a separately filtered stable-only `ot-ref` pack map/tool index;
- docs pack/index tables and managed per-pack highlights;
- skill owner/profile/coverage blocks;
- `ot-ask` coverage;
- help-topic inventory;
- documentation URLs.

Authored prose remains outside generated markers. Sync is the only writer; check mode SHALL render
in memory and fail with the exact stale targets. `just docs-sync` SHALL update every projection and
`just skills-check` SHALL validate without writing.

Validation SHALL catch:

- stable runtime pack without catalog entry/owner/docs page;
- beta runtime pack without an explicit skill-exclusion status and reason;
- catalog pack absent from the all-packs registry;
- skill with an invalid role/policy or no declared purpose;
- owned pack omitted by its skill or router;
- duplicate or missing help topic/resource;
- requirement/config metadata that cannot be parsed;
- packaged help/template drift;
- `doc_slug` not matching the MkDocs reference filename or a generated online route;
- summaries claiming tools/capabilities absent from the runtime inventory;
- examples using nonexistent tools/parameters or prohibited placeholder domains.
- any beta `console` content in a distributed skill artifact.

Public and skill-side indexes SHALL use the same renderer and composed inventory but different
catalog filters: public beta documentation may include `console`; every distributed skill
projection SHALL exclude it. The two indexes are therefore not required to be byte-identical.

### 13. Package help content and make links supplementary

Operational resources needed by an agent SHALL ship inside the Python distribution. Public docs
SHALL copy/include generated content from those resources where appropriate. Skills SHALL call
`ot.help()` by subject/topic and SHALL not depend on repository-relative sibling traversal.

Help output SHALL provide:

- the content needed to proceed;
- the canonical published documentation URL derived from a required valid `doc_slug`;
- a local source path only as diagnostic provenance, not as an access requirement.

Pack URLs SHALL be checked against the MkDocs nav/page inventory. The existing broken Brave/Ground
slug behavior SHALL be corrected by making the declared page filename the single slug authority.

### 14. Correct audited documentation and example drift

The implementation SHALL reconcile code, summaries, skills, and reference pages for all packs, not
only add infrastructure. Known required corrections include:

- remove Excel pivot claims unless a real pivot tool exists at implementation time;
- describe `package.audit` as manifest version staleness with its actual `path` argument, not a
  vulnerability audit;
- include all actual `ot_timer`, `ot_secrets`, and `localhist` lifecycle operations;
- remove `ot-forge` instructions to inspect templates unless such a callable operation exists;
- state the real default mutation behavior and return shape of `db.query`;
- replace invalid `console` examples/arguments and every `example.com` example with a supported,
  realistic target or omit the URL;
- make browser helper examples match actual function signatures;
- correct Direct CLI/API, Webfetch, Localhist, Context7, Knowledge CLI, context-write, install-extra,
  explicit-config, worker-isolation, root resource, and run-annotation claims;
- correct all doc slugs and links against the built documentation.

### 15. Developer guidance is a routed single source

Add:

- `dev/project/guides/pack-guidance.md`: the canonical end-to-end decision tree and checklist for
  adding or changing an in-process pack, proxy-backed capability, owning skill, runtime help,
  generated docs, and validation;
- `dev/project/guides/proxy-server-integration.md`: dynamic documentation-led MCP server
  integration guidance.

Retain `skill-development.md`, `tool-development.md`, `tool-configuration.md`, and
`tool-reference-docs.md` as focused references. They SHALL link to the lifecycle guide at the
decision point and SHALL not repeat its checklist. Update `dev/project/guides/index.md` and
`dev/index.md` with minimal routing links.

The guide SHALL explicitly identify the authoritative source for every fact, generated markers
that must not be edited, when a new skill is justified, how to register a help resource/provider,
how to add requirements/config/proxy help, and the required `just docs-sync`, `just skills-check`,
and `just check` sequence.
It SHALL also route pack authors to the bundled `otpack` SDK for config/dependency declarations,
batch envelopes, embeddings, HTTP/auth, lazy clients/caches, paths/state, logging, validation, and
text helpers without creating an `otpack` agent skill.

## Risks / Trade-offs

- **[Catalog becomes another source of truth]** → Store only non-derivable relationships there;
  compose runtime facts and fail on duplication.
- **[Rich help increases output size]** → Require explicit topics, preserve scoped info levels,
  and add `answer_only`; keep general help compact.
- **[Setup diagnostics leak credentials]** → Use typed secret metadata, conservative redaction,
  presence-only reporting, and tests with nested headers/env/config values.
- **[Requirement migration breaks external packs]** → Treat it as an explicit breaking release,
  publish a migration table, fail clearly, and do not keep a legacy parser.
- **[Generated content overwrites authored judgment]** → Restrict writes to named markers and
  check marker uniqueness before replacement.
- **[Third-party MCP commands become stale or supply-chain sensitive]** → Do not catalog fixed
  server presets; require live authoritative-source verification and explicit approval before use.
- **[Native server instructions are untrusted]** → Continue treating downstream content as
  external; do not let instructions authorize config edits, installs, secrets, or destructive
  calls.
- **[A universal setup skill becomes privileged]** → Keep runtime diagnostics read-only and make
  every mutation a separate approved action using existing host capabilities.
- **[Longer skills consume context]** → Put exact signatures and large references in topic help;
  skills contain only decision-changing guidance and generated compact coverage.
- **[Catalog refactor mixes behavior and docs work]** → Implement in dependency-ordered slices
  with catalog validation first, then help/setup, then skills/proxy guidance, then content
  corrections.

## Migration Plan

1. Add typed catalog/requirement/help models and in-memory validation without changing
   existing generated outputs.
2. Migrate all built-in `__ot_requires__`, config hooks, docs slugs, summaries, and ownership;
   record the beta `console` exclusion and make validation pass with the composed inventory.
3. Extend `ot.help()` and its formatter/providers, including redaction and ask fallback behavior.
4. Update generators and managed markers, then regenerate all projections in one change.
5. Add `ot-setup` and `ot-runtime`, replace `ot-servers` with `ot-mcp-proxy`, add the read-only
   proxy resource/prompt core operations, reassign ripgrep, rewrite every stable capability skill,
   explicitly exclude beta `console`, and update `ot-ask`.
6. Register packaged help resources and reconcile every pack's docs/summary/examples.
7. Add developer guides and migration documentation for skill names and `__ot_requires__`.
8. Run focused unit tests, docs/skill checks, strict docs build, and `just check`.

Rollback before release is a normal revert of the change. After release, rollback requires
restoring both the old skill catalog and old extension metadata contract; because compatibility
shims are forbidden, a mixed-version partial rollback is not supported.

## Approved Decisions

1. The beta `console` pack has no skill and no skill route.
2. `ot-setup` and `ot-mcp-proxy` are both user- and model-invocable.
3. OneTool maintains no server-specific MCP preset catalog. Current documented examples may use
   floating `@latest`, with live authoritative-source verification before use.
4. Azure has no special preset; follow the selected Azure MCP server's current documentation.
5. Runtime setup help remains read-only. Approved agents use existing CLI, configuration, package
   management, and secrets capabilities for mutations.
6. Skill validation requires semantic sections and applies a generous token ceiling.
7. The catalog uses typed Python records in runtime core.
8. If `answer_only=True` cannot produce an LLM answer, return the explicit LLM error together with
   the narrowed deterministic help.
9. Add user- and model-invocable `ot-runtime` as the single owner of ongoing root-runtime
   operations, with explicit setup/proxy/reference handoffs.
10. Add read-only public `ot.resources`, `ot.resource`, `ot.prompts`, and `ot.prompt` operations
    over already connected proxied servers.
11. `features/features.yaml` is non-authoritative historical tracking only and SHALL NOT be used by
    runtime code, catalogs, generators, validators, tests, or release gates.
12. Keep one `ot-knowledge` skill with distinct build/maintain and query/use workflows; do not add
    `ot-knowledge-admin`.
13. Keep the Python `[all]` extra equal to `[util,dev]`. Retain the extra name, but reword every
    description to state explicitly that it excludes the separately opt-in `[scrape]` dependencies
    and SHALL NOT be described as every optional OneTool capability.

No additional `ot-security`, `otpack`, provider-specific, browser-server-specific, Docker-only, or
console skill is recommended. Security belongs as mandatory `ot-ref` judgment and deterministic
help; `otpack` belongs in developer guidance; provider/server detail is versioned help/live
documentation; Docker is one runtime deployment; and beta `console` is excluded.
