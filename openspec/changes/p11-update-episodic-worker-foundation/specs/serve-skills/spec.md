## ADDED Requirements

### Requirement: Episodic orchestrator skill distribution

OneTool SHALL distribute `episodic-orchestrator` as a standard Agent Skill at
`skills/episodic-orchestrator/SKILL.md`. It SHALL include Codex sidecar metadata
that prohibits implicit invocation and SHALL NOT require an MCP skill-serving or
installation tool.

#### Scenario: Repository skill layout
- **WHEN** the repository skill directory is inspected
- **THEN** `skills/episodic-orchestrator/SKILL.md` SHALL exist with standard name and description frontmatter
- **AND** `skills/episodic-orchestrator/agents/openai.yaml` SHALL set `policy.allow_implicit_invocation` to `false`

#### Scenario: Skill is discoverable by a standard installer
- **WHEN** a standard Agent Skills installer lists repository skills
- **THEN** `episodic-orchestrator` SHALL be available for installation
- **AND** no OneTool runtime operation SHALL be required to retrieve or install it
