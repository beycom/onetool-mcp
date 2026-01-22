# bench-config Specification

## Purpose

Defines the YAML configuration schema for the ot-bench harness, including server connections, defaults, variable expansion, and environment handling.

---

## Requirements

### Requirement: YAML Configuration File

The harness SHALL load benchmark configuration from a YAML file.

#### Scenario: Load harness configuration
- **GIVEN** a YAML file with harness configuration
- **WHEN** `ot-bench run <file>` is executed
- **THEN** it SHALL parse and validate the configuration

#### Scenario: Multiple files via glob pattern
- **GIVEN** a glob pattern like `demo/bench/*.yaml`
- **WHEN** `ot-bench run demo/bench/*.yaml` is executed
- **THEN** it SHALL expand the pattern to matching files
- **AND** run benchmarks for each file sequentially
- **AND** aggregate results across all files

#### Scenario: Multiple explicit files
- **GIVEN** multiple file paths
- **WHEN** `ot-bench run file1.yaml file2.yaml` is executed
- **THEN** it SHALL run benchmarks for each file in order

#### Scenario: Missing configuration file
- **GIVEN** a non-existent file path
- **WHEN** the harness attempts to load it
- **THEN** it SHALL fail with FileNotFoundError

#### Scenario: Variable expansion from secrets
- **GIVEN** a configuration containing `${VAR_NAME}` patterns
- **WHEN** the configuration is loaded
- **THEN** it SHALL expand variables using bench-secrets.yaml only
- **AND** support `${VAR_NAME:-default}` syntax for defaults
- **AND** error if variable not found without default

### Requirement: Defaults Configuration

The harness SHALL support default values for tasks.

#### Scenario: Default timeout
- **GIVEN** no timeout specified on a task
- **WHEN** the task runs
- **THEN** it SHALL use the defaults.timeout value
- **DEFAULT** 120 seconds

#### Scenario: Default model
- **GIVEN** no model specified on a task
- **WHEN** the task runs with an LLM
- **THEN** it SHALL use the defaults.model value
- **DEFAULT** openai/gpt-5-mini

#### Scenario: System prompt
- **GIVEN** defaults.system_prompt configured
- **WHEN** tasks run
- **THEN** the system prompt SHALL be prepended to all task prompts
- **DEFAULT** null (no system prompt)

### Requirement: Server Configuration

The harness SHALL support multiple server connection types.

#### Scenario: stdio server
- **GIVEN** server with `type: stdio`
- **WHEN** the harness connects
- **THEN** it SHALL spawn the command with args and env
- **AND** communicate via stdin/stdout

#### Scenario: http server
- **GIVEN** server with `type: http`
- **WHEN** the harness connects
- **THEN** it SHALL connect to the URL with optional headers

#### Scenario: Server timeout override
- **GIVEN** server with `timeout: 30`
- **WHEN** the harness connects
- **THEN** it SHALL use 30 seconds as connection timeout

#### Scenario: Subprocess environment for stdio
- **GIVEN** a stdio server with env section
- **WHEN** the subprocess is spawned
- **THEN** it SHALL inherit only `PATH` from host
- **AND** add explicit env values from config
- **AND** `${VAR}` in env values expands from bench-secrets.yaml first, then os.environ

### Requirement: Secrets-Only Variable Expansion

The harness SHALL expand `${VAR}` patterns in configuration using bench-secrets.yaml only.

#### Scenario: Variable in secrets
- **GIVEN** `${API_KEY}` in a config value
- **AND** `API_KEY: "secret123"` in bench-secrets.yaml
- **WHEN** configuration is loaded
- **THEN** the value SHALL be expanded to "secret123"

#### Scenario: Variable not in secrets
- **GIVEN** `${UNKNOWN_VAR}` in a config value
- **AND** UNKNOWN_VAR not in bench-secrets.yaml
- **WHEN** configuration is loaded
- **THEN** it SHALL raise an error
- **AND** message SHALL indicate the missing variable and suggest bench-secrets.yaml

#### Scenario: No os.environ fallback
- **GIVEN** `${MY_VAR}` in a header or url
- **AND** MY_VAR set in os.environ but NOT in bench-secrets.yaml
- **WHEN** configuration is loaded
- **THEN** os.environ value SHALL NOT be used
- **AND** error SHALL be raised

### Requirement: Header Validation

The harness SHALL validate that all headers are fully expanded before use.

#### Scenario: Unexpanded variable in header
- **GIVEN** a header value containing `${VAR}` after expansion
- **WHEN** the harness prepares the HTTP request
- **THEN** it SHALL raise an error
- **AND** message SHALL indicate the unexpanded variable
- **AND** suggest adding to bench-secrets.yaml

#### Scenario: All headers expanded
- **GIVEN** all `${VAR}` patterns resolved from bench-secrets.yaml
- **WHEN** the harness prepares the HTTP request
- **THEN** headers SHALL be used normally

### Requirement: Subprocess Environment Restriction

The harness SHALL restrict subprocess environment inheritance.

#### Scenario: Minimal environment inheritance
- **GIVEN** a stdio server configuration
- **WHEN** the subprocess is spawned
- **THEN** it SHALL start with only `PATH` from os.environ
- **AND** NOT inherit other environment variables

#### Scenario: Explicit environment variables
- **GIVEN** stdio server with:
  ```yaml
  env:
    MY_VAR: value
    API_KEY: ${API_KEY}
  ```
- **WHEN** the subprocess is spawned
- **THEN** MY_VAR and API_KEY SHALL be set in subprocess
- **AND** no other variables from host (except PATH)

#### Scenario: Pass-through variables
- **GIVEN** stdio server with `env: { HOME: ${HOME} }`
- **WHEN** the subprocess is spawned
- **THEN** `${HOME}` SHALL read from bench-secrets.yaml first
- **AND** fall back to os.environ for pass-through
