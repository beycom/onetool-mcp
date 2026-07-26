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

### Requirement: Shared model registry
OneTool configuration SHALL support a strict top-level `models` mapping shared by
launcher and inference consumers.

#### Scenario: Model entry
- **WHEN** a model entry is loaded
- **THEN** it SHALL validate shortcut, concrete id, label, source, optional proxy
  alias, context metadata, modalities, and verified harness compatibility

#### Scenario: Unique identity
- **WHEN** shortcuts, model ids, or aliases are ambiguous
- **THEN** configuration validation SHALL reject the registry

#### Scenario: No hidden fallback
- **WHEN** a selected model is absent from configuration
- **THEN** runtime code SHALL not supply a hidden model definition or alias

### Requirement: Typed code-launch configuration
OneTool configuration SHALL support a strict optional top-level `code` section.

#### Scenario: Code section omitted
- **WHEN** `code` is absent
- **THEN** normal MCP server behavior SHALL remain unchanged
- **AND** launcher commands SHALL report that setup is required

#### Scenario: Route entry
- **WHEN** a named route is loaded
- **THEN** it SHALL validate harness, source, transport, model compatibility, adapter
  settings, and enabled state

#### Scenario: Valid defaults
- **WHEN** a default route or permission mode is configured
- **THEN** it SHALL reference an existing compatible route and accept only supported
  permission values

#### Scenario: Unknown field
- **WHEN** `code`, `models`, or any nested entry contains an unknown field
- **THEN** strict validation SHALL reject it without aliases or legacy handling

### Requirement: Configurable external clients
The `code.clients` section SHALL provide typed configuration for every external
client that OneTool may execute. Claude and Codex client entries SHALL support an
executable, optional user version constraint, optional working directory, and
ordered additional argument list. The CLIProxyAPI client entry SHALL be optional and
used only by supported delegated version or login commands.

#### Scenario: Executable name
- **WHEN** a client executable is a command name
- **THEN** OneTool SHALL resolve it from the child process `PATH`
- **AND** it SHALL verify that the resolved file is executable before route network
  checks or launch

#### Scenario: Absolute executable
- **WHEN** a client executable is an absolute path
- **THEN** OneTool SHALL check that exact path is an executable regular file
- **AND** it SHALL not interpret the value as a shell command

#### Scenario: Invalid executable form
- **WHEN** an executable is relative with path separators, is not executable, or
  contains a command plus arguments
- **THEN** configuration or pre-launch validation SHALL reject it actionably
- **AND** OneTool SHALL not invoke a shell to interpret it

#### Scenario: Explicit version constraint
- **WHEN** a client has a configured version constraint
- **THEN** OneTool SHALL parse the installed client's machine-readable or bounded
  version output and require it to satisfy that constraint
- **AND** an unparseable or non-matching version SHALL fail before launch

#### Scenario: No exact runtime pin
- **WHEN** no user version constraint is configured
- **THEN** OneTool SHALL not require an exact version used by development fixtures
- **AND** a newer release SHALL remain eligible unless it is known incompatible or
  lacks a safely verifiable capability required by the selected route

#### Scenario: Feature-specific minimum
- **WHEN** a selected route uses a feature that upstream added in a known release
- **THEN** OneTool SHALL enforce only that evidence-based minimum for that feature
- **AND** routes that do not use the feature SHALL not inherit its minimum

#### Scenario: Version cannot establish a required capability
- **WHEN** a required capability cannot be established from a parsed version or a
  safe non-billable check
- **THEN** the affected route SHALL fail with the missing capability and remediation
- **AND** unrelated routes SHALL remain eligible

#### Scenario: Working directory
- **WHEN** a client working directory is configured
- **THEN** OneTool SHALL resolve and validate the checked directory before launch
- **AND** it SHALL change only the child process working directory

#### Scenario: Ordered additional arguments
- **WHEN** a client has configured additional arguments
- **THEN** OneTool SHALL append the validated string-list values in documented order
  without shell parsing
- **AND** route-owned or secret-bearing arguments SHALL be rejected

#### Scenario: Missing client entry
- **WHEN** a selected harness has no client entry
- **THEN** launch SHALL fail with the exact missing configuration path
- **AND** it SHALL not fall back to a hard-coded executable or another client

### Requirement: Claude client configuration
Claude route entries SHALL support an optional checked, user-owned `settings_path`
and explicit proxy model-slot aliases when all three current slots have been
verified.

#### Scenario: Claude settings path
- **WHEN** `code.routes.<name>.settings_path` is configured for a Claude route
- **THEN** OneTool SHALL pass the checked path once using the current `--settings`
  flag
- **AND** it SHALL not parse, generate, merge, or rewrite the settings file

#### Scenario: Claude settings omitted
- **WHEN** `settings_path` is omitted
- **THEN** Claude Code SHALL retain its normal user/project settings resolution
- **AND** invocation-scoped route and permission arguments SHALL still take
  precedence for values owned by OneTool

#### Scenario: Claude model policy remains user-owned
- **WHEN** a Claude route is constructed
- **THEN** OneTool SHALL not generate an inline `availableModels` policy or alter
  user, project, local, or managed settings
- **AND** it SHALL use the selected route model and complete model-slot mapping
  instead of treating an allowlist as provider configuration

#### Scenario: Claude proxy slots omitted
- **WHEN** a proxied Claude route does not configure distinct verified model slots
- **THEN** the selected proxy alias SHALL populate the Opus, Sonnet, and Haiku slot
  variables for the child

#### Scenario: Claude proxy slots configured
- **WHEN** a proxied Claude route configures model-slot aliases
- **THEN** Opus, Sonnet, and Haiku values SHALL all be required
- **AND** every alias SHALL be present in the shared model registry and live proxy
  discovery before launch

#### Scenario: Legacy Claude model variables
- **WHEN** configuration supplies legacy Claude Code 1.x model environment fields
- **THEN** strict validation SHALL reject them without aliases or compatibility
  translation

### Requirement: Codex client configuration
The Codex client entry SHALL support an optional checked `home_path`. Codex route
entries SHALL support optional `profile` and checked `model_catalog_path` settings
and only typed provider capabilities verified against the installed client's
capabilities.

#### Scenario: Codex home path
- **WHEN** `code.clients.codex.home_path` is configured
- **THEN** OneTool SHALL set it for the Codex child only using the current supported
  Codex home mechanism
- **AND** it SHALL validate required user-owned auth/config state without reading,
  copying, or modifying that state

#### Scenario: Current Codex profile
- **WHEN** `code.routes.<name>.profile` is configured for a Codex route
- **THEN** OneTool SHALL select that profile once with `--profile`
- **AND** it SHALL validate the current separate
  `<codex-home>/<profile>.config.toml` form before launch

#### Scenario: Removed Codex profile form
- **WHEN** launcher configuration attempts to define or rely on
  `[profiles.<name>]` in the main Codex config
- **THEN** OneTool SHALL reject the unsupported form
- **AND** it SHALL not generate a compatibility profile

#### Scenario: Codex model catalog
- **WHEN** `code.routes.<name>.model_catalog_path` is configured for a compatible
  Codex route
- **THEN** OneTool SHALL pass the checked user-owned path with an
  invocation-scoped Codex configuration override
- **AND** it SHALL not generate or rewrite the catalog

#### Scenario: Codex provider capability
- **WHEN** a non-native route configures a capability such as WebSocket support
- **THEN** the value SHALL be represented by a typed route field and accepted only
  when verified for the installed Codex, endpoint, and wire protocol

### Requirement: Client argument ownership
OneTool SHALL own model, provider, transport, settings/profile, permission, auth, and
other route-determining arguments for each launched client.

#### Scenario: Configured argument conflicts
- **WHEN** configured additional arguments contain a route-owned flag, its short
  form, an inline assignment, or a positional subcommand that changes launch mode
- **THEN** validation SHALL reject the conflict and identify the typed OneTool field
  that must be used instead

#### Scenario: Passthrough argument conflicts
- **WHEN** arguments after `--` contain a route-owned flag or launch-mode subcommand
- **THEN** pre-launch validation SHALL reject the conflict
- **AND** it SHALL not use first-flag-wins or last-flag-wins behavior

#### Scenario: Non-conflicting arguments
- **WHEN** additional or passthrough arguments do not conflict with route ownership
- **THEN** their token boundaries and order SHALL be preserved exactly

### Requirement: CLIProxyAPI connection configuration
The `code` section SHALL describe only inference access to an external CLIProxyAPI
instance.

#### Scenario: Inference fields
- **WHEN** any configured route uses CLIProxyAPI
- **THEN** base URL, named inference secret, timeout, and finite model-cache TTL SHALL
  be required and validated

#### Scenario: Optional upstream config path
- **WHEN** a user-owned CLIProxyAPI config path is configured
- **THEN** it SHALL be used only for display or verified delegated commands
- **AND** OneTool SHALL not parse credentials from or rewrite the file

#### Scenario: Management fields rejected
- **WHEN** configuration contains management credentials, generated proxy config,
  managed lifecycle, auto-start, PID, proxy log, remote administration, account, or
  raw payload settings
- **THEN** strict validation SHALL reject them

### Requirement: Adapter configuration
Code routes SHALL expose stable user intent while volatile upstream details remain
internal.

#### Scenario: Codex OpenRouter adapter
- **WHEN** a Codex OpenRouter route is configured
- **THEN** it SHALL reference a named OpenRouter secret and validated invocation
  profile/catalog inputs

#### Scenario: Codex provider credential
- **WHEN** a non-native Codex provider requires a client key
- **THEN** the route SHALL reference a named OneTool secret
- **AND** the adapter SHALL expose it to Codex through an `env_key` that names a
  private child-only environment variable
- **AND** it SHALL not accept an inline bearer-token value

#### Scenario: Claude subscription proxy default
- **WHEN** Claude subscription proxy enablement is omitted
- **THEN** it SHALL default to disabled

#### Scenario: Claude subscription proxy enabled
- **WHEN** the enablement switch is true
- **THEN** compatible configured Claude subscription proxy routes MAY be selected
- **AND** configuration guidance SHALL contain the required terms/account/billing
  warning

#### Scenario: Raw adapter settings rejected
- **WHEN** configuration supplies raw CLIProxyAPI YAML, arbitrary request data,
  arbitrary environment variables, generated Claude model policy, or arbitrary
  command templates
- **THEN** strict validation SHALL reject them

### Requirement: Typed tool generation selections

Generation-capable tool configuration SHALL accept reusable typed `llm` selections
at pack or operation scope. A partial selection that omits `backend` MAY contain
provider-neutral model, effort, timeout, and output-limit overrides. A selection
that specifies `backend` SHALL be a complete discriminated backend selection:
`cliproxy` SHALL use the external `code.cliproxy` inference connection, and
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
