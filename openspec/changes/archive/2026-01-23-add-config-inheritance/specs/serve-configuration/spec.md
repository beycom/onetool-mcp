## ADDED Requirements

### Requirement: Config Inheritance Directive

The system SHALL support an `inherit` directive to control config merging behaviour.

#### Scenario: Implicit global inheritance
- **GIVEN** a project config without `inherit` field
- **WHEN** the config is loaded
- **THEN** it SHALL behave as if `inherit: global` was specified
- **AND** the project config SHALL be merged on top of global config

#### Scenario: Explicit global inheritance
- **GIVEN** a project config with `inherit: global`
- **WHEN** the config is loaded
- **THEN** it SHALL load `~/.onetool/ot-serve.yaml` first
- **AND** process its includes
- **AND** deep merge the project config on top

#### Scenario: Bundled inheritance
- **GIVEN** a project config with `inherit: bundled`
- **WHEN** the config is loaded
- **THEN** it SHALL load bundled defaults first
- **AND** skip global config
- **AND** deep merge the project config on top

#### Scenario: No inheritance
- **GIVEN** a project config with `inherit: none`
- **WHEN** the config is loaded
- **THEN** it SHALL NOT merge with any other config
- **AND** only the project config SHALL be used

#### Scenario: Global config inheritance
- **GIVEN** `~/.onetool/ot-serve.yaml` with `inherit: bundled`
- **WHEN** the global config is loaded
- **THEN** bundled defaults SHALL be merged first
- **AND** global overrides SHALL be applied

### Requirement: Three-Tier Include Resolution

The system SHALL resolve `include:` paths with three-tier fallback.

#### Scenario: Include found in project
- **GIVEN** project config includes `prompts.yaml`
- **AND** `cwd/.onetool/prompts.yaml` exists
- **WHEN** the include is resolved
- **THEN** the project file SHALL be used

#### Scenario: Include falls back to global
- **GIVEN** project config includes `prompts.yaml`
- **AND** `cwd/.onetool/prompts.yaml` does NOT exist
- **AND** `~/.onetool/prompts.yaml` exists
- **WHEN** the include is resolved
- **THEN** the global file SHALL be used

#### Scenario: Include falls back to bundled
- **GIVEN** project config includes `prompts.yaml`
- **AND** `cwd/.onetool/prompts.yaml` does NOT exist
- **AND** `~/.onetool/prompts.yaml` does NOT exist
- **AND** bundled `prompts.yaml` exists
- **WHEN** the include is resolved
- **THEN** the bundled file SHALL be used

#### Scenario: Include not found anywhere
- **GIVEN** project config includes `custom.yaml`
- **AND** the file does NOT exist in project, global, or bundled
- **WHEN** the include is resolved
- **THEN** a warning SHALL be logged
- **AND** loading SHALL continue without that include

#### Scenario: Absolute include path
- **GIVEN** config includes `/etc/onetool/prompts.yaml`
- **WHEN** the include is resolved
- **THEN** the absolute path SHALL be used directly
- **AND** no fallback SHALL occur

#### Scenario: Include with tilde expansion
- **GIVEN** config includes `~/shared/prompts.yaml`
- **WHEN** the include is resolved
- **THEN** `~` SHALL expand to home directory
- **AND** no fallback SHALL occur

### Requirement: Deep Merge Behaviour

The system SHALL deep merge inherited configs with specific semantics.

#### Scenario: Dict fields are merged
- **GIVEN** global config with `tools: {brave: {timeout: 60}}`
- **AND** project config with `tools: {brave: {retries: 3}}`
- **WHEN** configs are merged
- **THEN** result SHALL be `tools: {brave: {timeout: 60, retries: 3}}`

#### Scenario: Scalar fields are replaced
- **GIVEN** global config with `log_level: DEBUG`
- **AND** project config with `log_level: INFO`
- **WHEN** configs are merged
- **THEN** result SHALL be `log_level: INFO`

#### Scenario: List fields are replaced
- **GIVEN** global config with `tools_dir: [src/ot_tools/*.py]`
- **AND** project config with `tools_dir: [./tools/*.py]`
- **WHEN** configs are merged
- **THEN** result SHALL be `tools_dir: [./tools/*.py]`
- **AND** global list SHALL NOT be appended

#### Scenario: Nested dict override
- **GIVEN** global config with `servers: {github: {timeout: 60}}`
- **AND** project config with `servers: {github: {timeout: 120}}`
- **WHEN** configs are merged
- **THEN** result SHALL be `servers: {github: {timeout: 120}}`

#### Scenario: Additional dict keys preserved
- **GIVEN** global config with `servers: {github: {...}}`
- **AND** project config with `servers: {local: {...}}`
- **WHEN** configs are merged
- **THEN** result SHALL contain both `github` and `local`

## MODIFIED Requirements

### Requirement: YAML Configuration File

The system SHALL load configuration from a YAML file using a standard resolution order.

#### Scenario: Default configuration file resolution
- **GIVEN** no explicit config path provided
- **AND** no `OT_SERVE_CONFIG` environment variable
- **WHEN** the server starts
- **THEN** it SHALL look for `cwd/.onetool/ot-serve.yaml` first
- **AND** fall back to `~/.onetool/ot-serve.yaml` if not found
- **AND** use bundled defaults if neither exists

#### Scenario: Environment variable override
- **GIVEN** `OT_SERVE_CONFIG=/path/to/config.yaml` environment variable
- **WHEN** the server starts
- **THEN** it SHALL load from the specified path
- **AND** skip the standard resolution order

#### Scenario: OT_CWD affects config resolution
- **GIVEN** `OT_CWD=myproject` environment variable
- **AND** no explicit config path
- **WHEN** the server starts
- **THEN** it SHALL look for `myproject/.onetool/ot-serve.yaml`
- **AND** fall back to `~/.onetool/ot-serve.yaml`

#### Scenario: Custom configuration file
- **GIVEN** `--config /path/to/config.yaml` argument
- **WHEN** the server starts
- **THEN** it SHALL load from the specified path

#### Scenario: Missing configuration file
- **GIVEN** no configuration file exists at any resolution location
- **WHEN** the server starts
- **THEN** it SHALL use bundled default settings

### Requirement: Config Include

The system SHALL support a top-level `include:` key for merging external config files.

#### Scenario: Single include file
- **GIVEN** configuration with:
  ```yaml
  include:
    - base.yaml
  ```
- **WHEN** the config is loaded
- **THEN** the content of `base.yaml` SHALL be merged into the config

#### Scenario: Multiple include files
- **GIVEN** configuration with:
  ```yaml
  include:
    - shared.yaml
    - project.yaml
    - local.yaml
  ```
- **WHEN** the config is loaded
- **THEN** files SHALL be merged left-to-right
- **AND** later files SHALL override earlier files on key conflicts

#### Scenario: Inline content overrides includes
- **GIVEN** configuration with:
  ```yaml
  include:
    - base.yaml  # contains servers: {github: {...}}
  servers:
    github:
      timeout: 120  # override
    local:
      type: stdio   # addition
  ```
- **WHEN** the config is loaded
- **THEN** inline `servers.github` SHALL override included `servers.github`
- **AND** inline `servers.local` SHALL be added

#### Scenario: Deep merge nested dicts
- **GIVEN** `base.yaml` contains `tools: {brave: {timeout: 60}}`
- **AND** main config contains `tools: {brave: {retries: 3}}`
- **WHEN** merged
- **THEN** result SHALL be `tools: {brave: {timeout: 60, retries: 3}}`

#### Scenario: Non-dict values replaced
- **GIVEN** `base.yaml` contains `log_level: DEBUG`
- **AND** main config contains `log_level: INFO`
- **WHEN** merged
- **THEN** result SHALL be `log_level: INFO`

#### Scenario: Missing include file with fallback
- **GIVEN** `include:` references `snippets.yaml`
- **AND** the file does NOT exist in config directory
- **WHEN** the config is loaded
- **THEN** fallback resolution SHALL search global then bundled
- **AND** if found, the fallback file SHALL be loaded

#### Scenario: Path resolution with three-tier fallback
- **GIVEN** a relative path in `include:`
- **WHEN** the file is loaded
- **THEN** the path SHALL be resolved in order:
  1. Relative to the config file directory
  2. In `~/.onetool/`
  3. In bundled defaults
- **AND** `~` SHALL expand to user home directory

#### Scenario: Nested includes
- **GIVEN** `base.yaml` contains its own `include:` key
- **WHEN** the config is loaded
- **THEN** nested includes SHALL be processed recursively
- **AND** merge order SHALL be depth-first

#### Scenario: Circular include detection
- **GIVEN** `a.yaml` includes `b.yaml` which includes `a.yaml`
- **WHEN** the config is loaded
- **THEN** circular includes SHALL be detected and skipped
- **AND** loading SHALL continue without error

#### Scenario: No include key
- **GIVEN** configuration without `include:` key
- **WHEN** the config is loaded
- **THEN** loading SHALL proceed normally with no external files

#### Scenario: Snippet file format with include
- **GIVEN** an external snippet file loaded via `include:`
- **WHEN** parsed
- **THEN** it SHALL contain the `snippets:` key:

  ```yaml
  snippets:
    snippet_name:
      description: "What it does"
      params:
        param1: {default: "value", description: "Param description"}
      body: |
        code_template()
  ```
