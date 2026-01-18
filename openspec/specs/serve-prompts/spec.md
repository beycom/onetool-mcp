# serve-prompts Specification

## Purpose

Defines the YAML-based prompts configuration system for the MCP server. Covers server instructions, tool descriptions, prompt templates, and the `__onetool__run` trigger pattern documentation.
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

The system SHALL support externalized server instructions with explicit trigger documentation.

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
- **THEN** it SHALL return default instructions including `__onetool__run` trigger documentation

#### Scenario: Trigger pattern in default
- **GIVEN** no prompts.yaml or no instructions key
- **WHEN** default instructions are used
- **THEN** they SHALL include the `__onetool__run` trigger pattern and canonical formats

### Requirement: Tool-Specific Prompts

The system SHALL support tool-specific descriptions and examples.

#### Scenario: Tool description override
- **GIVEN** prompts.yaml with `tools.run.description: "Custom run description"`
- **WHEN** the run tool is registered
- **THEN** it SHALL use the custom description

#### Scenario: Tool examples
- **GIVEN** prompts.yaml with `tools.run.examples: ["example1", "example2"]`
- **WHEN** tool descriptions are formatted
- **THEN** examples SHALL be included in the description

#### Scenario: Unknown tool
- **GIVEN** prompts.yaml with description for non-existent tool
- **WHEN** prompts are loaded
- **THEN** the extra config SHALL be ignored without error

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

### Requirement: Explicit Trigger Documentation

The server instructions SHALL document the `__onetool__run` trigger pattern.

#### Scenario: Trigger pattern in instructions
- **GIVEN** prompts.yaml with instructions section
- **WHEN** the instructions are loaded
- **THEN** they SHALL include documentation of the `__onetool__run` trigger

#### Scenario: When to use documentation
- **GIVEN** prompts.yaml instructions
- **WHEN** an LLM reads the instructions
- **THEN** it SHALL understand to call `run` when it sees `__onetool__run` in user messages

### Requirement: Canonical Format Documentation

The server instructions SHALL document the four canonical invocation formats.

#### Scenario: Simple format documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL document `__onetool__run func(arg="value")`

#### Scenario: Backtick format documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL document `__onetool__run \`code\``

#### Scenario: Code fence format documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL document `__onetool__run` followed by code fence

#### Scenario: Direct MCP format documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL document `mcp__onetool__run(command='...')`

### Requirement: MCP Tool Naming Convention

The server instructions SHALL document the MCP tool naming pattern.

#### Scenario: Tool name documented
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL specify the MCP tool name as `mcp__onetool__run`

#### Scenario: Convention explained
- **GIVEN** prompts.yaml instructions
- **WHEN** loaded
- **THEN** they SHALL explain the `mcp__<server>__<tool>` pattern

