## ADDED Requirements

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
