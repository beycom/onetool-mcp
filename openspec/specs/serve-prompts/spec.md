# serve-prompts Specification

## Purpose

Defines the YAML-based prompts configuration system for the MCP server. Covers server instructions, tool descriptions, prompt templates, and the invocation contract for the `run` tool.
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

### Requirement: Three-Mode Execution Model

The run tool description SHALL describe three distinct invocation modes by input shape.

#### Scenario: Mode 1 — Code documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** the run tool description SHALL describe fenced or backticked content as literal Python code
- **AND** SHALL document that valid unfenced Python is also code
- **AND** SHALL document that Python syntax applies (strings must be quoted)
- **AND** SHALL document that short param names are resolved by pack proxy prefix matching

#### Scenario: Mode 2 — Snippets documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** the run tool description SHALL describe Snippets as Jinja2 templates invoked with `:name key=value`
- **AND** SHALL document that values are plain strings (Python syntax does not apply)
- **AND** SHALL document that outer quotes are stripped (`q=abc` ≡ `q="abc"`)
- **AND** SHALL document that param names support prefix abbreviation
- **AND** SHALL document that per-template features (e.g. pipe batch) are not snippet language features

#### Scenario: Mode 3 — Natural language to code documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** the run tool description SHALL explain that free-form requests naming OneTool or a tool ask the agent to synthesize code
- **AND** SHALL require known or discovered signatures for tool-call synthesis
- **AND** SHALL direct agents to call `ot.tool_info(name="pack.tool")` or `ot.help(query="pack.tool")` when args are unknown
- **AND** SHALL direct agents to ask the user when required args remain ambiguous

#### Scenario: Modes are separate
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** the three modes SHALL be presented by shape with different rules
- **AND** SHALL NOT conflate snippet string-value rules with Python code syntax rules

### Requirement: Invocation Contract

The run tool description SHALL document the complete invocation contract.

#### Scenario: Supported prefixes documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** the run tool description SHALL identify `__onetool` as the canonical trigger
- **AND** SHALL identify `__ot` as the supported short alias
- **AND** SHALL document `:name key=value` as snippet syntax
- **AND** SHALL state that colon syntax applies only to snippets and must not be added to direct `pack.tool(...)` calls
- **AND** SHALL state that connected agents should call MCP `run(command=...)`
- **AND** SHALL state that direct pack calls use `pack.tool(arg=value)`, not `ot.pack.tool(...)`
- **AND** SHALL state that agents must not guess tool names, parameter names, or allowed values when they are unknown

#### Scenario: Tool call repair documented
- **GIVEN** default prompts configuration
- **WHEN** run tool description is generated
- **THEN** it SHALL direct agents to repair obvious tool-call shape issues using known or discovered signatures
- **AND** SHALL document that keyword-only tools must be called with keyword args, not positional args
- **AND** SHALL document that obvious syntax failures should not be sent just to fail

#### Scenario: Removed triggers not advertised
- **GIVEN** the default prompts template
- **WHEN** instructions are generated
- **THEN** `>>>`, `__run`, `__r`, `__ot__run`, `__onetool__run`, and `mcp__onetool__run` SHALL NOT appear as supported runtime prefixes

### Requirement: Snippet Param Prefix Resolution

The system SHALL resolve abbreviated snippet param names using prefix matching.

#### Scenario: Abbreviated param resolved
- **GIVEN** a snippet with param `query` defined in snippets.yaml
- **WHEN** the user invokes `__onetool :snip q=test`
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

### Requirement: MCP Tool Calling Convention

The prompts SHALL prefer direct MCP calls to the OneTool `run` tool.

#### Scenario: MCP call shape documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL specify the call shape as `run(command='<code>')`

#### Scenario: Local execution discouraged for tool calls
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL direct connected agents to use MCP `run(command=...)` for OneTool calls
- **AND** SHALL reserve local scripts for heavy repo/file transformations

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

### Requirement: Prompts Configuration Schema

The system SHALL validate prompt configuration using a typed schema before
server instructions, tool prompts, or MCP prompts are exposed.

#### Scenario: Top-level prompt configuration
- **GIVEN** prompts.yaml is loaded
- **WHEN** parsed
- **THEN** it SHALL accept `instructions` as a string, `tools` as a mapping, and `templates` as a mapping

#### Scenario: Tool prompt entries
- **GIVEN** a tool prompt entry
- **WHEN** parsed
- **THEN** it SHALL require a string description and a list of string examples

#### Scenario: Prompt template entries
- **GIVEN** a template entry
- **WHEN** parsed
- **THEN** it SHALL require a string description and string template body

### Requirement: Instruction Resolution

The system SHALL resolve server instructions from configured prompt content before using default instructions.

#### Scenario: Get from file
- **GIVEN** prompts.yaml exists with instructions
- **WHEN** server instructions are requested
- **THEN** it SHALL return the file-based instructions

#### Scenario: Get fallback
- **GIVEN** no prompts file or no instructions key
- **WHEN** server instructions are requested
- **THEN** it SHALL return default instructions

#### Scenario: Caching
- **GIVEN** prompts.yaml has been loaded once
- **WHEN** server instructions are requested again
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

