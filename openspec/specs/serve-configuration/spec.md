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

The root config SHALL support the current runtime sections, including independent
generation and embedding sections. A generation model registry and coding-harness
launch behaviour SHALL not be part of MCP configuration.

#### Scenario: Supported root sections
- **GIVEN** a config containing `include`, `env`, `llm`, `embeddings`, `alias`, `snippets`, `servers`, `direct`, `tools`, `security`, `stats`, `telemetry`, `output`, `tools_dir`, `prompts`, `log_level`, `log_dir`, `compact_max_length`, `log_verbose`, or `debug_tracebacks`
- **WHEN** OneTool loads configuration
- **THEN** each recognised section SHALL be validated according to its current schema

#### Scenario: Backend-aware generation configuration
- **GIVEN** a top-level `llm` section
- **WHEN** OneTool loads configuration
- **THEN** the strict section SHALL accept backend, interface, base URL, direct
  model, named secret, effort, timeout, and `max_tokens`
- **AND** omitted backend, interface, and secret name SHALL use OpenAI-compatible defaults
- **AND** backend-inapplicable or unknown fields SHALL be rejected

#### Scenario: Embedding configuration is independent
- **GIVEN** a top-level `embeddings` section
- **WHEN** OneTool loads configuration
- **THEN** the section SHALL validate an `openai_compatible` backend with its own model, base URL, named secret, dimensions, timeout, batching, and token-limit settings
- **AND** no generation field SHALL be used to derive an embedding route

#### Scenario: CLIProxyAPI embeddings are rejected
- **GIVEN** a top-level `embeddings` section with `backend: cliproxy`
- **WHEN** OneTool loads configuration
- **THEN** strict validation SHALL reject the unsupported embedding backend
- **AND** OneTool SHALL NOT send embedding requests to the CLIProxyAPI generation endpoint

#### Scenario: Unknown root section
- **GIVEN** a config containing an unrecognised root key
- **WHEN** OneTool loads configuration
- **THEN** the unknown key SHALL be ignored
- **AND** OneTool SHALL emit a warning naming the ignored attribute

#### Scenario: Unknown typed nested attribute
- **GIVEN** a config containing an unrecognised key under a typed section such as `llm`, `embeddings`, `direct.host`, `security`, `stats`, `telemetry`, or `output`
- **WHEN** OneTool loads configuration
- **THEN** the unknown nested key SHALL be rejected when that section is strict or otherwise ignored according to its current schema
- **AND** an ignored key SHALL emit a warning naming the ignored attribute path

#### Scenario: Tool-specific config sections
- **GIVEN** a config containing extra pack names under `tools`
- **WHEN** OneTool loads configuration
- **THEN** those pack-specific dictionaries SHALL be preserved for runtime tool lookup

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

Configuration paths SHALL resolve relative to the directory containing the loaded
config file—the active OneTool config directory—unless a path is absolute.

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

### Requirement: Shared generation connection

The strict top-level `llm` section SHALL configure the shared backend-aware
generation client. It SHALL accept direct model selection and the connection
fields permitted by the selected backend.

#### Scenario: Compatible defaults
- **WHEN** `llm` or its backend fields are omitted
- **THEN** published OpenAI-compatible generation model, endpoint, token limit, Chat Completions, and credential defaults SHALL apply

#### Scenario: CLIProxy restrictions
- **WHEN** `llm.backend` is `cliproxy`
- **THEN** Responses and `CLIPROXY_INFERENCE_KEY` SHALL be fixed
- **AND** explicit interface or secret-name fields SHALL be rejected

#### Scenario: Unsupported output-limit field
- **WHEN** `llm` contains `max_output_tokens` instead of `max_tokens`
- **THEN** strict validation SHALL reject it

#### Scenario: Launcher independence
- **WHEN** MCP configuration is absent, invalid, or changed
- **THEN** standalone code launcher construction SHALL remain determined only by its arguments and process environment

### Requirement: Typed tool generation selections

Each generation-capable pack SHALL accept optional direct `model` and `effort`
fields at pack scope. Pack configuration SHALL NOT select endpoint, credential,
backend, interface, timeout, output bound, alias, or operation-specific routes.

#### Scenario: Pack model override
- **WHEN** `tools.ot_image.model` contains a non-empty direct model ID
- **THEN** OneTool SHALL preserve it as the image pack override

#### Scenario: Pack effort override
- **WHEN** `tools.ot_llm.effort` contains `low`, `medium`, or `high`
- **THEN** OneTool SHALL preserve it as the pack effort override

#### Scenario: Knowledge uses one pack selection
- **WHEN** `tools.knowledge.model` or `tools.knowledge.effort` is configured
- **THEN** reranking, synthesis, and enrichment SHALL use those values when calls omit overrides
- **AND** separate ask, rerank, and enrich generation routes SHALL not exist

#### Scenario: Connection fields remain root-owned
- **WHEN** a pack omits model or effort
- **THEN** the corresponding root value SHALL apply
- **AND** endpoint, credential, timeout, and output bounds SHALL always come from top-level `llm`

#### Scenario: Unsupported pack routing fields
- **WHEN** a typed generation pack receives nested `llm`, backend, interface, source, endpoint, secret, operation route, or capability fields
- **THEN** strict configuration validation SHALL reject them

#### Scenario: Invalid effort
- **WHEN** root or pack configuration supplies a non-canonical effort
- **THEN** strict validation SHALL reject it
