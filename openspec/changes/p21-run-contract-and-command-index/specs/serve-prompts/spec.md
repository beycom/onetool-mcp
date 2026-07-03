# serve-prompts Delta

Note: `p11-skills-standard-layout` also touches this spec (removing `ot.skills` references).
This change's wording is the final state where the two overlap; archive p11 first, then this.

## ADDED Requirements

### Requirement: Two Request Forms Documented

The run tool description SHALL state the two request forms side by side with one contrasting
example pair, so an agent never passes a natural-language sentence as code and never
over-literalizes an intent.

#### Scenario: Literal call form documented
- **GIVEN** the default prompts configuration
- **WHEN** the run tool description is generated
- **THEN** it SHALL document the literal form with the example `__ot ground.search(q='mcp features 2026')` → pass through and execute exactly as written

#### Scenario: Natural-language intent form documented
- **GIVEN** the default prompts configuration
- **WHEN** the run tool description is generated
- **THEN** it SHALL document the intent form with the example `use __ot ground.search to see MCP features 2026` → map to `ground.search(query='mcp features 2026')`, synthesizing args from the stated goal
- **AND** it SHALL direct the agent to inspect the signature first when unsure

### Requirement: Single Colon Rule Statement

The colon (snippet-prefix) rule SHALL be stated exactly once in the run tool description, as one
rule with one positive/negative example pair.

#### Scenario: One statement with example pair
- **GIVEN** the default prompts configuration
- **WHEN** the run tool description is generated
- **THEN** the snippet-only colon rule SHALL appear exactly once
- **AND** SHALL include a correct example (`:pkg_npm packages=react`) and an incorrect example (`:brave.search(query='x')`) side by side

### Requirement: Zero-Config Examples

Every example shipped in the run tool description SHALL execute successfully on a fresh base
install with no secrets configured.

#### Scenario: No key-gated examples
- **GIVEN** the default prompts configuration
- **WHEN** the run tool examples are generated
- **THEN** no example SHALL require an API key or secret (e.g. `brave.search(...)` SHALL NOT appear as an example)

#### Scenario: Fresh-install smoke
- **GIVEN** a fresh base install with no secrets.yaml entries
- **WHEN** each example from the run tool description is executed via `run`
- **THEN** every example SHALL succeed

### Requirement: Engine Forgiveness Documented Affirmatively

The run tool description SHALL teach the resolution forgiveness affirmatively so agents rely on it.

#### Scenario: Forgiveness line present
- **GIVEN** the default prompts configuration
- **WHEN** the run tool description is generated
- **THEN** it SHALL state that short kwarg prefixes resolve (with the `q=` → `query=` example)
- **AND** SHALL state that packs have short aliases (with the `wb.draw` → `whiteboard.draw` example)
- **AND** SHALL state that proxied tool names match in snake/camel/Pascal case

### Requirement: No Pack Summary Injection

The connection-time instructions SHALL NOT inline a pack list; the pack map is delivered via the
ot-ref skill layer.

#### Scenario: Placeholder mechanism removed
- **GIVEN** the server builds handshake instructions
- **WHEN** instructions are generated
- **THEN** no `{pack_summary}` placeholder handling SHALL exist in the server
- **AND** `rg -n "pack_summary" src/ot/` SHALL return no matches

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
- **AND** SHALL point agents to the host-installed `ot-ref` skill (load before the first OneTool call) and include the external content boundary warning
- **AND** SHALL NOT reference `ot.skills(...)` (surface removed)

#### Scenario: Discovery hint present
- **WHEN** an agent is lost or encountering errors
- **THEN** the prompt SHALL direct the agent to run `ot.help(query="topic")` for discovery
- **AND** MAY reference the `ot-ref` skill as the extended reference path

### Requirement: Tool-Specific Prompts

The system SHALL support tool-specific descriptions and examples with minimal redundancy.

#### Scenario: Tool description override
- **GIVEN** prompts.yaml with `tools.run.description: "Custom run description"`
- **WHEN** the run tool is registered
- **THEN** it SHALL use the custom description

#### Scenario: Run description includes proxy + reference guidance
- **GIVEN** default prompts configuration
- **WHEN** run tool description is generated
- **THEN** it SHALL include discovery references to `ot.help(...)`, `ot.tool_info(...)`, and `ot.tools(pattern='pack.', info='signatures')`
- **AND** it SHALL include proxy enable guidance (`ot_servers.enable(name="...")` → retry once)
- **AND** it SHALL NOT reference `ot.skills(...)` (surface removed)

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
