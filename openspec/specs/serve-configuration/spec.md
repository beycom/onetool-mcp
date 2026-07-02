# serve-configuration Specification

## Purpose

Defines the current `onetool.yaml` configuration contract loaded by the OneTool
runtime. This spec covers schema shape, include handling, unknown-field behavior,
path resolution, and runtime variable expansion. Feature-specific behavior for
proxy servers, stats, output handling, direct execution, telemetry, prompts, and
secrets is covered by the dedicated specs for those capabilities.

## Requirements

### Requirement: Explicit YAML Configuration

OneTool SHALL load runtime configuration from an explicit YAML file path supplied
by the caller.

#### Scenario: Existing config file loads
- **GIVEN** `onetool serve --config /path/to/onetool.yaml`
- **WHEN** the file exists and contains valid YAML
- **THEN** OneTool SHALL parse and validate it as a version 2 config
- **AND** cache the loaded config for subsequent runtime lookups

#### Scenario: Missing config file fails
- **GIVEN** a config path that does not exist
- **WHEN** OneTool loads configuration
- **THEN** it SHALL raise an error identifying the missing config file

#### Scenario: Empty config file
- **GIVEN** an existing empty YAML config file
- **WHEN** OneTool loads configuration
- **THEN** it SHALL apply current defaults for omitted sections

### Requirement: Schema Version Handling

Config files SHALL use schema version 2.

#### Scenario: Version omitted
- **GIVEN** a config file without a `version` field
- **WHEN** OneTool loads configuration
- **THEN** it SHALL treat the config as version 2

#### Scenario: Version 1 rejected
- **GIVEN** a config file with `version: 1`
- **WHEN** OneTool loads configuration
- **THEN** it SHALL fail with a message that version 1 is unsupported

#### Scenario: Future version rejected
- **GIVEN** a config file with a version greater than the current supported version
- **WHEN** OneTool loads configuration
- **THEN** it SHALL fail with a message identifying the maximum supported version

### Requirement: Root Configuration Sections

The root config SHALL support the current top-level sections used by the runtime.

#### Scenario: Supported root sections
- **GIVEN** a config containing `include`, `env`, `llm`, `alias`, `snippets`, `servers`, `direct`, `display`, `tools`, `security`, `stats`, `telemetry`, `output`, `tools_dir`, `prompts`, `log_level`, `log_dir`, `compact_max_length`, `log_verbose`, or `debug_tracebacks`
- **WHEN** OneTool loads configuration
- **THEN** each recognised section SHALL be validated according to its current schema

#### Scenario: Unknown root section
- **GIVEN** a config containing an unrecognised root key
- **WHEN** OneTool loads configuration
- **THEN** the unknown key SHALL be ignored
- **AND** OneTool SHALL emit a warning naming the ignored attribute

#### Scenario: Unknown typed nested attribute
- **GIVEN** a config containing an unrecognised key under a typed section such as `direct.host`, `security`, `stats`, `telemetry`, or `output`
- **WHEN** OneTool loads configuration
- **THEN** the unknown nested key SHALL be ignored
- **AND** OneTool SHALL emit a warning naming the ignored attribute path

#### Scenario: Tool-specific config sections
- **GIVEN** a config containing extra pack names under `tools`
- **WHEN** OneTool loads configuration
- **THEN** those pack-specific dictionaries SHALL be preserved for runtime tool lookup

### Requirement: Display Queue Configuration

The root `display` config section SHALL control MCP-side display producer
retention.

#### Scenario: Display queue default
- **GIVEN** no `display` section
- **WHEN** OneTool loads configuration
- **THEN** `display.max_queue_messages` SHALL default to `1000`

#### Scenario: Display queue validation
- **GIVEN** `display.max_queue_messages` is less than `1`
- **WHEN** OneTool loads configuration
- **THEN** configuration loading SHALL fail with a validation error

### Requirement: Include Processing

Config files SHALL support reusable include files merged before validation.

#### Scenario: Relative include resolved from config directory
- **GIVEN** `include: ["prompts.yaml"]` in `/project/.onetool/onetool.yaml`
- **WHEN** `/project/.onetool/prompts.yaml` exists
- **THEN** OneTool SHALL merge that file into the effective config before validation

#### Scenario: Relative include falls back to packaged templates
- **GIVEN** a relative include that does not exist beside the config file
- **WHEN** a matching packaged template exists
- **THEN** OneTool SHALL merge the packaged template

#### Scenario: Include merge precedence
- **GIVEN** multiple include files and inline config values
- **WHEN** OneTool processes includes
- **THEN** include files SHALL merge left to right
- **AND** inline values in the main config SHALL override included values

#### Scenario: Nested include depth exceeded
- **GIVEN** nested includes deeper than the supported include depth
- **WHEN** OneTool processes configuration
- **THEN** it SHALL fail with an include-depth error

#### Scenario: Missing include skipped
- **GIVEN** an include path that cannot be resolved
- **WHEN** OneTool processes configuration
- **THEN** it SHALL continue loading the remaining config
- **AND** log a warning for the missing include

### Requirement: Path Resolution

Configuration paths SHALL resolve relative to the `.onetool` directory that
contains the loaded config file unless a path is absolute.

#### Scenario: Tool discovery path
- **GIVEN** `tools_dir: ["tools/*.py"]` in `/project/.onetool/onetool.yaml`
- **WHEN** OneTool discovers user tools
- **THEN** the pattern SHALL resolve relative to `/project/.onetool`
- **AND** only Python files matching the configured patterns SHALL be returned

#### Scenario: Absolute tool discovery path
- **GIVEN** an absolute pattern in `tools_dir`
- **WHEN** OneTool discovers user tools
- **THEN** the absolute pattern SHALL be used as-is

#### Scenario: Tilde path
- **GIVEN** a config path value beginning with `~`
- **WHEN** OneTool resolves that path
- **THEN** it SHALL expand the user home directory before deciding whether the path is absolute

### Requirement: Runtime Variable Expansion

Variable expansion SHALL occur at point of use, not while the root config file is
initially parsed.

#### Scenario: Tool config variable
- **GIVEN** `tools.brave.api_key: "${BRAVE_API_KEY}"`
- **WHEN** a tool requests typed config for the `brave` pack
- **THEN** OneTool SHALL expand `${BRAVE_API_KEY}` before schema validation

#### Scenario: Expansion precedence
- **GIVEN** the same variable name exists in secrets, caller-provided env, root config `env`, and the process environment
- **WHEN** a runtime value is expanded
- **THEN** OneTool SHALL use the first value in that order

#### Scenario: Default value syntax
- **GIVEN** a value containing `${MODEL:-gpt-5.4-nano}`
- **WHEN** `MODEL` is not available from any earlier expansion source
- **THEN** OneTool SHALL use `gpt-5.4-nano`

#### Scenario: Missing variable
- **GIVEN** a value containing `${MISSING_VAR}` without a default
- **WHEN** the value is expanded
- **THEN** OneTool SHALL fail with a message listing the missing variable

### Requirement: Tool Configuration Lookup

Tool packs SHALL retrieve their pack-specific configuration through the runtime
tool config lookup contract.

#### Scenario: Raw tool config lookup
- **GIVEN** `tools.webfetch.timeout: 10`
- **WHEN** the `webfetch` pack requests raw config
- **THEN** OneTool SHALL return the expanded dictionary for `tools.webfetch`

#### Scenario: Typed tool config lookup
- **GIVEN** a tool pack supplies a schema for its config
- **WHEN** the configured values match the schema
- **THEN** OneTool SHALL return a typed config object with configured values and schema defaults

#### Scenario: Unknown typed tool config key
- **GIVEN** a configured key not recognised by a tool pack's typed schema
- **WHEN** the pack requests typed config
- **THEN** OneTool SHALL fail visibly with an invalid tool configuration error

### Requirement: Runtime Logging Configuration

Logging configuration SHALL be available from config defaults and environment
overrides.

#### Scenario: Configured log level
- **GIVEN** `log_level: DEBUG`
- **WHEN** runtime logging asks for the effective log level
- **THEN** OneTool SHALL return `DEBUG`

#### Scenario: Environment log level override
- **GIVEN** `OT_LOG_LEVEL=ERROR`
- **WHEN** runtime logging asks for the effective log level
- **THEN** OneTool SHALL return `ERROR`

#### Scenario: Log directory override
- **GIVEN** `OT_LOG_DIR` is set
- **WHEN** runtime logging asks for the effective log directory
- **THEN** OneTool SHALL use the environment value instead of `log_dir`

#### Scenario: Compact length override
- **GIVEN** `OT_COMPACT_MAX_LENGTH` is set to an integer
- **WHEN** compact log formatting asks for the maximum value length
- **THEN** OneTool SHALL use the environment value instead of `compact_max_length`
