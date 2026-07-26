## MODIFIED Requirements

### Requirement: Curated catalog coverage

Every stable built-in documented pack SHALL have exactly one operating-guidance owner in the
curated catalog, and catalog profiles SHALL derive from reviewed pack ownership plus explicitly
declared Foundation skills. A beta pack MAY be excluded from all skills only through an explicit
catalog status and reason. Cross-catalog skills such as setup and routing MAY own no pack when
their typed role explicitly permits it.

#### Scenario: Catalog consistency is checked
- **WHEN** the read-only skill catalog validation runs
- **THEN** every stable built-in pack SHALL be covered exactly once
- **AND** an unowned beta pack SHALL carry an explicit guidance-exclusion status and reason
- **AND** every owner SHALL identify an existing catalog skill
- **AND** Foundation and install-profile membership SHALL derive from catalog roles and pack extras
- **AND** `ot-runtime` SHALL be included in Core through its explicit operational profile role
- **AND** validation SHALL NOT depend on a second hard-coded owner map, profile list, or exact catalog count

### Requirement: Role-appropriate invocation

The catalog SHALL declare invocation policy by skill role rather than special-casing a skill name.
Model-only capability skills SHALL remain outside the user command menu. `ot-ask` SHALL remain
user-invoked with implicit model invocation prohibited. `ot-setup`, `ot-runtime`, and
`ot-mcp-proxy` SHALL support both explicit user invocation and implicit model invocation.

#### Scenario: Skill metadata is inspected
- **WHEN** a skill's frontmatter and any present Codex sidecar are parsed
- **THEN** the effective user and model invocation policies SHALL agree with its catalog role
- **AND** a default model-invoked skill without a sidecar SHALL retain implicit invocation
- **AND** validation SHALL reject a skill whose declared policy differs from its catalog role

### Requirement: Advisory capability guidance

Capability skills SHALL provide distinct operating judgment without copying shared call mechanics,
complete signatures, large references, or setup boilerplate. Conditional capabilities SHALL use
live help/setup diagnostics and SHALL hand missing prerequisites to `ot-setup` or, for MCP server
configuration and lifecycle, `ot-mcp-proxy`.

#### Scenario: A prerequisite is unavailable
- **WHEN** a capability preflight or first operation identifies a missing pack, extra, library, executable, credential, config value, renderer, or server
- **THEN** the skill SHALL stop before attempting the dependent operation
- **AND** it SHALL identify the relevant `ot.help(..., topic="setup")` subject
- **AND** it SHALL route pack/config work to `ot-setup` or server work to `ot-mcp-proxy`
- **AND** it SHALL NOT install, configure, connect, start services, or add credentials without a separate explicit approval

### Requirement: Catalog router

`ot-ask` SHALL route user situations to every current skill role, guidance owner, or the `ot-ref`
fallback without naming unknown skills or duplicating capability workflows. Its authored routing
rules SHALL be accompanied by generated catalog coverage.

#### Scenario: The router is validated
- **WHEN** catalog consistency checking reads `ot-ask`
- **THEN** every guidance owner and cross-catalog operational skill SHALL be reachable
- **AND** every named OneTool skill SHALL exist in the curated catalog
- **AND** missing pack/config/extras situations SHALL route to `ot-setup`
- **AND** root serving, Direct API, runtime status/debug/reload, statistics/telemetry, logs/results, and operational recovery SHALL route to `ot-runtime`
- **AND** MCP server setup, use, discovery, and recovery SHALL route to `ot-mcp-proxy`
- **AND** an explicitly guidance-excluded beta pack SHALL not be advertised by the router
- **AND** no distributed skill artifact, including `ot-ref` references, SHALL contain an excluded beta pack

## ADDED Requirements

### Requirement: Strategic pack guidance

Every stable built-in pack SHALL have authored guidance that explains its capability boundary,
high-value workflows, sequencing, material safety concerns, success verification, and pack-specific recovery.
Exact live signatures, config schemas, dependency state, and large DSL/policy references SHALL be
retrieved from runtime help rather than copied into the skill.

#### Scenario: A pack skill is reviewed
- **WHEN** an agent loads the owning skill for a built-in pack
- **THEN** it SHALL be able to decide when and why to use that pack
- **AND** it SHALL find a shortest safe workflow and a way to verify success
- **AND** it SHALL be directed to exact topic-scoped runtime help for details that can drift

#### Scenario: Complex pack guidance is validated
- **WHEN** skill validation examines an authored capability skill
- **THEN** it SHALL validate required semantic guidance and generated coverage markers
- **AND** it SHALL NOT force every capability skill into a fixed 15–40-line range

#### Scenario: The execution trust boundary is explained
- **WHEN** an agent loads `ot-ref` or requests deterministic security workflow help
- **THEN** it SHALL state that OneTool executes trusted Python with full builtins
- **AND** AST validation and output sanitization SHALL be described as defense-in-depth rather than a sandbox
- **AND** process, user, environment, path, secret, and external-content boundaries SHALL be explained without overstating isolation

### Requirement: Foundation setup skill

The catalog SHALL include `ot-setup` in every installation profile. The skill SHALL diagnose the
active OneTool environment before proposing installation or configuration work and SHALL separate
diagnosis, approval, mutation, and verification.

#### Scenario: Pack setup is requested
- **WHEN** a user asks to configure a pack or a capability skill reports a missing prerequisite
- **THEN** `ot-setup` SHALL inspect runtime status, config, and topic-scoped setup help
- **AND** it SHALL classify the missing extra, library, executable, secret, config, or server requirement
- **AND** it SHALL present the exact target and proposed action before requesting approval

#### Scenario: Approved setup is verified
- **WHEN** the user separately approves a proposed installation or config change
- **THEN** `ot-setup` SHALL use available host/CLI/config/secrets capabilities to apply only that scope
- **AND** it SHALL validate configuration, reload when required, repeat readiness diagnostics, and use a non-mutating smoke operation when available
- **AND** if the agent cannot modify the OneTool host it SHALL provide operator instructions instead of claiming success

### Requirement: MCP proxy lifecycle skill

The catalog SHALL replace `ot-servers` with `ot-mcp-proxy`. The new skill SHALL cover
authoritative-source selection, persistent stdio/HTTP/auth configuration, session lifecycle, live
tool/resource/prompt discovery, safe proxy use, verification, and bounded recovery for arbitrary
MCP servers using their current authoritative documentation.

#### Scenario: A proxy server is set up
- **WHEN** a user asks to set up an MCP server such as Playwright, Chrome DevTools, or an Azure integration
- **THEN** `ot-mcp-proxy` SHALL identify the exact server and authoritative source
- **AND** it SHALL consult the server's current MCP documentation instead of a maintained OneTool preset
- **AND** it SHALL distinguish persistent config from session-only enablement
- **AND** it SHALL propose redacted transport/auth/environment configuration and request approval before mutation
- **AND** it SHALL validate and connect only the named server

#### Scenario: A connected proxy is used
- **WHEN** the named server connects successfully
- **THEN** `ot-mcp-proxy` SHALL inspect exact server help, tools, resources, and prompts as relevant
- **AND** it SHALL call the live proxy namespace using inspected signatures
- **AND** it SHALL verify the requested external outcome
- **AND** it SHALL attempt connection recovery at most once before surfacing the failure

#### Scenario: Browser annotation boundary
- **WHEN** a task uses Playwright or Chrome DevTools through OneTool
- **THEN** `ot-browser-guidance` SHALL own only annotation/highlighting workflows from `play_util` or `chrome_util`
- **AND** navigation, clicking, typing, inspection, resources, prompts, and other browser operations SHALL use the underlying proxied namespace and `ot-mcp-proxy`

### Requirement: Runtime operations skill

The catalog SHALL include user- and model-invocable `ot-runtime` as the single workflow owner for
ongoing root-runtime operation after setup.

#### Scenario: A runtime operation is requested
- **WHEN** a user or agent needs root stdio/HTTP serving, Direct API use, status/debug/readiness, reload, statistics/telemetry, logs/results, or bounded operational recovery
- **THEN** `ot-runtime` SHALL explain and sequence the current runtime operations
- **AND** it SHALL distinguish the root runtime from outbound proxied MCP servers
- **AND** it SHALL warn that root HTTP has no built-in authentication and require an explicitly secured deployment before non-loopback exposure
- **AND** installation, extras, secrets, or persistent config mutation SHALL hand off to `ot-setup`
- **AND** outbound MCP server lifecycle SHALL hand off to `ot-mcp-proxy`
- **AND** general call syntax and tool discovery SHALL remain in `ot-ref`

### Requirement: Unified knowledge lifecycle skill

The catalog SHALL keep one `ot-knowledge` skill and SHALL NOT add a separate
`ot-knowledge-admin` skill.

#### Scenario: Knowledge guidance is requested
- **WHEN** an agent needs to build, maintain, query, or use a configured knowledge base
- **THEN** `ot-knowledge` SHALL present distinct build/maintain and query/use workflows
- **AND** it SHALL distinguish CLI index/reindex/enrich/scrape operations from MCP CRUD/retrieval/synthesis operations
- **AND** both workflows SHALL share setup, configuration, verification, degradation, and recovery guidance without duplicating ownership

### Requirement: Generated skill seams

Mechanical catalog facts SHALL be generated into named managed blocks while operating judgment
outside those blocks remains authored.

#### Scenario: Skill projections are synchronized
- **WHEN** the documentation/skill synchronization command runs
- **THEN** owned-pack coverage, available help topics, setup handoff, router coverage, profile membership, pack map, and central tool index SHALL be regenerated from the composed catalog
- **AND** content outside managed markers SHALL remain unchanged
- **AND** read-only skill validation SHALL fail when a projection is stale
- **AND** every skill-side projection SHALL exclude a beta pack whose catalog disposition prohibits skill guidance

### Requirement: Derived skill installation profiles

OneTool SHALL document selectable Foundation, Core, Core + `[util]`, Core + `[dev]`, and skill
`[all]` memberships derived from catalog roles and pack ownership. These names SHALL be presented as
documented selection recipes, not native installer profile names or fixed counts.

#### Scenario: A user installs a documented profile
- **WHEN** a user follows the skill installation documentation
- **THEN** the documentation SHALL use currently verified `npx skills@latest` interactive or explicit selective-install syntax
- **AND** recommended composed profiles SHALL include `ot-ref`
- **AND** individual skill installation SHALL remain supported
- **AND** the documentation SHALL distinguish skill `[all]` from the Python package `[all]` extra

#### Scenario: Installation profiles are verified
- **WHEN** distribution verification runs in clean temporary environments
- **THEN** the repository SHALL expose every catalog skill at its root skill path
- **AND** selective installation SHALL add only the requested skills
- **AND** skill `[all]` SHALL add every current catalog skill without relying on a hard-coded count
- **AND** list, discovery, install, update, and removal SHALL be exercised for each supported coding-agent target
- **AND** no OneTool runtime installer, `uvx` flow, or plugin packaging SHALL be introduced
