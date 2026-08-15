# serve-skills Specification

## Purpose

Defines how OneTool distributes skills as standard Agent Skills at the repository root (`skills/ot-ref/SKILL.md`), discoverable and installable by third-party skill installers (e.g. vercel-labs/skills, `npx skills add`). OneTool does not serve, retrieve, or install skill content at runtime; there is no `ot.skills()` tool. Host agents load skill content through their own skill-loading mechanism once a skill is installed by an external installer.

## Requirements

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

### Requirement: Use-worker skill distribution

OneTool SHALL distribute `use-worker` as a standard Agent Skill at
`skills/use-worker/SKILL.md`. It SHALL include Codex sidecar metadata
that prohibits implicit invocation and SHALL NOT require an MCP skill-serving or
installation tool.

#### Scenario: Repository skill layout
- **WHEN** the repository skill directory is inspected
- **THEN** `skills/use-worker/SKILL.md` SHALL exist with standard name and description frontmatter
- **AND** `skills/use-worker/agents/openai.yaml` SHALL set `policy.allow_implicit_invocation` to `false`

#### Scenario: Skill is discoverable by a standard installer
- **WHEN** a standard Agent Skills installer lists repository skills
- **THEN** `use-worker` SHALL be available for installation
- **AND** no OneTool runtime operation SHALL be required to retrieve or install it
