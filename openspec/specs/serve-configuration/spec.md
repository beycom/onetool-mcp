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

The root config SHALL support the current top-level sections used by the runtime,
including independent model-registry, generation, embedding, and code-launch
sections.

#### Scenario: Supported root sections
- **GIVEN** a config containing `include`, `env`, `models`, `llm`, `embeddings`, `code`, `alias`, `snippets`, `servers`, `direct`, `tools`, `security`, `stats`, `telemetry`, `output`, `tools_dir`, `prompts`, `log_level`, `log_dir`, `compact_max_length`, `log_verbose`, or `debug_tracebacks`
- **WHEN** OneTool loads configuration
- **THEN** each recognised section SHALL be validated according to its current schema

#### Scenario: Generation configuration is independent
- **GIVEN** a top-level `llm` section
- **WHEN** OneTool loads configuration
- **THEN** the section SHALL validate generation backend, explicit interface, model,
  effort, timeout, and output-limit settings
- **AND** it SHALL NOT accept embedding model, dimensions, batching, or token-limit settings

#### Scenario: Embedding configuration is independent
- **GIVEN** a top-level `embeddings` section
- **WHEN** OneTool loads configuration
- **THEN** the section SHALL validate an `openai_compatible` backend with its own model, base URL, named secret, dimensions, timeout, batching, and token-limit settings
- **AND** it SHALL NOT inherit endpoint, model, or credentials from `llm`

#### Scenario: CLIProxyAPI embeddings are rejected
- **GIVEN** a top-level `embeddings` section with `backend: cliproxy`
- **WHEN** OneTool loads configuration
- **THEN** strict validation SHALL reject the unsupported embedding backend
- **AND** OneTool SHALL NOT send embedding requests to the CLIProxyAPI generation endpoint

#### Scenario: Removed embedding key is rejected
- **GIVEN** a config containing `llm.embedding_model`
- **WHEN** OneTool loads configuration
- **THEN** strict nested validation SHALL reject the removed key
- **AND** OneTool SHALL NOT interpret it as an alias for `embeddings.model`

#### Scenario: Unknown root section
- **GIVEN** a config containing an unrecognised root key
- **WHEN** OneTool loads configuration
- **THEN** the unknown key SHALL be ignored
- **AND** OneTool SHALL emit a warning naming the ignored attribute

#### Scenario: Unknown typed nested attribute
- **GIVEN** a config containing an unrecognised key under a typed section such as `models`, `llm`, `embeddings`, `code`, `direct.host`, `security`, `stats`, `telemetry`, or `output`
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

### Requirement: Generation model registry

The strict top-level `models` mapping SHALL belong only to generation consumers.
The code launcher SHALL not read it.

#### Scenario: Generation model entry
- **WHEN** a top-level model entry is loaded
- **THEN** it SHALL validate exact shortcut, concrete id, source, optional
  generation proxy alias, modalities, interfaces, structured-output modes,
  efforts, and default effort
- **AND** it SHALL reject launcher-only or unused label, context-window, and harness
  metadata

#### Scenario: Launcher independence
- **WHEN** top-level models are absent, changed, or use generation-only aliases
- **THEN** code launcher resolution SHALL remain determined solely by the `code`
  target records

### Requirement: Typed code-launch configuration

The optional strict `code` section SHALL contain at least one proxy route or direct
Codex profile, plus optional default, permission, client overrides, and
presentation settings.

#### Scenario: Minimal proxy configuration
- **WHEN** configuration contains `code.proxy.routes` with one or more model
  records
- **THEN** it SHALL be valid
- **AND** connection, client, permission, and presentation defaults SHALL apply

#### Scenario: Minimal direct configuration
- **WHEN** configuration contains one or more `code.direct.codex.profiles` records
  without `code.proxy`
- **THEN** it SHALL be valid
- **AND** no proxy connection or credential SHALL be required

#### Scenario: Missing targets
- **WHEN** `code` contains neither a proxy route nor a direct Codex profile
- **THEN** strict validation SHALL reject it

#### Scenario: Proxy route mapping
- **WHEN** `code.proxy.routes` is loaded
- **THEN** its keys SHALL be exact `claude_subscription`, `codex_subscription`, or
  `openrouter` identifiers
- **AND** each configured value SHALL be a non-empty list of model records

#### Scenario: Direct Codex profile mapping
- **WHEN** `code.direct.codex.profiles` is loaded
- **THEN** each key SHALL be an exact profile name
- **AND** each value SHALL contain one or more model records

#### Scenario: Launcher model fields
- **WHEN** a launcher model record is loaded
- **THEN** only `id` SHALL be required
- **AND** the record MAY additionally contain a globally unique `shortcut`, a
  presentation-only non-empty `label`, and Claude context policy where applicable

#### Scenario: Claude context policy
- **WHEN** a launcher model contains `claude`
- **THEN** `context` SHALL accept only `standard` or `1m`
- **AND** optional `auto_compact_window` SHALL be a positive integer below
  1,000,000 and require `context: 1m`

#### Scenario: Duplicate within one target
- **WHEN** one route or profile contains the same exact model id more than once
- **THEN** strict validation SHALL reject it

#### Scenario: Same model across targets
- **WHEN** the same exact id appears in multiple routes or profiles
- **THEN** configuration SHALL be valid
- **AND** selecting it SHALL require an exact target

#### Scenario: Launcher identity collision
- **WHEN** any two launcher records use the same shortcut
- **OR** one record's shortcut equals a different record's model id
- **THEN** strict validation SHALL reject it

#### Scenario: Optional default
- **WHEN** `code.default` is configured
- **THEN** it SHALL contain a model id and at most one route or profile
- **AND** when neither target selector is supplied, the model id SHALL identify
  exactly one compatible configured target

#### Scenario: Permission
- **WHEN** `code.permission` is configured
- **THEN** it SHALL accept only `normal` or `bypass`
- **AND** omission SHALL default to `normal`

#### Scenario: Unknown or removed field
- **WHEN** launcher configuration contains an unknown field, removed model
  metadata, old route layout, transport, source, proxy alias, or proxy id
- **THEN** strict validation SHALL reject it without compatibility handling

### Requirement: Configurable harness clients

`code.clients` SHALL optionally override Claude and Codex executables, working
directories, and ordered additional argument lists. Codex MAY additionally define
`home_path`.

#### Scenario: Clients omitted
- **WHEN** `code.clients` or either client record is omitted
- **THEN** Claude SHALL default to executable `claude`
- **AND** Codex SHALL default to executable `codex`

#### Scenario: Executable
- **WHEN** an executable is a command name or absolute path
- **THEN** OneTool SHALL resolve and verify an executable file without a shell

#### Scenario: Invalid executable
- **WHEN** an executable is a relative path with separators, contains arguments, or
  is not executable
- **THEN** configuration or launch SHALL fail actionably

#### Scenario: Working directory
- **WHEN** a working directory is configured
- **THEN** OneTool SHALL resolve and validate it and change to it immediately before
  process replacement

#### Scenario: Codex home
- **WHEN** `code.clients.codex.home_path` is configured
- **THEN** OneTool SHALL validate it and set `CODEX_HOME` only for the child

#### Scenario: Additional arguments
- **WHEN** configured additional arguments do not contain a OneTool-owned long
  option, long option with `=`, separated short option, or attached short option
- **THEN** their token boundaries and order SHALL be preserved
- **AND** OneTool SHALL not interpret upstream commands or option values

#### Scenario: Removed client fields
- **WHEN** configuration supplies a client version constraint, CLIProxyAPI client,
  typed settings/profile/catalog path, or delegated login configuration
- **THEN** strict validation SHALL reject it

### Requirement: CLIProxyAPI connection configuration

Optional `code.proxy` SHALL contain one or more launcher route lists plus optional
`base_url`, `secret_name`, `connect_timeout`, and `request_timeout`.

#### Scenario: Proxy omitted
- **WHEN** code configuration uses only direct Codex profiles
- **THEN** no CLIProxyAPI connection fields SHALL be required

#### Scenario: No proxy file path
- **WHEN** code configuration is loaded
- **THEN** it SHALL expose no CLIProxyAPI config path or management key field

#### Scenario: No model cache setting
- **WHEN** code configuration is loaded
- **THEN** it SHALL expose no public `model_cache_ttl`

#### Scenario: Management fields rejected
- **WHEN** configuration contains management credentials, lifecycle, process, log,
  account, OAuth, or raw proxy payload settings
- **THEN** strict validation SHALL reject them

### Requirement: Typed tool generation selections

Generation-capable tool configuration SHALL accept reusable typed `llm` selections
at pack or operation scope. A partial selection that omits `backend` MAY contain
provider-neutral model, effort, timeout, and output-limit overrides. A selection
that specifies `backend` SHALL be a complete discriminated backend selection:
`cliproxy` SHALL use the external `code.proxy` inference connection, and
`openai_compatible` SHALL contain its own base URL and named secret. Every complete backend selection
SHALL include `interface: responses` or `interface: chat_completions`.
Backend-specific fields, including `interface`, SHALL NOT be accepted in a partial
selection that omits `backend`.

#### Scenario: Pack selection validates
- **WHEN** `tools.ot_image.llm` contains a valid partial generation selection
- **THEN** OneTool SHALL preserve it as a typed pack-level override

#### Scenario: Operation selection validates
- **WHEN** `tools.knowledge.ask.llm` or `tools.knowledge.enrich.llm` contains a valid partial generation selection
- **THEN** OneTool SHALL preserve it as a typed operation-level override

#### Scenario: Nested direct backend is complete
- **GIVEN** top-level `llm.backend` is `cliproxy`
- **WHEN** `tools.ot_llm.llm` selects `backend: openai_compatible`
- **THEN** that nested selection SHALL require its own base URL and named secret
- **AND** it SHALL NOT inherit the CLIProxyAPI endpoint or inference credential

#### Scenario: Incomplete nested backend is rejected
- **WHEN** a pack or operation selection specifies `backend: openai_compatible` without its required base URL or named secret
- **THEN** configuration validation SHALL fail at that selection's path

#### Scenario: Missing or unsupported interface is rejected
- **WHEN** a complete generation backend omits `interface` or selects an interface
  unsupported by its backend or model metadata
- **THEN** configuration validation SHALL fail at that setting's path
- **AND** OneTool SHALL not select an SDK default

#### Scenario: Invalid effort is rejected
- **WHEN** any generation selection configures an effort other than `low`, `medium`, or `high`
- **THEN** configuration validation SHALL fail at that setting's path
