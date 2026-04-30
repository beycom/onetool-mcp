# serve-prompts Specification v2

## Purpose

Defines the YAML-based prompts configuration system for the MCP server. Covers server instructions, tool descriptions, prompt templates, and the trigger hierarchy for the `run` tool. Version 2 introduces a two-mode execution model (Snippets vs Code), a new trigger hierarchy (`>>>`, `__run`), and snippet param prefix resolution.

## Requirements

### Requirement: Prompts File Loading

The system SHALL load MCP prompts from a YAML configuration file.

#### Scenario: Default prompts file
- **GIVEN** prompts.yaml exists in the project root
- **WHEN** the server starts
- **THEN** it SHALL load prompts from prompts.yaml

#### Scenario: Missing prompts file
- **GIVEN** prompts.yaml does not exist
- **WHEN** the server starts
- **THEN** it SHALL use default hardcoded instructions

#### Scenario: Custom prompts path
- **GIVEN** config with `server.instructions_file: custom/prompts.yaml`
- **WHEN** the server starts
- **THEN** it SHALL load prompts from the specified path

#### Scenario: Invalid YAML
- **GIVEN** prompts.yaml contains invalid YAML syntax
- **WHEN** the server attempts to load it
- **THEN** it SHALL log a warning and use default instructions

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

#### Scenario: Trigger pattern in default
- **GIVEN** no prompts.yaml or no instructions key
- **WHEN** default instructions are used
- **THEN** they SHALL include the `>>>` trigger and `mcp__onetool__run` canonical name

#### Scenario: Instructions are concise
- **WHEN** the server builds the handshake instructions
- **THEN** the resulting prompt SHALL contain at most 35 lines
- **AND** SHALL include: identity line, trigger aliases (`>>>`, `__run`, `mcp__onetool__run`), pass-through rule, keyword-args rule, batch rule, discovery hint (`>>> ot.help(query="...")`), proxy recovery guidance (`ot_servers.enable(name="...")` then retry once when name is known; `ot.servers()` when unknown), external content boundary warning, and tool output directive

#### Scenario: Discovery hint present
- **WHEN** an agent is lost or encountering errors
- **THEN** the prompt SHALL direct the agent to run `>>> ot.help(query="topic")` for discovery
- **AND** MAY include `ot.skills(name="ot-ref")` as an optional extended reference path

### Requirement: Two-Mode Execution Model

The server instructions SHALL describe two distinct execution modes as first-class, separate systems.

#### Scenario: Mode 1 — Snippets documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL describe Snippets as Jinja2 templates invoked with `>>> $name key=value`
- **AND** SHALL document that values are plain strings (Python syntax does not apply)
- **AND** SHALL document that outer quotes are stripped (`q=abc` ≡ `q="abc"`)
- **AND** SHALL document that param names support prefix abbreviation
- **AND** SHALL document that per-template features (e.g. pipe batch) are not snippet language features

#### Scenario: Mode 2 — Code documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL describe Code as direct Python execution via `>>> pack.fn(key="val")`
- **AND** SHALL document that Python syntax applies (strings must be quoted)
- **AND** SHALL document that short param names are resolved by pack proxy prefix matching
- **AND** SHALL document that keyword arguments only are accepted

#### Scenario: Modes are separate
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** the two modes SHALL be presented as separate systems with different rules
- **AND** SHALL NOT conflate snippet string-value rules with Python code syntax rules

### Requirement: Trigger Hierarchy

The server instructions SHALL document the full trigger hierarchy with rationale.

#### Scenario: Trigger hierarchy documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL identify `>>>` as the recommended human-friendly trigger (Python REPL symbol)
- **AND** SHALL identify `__run` as the systematic short form following the `__(tool)` pattern
- **AND** SHALL identify `mcp__onetool__run` as the canonical MCP name (`mcp__(server)__(tool)`)
- **AND** SHALL identify `__ot`, `__onetool` etc. as legacy triggers kept for backward compat only

#### Scenario: Legacy triggers not advertised
- **GIVEN** the default prompts template
- **WHEN** instructions are generated
- **THEN** `__ot` and `__onetool` SHALL NOT appear as recommended forms
- **AND** SHALL be kept working (recognised by the fence processor) without documentation

### Requirement: Snippet Param Prefix Resolution

The system SHALL resolve abbreviated snippet param names using prefix matching.

#### Scenario: Abbreviated param resolved
- **GIVEN** a snippet with param `query` defined in snippets.yaml
- **WHEN** the user invokes `>>> $snip q=test`
- **THEN** `q` SHALL be resolved to `query` (prefix match, single candidate)

#### Scenario: Exact match wins
- **GIVEN** a snippet with params `quality` and `query`
- **WHEN** the user invokes with `query=abc`
- **THEN** `query` SHALL resolve to `query` (exact match, not `quality`)

#### Scenario: First in definition order wins on tie
- **GIVEN** a snippet with params `quality` and `query` (in that order)
- **WHEN** the user invokes with `q=abc`
- **THEN** `q` SHALL resolve to `quality` (first prefix match in YAML definition order)

#### Scenario: No match passthrough
- **GIVEN** a snippet with param `query`
- **WHEN** the user invokes with an unknown param name
- **THEN** the unknown param SHALL pass through; the existing warning SHALL be emitted

### Requirement: MCP Tool Naming Convention

The server instructions SHALL document the MCP tool naming pattern and its derived short forms.

#### Scenario: Canonical name documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL specify the MCP tool name as `mcp__onetool__run`

#### Scenario: Convention explained
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL explain the `mcp__<server>__<tool>` pattern
- **AND** SHALL explain that `__run` is the derived short form (`__(tool)` pattern)

### Requirement: Prompt Templates

The system SHALL support reusable prompt templates.

#### Scenario: Template definition
- **GIVEN** prompts.yaml with templates section containing named templates
- **WHEN** templates are loaded
- **THEN** each template SHALL have description and template fields

#### Scenario: Template variables
- **GIVEN** template with `{variable}` placeholders
- **WHEN** template is rendered with kwargs
- **THEN** placeholders SHALL be replaced with provided values

#### Scenario: Template registration
- **GIVEN** templates defined in prompts.yaml
- **WHEN** the MCP server starts
- **THEN** templates SHALL be registered as MCP prompts

### Requirement: Prompts Configuration Model

The system SHALL use a Pydantic model for prompts configuration.

#### Scenario: PromptsConfig structure
- **GIVEN** prompts.yaml is loaded
- **WHEN** parsed
- **THEN** it SHALL validate against PromptsConfig model with: instructions (str), tools (dict), templates (dict)

#### Scenario: ToolPrompt structure
- **GIVEN** a tool prompt entry
- **WHEN** parsed
- **THEN** it SHALL validate: description (str), examples (list[str])

#### Scenario: PromptTemplate structure
- **GIVEN** a template entry
- **WHEN** parsed
- **THEN** it SHALL validate: description (str), template (str)

### Requirement: Get Instructions Helper

The system SHALL provide a helper function for getting instructions.

#### Scenario: Get from file
- **GIVEN** prompts.yaml exists with instructions
- **WHEN** get_instructions() is called
- **THEN** it SHALL return the file-based instructions

#### Scenario: Get fallback
- **GIVEN** no prompts file or no instructions key
- **WHEN** get_instructions() is called
- **THEN** it SHALL return default instructions

#### Scenario: Caching
- **GIVEN** prompts.yaml has been loaded once
- **WHEN** get_instructions() is called again
- **THEN** it MAY use cached result for performance

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
- **AND** it MAY include `ot.skills(name="ot-ref")` as an optional advanced reference

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
- **THEN** trigger patterns SHALL be documented in instructions only (not duplicated in tool description)

#### Scenario: Critical rules in both
- **GIVEN** default prompts configuration
- **WHEN** tool description and instructions are generated
- **THEN** critical pass-through rules ("DO NOT rewrite", "JUST pass the exact command") SHALL appear in both for redundancy

## Removed Requirements

### Requirement: Canonical Format Documentation
**Reason:** Superseded by Two-Mode Execution Model + Trigger Hierarchy requirements. The old three code styles (simple, backtick, fence) are replaced by the two-mode framing. Backtick style is dropped. The canonical reference format (`mcp__onetool__run(command='...')`) is retained only as an example of direct MCP invocation.

### Requirement: Explicit Trigger Documentation (v1)
**Reason:** Replaced by the new Trigger Hierarchy requirement, which documents the full `>>>` / `__run` / `mcp__onetool__run` / legacy hierarchy with rationale.

### Requirement: Discovery functions documented
**Reason:** Discovery reference material is too detailed for the always-on prompt. Core guidance remains in always-on instructions; advanced edge cases live in `ot-ref`.

**Migration:** Agents can run `>>> ot.help(query="topic")` directly for discovery. `ot-ref` remains optional.
