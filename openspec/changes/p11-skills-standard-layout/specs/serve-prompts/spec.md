## MODIFIED Requirements

### Requirement: Server Instructions

The system SHALL support externalised server instructions with a minimal footprint.

#### Scenario: Instructions loaded
- **GIVEN** prompts.yaml with `instructions: "Custom instructions..."`
- **WHEN** FastMCP server is created
- **THEN** it SHALL use the custom instructions

#### Scenario: Multiline instructions
- **GIVEN** prompts.yaml with multiline instructions using YAML literal block
- **WHEN** instructions are loaded
- **THEN** line breaks and formatting SHALL be preserved

#### Scenario: Instructions fallback
- **GIVEN** prompts.yaml without instructions key
- **WHEN** instructions are requested
- **THEN** it SHALL return default instructions

#### Scenario: Invocation contract referenced in default
- **GIVEN** no prompts.yaml or no instructions key
- **WHEN** default instructions are used
- **THEN** they SHALL direct agents to follow the `run` tool description first
- **AND** the `run` tool description SHALL include the supported prefixes `__onetool` and `__ot`

#### Scenario: Instructions are concise
- **WHEN** the server builds the handshake instructions
- **THEN** the resulting prompt SHALL contain at most 50 lines
- **AND** SHALL orient agents to use `run(command=...)` for available `pack.tool(...)` calls and light orchestration
- **AND** SHALL reserve local scripts for heavy repo/file transformations or reusable generation logic
- **AND** SHALL state that the `run` tool description is authoritative for invocation syntax, no-guessing, and pass-through behavior
- **AND** SHALL include an external content boundary warning

#### Scenario: Discovery hint present
- **WHEN** an agent is lost or encountering errors
- **THEN** the prompt SHALL direct the agent to run `ot.help(query="topic")` for discovery

### Requirement: Tool-Specific Prompts

The system SHALL support tool-specific descriptions and examples with minimal redundancy.

#### Scenario: Tool description override
- **GIVEN** prompts.yaml with `tools.run.description: "Custom run description"`
- **WHEN** the run tool is registered
- **THEN** it SHALL use the custom description

#### Scenario: Run description includes proxy + reference guidance
- **GIVEN** default prompts configuration
- **WHEN** run tool description is generated
- **THEN** it SHALL include discovery references to `ot.help(...)` and `ot.tool_info(...)`
- **AND** it SHALL include proxy enable guidance (`ot_servers.enable(name="...")` → retry once)

#### Scenario: Tool examples
- **GIVEN** prompts.yaml with `tools.run.examples: ["example1", "example2"]`
- **WHEN** tool descriptions are formatted
- **THEN** examples SHALL be included in the description

#### Scenario: Unknown tool
- **GIVEN** prompts.yaml with description for non-existent tool
- **WHEN** prompts are loaded
- **THEN** the extra config SHALL be ignored without error

#### Scenario: Trigger documentation placement
- **GIVEN** default prompts configuration
- **WHEN** the run tool description is generated
- **THEN** trigger patterns SHALL be documented in the run tool description, not duplicated in the server instructions

#### Scenario: Critical rules in run tool description
- **GIVEN** default prompts configuration
- **WHEN** tool description and instructions are generated
- **THEN** critical invocation modes and repair rules SHALL appear in the run tool description
- **AND** broad unscoped pass-through rules such as "JUST pass the exact command" SHALL NOT be required
