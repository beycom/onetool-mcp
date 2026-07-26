## 1. Approval And Baseline

- [x] 1.1 Verify that every approved decision in `design.md` is encoded consistently in the proposal, design, tasks, and spec deltas before implementation.
- [x] 1.2 Capture the current all-packs runtime inventory, skill catalog validation result, generated-doc result, and focused help/proxy test baseline without modifying generated targets.
- [x] 1.3 Add a migration note for the `ot-servers` → `ot-mcp-proxy` skill rename and the normalized `__ot_requires__` contract; do not add aliases, legacy parsing, or transitional code.
- [x] 1.4 Verify the five final user decisions in `design.md` are encoded without conditional alternatives before implementation.
- [x] 1.5 Mark `wip/issues/1-new/add-onetool-skill-installation-profiles.md` as superseded by this change after capturing all still-valid acceptance criteria; do not retain its fixed skill lists or counts as a second source of truth.

## 2. Typed Catalog Foundation

- [x] 2.1 Add runtime-safe typed Python models for pack guidance, pack stability/skill exclusion, skill roles/invocation, help-topic descriptors, normalized requirements, and config hooks under `src/ot/`, without importing optional pack implementations.
- [x] 2.2 Define the reviewed non-derivable catalog entries for every built-in pack and skill, including display name, install extra, default summary, owner, profile role, invocation role, and help-topic registrations; assign `ot-runtime` explicitly to Core.
- [x] 2.3 Implement a composed catalog read model that joins the reviewed entries with runtime registry aliases/tools/signatures/docs slugs, active config, requirements, config schemas, and live proxy state.
- [x] 2.4 Replace `CURATED_SKILLS` and manually duplicated `PROFILE_SKILLS` membership with role/ownership-derived Foundation, Core, Core + `[util]`, Core + `[dev]`, and `[all]` profiles.
- [x] 2.5 Update catalog validation to reject missing/duplicate stable runtime packs, owners, skills, extras, docs pages/slugs, topic resources, config hooks, and invalid invocation roles, and require an explicit status/reason for any beta pack excluded from skill ownership.
- [x] 2.6 Add unit tests for successful composition, every catalog drift failure, cross-catalog skills that own no pack, derived profiles, and role-based invocation policy.

## 3. Pack Requirement And Config Metadata

- [x] 3.1 Implement the single normalized requirement schema for `lib`, `cli`, `secret`, `server`, and `config` requirements, including install extra, import/executable identity, purpose, optionality, and activation conditions.
- [x] 3.2 Replace registry AST extraction and dependency checking support for tuple/string/ad hoc declarations with strict normalized-declaration parsing and clear validation errors.
- [x] 3.3 Migrate every built-in `__ot_requires__` declaration in `ottools`, `otutil`, and `otdev`, including optional formula/embedding/rendering/scrape requirements and browser-proxy requirements.
- [x] 3.4 Add explicit config-model hooks to every configurable pack, including packs whose model is imported or subclassed from a submodule.
- [x] 3.5 Implement config-schema/current-state introspection using the declared Pydantic model, active expanded config, defaults, field descriptions, and validation errors.
- [x] 3.6 Implement conservative nested redaction for secrets, tokens, headers, environment values, credential-like config fields, and variable expansions; expose secret names and set/unset state only.
- [x] 3.7 Add unit tests for every requirement kind and declaration error, inactive conditional requirements, missing extras/libraries/executables/secrets/servers/config, imported config models, invalid pack config, and nested redaction.

## 4. Topic-Scoped Runtime Help

- [x] 4.1 Extend the keyword-only `ot.help()` contract with `topic` and `answer_only`, preserving existing query/info/ask behavior and validating `answer_only=True` requires a non-empty `ask`.
- [x] 4.2 Implement exact subject resolution for tools, packs/aliases, configured servers, snippets, and aliases before topic resolution and fuzzy search.
- [x] 4.3 Implement typed read-only topic providers for packaged UTF-8 resources, dynamic catalog/config/status renderers, and explicitly adapted existing read-only pack providers.
- [x] 4.4 Add standard pack `overview`, `workflow`, `setup`, and `config` topics, standard configured-server `overview`, `workflow`, `setup`, `config`, `resources`, and `prompts` topics, and generic proxy setup/config topics rendered from `McpServerConfig`.
- [x] 4.5 Implement unknown-topic errors listing valid topics and fuzzy discovery over configured subjects plus topic names/descriptions.
- [x] 4.6 Implement `answer_only` success output and the approved LLM-unavailable fallback while keeping ask answers grounded only in the selected deterministic topic.
- [x] 4.7 Replace hard-coded help URL overrides with required valid pack `doc_slug` metadata and canonical published reference URLs.
- [x] 4.8 Add focused unit tests for every exact subject type, topic provider type, alias resolution, configured-server precedence, generic proxy setup, unknown/fuzzy topics, ask modes, mutation-free providers, and URL generation.
- [x] 4.9 Add keyword-only public `ot.resources(server=...)`, `ot.resource(server=..., uri=...)`, `ot.prompts(server=...)`, and `ot.prompt(server=..., name=..., arguments=...)` operations by adapting the existing proxy manager; register and document them, return explicit disconnected/unsupported/error states, identify returned content as untrusted, and never implicitly mutate server state.
- [x] 4.10 Add deterministic security workflow help for `ot.security()` preflight/full/audit modes and `SecurityBlockedError` recovery without creating a separate security skill.

## 5. Setup Diagnostics

- [x] 5.1 Implement an internal structured readiness report that distinguishes ready, missing extra, missing library, missing executable, unset secret, missing/invalid config, inactive optional requirement, unconfigured proxy server, disabled server, connecting server, and disconnected server.
- [x] 5.2 Render pack `setup` and `config` help from the readiness report with exact non-mutating next steps, resolved config provenance, supported install target, and registered smoke verification.
- [x] 5.3 Render configured-server setup/config help and generic `McpServerConfig` guidance with redacted transport/auth/env state, sanitized errors, persistent config proposals, and session-versus-persistent lifecycle guidance.
- [x] 5.4 Ensure setup/config help performs no package installation, file/config mutation, credential grant, service start, or proxy connection.
- [x] 5.5 Add tests for ready and every degraded readiness state, multiple simultaneous gaps, optional/conditional requirements, remote-host/operator handoff text, no secret leakage, and zero mutation side effects.

## 6. Dynamic MCP Proxy Guidance

- [x] 6.1 Implement generic stdio/HTTP proxy setup guidance from the typed `McpServerConfig` schema without a server-specific preset catalog.
- [x] 6.2 Make `ot-mcp-proxy` require the selected server's current authoritative MCP documentation before proposing command, URL, arguments, authentication, scopes, or smoke validation.
- [x] 6.3 Treat Playwright, Chrome DevTools, Azure, and every other MCP server through the same documentation-led workflow; do not add Azure-specific or other fixed presets.
- [x] 6.4 Keep any convenience command examples outside the runtime catalog, use floating `@latest` where the current publisher documentation does, and label every example for live source verification.
- [x] 6.5 Preserve configured-server values as authoritative and native MCP initialization instructions before user-configured additions.
- [x] 6.6 Ensure every valid stdio/HTTP server retains namespace, tool, public read-only resource/prompt access, and native-instruction behavior through live discovery.
- [x] 6.7 Add tests for generic proxy configuration, configured values, arbitrary servers, native/configured instruction ordering, auth redaction, unrelated-server preservation, absence of fixed presets, and bounded one-retry recovery guidance.

## 7. Skills And Routing

- [x] 7.1 Add Foundation `skills/ot-setup/SKILL.md` with diagnose → classify → propose → approve → apply through existing host/CLI/config/secrets capabilities → validate/reload/smoke workflow and remote-host operator fallback.
- [x] 7.2 Delete `skills/ot-servers/` and add `skills/ot-mcp-proxy/` covering authoritative selection, stdio/HTTP/auth config, persistent versus session state, live tools/resources/prompts, safe use, verification, and bounded recovery.
- [x] 7.3 Record beta `console` as intentionally excluded from every skill artifact and router route, including the `ot-ref` pack map/tool index/reference blocks, reject any `ot-console` skill/route while it remains beta, and keep its non-skill public reference documentation accurate.
- [x] 7.4 Reassign `ripgrep` to `ot-file`, keep `ot_timer` under `ot-ref`, and update catalog ownership without retaining old owner aliases.
- [x] 7.5 Rewrite `ot-ref` around exact `run(command='pack.tool(...)')` and direct-trigger mechanics, kwarg-prefix and alias forgiveness boundaries, help-first discovery, scoped signatures, complete built-in control functions, the absence of a sandbox around trusted tool code, security, recovery, large-result handling, complete timer instrumentation, and stable-only generated pack/tool indexes.
- [x] 7.6 Rewrite core capability guidance for `ot_context`, `ot_forge`, `ot_image`, `ot_llm`, and `ot_secrets` after comparing each pack's current code and reference page against the design matrix; do not claim arbitrary context dictionaries, Forge extension lifecycle APIs, or secrets rotation/versioning APIs that do not exist.
- [x] 7.7 Rewrite util guidance for `brave`, `convert`, `excel`, `file`, `ground`, `knowledge`, `mem`, `tavily`, and `whiteboard`, preserving research-pack selection boundaries; keep one `ot-knowledge` skill with distinct CLI build/maintain and MCP query/use workflows, and do not add `ot-knowledge-admin`.
- [x] 7.8 Rewrite dev guidance for `arch`, `context7`, `db`, `diagram`, `localhist`, `package`, `ripgrep`, and `webfetch` with current workflow, safety, verification, and recovery behavior.
- [x] 7.9 Keep `ot-browser-guidance` annotation-only, explicitly route navigation/interaction/inspection to the underlying Playwright/Chrome proxy, and route server setup/use to `ot-mcp-proxy`.
- [x] 7.10 Update `ot-ask` authored situation routes for all owners plus generated coverage, including missing prerequisites → `ot-setup` and MCP server lifecycle → `ot-mcp-proxy`.
- [x] 7.11 Add compact generated skill blocks for owned packs, registered topics, and standard setup handoff without overwriting authored prose.
- [x] 7.12 Replace fixed skill line-count assertions with required semantic guidance/marker checks and the approved generous token ceiling; test every skill's role, coverage, router reachability, and generated-block integrity.
- [x] 7.13 Add user- and model-invocable `skills/ot-runtime/SKILL.md` for root serving/transports, Direct API, status/debug/readiness/reload, statistics/telemetry, logs/results, safe HTTP exposure, and bounded recovery, with explicit handoffs to `ot-setup`, `ot-mcp-proxy`, and `ot-ref`.
- [x] 7.14 Route runtime status/debug/reload/stats/telemetry/log/result recovery situations through `ot-ask`, with configuration/install handoff to `ot-setup` and outbound MCP lifecycle handoff to `ot-mcp-proxy`.

## 8. Pack Help Resources And Operating Content

- [x] 8.1 Register the existing whiteboard DSL as packaged `whiteboard/dsl` help and add current workflow/setup/config topics without duplicating the DSL in the skill.
- [x] 8.2 Register diagram policy, providers, templates, output config, workflow, and setup through packaged resources or explicit read-only adapters to the current providers.
- [x] 8.3 Add or revise compact packaged workflow resources for stable packs whose safe operating detail does not fit the skill, ensuring every stable built-in pack satisfies its design-matrix obligation while beta packs remain explicitly excluded from skills.
- [x] 8.4 Verify every resource is included in the built wheel, readable without a repository checkout, returned through `ot.help()`, and projected into public docs only from its canonical source.
- [x] 8.5 Add resource/provider tests for package inclusion, UTF-8 loading, version-correct content, remote-agent access, topic inventory, and failure on a missing/duplicate resource.

## 9. DRY Generation And Drift Validation

- [x] 9.1 Refactor `otdev.docsgen` to consume one composed inventory for pack summaries, docs metadata, skill ownership/profiles, help topics, beta exclusions, and runtime tool data.
- [x] 9.2 Generate default pack summaries used by runtime discovery from the catalog while preserving active user prompt overrides.
- [x] 9.3 Generate target-filtered stable-only `ot-ref` pack/tool indexes, public docs pack/index blocks, managed pack highlights, skill/router coverage, installation-profile documentation, help-topic inventory, beta exclusion records, and canonical links.
- [x] 9.4 Make synchronization write only named managed blocks/generated files and make check mode render in memory with exact stale-target diagnostics.
- [x] 9.5 Wire every generated projection into `just docs-sync` and every read-only invariant into `just skills-check` or the existing docs-registry check without introducing parallel source mappings.
- [x] 9.6 Add generator/validator tests for stable ordering, idempotence, marker uniqueness, authored-content preservation, target-specific beta filtering, stale projections, unsupported summary claims, invalid slugs, and missing MkDocs pages; do not require public and skill indexes to be byte-identical when their stability filters differ.
- [x] 9.7 Generate each pack reference page's runtime-requirement section from normalized registry metadata and its distribution from the typed catalog; migrate authored `Requires` sections into named managed blocks so requirement facts have one source of truth.

## 10. Documentation Accuracy Corrections

- [x] 10.1 Remove Excel pivot claims unless the implementation has a current callable pivot operation; synchronize its summary, skill, highlights, and reference functions.
- [x] 10.2 Correct package guidance to its actual version/staleness behavior and `path` signature; remove every vulnerability/security-audit implication.
- [x] 10.3 Document exact current timer, secrets, and localhist lifecycle operations, including timer begin/checkpoint/end, secrets init/status/audit/get/set/unset/encrypt/rotate, and `localhist.prune(older_than_days=...)`, in summaries, skills, help, and references.
- [x] 10.4 Remove Forge template-inspection guidance and align the skill/reference with its exact `create_ext` and `validate_ext` surface; do not claim create, generate, execution, or behavioral-test operations.
- [x] 10.5 Correct DB guidance for the actual `db.query` `read_only=False` default, autocommit behavior, and return shape; require an explicit mutation decision in the skill.
- [x] 10.6 Correct console and browser companion examples to current function names/parameters and replace every `example.com` test or example with a supported realistic target or no URL.
- [x] 10.7 Correct every pack `doc_slug` to its MkDocs reference filename, especially Brave and Ground, and verify all generated public help links against the built site.
- [x] 10.8 Review every remaining pack summary, Highlights section, requirement disclosure, function table, example, and owning skill against current code so the known corrections do not become the limit of the audit.
- [x] 10.9 Use the audit leads for Direct CLI, Webfetch download limits, Localhist prune, Context7 arguments, Knowledge CLI syntax, and Context receipt-only writes to verify and correct authoritative skills/help/public docs only; do not read, migrate, validate, generate from, or make acceptance depend on `features/features.yaml`.
- [x] 10.10 Correct MCP discoverability documentation/specs to the `ot://` resource scheme, the local-only individual tool-detail boundary, and `destructiveHint=true`.
- [x] 10.11 Correct platform documentation for current config architecture, selective worker isolation, Direct's `run`-only CLI, root HTTP arbitrary-bind security warnings, and the retained Python `[all] = [util,dev]` contract; state explicitly that `[scrape]` remains separately opt-in and `[all]` does not mean every optional capability.
- [x] 10.12 Apply every remaining pack-specific correction recorded in the audited design matrix and review synthesis, and add regression checks so the named examples are not treated as the audit limit.

## 11. Canonical Developer Guidance

- [x] 11.1 Add `dev/project/guides/pack-guidance.md` as the end-to-end decision tree/checklist for in-process packs, proxy-backed capabilities, owning skills, requirements/config hooks, help topics, generated outputs, docs links, and validation.
- [x] 11.2 Add `dev/project/guides/proxy-server-integration.md` for documentation-led arbitrary MCP server setup and use, including authoritative-source checks, transports, auth/secrets, disabled defaults, instruction layering, companion packs, floating examples, live discovery, and tests.
- [x] 11.3 Update `skill-development.md`, `tool-development.md`, `tool-configuration.md`, and `tool-reference-docs.md` only with decision-point links and focused details; remove duplicated lifecycle/checklist text.
- [x] 11.4 Update `dev/project/guides/index.md`, `dev/index.md`, and relevant user docs with minimal routes to the canonical guides.
- [x] 11.5 Document authored-versus-derived ownership, managed-marker rules, extension requirement migration, skill-name migration, and the `just docs-sync` → `just skills-check` → `just check` sequence.
- [x] 11.6 Validate internal links, link depth, guide single-source boundaries, and absence of duplicated canonical checklists.
- [x] 11.7 Document `otpack` as a pack-authoring/developer workflow—including build/install/test/validation boundaries—without creating a general runtime skill for it.
- [x] 11.8 Document selectable OneTool skill installation profiles generated from the typed catalog, using current `npx skills@latest` syntax without implying native named-profile support or retaining fixed membership/count tables.

## 12. Verification

- [x] 12.1 Run focused unit tests for catalog, registry requirements, config introspection/redaction, help topics/ask behavior, setup diagnostics, public proxy resource/prompt operations, dynamic proxy behavior, runtime/knowledge skill contracts, and docs generators.
- [x] 12.2 Run `just docs-sync`, confirm a second run is clean/idempotent, then run `just skills-check`.
- [x] 12.3 Build the wheel and verify packaged help resources and runtime catalogs in an installed environment without repository-relative access.
- [x] 12.4 Run the strict MkDocs build and validate generated pack/help links and examples against the current runtime inventory.
- [x] 12.5 Run `just check` and resolve all lint, type, test, spec, skills, and docs failures before marking the change implemented.
- [x] 12.6 From clean temporary environments, verify current `npx skills@latest` list/discovery, selective installation, all-profile installation, update, and removal behavior for supported coding agents, including that recommended profiles contain `ot-ref` and selective installs contain only requested skills.
