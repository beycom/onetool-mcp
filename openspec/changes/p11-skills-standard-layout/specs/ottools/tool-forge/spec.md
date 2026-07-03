## REMOVED Requirements

### Requirement: Install Skill Stub Function

**Reason**: The bundled-skills installer path is removed per maintainer ruling (2026-07-03): standard skill installation now exists (`npx skills add` / vercel-labs/skills, APM, manual copy), and OneTool should not own per-agent stub installation. Per the V3 no-backcompat rule, removal is clean — no shim, no alias.
**Migration**: Use an external skill installer against the repository's top-level `skills/` directory, e.g. `npx skills add <repo> --skill ot-ref --agent codex`. See the `serve-skills` capability's "External Installer Discovery" requirement.

The ot_forge pack SHALL provide an `install_skills()` function to install skill stubs for AI tools.

#### Scenario: Install stub for Claude Code (default)
- **WHEN** `ot_forge.install_skills(install="ot-ref")` is called
- **THEN** it SHALL write a stub file to `.claude/skills/ot-ref/SKILL.md`
- **AND** the stub SHALL contain the full body content of the skill

#### Scenario: Install stub for Codex
- **WHEN** `ot_forge.install_skills(install="ot-ref", tool="codex")` is called
- **THEN** it SHALL write a stub file to `.codex/skills/ot-ref/SKILL.md`

#### Scenario: Install stub for OpenCode
- **WHEN** `ot_forge.install_skills(install="ot-ref", tool="opencode")` is called
- **THEN** it SHALL write a stub file to `.opencode/skills/ot-ref/SKILL.md`

#### Scenario: Install stub for Pi
- **WHEN** `ot_forge.install_skills(install="ot-ref", tool="pi")` is called
- **THEN** it SHALL write a stub file to `.pi/skills/ot-ref/SKILL.md`

#### Scenario: Install all stubs
- **WHEN** `ot_forge.install_skills(install="all")` is called
- **THEN** it SHALL install stubs for all bundled skills
- **AND** default tool SHALL be `"claude"`

#### Scenario: Stub already installed
- **WHEN** `ot_forge.install_skills(install="ot-ref")` is called
- **AND** the stub file already exists
- **THEN** it SHALL overwrite the existing stub
- **AND** report that it was updated

#### Scenario: Unknown skill name
- **WHEN** `ot_forge.install_skills(install="unknown-skill")` is called
- **THEN** it SHALL return an error message listing available skill names

#### Scenario: Unsupported tool
- **WHEN** `ot_forge.install_skills(install="ot-ref", tool="unknown-tool")` is called
- **THEN** it SHALL return an error message listing supported tools

### Requirement: Stub File Format

**Reason**: Depends on `install_skills()`, removed for the same reason above.
**Migration**: None — `SKILL.md` at `skills/ot-ref/SKILL.md` already uses the standard `name:`/`description:` frontmatter contract external installers expect; no OneTool-side format concern remains.

Skill stub files SHALL use a unified frontmatter format with `name:` and `description:` fields.

#### Scenario: Stub frontmatter format (all tools)
- **WHEN** a stub is installed for any supported tool
- **THEN** the file SHALL have YAML frontmatter with both `name:` and `description:` fields
- **AND** the body SHALL contain the full content of the skill (not a call to `ot.skills()`)

### Requirement: Tool Path Configuration

**Reason**: Depends on `install_skills()`, removed for the same reason above. `global_templates/skills.md` (the per-agent path config it read) is deleted alongside it.
**Migration**: Per-agent path resolution is now an external installer's responsibility (e.g. vercel-labs/skills already resolves `.claude/skills/`, `.codex/skills/`, `.opencode/skills/`, etc. per agent).

Stub installation paths SHALL be driven by configuration in `global_templates/skills.md`.

#### Scenario: Path config read from skills.md
- **WHEN** `ot_forge.install_skills()` resolves the installation path
- **THEN** it SHALL read the path template from `global_templates/skills.md` for the specified tool
- **AND** substitute `{name}` with the skill name
