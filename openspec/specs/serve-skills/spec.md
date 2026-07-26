# serve-skills Specification

## Purpose

Defines OneTool's curated, repository-distributed Agent Skills catalog. Skills are installed and
loaded by host agents; OneTool does not serve or install them at runtime.

## Requirements

### Requirement: Curated catalog coverage

Every built-in documented pack SHALL have exactly one operating-guidance owner in the 20-skill
catalog, and catalog profiles SHALL resolve from that reviewed ownership metadata.

#### Scenario: Catalog consistency is checked
- **WHEN** the read-only skill catalog validation runs
- **THEN** ownership SHALL cover every built-in pack exactly once
- **AND** derived profile membership SHALL match the documented profile contract

### Requirement: Role-appropriate invocation

Model-invoked skills SHALL rely on Codex's default implicit invocation unless they need optional
Codex-specific metadata, and SHALL remain outside the user command menu. `ot-ask` SHALL be
user-invoked and SHALL use a Codex sidecar to prohibit implicit model invocation.

#### Scenario: Skill metadata is inspected
- **WHEN** a skill's frontmatter and any present Codex sidecar are parsed
- **THEN** the effective policy SHALL agree with that skill's invocation role
- **AND** absence of a model-invoked skill sidecar SHALL use the default implicit policy

### Requirement: Advisory capability guidance

Capability skills SHALL provide distinct operating guidance without copying shared call mechanics.
Conditional capabilities SHALL check live availability and advise on missing requirements without
installing, configuring, starting services, or adding credentials automatically.

#### Scenario: A prerequisite is unavailable
- **WHEN** a capability preflight or first operation identifies a missing prerequisite
- **THEN** the skill SHALL stop, state what is missing, and offer installation or configuration guidance

### Requirement: Catalog router

`ot-ask` SHALL route user situations to every current guidance owner or the `ot-ref` fallback
without naming unknown skills or duplicating capability workflows.

#### Scenario: The router is validated
- **WHEN** catalog consistency checking reads `ot-ask`
- **THEN** every guidance owner SHALL be reachable
- **AND** every named OneTool skill SHALL exist in the curated catalog

### Requirement: External distribution boundary

Skills SHALL live under the repository-root `skills/` directory for standard third-party
installers. OneTool SHALL expose no MCP skill-content or skill-installer tool.

#### Scenario: Runtime tools are inspected
- **WHEN** the OneTool registry is listed
- **THEN** no runtime tool SHALL list, retrieve, or install skill content
