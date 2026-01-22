# serve-configuration Specification

## Purpose

Defines the YAML configuration system for OneTool. Configuration controls tool discovery, logging, and server settings.
## Requirements
### Requirement: YAML Configuration File

The system SHALL load configuration from a YAML file using a standard resolution order.

#### Scenario: Default configuration file resolution
- **GIVEN** no explicit config path provided
- **AND** no `OT_SERVE_CONFIG` environment variable
- **WHEN** the server starts
- **THEN** it SHALL look for `cwd/.onetool/ot-serve.yaml` first
- **AND** fall back to `~/.onetool/ot-serve.yaml` if not found
- **AND** use built-in defaults if neither exists

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
- **THEN** it SHALL use default settings

### Requirement: Execution Settings

The system SHALL use direct (host) execution.

#### Scenario: Default timeout
- **GIVEN** no timeout in configuration
- **WHEN** execution starts
- **THEN** it SHALL use default timeout (120s)

### Requirement: Transform Tool Configuration

The transform() tool SHALL use OpenRouter configuration.

#### Scenario: Default model
- **GIVEN** no model specified in configuration
- **WHEN** transform() is called
- **THEN** it SHALL use `openai/gpt-5-mini` via OpenRouter

#### Scenario: Model configuration
- **GIVEN** `OT_TRANSFORM_MODEL=anthropic/claude-3-5-haiku`
- **WHEN** transform() is called
- **THEN** it SHALL use the specified model

#### Scenario: Max tokens configuration
- **GIVEN** `transform.max_tokens: 8192`
- **WHEN** transform() is called
- **THEN** it SHALL limit output to 8192 tokens
- **DEFAULT** 4096

#### Scenario: API key from secrets
- **GIVEN** `OPENAI_API_KEY` configured in `secrets.yaml`
- **WHEN** transform() is called
- **THEN** it SHALL use the key for OpenRouter API calls

### Requirement: Advanced Configuration

The system SHALL support advanced configuration options with config-relative path resolution.

#### Scenario: Custom tools directory
- **GIVEN** `tools_dir: ["src/ot_tools/*.py", "plugins/*.py"]`
- **WHEN** the server starts
- **THEN** it SHALL discover tools from all matching glob patterns
- **DEFAULT** ["src/ot_tools/*.py"]

#### Scenario: Log level configuration
- **GIVEN** `log_level: DEBUG`
- **WHEN** the server starts
- **THEN** it SHALL use DEBUG logging level
- **DEFAULT** INFO
- **VALUES** DEBUG, INFO, WARNING, ERROR

#### Scenario: Code validation toggle
- **GIVEN** `validate_code: false`
- **WHEN** code is executed
- **THEN** it SHALL skip syntax validation before execution
- **DEFAULT** true

### Requirement: Configuration Validation

The system SHALL validate configuration on load.

#### Scenario: Invalid timeout value
- **GIVEN** config with `timeout: -5`
- **WHEN** configuration loads
- **THEN** it SHALL fail with validation error

#### Scenario: Invalid memory format
- **GIVEN** config with `memory: invalid`
- **WHEN** configuration loads
- **THEN** it SHALL fail with validation error (expected format: 512m, 1g, etc.)

### Requirement: Tool Discovery Configuration

OneTool SHALL discover tools from configurable glob patterns with sensible defaults.

#### Scenario: Default tool discovery
- **GIVEN** no tools_dir in config
- **WHEN** OneTool loads configuration
- **THEN** it SHALL load tools from `src/ot_tools/*.py`

#### Scenario: Custom tool sources
- **GIVEN** config with `tools.sources: ["src/ot_tools/*.py", "custom/**/*.py"]`
- **WHEN** OneTool loads configuration
- **THEN** it SHALL load tools from both patterns

#### Scenario: Tool exclusion patterns
- **GIVEN** config with `tools.sources: ["src/ot_tools/*.py", "!src/ot_tools/_*.py"]`
- **WHEN** OneTool loads configuration
- **THEN** it SHALL exclude files starting with underscore

### Requirement: Execution Validation Configuration

The system SHALL support configurable pre-execution validation.

#### Scenario: Validation enabled
- **GIVEN** config with `execution.validate.enabled: true`
- **WHEN** Python code is submitted
- **THEN** it SHALL be validated before execution

#### Scenario: Security check configuration
- **GIVEN** config with `execution.validate.check_security: true`
- **WHEN** code contains dangerous patterns (exec, eval, __import__)
- **THEN** execution SHALL be blocked with an error

#### Scenario: Lint warnings disabled
- **GIVEN** config with `execution.validate.lint_warnings: false`
- **WHEN** code is validated
- **THEN** optional ruff linting SHALL be skipped

### Requirement: Enhanced Logging Configuration

The system SHALL support enhanced logging configuration.

#### Scenario: Log format configuration
- **GIVEN** config with `logging.format: json`
- **WHEN** logs are written
- **THEN** they SHALL use JSON format instead of dev format

#### Scenario: Span configuration
- **GIVEN** config with `logging.spans.enabled: true`
- **WHEN** operations are logged
- **THEN** span-based logging SHALL be active

#### Scenario: Log file configuration
- **GIVEN** config with `logging.file: .local/logs/ot.log`
- **WHEN** the server runs
- **THEN** logs SHALL be written to the specified file
- **DEFAULT** `.local/logs/ot.log`

### Requirement: Server Metadata Configuration

The system SHALL support server metadata in configuration.

#### Scenario: Server name
- **GIVEN** config with `server.name: my-onetool`
- **WHEN** the MCP server starts
- **THEN** it SHALL use the configured name

#### Scenario: Instructions file reference
- **GIVEN** config with `server.instructions_file: prompts/custom.md`
- **WHEN** the server starts
- **THEN** it SHALL load instructions from the specified file

### Requirement: V1 Minimal Configuration

The system SHALL support a minimal V1 configuration schema.

#### Scenario: Minimal valid config
- **GIVEN** configuration with only `tools_dir` and optional `environment_file`
- **WHEN** configuration is loaded
- **THEN** it SHALL be valid for V1

#### Scenario: V1 config example
- **GIVEN** configuration file:
  ```yaml
  tools_dir: ./tools
  environment_file: .env
  ```
- **WHEN** the server starts
- **THEN** it SHALL load tools from ./tools and environment from .env

### Requirement: MCP Server Proxying Configuration

The system SHALL support configuration for proxying external MCP servers.

#### Scenario: HTTP/SSE MCP server
- **GIVEN** configuration with:
  ```yaml
  servers:
    context7:
      type: http
      url: https://mcp.context7.com/mcp
      headers:
        Authorization: Bearer ${CONTEXT7_API_KEY}
  ```
- **WHEN** the server starts
- **THEN** it SHALL expand `${VAR}` in headers using secrets.yaml values
- **AND** error if variable not found in secrets

#### Scenario: Stdio MCP server
- **GIVEN** configuration with:
  ```yaml
  servers:
    github:
      type: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}
  ```
- **WHEN** the server starts
- **THEN** it SHALL spawn the subprocess and connect via stdio
- **AND** expand `${VAR}` in env section using secrets.yaml first, then os.environ for pass-through

#### Scenario: Subprocess environment inheritance
- **GIVEN** a stdio server configuration with env section
- **WHEN** the subprocess is spawned
- **THEN** it SHALL inherit only `PATH` from the host environment
- **AND** add all explicit env values from config
- **AND** `${VAR}` in env values expands from secrets.yaml first, then os.environ

#### Scenario: Disabled MCP server
- **GIVEN** configuration with `servers.server_name.enabled: false`
- **WHEN** the server starts
- **THEN** it SHALL skip connecting to that MCP server

#### Scenario: No servers section
- **GIVEN** configuration without `servers` section
- **WHEN** the server starts
- **THEN** it SHALL start normally without proxy functionality

#### Scenario: Variable expansion in config
- **GIVEN** servers config with `${VAR_NAME}` in urls, headers, args, or command
- **WHEN** configuration is loaded
- **THEN** it SHALL expand from secrets.yaml only
- **AND** error if variable not found (no os.environ fallback)

#### Scenario: Connection timeout
- **GIVEN** servers config with `timeout: 30`
- **WHEN** connecting to the MCP server
- **THEN** connection SHALL timeout after 30 seconds
- **DEFAULT** 60 seconds

### Requirement: MCP Proxy Error Handling

The system SHALL handle MCP proxy configuration errors gracefully.

#### Scenario: Invalid MCP type
- **GIVEN** servers config with `type: invalid`
- **WHEN** configuration is loaded
- **THEN** it SHALL fail with validation error listing valid types (http, stdio)

#### Scenario: Missing URL for HTTP type
- **GIVEN** servers config with `type: http` but no `url`
- **WHEN** configuration is loaded
- **THEN** it SHALL fail with validation error

#### Scenario: Missing command for stdio type
- **GIVEN** servers config with `type: stdio` but no `command`
- **WHEN** configuration is loaded
- **THEN** it SHALL fail with validation error

### Requirement: CLI Entry Point Naming

The MCP server CLI SHALL follow the `ot-<purpose>` naming convention.

#### Scenario: CLI command name
- **GIVEN** the OneTool MCP server package
- **WHEN** the user invokes the CLI
- **THEN** the command SHALL be `ot-serve`
- **AND** it SHALL be consistent with other CLIs (`ot-bench`, `ot-browse`)

#### Scenario: CLI help
- **GIVEN** the user runs `ot-serve --help`
- **WHEN** help is displayed
- **THEN** it SHALL describe the MCP server functionality
- **AND** it SHALL show available options including `--config` and `--version`

#### Scenario: CLI version
- **GIVEN** the user runs `ot-serve --version`
- **WHEN** version is displayed
- **THEN** it SHALL show the package version

### Requirement: Projects Configuration

The system SHALL support rich project configuration with paths and attributes.

#### Scenario: Project with attributes
- **GIVEN** configuration with:
  ```yaml
  projects:
    myproject:
      path: ~/projects/myproject
      attrs:
        db_url: sqlite:///data/app.db
        api_key: ${MY_API_KEY}
  ```
- **WHEN** configuration is loaded
- **THEN** project path and attributes SHALL be available

#### Scenario: Path expansion
- **GIVEN** a project path containing `~`
- **WHEN** configuration is loaded
- **THEN** the path SHALL be expanded using home directory only
- **AND** `${VAR}` patterns are NOT expanded in paths

#### Scenario: Attribute expansion
- **GIVEN** an attribute value containing `${VAR}`
- **WHEN** configuration is loaded
- **THEN** the attribute value SHALL be expanded using secrets.yaml only
- **AND** error if variable not found

#### Scenario: No attrs section
- **GIVEN** a project with path but no attrs
- **WHEN** configuration is loaded
- **THEN** an empty attrs mapping SHALL be used

#### Scenario: Invalid project format
- **GIVEN** a project configured as simple string (old format)
- **WHEN** configuration is loaded
- **THEN** it SHALL fail with validation error

#### Scenario: No projects section
- **GIVEN** configuration without a `projects` section
- **WHEN** configuration is loaded
- **THEN** an empty projects mapping SHALL be used

### Requirement: Config Schema Version

Configuration files SHALL include a schema version for migration support.

#### Scenario: Version field present
- **GIVEN** a config file `ot-serve.yaml`
- **WHEN** the file is loaded
- **THEN** the `version` field SHALL be read if present
- **DEFAULT** 1 if missing

#### Scenario: Version validation
- **GIVEN** a config file with `version: N`
- **WHEN** N is greater than the current schema version
- **THEN** loading SHALL fail with error indicating minimum OneTool version required

#### Scenario: Version in new configs
- **GIVEN** a new config file is created
- **WHEN** the file is written
- **THEN** it SHALL include `version: 1` as the first field

### Requirement: Tool Dependency Metadata

Tools SHALL declare their dependencies for verification by `onetool check`.

#### Scenario: Dependency declaration
- **GIVEN** a tool module in `src/ot_tools/`
- **WHEN** the tool has external dependencies
- **THEN** it SHALL declare them via `__onetool_requires__` module attribute

#### Scenario: Dependency format
- **GIVEN** a tool with dependencies
- **WHEN** `__onetool_requires__` is defined
- **THEN** it SHALL be a dict with optional keys: `secrets`, `system`
- **AND** each value SHALL be a list of strings

#### Scenario: Example declaration
- **GIVEN** a tool requiring an API key and system command
- **WHEN** declaring dependencies
- **THEN** format SHALL be:
  ```python
  __onetool_requires__ = {
      "secrets": ["BRAVE_API_KEY"],
      "system": ["rg"],
  }
  ```

#### Scenario: No dependencies
- **GIVEN** a tool with no external dependencies
- **WHEN** the tool is loaded
- **THEN** missing `__onetool_requires__` SHALL be treated as no requirements

### Requirement: Configuration Validation (modified)

The system SHALL validate configuration on load with field-level constraints.

#### Scenario: Tool timeout out of range
- **GIVEN** config with `tools.brave.timeout: 500`
- **WHEN** configuration loads
- **THEN** it SHALL fail with validation error indicating max is 300.0

#### Scenario: Tool limit out of range
- **GIVEN** config with `tools.code_search.limit: 0`
- **WHEN** configuration loads
- **THEN** it SHALL fail with validation error indicating min is 1

### Requirement: Tools Configuration Section

The system SHALL support tool-specific configuration via the `tools:` section.

#### Scenario: Default tool configuration
- **GIVEN** no `tools:` section in configuration
- **WHEN** tools are loaded
- **THEN** they SHALL use built-in default values

#### Scenario: Partial tools configuration
- **GIVEN** configuration with only some tools configured:
  ```yaml
  tools:
    ground:
      model: gemini-2.0-flash
  ```
- **WHEN** other tools are used
- **THEN** they SHALL use their built-in defaults

#### Scenario: Brave timeout configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    brave:
      timeout: 120.0
  ```
- **WHEN** brave.* functions are called
- **THEN** they SHALL use 120 second timeout
- **DEFAULT** 60.0 seconds
- **RANGE** 1.0 - 300.0 seconds

#### Scenario: Grounding search model configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    ground:
      model: gemini-2.0-flash
  ```
- **WHEN** ground.search() is called
- **THEN** it SHALL use the configured model
- **DEFAULT** gemini-2.5-flash

#### Scenario: Context7 configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    context7:
      timeout: 45.0
      docs_limit: 20
  ```
- **WHEN** context7.* functions are called
- **THEN** they SHALL use 45 second timeout and 20 docs limit
- **DEFAULT** timeout: 30.0, docs_limit: 10
- **RANGE** timeout: 1.0-120.0, docs_limit: 1-20

#### Scenario: Web fetch configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    web_fetch:
      timeout: 60.0
      max_length: 100000
  ```
- **WHEN** web_fetch.* functions are called
- **THEN** they SHALL use 60 second timeout and 100000 max length
- **DEFAULT** timeout: 30.0, max_length: 50000
- **RANGE** timeout: 1.0-120.0, max_length: 1000-500000

#### Scenario: Ripgrep configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    ripgrep:
      timeout: 120.0
  ```
- **WHEN** ripgrep.* functions are called
- **THEN** they SHALL use 120 second timeout
- **DEFAULT** 60.0 seconds
- **RANGE** 1.0 - 300.0 seconds

#### Scenario: Code search configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    code_search:
      limit: 25
  ```
- **WHEN** code_search.* functions are called
- **THEN** they SHALL return up to 25 results
- **DEFAULT** 10
- **RANGE** 1 - 100

#### Scenario: Database configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    db:
      max_chars: 8000
  ```
- **WHEN** db.* functions return results
- **THEN** they SHALL truncate at 8000 characters
- **DEFAULT** 4000
- **RANGE** 100 - 100000

#### Scenario: Page view configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    page_view:
      sessions_dir: .local/browser
  ```
- **WHEN** page_view.* functions are called
- **THEN** they SHALL use the configured sessions directory
- **DEFAULT** .browse

#### Scenario: Package tool configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    package:
      timeout: 45.0
  ```
- **WHEN** package.* functions are called
- **THEN** they SHALL use 45 second timeout
- **DEFAULT** 30.0 seconds
- **RANGE** 1.0 - 120.0 seconds

#### Scenario: Invalid tool configuration value
- **GIVEN** configuration with invalid value:
  ```yaml
  tools:
    brave:
      timeout: -5
  ```
- **WHEN** configuration is loaded
- **THEN** it SHALL fail with validation error indicating the field and constraint

### Requirement: Cross-Platform Install Hints

The system SHALL provide platform-appropriate installation instructions for external dependencies.

#### Scenario: Ripgrep not installed on macOS
- **GIVEN** ripgrep is not in PATH
- **AND** platform is macOS
- **WHEN** ripgrep.* function is called
- **THEN** error SHALL include: "brew install ripgrep"

#### Scenario: Ripgrep not installed on Linux
- **GIVEN** ripgrep is not in PATH
- **AND** platform is Linux
- **WHEN** ripgrep.* function is called
- **THEN** error SHALL include Linux install options

#### Scenario: Ripgrep not installed on Windows
- **GIVEN** ripgrep is not in PATH
- **AND** platform is Windows
- **WHEN** ripgrep.* function is called
- **THEN** error SHALL include: "winget install" or "scoop install"

### Requirement: Secrets File Configuration

The system SHALL support a `secrets_file` field for loading secrets relative to the config file.

#### Scenario: Default secrets file
- **GIVEN** no `secrets_file` in configuration
- **WHEN** the server starts
- **THEN** it SHALL look for `secrets.yaml` in the same directory as `ot-serve.yaml`

#### Scenario: Custom secrets file
- **GIVEN** `secrets_file: ../shared/secrets.yaml`
- **WHEN** the server starts
- **THEN** it SHALL resolve the path relative to the config file directory

#### Scenario: Absolute secrets file path
- **GIVEN** `secrets_file: /etc/onetool/secrets.yaml`
- **WHEN** the server starts
- **THEN** it SHALL use the absolute path directly

#### Scenario: Secrets file with expansion
- **GIVEN** `secrets_file: ~/.onetool/secrets.yaml`
- **WHEN** the server starts
- **THEN** it SHALL expand `~` to home directory

#### Scenario: Missing secrets file
- **GIVEN** the resolved secrets file does not exist
- **WHEN** the server starts
- **THEN** it SHALL continue with empty secrets (no error)
- **AND** log a debug message about missing secrets file

### Requirement: Config Directory Tracking

The system SHALL track the directory containing the loaded configuration file.

#### Scenario: Config loaded from file
- **GIVEN** configuration loaded from `/project/.onetool/ot-serve.yaml`
- **WHEN** relative paths are resolved
- **THEN** they SHALL resolve relative to `/project/.onetool/`

#### Scenario: Config loaded from defaults
- **GIVEN** no configuration file exists
- **WHEN** the server starts with defaults
- **THEN** relative paths SHALL resolve relative to `get_effective_cwd() / ".onetool"`

#### Scenario: Config directory available
- **GIVEN** configuration is loaded
- **WHEN** code needs the config directory
- **THEN** it SHALL be available via a method on the config object

### Requirement: Secrets-Only Variable Expansion

The system SHALL expand `${VAR}` patterns using secrets.yaml as the only source.

#### Scenario: Variable found in secrets
- **GIVEN** `${API_KEY}` in a config value
- **AND** `API_KEY: "secret123"` in secrets.yaml
- **WHEN** configuration is loaded
- **THEN** the value SHALL be expanded to "secret123"

#### Scenario: Variable not found
- **GIVEN** `${UNKNOWN_VAR}` in a config value
- **AND** UNKNOWN_VAR not in secrets.yaml
- **WHEN** configuration is loaded
- **THEN** it SHALL raise an error with message indicating the missing variable
- **AND** suggest adding it to secrets.yaml

#### Scenario: Default value syntax
- **GIVEN** `${VAR:-default}` in a config value
- **AND** VAR not in secrets.yaml
- **WHEN** configuration is loaded
- **THEN** the value SHALL be expanded to "default"

#### Scenario: No os.environ reading
- **GIVEN** `${MY_VAR}` in a config value
- **AND** MY_VAR set in os.environ but NOT in secrets.yaml
- **WHEN** configuration is loaded
- **THEN** MY_VAR from os.environ SHALL NOT be used
- **AND** error or default SHALL apply

### Requirement: Subprocess Environment Pass-through

The system SHALL support explicit environment pass-through for subprocess env sections.

#### Scenario: Pass-through from host
- **GIVEN** stdio server config with:
  ```yaml
  env:
    HOME: ${HOME}
    LANG: ${LANG:-en_US.UTF-8}
  ```
- **WHEN** the subprocess is spawned
- **THEN** `${HOME}` SHALL read from os.environ (pass-through)
- **AND** `${LANG}` SHALL use default if not in os.environ
- **NOTE** Subprocess env is the ONLY place where os.environ reading is allowed

#### Scenario: Secrets take precedence in subprocess env
- **GIVEN** stdio server config with `env: { API_KEY: ${API_KEY} }`
- **AND** API_KEY exists in both secrets.yaml and os.environ
- **WHEN** the subprocess is spawned
- **THEN** the secrets.yaml value SHALL be used

### Requirement: Logging Configuration in YAML

The system SHALL support logging settings in YAML config instead of environment variables.

#### Scenario: Log level in config
- **GIVEN** configuration with `log_level: DEBUG`
- **WHEN** the server starts
- **THEN** it SHALL use DEBUG logging level
- **DEFAULT** INFO

#### Scenario: Log directory in config
- **GIVEN** configuration with `log_dir: .local/logs`
- **WHEN** the server starts
- **THEN** logs SHALL be written to the specified directory
- **DEFAULT** .local/logs

#### Scenario: Compact max length in config
- **GIVEN** configuration with `compact_max_length: 200`
- **WHEN** compact console output is used
- **THEN** values SHALL be truncated at 200 characters
- **DEFAULT** 120

### Requirement: Remote GitHub MCP Server Configuration

The system SHALL support configuration for the Remote GitHub MCP Server as a documented example.

#### Scenario: Remote GitHub MCP server via HTTP
- **GIVEN** configuration with:
  ```yaml
  servers:
    github:
      type: http
      url: https://api.githubcopilot.com/mcp/
      headers:
        Authorization: Bearer ${GITHUB_TOKEN}
        X-GitHub-Api-Version: "2022-11-28"
  ```
- **WHEN** the server starts
- **THEN** it SHALL connect to GitHub's hosted MCP server
- **AND** expose GitHub tools via the `github` namespace

#### Scenario: GitHub Enterprise Cloud with data residency
- **GIVEN** configuration with:
  ```yaml
  servers:
    github:
      type: http
      url: https://copilot-api.octocorp.ghe.com/mcp/
      headers:
        Authorization: Bearer ${GITHUB_TOKEN}
  ```
- **WHEN** the server starts
- **THEN** it SHALL connect to the enterprise-specific endpoint

#### Scenario: GitHub token from secrets file
- **GIVEN** `secrets.yaml` contains `GITHUB_TOKEN: ghp_xxx`
- **AND** server config references `${GITHUB_TOKEN}`
- **WHEN** the server starts
- **THEN** the token SHALL be expanded from secrets

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

#### Scenario: Missing include file
- **GIVEN** `include:` references a non-existent file
- **WHEN** the config is loaded
- **THEN** a warning SHALL be logged
- **AND** loading SHALL continue with remaining files

#### Scenario: Path resolution
- **GIVEN** a relative path in `include:`
- **WHEN** the file is loaded
- **THEN** the path SHALL be resolved relative to the config file directory
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

### Requirement: Security Configuration

The system SHALL support configurable security patterns for code validation at the root level.

#### Scenario: Security section at root level
- **GIVEN** configuration with:

  ```yaml
  security:
    validate_code: true
    enabled: true
    blocked:
      - my_dangerous.*
    warned:
      - custom_risky.*
    allow:
      - open
  ```

- **WHEN** code is validated
- **THEN** configured patterns SHALL be merged with defaults

#### Scenario: Default security configuration
- **GIVEN** no `security` section in configuration
- **WHEN** code is validated
- **THEN** built-in default patterns SHALL be used

#### Scenario: Security disabled
- **GIVEN** configuration with `security.enabled: false`
- **WHEN** code is validated
- **THEN** security pattern checks SHALL be skipped

#### Scenario: Additive pattern behavior
- **GIVEN** configuration with custom patterns:

  ```yaml
  security:
    blocked:
      - my_dangerous.*
  ```

- **WHEN** patterns are loaded
- **THEN** `my_dangerous.*` SHALL be added to defaults
- **AND** default blocked patterns (exec, eval, subprocess.*, etc.) SHALL still apply
- **RATIONALE** Prevents accidental removal of critical security patterns

#### Scenario: Allow list exemption
- **GIVEN** configuration with:

  ```yaml
  security:
    allow:
      - open
  ```

- **WHEN** code calls `open()`
- **THEN** validation SHALL pass without warning
- **AND** `open` SHALL be removed from warned defaults

#### Scenario: Promoting warning to block
- **GIVEN** configuration adding `open` to blocked:

  ```yaml
  security:
    blocked:
      - open
  ```

- **WHEN** code calls `open()`
- **THEN** validation SHALL fail with error
- **AND** blocked takes precedence over warned

#### Scenario: Wildcard patterns in security config
- **GIVEN** security patterns containing wildcards (*, ?, [seq])
- **WHEN** patterns are loaded
- **THEN** they SHALL be matched using fnmatch semantics
- **EXAMPLE** `subprocess.*` matches `subprocess.run`, `subprocess.Popen`, etc.

#### Scenario: Pattern type auto-detection
- **GIVEN** patterns in blocked/warned lists
- **WHEN** matching occurs
- **THEN** patterns without dots SHALL match builtins and imports
- **AND** patterns with dots SHALL match qualified function calls
- **EXAMPLE** `subprocess` matches `import subprocess`; `subprocess.*` matches `subprocess.run()`

