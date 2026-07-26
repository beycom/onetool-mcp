## Why

OneTool's distributed skills currently repeat a minimal availability pattern while leaving much
of each pack's operating power, configuration, safety boundaries, and recovery knowledge
undiscoverable. Pack facts are also duplicated across runtime modules, prompt YAML, documentation,
skill metadata, and tests, which has already allowed claims, tool coverage, dependency guidance,
and documentation links to drift from the implementation.

## What Changes

- Introduce a composed, typed catalog that declares each non-derivable pack, skill, help-topic,
  and installation-profile relationship once, while continuing to
  derive signatures, aliases, config schemas, prerequisites, and live status from their runtime
  sources.
- Extend `ot.help()` with pack/server topics such as `workflow`, `setup`, `config`, `dsl`,
  `policy`, `providers`, and `templates`, plus an `answer_only` ask mode for large references.
  Help content SHALL be usable through the tool result without requiring repository filesystem
  access or web access; local packaged resources are primary and version-correct online links are
  supplementary.
- Add a read-only, redacted setup diagnostic assembled from the active config, install profile,
  normalized pack requirements, pack config schema, secrets presence, executables, proxy state,
  and the generic MCP server configuration schema.
- Add a Foundation `ot-setup` skill for diagnosing and, only after explicit approval, guiding or
  performing OneTool installation, pack-extra, config, secret, validation, and reload workflows.
- Add a user- and model-invocable `ot-runtime` skill for root serving/transports, Direct API,
  status/debug/reload, statistics/telemetry, safe HTTP exposure, results/logs, and operational
  recovery.
- **BREAKING**: replace the narrow `ot-servers` skill with `ot-mcp-proxy`, covering authoritative
  server selection, persistent stdio/HTTP/auth configuration, session lifecycle, live discovery,
  safe use, and bounded recovery for arbitrary MCP servers. Server-specific setup SHALL be derived
  from current authoritative MCP documentation rather than maintained OneTool presets. No legacy
  skill alias is retained.
- Add read-only `ot.resources`, `ot.resource`, `ot.prompts`, and `ot.prompt` core operations so
  agents can list/read proxied MCP resources and list/render proxied MCP prompts through the public
  OneTool surface.
- Keep `ot-browser-guidance` limited to `chrome_util`/`play_util` annotations; navigation,
  interaction, resources, prompts, and other server capabilities remain owned by the underlying
  proxied namespace and `ot-mcp-proxy`.
- **BREAKING**: normalize `__ot_requires__` to one validated typed declaration for Python
  distributions/import names, CLI executables, secrets, proxy servers, config conditions,
  install extras, and optional/conditional requirements. Remove support for the existing mixed
  tuple/string/dict forms rather than adding compatibility parsing.
- Rework every capability skill around pack-specific selection, sequencing, high-value workflows,
  safety, verification, and recovery. Generate only catalog facts, coverage, and the common setup
  handoff; do not generate or duplicate authored operating judgment.
- Fold the existing skill-installation-profile issue into this change: derive selectable
  Foundation/Core/extra/all memberships from the catalog, document and verify current
  `npx skills@latest` interactive/selective installation without implying native named-profile
  support, and avoid hard-coded profile counts.
- Exclude the beta `console` pack from skill ownership and guidance until it is promoted from beta;
  catalog validation SHALL require the exclusion status and reason rather than silently assigning
  it to a general skill. It SHALL also be absent from every distributed skill artifact, including
  the `ot-ref` pack map and skill-side tool index.
- Keep `features/features.yaml` outside the implementation architecture. It is non-authoritative
  historical/changelog tracking that informed the audit only; runtime code, catalogs, generators,
  validation, skills, and documentation SHALL NOT import, parse, compose with, or depend on it.
- Generate or validate the prompt pack summary, pack map, tool index, skill coverage, profile
  membership, router coverage, help-topic inventory, reference-doc blocks, and
  documentation links from the composed catalog and runtime registry.
- Correct all drift found during the pack-by-pack code/reference review, including unsupported
  Excel pivot and package security-audit claims, incomplete timer/secrets/localhist coverage,
  Forge/template and Tavily/Context7 claims, DB mutation defaults, Direct CLI, Webfetch,
  Knowledge CLI, context-write examples, MCP resource URIs/annotations,
  console examples, installation extras, configuration/security descriptions, and invalid
  documentation slugs.
- Add canonical developer guides for the complete pack-guidance lifecycle and proxy-server
  integration, link them from the guides index and tool-development workflow, and document which
  facts are authored versus derived.

## Capabilities

### New Capabilities

None. The new behavior extends the existing help, skill, tool-package, proxy, and documentation
capabilities rather than introducing a separate product surface.

### Modified Capabilities

- `tool-ot`: add topic-scoped help, answer-only ask output, local packaged help resources,
  redacted setup/config diagnostics, generic proxy configuration help, and canonical
  documentation-link behavior.
- `serve-skills`: expand the catalog roles, invocation policies, generated coverage, Foundation
  setup guidance, complete pack operating guidance, and MCP proxy lifecycle guidance.
- `serve-tools-packages`: define the normalized pack requirement/config/help metadata contract
  used by discovery and setup diagnostics.
- `_nf-docs`: require generated, version-correct, non-duplicated pack/server guidance and correct
  the audited documentation/runtime mismatches.
- `serve-mcp-discoverability`: correct the current resource URI and destructive-capable run
  annotation contract, and add public read-only proxied resource/prompt operations.

## Impact

- Runtime help and discovery under `src/ot/meta/`, pack registry models and extraction, dependency
  checking, config-schema discovery, generic proxy setup help, and default prompt descriptions.
- All built-in pack requirement declarations and selected pack metadata.
- The curated `skills/` catalog, router, profile derivation, generated references, and validation.
- Documentation generation scripts, public tool/proxy documentation, developer guides, MkDocs
  navigation, skill installation-profile documentation/verification, and link validation.
- Existing extension packs using old `__ot_requires__` shapes must migrate to the new typed
  declaration; users referring to `ot-servers` must use `ot-mcp-proxy`.
