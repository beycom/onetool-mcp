## REMOVED Requirements

### Requirement: Skills Listing

**Reason**: The runtime `ot.skills()` serving path is removed per maintainer ruling (2026-07-03): it predates the now-standard Agent Skills layout, and external installers (e.g. `npx skills add`) now own skill delivery. Per the V3 no-backcompat rule, removal is clean — no shim, no alias.
**Migration**: There is no runtime replacement. Agents discover and load skill content through their host's own skill-loading mechanism once a skill is installed via an external installer (see the new "Top-Level Skill Layout" and "External Installer Discovery" requirements below). There is no `ot.*` call that lists or filters skills at runtime anymore.

The system SHALL provide an `ot.skills()` function that lists available bundled skills.

#### Scenario: List all skills
- **WHEN** `ot.skills()` is called with no arguments
- **THEN** it SHALL return a formatted list of all bundled skills
- **AND** each entry SHALL include the skill name and description

#### Scenario: Min info level
- **WHEN** `ot.skills(info="min")` is called
- **THEN** it SHALL return skill names only

#### Scenario: Default info level
- **WHEN** `ot.skills(info="default")` is called
- **THEN** it SHALL return skill name and description for each entry

#### Scenario: Filter by pattern
- **WHEN** `ot.skills(pattern="devtools")` is called
- **THEN** it SHALL return only skills whose name contains "devtools"

#### Scenario: Full info level
- **WHEN** `ot.skills(info="full")` is called
- **THEN** it SHALL return name, description, tags, and source path for each skill

#### Scenario: Invalid info level
- **WHEN** `ot.skills(info="list")` is called
- **THEN** it SHALL raise a ValueError indicating valid levels are `min`, `default`, and `full`

#### Scenario: No skills match pattern
- **WHEN** `ot.skills(pattern="nonexistent")` is called
- **THEN** it SHALL return a message indicating no skills matched

### Requirement: Skill Content Retrieval

**Reason**: Same as "Skills Listing" — the runtime serving path is removed cleanly in V3.
**Migration**: None. Skill body content is no longer retrievable through a OneTool tool call; it is read directly from the installed `SKILL.md` file by the host agent's skill loader.

The system SHALL return the full body of a named skill via `ot.skills(name=...)`.

#### Scenario: Retrieve bundled skill
- **WHEN** `ot.skills(name="ot-ref")` is called
- **THEN** it SHALL return the full Markdown body of the skill (below the frontmatter)
- **AND** the body SHALL reflect the currently running server version

#### Scenario: Unknown skill name
- **WHEN** `ot.skills(name="does-not-exist")` is called
- **THEN** it SHALL return an error message listing available skill names

#### Scenario: Bundled skill content location
- **WHEN** a bundled skill is requested
- **THEN** it SHALL be read from `global_templates/skills/<name>.md`
- **AND** frontmatter (between `---` markers) SHALL be parsed and excluded from the returned body

### Requirement: Bundled Skill Set

**Reason**: This requirement described a runtime "bundling" concept (`global_templates/skills/`) that no longer exists, and required two skills (`ot-chrome-devtools-mcp`, `ot-playwright-mcp`) that were never implemented — a spec/reality drift being resolved by this change alongside the removal.
**Migration**: See "Top-Level Skill Layout" below — `ot-ref` is now distributed as `skills/ot-ref/SKILL.md`. No replacement is planned for `ot-chrome-devtools-mcp` or `ot-playwright-mcp`; they were never built and are out of scope.

The system SHALL bundle an initial set of skills for on-demand discovery and server guides.

#### Scenario: ot-ref skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-ref` SHALL be listed

#### Scenario: ot-ref direct run discoverability
- **WHEN** bundled `ot-ref` frontmatter is parsed
- **THEN** its description SHALL include trigger terms for `__onetool`, MCP `run`, direct pack calls, and run-vs-local-script decisions

#### Scenario: ot-ref advanced reference scope
- **WHEN** `ot.skills(name="ot-ref")` is called
- **THEN** the returned body SHALL include advanced recovery, proxy handling, security, output, and ctx guidance
- **AND** it SHALL open with guidance that it applies when a OneTool `__onetool`/MCP run request needs advanced recovery or decision-boundary help
- **AND** it SHALL include parameter prefix matching and readable discovery hints
- **AND** it SHALL NOT be the only place where normal invocation modes are documented
- **AND** its content SHALL include error recovery patterns, security allowlist guidance, output format/sanitisation controls, multi-step patterns, pack extras, and parameter traps

#### Scenario: ot-chrome-devtools-mcp skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-chrome-devtools-mcp` SHALL be listed
- **AND** its content SHALL cover Chrome DevTools-compatible MCP server tools, connection modes, and usage patterns

#### Scenario: ot-playwright-mcp skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-playwright-mcp` SHALL be listed
- **AND** its content SHALL cover Playwright-compatible MCP server tools and usage patterns

## ADDED Requirements

### Requirement: Top-Level Skill Layout

OneTool SHALL distribute skills as standard Agent Skills at the repository root, not as a server-served or per-agent-installed resource.

#### Scenario: SKILL.md exists at the standard path
- **WHEN** the repository is inspected at its root
- **THEN** `skills/ot-ref/SKILL.md` SHALL exist
- **AND** it SHALL be the only copy of the `ot-ref` skill content in the repository (no duplicate under `src/ot/config/global_templates/skills/`)

#### Scenario: No runtime-serving copy remains
- **WHEN** the repository source tree is searched for `global_templates/skills/`
- **THEN** no `.md` skill files SHALL exist under that path
- **AND** no code path SHALL read skill content from `global_templates/skills/` at runtime

### Requirement: SKILL.md Frontmatter Contract

`skills/ot-ref/SKILL.md` SHALL use standard YAML frontmatter compatible with Claude/Agent Skills and the vercel-labs/skills installer.

#### Scenario: Frontmatter has name and description
- **WHEN** `skills/ot-ref/SKILL.md` is parsed
- **THEN** its YAML frontmatter SHALL contain a `name` field with value `ot-ref`
- **AND** SHALL contain a `description` field

### Requirement: Codex Sidecar Metadata

`skills/ot-ref/` SHALL include an OpenAI Codex Skills sidecar file providing invocation policy metadata.

#### Scenario: openai.yaml exists with implicit invocation allowed
- **WHEN** `skills/ot-ref/agents/openai.yaml` is inspected
- **THEN** the file SHALL exist
- **AND** it SHALL set `policy.allow_implicit_invocation` to `true`
- **AND** it SHALL NOT set `policy.allow_implicit_invocation` to `false` (a proactive tools-leverage skill wants implicit invocation on; this reverses the source issue's proposed `false` value per maintainer ruling)

### Requirement: External Installer Discovery

Skills SHALL be discoverable and installable by standard third-party skill installers without any OneTool-specific tooling.

#### Scenario: vercel-labs/skills discovers the skill
- **WHEN** `npx skills add <repo> --list` is run against the OneTool repository
- **THEN** `ot-ref` SHALL be listed as an installable skill

#### Scenario: vercel-labs/skills installs the skill for an agent
- **WHEN** `npx skills add <repo> --skill ot-ref --agent <agent>` is run
- **THEN** the installer SHALL place `ot-ref`'s `SKILL.md` (and, for Codex, `agents/openai.yaml`) at that agent's standard skill path
- **AND** OneTool SHALL NOT need to run any code to make this succeed (no server-side installer, no MCP tool call)

### Requirement: No OneTool-Owned Runtime Serving or Installer

OneTool SHALL NOT expose an MCP tool that lists, retrieves, or installs skill content.

#### Scenario: No ot.skills tool
- **WHEN** the OneTool MCP tool registry is inspected (e.g. `ot.tools()`)
- **THEN** no tool named `ot.skills` SHALL be present

#### Scenario: No ot_forge.install_skills tool
- **WHEN** the OneTool MCP tool registry is inspected (e.g. `ot.tools()`)
- **THEN** no tool named `ot_forge.install_skills` SHALL be present

#### Scenario: No installer machinery remains
- **WHEN** the repository source tree is searched for `install_skills`, `skill_stub`, `ot\.skills`, or `ottools.skills`
- **THEN** no matches SHALL be found outside the new `skills/` distribution content itself
