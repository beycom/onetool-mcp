# serve-configuration Specification

## Purpose

Defines the YAML configuration system for OneTool. Configuration controls tool discovery, logging, and server settings.
## Requirements
### Requirement: YAML Configuration File

The system SHALL load configuration from a YAML file using a standard resolution order.

#### Scenario: Default configuration file resolution
- **GIVEN** no explicit config path provided
- **AND** no `ONETOOL_CONFIG` environment variable
- **WHEN** the server starts
- **THEN** it SHALL look for `~/.onetool/config/onetool.yaml`
- **AND** require initialisation if not found

#### Scenario: Environment variable override
- **GIVEN** `ONETOOL_CONFIG=/path/to/config.yaml` environment variable
- **WHEN** the server starts
- **THEN** it SHALL load from the specified path
- **AND** skip the standard resolution order

#### Scenario: Custom configuration file
- **GIVEN** `--config /path/to/config.yaml` argument
- **WHEN** the server starts
- **THEN** it SHALL load from the specified path

#### Scenario: Missing configuration file
- **GIVEN** no configuration file exists at any resolution location
- **WHEN** the server starts
- **THEN** it SHALL prompt user to initialise (interactive mode)
- **OR** exit with error message (non-interactive mode)

### Requirement: Unknown Config Attributes

The system SHALL ignore unrecognised configuration attributes and report them as warnings.

#### Scenario: Unknown nested attribute
- **GIVEN** `onetool.yaml` contains an unrecognised nested attribute
- **WHEN** configuration is loaded
- **THEN** the attribute SHALL be ignored
- **AND** a warning SHALL identify the dotted config path
- **AND** recognised sibling attributes SHALL still be applied

#### Scenario: Invalid recognised attribute
- **GIVEN** `onetool.yaml` contains a recognised attribute with an invalid value
- **WHEN** configuration is loaded
- **THEN** loading SHALL fail with a validation error

### Requirement: Config Include Fallback to Package Defaults

The system SHALL treat the **config dir** as `config_path.parent` (the directory containing `onetool.yaml`) and resolve all relative include paths from that directory.

When an include path is not found in the config dir, the system SHALL fall back to the matching path in the package's `global_templates/` directory.

#### Scenario: Include resolved from user config dir
- **GIVEN** `include: servers.yaml` in `onetool.yaml`
- **AND** `<config-dir>/servers.yaml` exists
- **WHEN** the config is loaded
- **THEN** `<config-dir>/servers.yaml` SHALL be used (user file takes precedence)

#### Scenario: Include falls back to package default
- **GIVEN** `include: servers.yaml` in `onetool.yaml`
- **AND** `<config-dir>/servers.yaml` does NOT exist
- **WHEN** the config is loaded
- **THEN** `global_templates/servers.yaml` SHALL be loaded as the fallback
- **AND** an INFO log message SHALL record that the package default was used

#### Scenario: Absolute include path — no fallback
- **GIVEN** `include: /absolute/path/to/file.yaml`
- **AND** the file does not exist
- **WHEN** the config is loaded
- **THEN** a warning SHALL be logged and the include SHALL be skipped
- **AND** no fallback to `global_templates/` SHALL occur

#### Scenario: Include not found anywhere
- **GIVEN** `include: nonexistent.yaml`
- **AND** neither `<config-dir>/nonexistent.yaml` nor `global_templates/nonexistent.yaml` exists
- **WHEN** the config is loaded
- **THEN** a warning SHALL be logged
- **AND** loading SHALL continue without that include

### Requirement: Graceful Cold Start

The system SHALL start successfully with only a minimal `onetool.yaml` file, without requiring `onetool init` to be run first.

#### Scenario: Bare config file
- **GIVEN** an `onetool.yaml` containing only `version: 2`
- **WHEN** the server starts
- **THEN** it SHALL start successfully
- **AND** security rules SHALL be loaded from the package default via include fallback
- **AND** no servers SHALL be configured (no proxy functionality)

#### Scenario: Config without init
- **GIVEN** no files exist in the config dir except `onetool.yaml`
- **WHEN** the server starts
- **THEN** it SHALL start successfully using package default includes

### Requirement: First-Run Initialization

The system SHALL support a graceful cold start without requiring prior initialisation. Explicit initialisation via `onetool init` remains available for users who want to customise config files.

#### Scenario: First-run with bare config
- **GIVEN** `onetool.yaml` exists with `version: 2` and no other files in the config dir
- **WHEN** the server starts
- **THEN** it SHALL start normally using package default fallbacks
- **AND** no initialization prompt SHALL be shown

#### Scenario: First-run interactive mode (no config at all)
- **GIVEN** no `onetool.yaml` exists anywhere
- **AND** stdin is a TTY (interactive mode)
- **WHEN** the server starts
- **THEN** it SHALL prompt "OneTool is not initialized. Initialize now? [Y/n]"
- **AND** on "y": call `ensure_ot_dir(config_path)` and continue
- **AND** on "n": print "Run 'onetool init' when ready." and exit(1)

#### Scenario: First-run non-interactive mode (no config at all)
- **GIVEN** no `onetool.yaml` exists anywhere
- **AND** stdin is NOT a TTY
- **WHEN** the server starts
- **THEN** it SHALL print "OneTool not initialized. Run: onetool init"
- **AND** exit with code 1

#### Scenario: Already initialized
- **GIVEN** `onetool.yaml` exists
- **WHEN** the server starts
- **THEN** it SHALL load configuration normally
- **AND** no initialization prompt SHALL be shown

## Change Notes

### Removed: DevTools Server Instructions Field

**Reason**: Server `instructions:` fields are removed from `servers.yaml`. DevTools usage guidance moves to the `ot-chrome-devtools-mcp` skill, retrieved on-demand via `ot.skills(name="ot-chrome-devtools-mcp")`.

**Migration**: Run `scaffold.skills(install="ot-chrome-devtools-mcp")` to install a stub, or call `>>> ot.skills(name="ot-chrome-devtools-mcp")` directly.

### Removed: Playwright Server Instructions Field

**Reason**: Server `instructions:` fields are removed from `servers.yaml`. Playwright usage guidance moves to the `ot-playwright-mcp` skill, retrieved on-demand via `ot.skills(name="ot-playwright-mcp")`.

**Migration**: Run `scaffold.skills(install="ot-playwright-mcp")` to install a stub, or call `>>> ot.skills(name="ot-playwright-mcp")` directly.

### Removed: Config Version Migration Detection

The system SHALL detect incompatible config versions.

#### Scenario: Future config version
- **GIVEN** a config file with `version: N` where N > CURRENT_CONFIG_VERSION
- **WHEN** configuration is loaded
- **THEN** loading SHALL fail with error
- **AND** the error SHALL indicate minimum OneTool version required
- **AND** suggest upgrading: "uv tool upgrade onetool"

#### Scenario: Missing version field
- **GIVEN** a config file without `version` field
- **WHEN** configuration is loaded
- **THEN** version 1 SHALL be assumed

### Removed: Execution Settings

The system SHALL use direct (host) execution.

#### Scenario: Default timeout
- **GIVEN** no timeout in configuration
- **WHEN** execution starts
- **THEN** it SHALL use default timeout (120s)

### Removed: Transform Tool Configuration

The transform() tool SHALL use OpenAI-compatible API configuration via `tools.transform`.

#### Scenario: Model configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    transform:
      model: "openai/gpt-4o-mini"
      base_url: "https://openrouter.ai/api/v1"
  ```
- **WHEN** llm.transform() is called
- **THEN** it SHALL use the specified model and base URL
- **DEFAULT** model: "" (empty - must be configured), base_url: "" (empty)

#### Scenario: Max tokens configuration
- **GIVEN** `tools.transform.max_tokens: 8192`
- **WHEN** llm.transform() is called
- **THEN** it SHALL limit output to 8192 tokens
- **DEFAULT** null (no limit)

#### Scenario: Timeout configuration
- **GIVEN** `tools.transform.timeout: 60`
- **WHEN** llm.transform() is called
- **THEN** it SHALL use 60 second timeout
- **DEFAULT** 30 seconds

#### Scenario: API key from secrets
- **GIVEN** `OPENAI_API_KEY` configured in `secrets.yaml`
- **WHEN** llm.transform() is called
- **THEN** it SHALL use the key for API calls

### Removed: Advanced Configuration

The system SHALL support advanced configuration options with config-relative path resolution.

#### Scenario: Custom tools directory
- **GIVEN** `tools_dir: ["tools/*.py", "plugins/*.py"]`
- **WHEN** the server starts
- **THEN** it SHALL discover tools from all matching glob patterns
- **AND** paths SHALL be resolved relative to the active .onetool directory (OT_DIR)
- **DEFAULT** ["tools/*.py"]

#### Scenario: Tools directory with CWD prefix
- **GIVEN** `tools_dir: ["CWD/tools/*.py"]`
- **WHEN** the server starts
- **THEN** it SHALL resolve paths relative to the project working directory (CWD)

#### Scenario: Tools directory with tilde
- **GIVEN** `tools_dir: ["~/shared/tools/*.py"]`
- **WHEN** the server starts
- **THEN** it SHALL expand `~` to the user's home directory

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

### Removed: Configuration Validation

The system SHALL validate configuration on load.

#### Scenario: Invalid timeout value
- **GIVEN** config with `timeout: -5`
- **WHEN** configuration loads
- **THEN** it SHALL fail with validation error

#### Scenario: Invalid memory format
- **GIVEN** config with `memory: invalid`
- **WHEN** configuration loads
- **THEN** it SHALL fail with validation error (expected format: 512m, 1g, etc.)

### Removed: Tool Discovery Configuration

OneTool SHALL discover tools from configurable glob patterns with sensible defaults.

#### Scenario: Default tool discovery
- **GIVEN** no tools_dir in config
- **WHEN** OneTool loads configuration
- **THEN** it SHALL load tools from `src/ottools/*.py`

#### Scenario: Custom tool sources
- **GIVEN** config with `tools.sources: ["src/ottools/*.py", "custom/**/*.py"]`
- **WHEN** OneTool loads configuration
- **THEN** it SHALL load tools from both patterns

#### Scenario: Tool exclusion patterns
- **GIVEN** config with `tools.sources: ["src/ottools/*.py", "!src/ottools/_*.py"]`
- **WHEN** OneTool loads configuration
- **THEN** it SHALL exclude files starting with underscore

### Removed: Execution Validation Configuration

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

### Removed: Enhanced Logging Configuration

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

### Removed: Server Metadata Configuration

The system SHALL support server metadata in configuration.

#### Scenario: Server name
- **GIVEN** config with `server.name: my-onetool`
- **WHEN** the MCP server starts
- **THEN** it SHALL use the configured name

#### Scenario: Instructions file reference
- **GIVEN** config with `server.instructions_file: prompts/custom.md`
- **WHEN** the server starts
- **THEN** it SHALL load instructions from the specified file

### Removed: V1 Minimal Configuration

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

### Removed: MCP Server Proxying Configuration

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

#### Scenario: OAuth authentication for HTTP server
- **GIVEN** configuration with:
  ```yaml
  servers:
    context7:
      type: http
      url: https://mcp.context7.com/mcp
      auth:
        type: oauth
        scopes: [tools:read, tools:write]
  ```
- **WHEN** the server starts
- **THEN** it SHALL initiate OAuth 2.1 + PKCE flow with browser authorization
- **AND** automatically refresh tokens when expired
- **AND** store tokens in-memory by default

#### Scenario: Bearer token authentication for HTTP server
- **GIVEN** configuration with:
  ```yaml
  servers:
    github:
      type: http
      url: https://api.githubcopilot.com/mcp/
      auth:
        type: bearer
        token: ${GITHUB_TOKEN}
  ```
- **WHEN** the server starts
- **THEN** it SHALL expand `${VAR}` in token using secrets.yaml values
- **AND** use the token for Bearer authentication
- **AND** error if variable not found in secrets

#### Scenario: No authentication (default)
- **GIVEN** configuration without auth field:
  ```yaml
  servers:
    local:
      type: http
      url: https://localhost:3000/mcp
  ```
- **WHEN** the server starts
- **THEN** it SHALL connect without authentication
- **AND** auth SHALL be None

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

#### Scenario: Variable expansion in server config
- **GIVEN** servers config with `${VAR_NAME}` in urls, headers, args, or command
- **WHEN** the server is initialized at runtime
- **THEN** it SHALL expand from secrets.yaml first, then env: section
- **AND** error if variable not found and no default provided

#### Scenario: Connection timeout
- **GIVEN** servers config with `timeout: 30`
- **WHEN** connecting to the MCP server
- **THEN** connection SHALL timeout after 30 seconds
- **DEFAULT** 60 seconds

### Removed: MCP Proxy Error Handling

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

### Removed: CLI Entry Point Naming

The MCP server CLI SHALL follow the `ot-<purpose>` naming convention.

#### Scenario: CLI command name
- **GIVEN** the OneTool MCP server package
- **WHEN** the user invokes the CLI
- **THEN** the command SHALL be `onetool`
- **AND** it SHALL be consistent with other CLIs (`bench`)

#### Scenario: CLI help
- **GIVEN** the user runs `onetool --help`
- **WHEN** help is displayed
- **THEN** it SHALL describe the MCP server functionality
- **AND** it SHALL show available options including `--config` and `--version`

#### Scenario: CLI version
- **GIVEN** the user runs `onetool --version`
- **WHEN** version is displayed
- **THEN** it SHALL show the package version

### Removed: Config Schema Version

Configuration files SHALL include a schema version for migration support.

#### Scenario: Version field present
- **GIVEN** a config file `onetool.yaml`
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

### Removed: Tool Dependency Metadata

Tools SHALL declare their dependencies for verification by `onetool check`.

#### Scenario: Dependency declaration
- **GIVEN** a tool module in `src/ottools/`
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

### Removed: Configuration Validation (modified)

The system SHALL validate configuration on load using discovered tool schemas.

#### Scenario: Tool timeout out of range
- **GIVEN** config with `tools.brave.timeout: 500`
- **WHEN** configuration loads
- **THEN** it SHALL fail with validation error from BraveConfig schema
- **AND** indicate max is 300.0

#### Scenario: Tool limit out of range
- **GIVEN** config with `tools.code.limit: 0`
- **WHEN** configuration loads
- **THEN** it SHALL fail with validation error from CodeConfig schema
- **AND** indicate min is 1

### Removed: Tools Configuration Section

The system SHALL support tool-specific configuration via the `tools:` section, with schemas discovered from tool files.

#### Scenario: Default tool configuration
- **GIVEN** no `tools:` section in configuration
- **WHEN** tools are loaded
- **THEN** they SHALL use defaults from their `Config` class
- **OR** built-in defaults if no Config class exists

#### Scenario: Partial tools configuration
- **GIVEN** configuration with only some tools configured:
  ```yaml
  tools:
    ground:
      model: gemini-2.0-flash
  ```
- **WHEN** other tools are used
- **THEN** they SHALL use their Config class defaults
- **OR** built-in defaults if no Config class

#### Scenario: Brave timeout configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    brave:
      timeout: 120.0
  ```
- **WHEN** brave.* functions are called
- **THEN** they SHALL use 120 second timeout
- **DEFAULT** 60.0 seconds (from brave_search.py Config class)
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
- **DEFAULT** gemini-2.5-flash (from grounding_search.py Config class)

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
- **DEFAULT** timeout: 30.0, docs_limit: 10 (from context7.py Config class)
- **RANGE** timeout: 1.0-120.0, docs_limit: 1-20

#### Scenario: Webfetch configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    webfetch:
      timeout: 60.0
      max_length: 100000
  ```
- **WHEN** webfetch.* functions are called
- **THEN** they SHALL use 60 second timeout and 100000 max length
- **DEFAULT** timeout: 30.0, max_length: 50000 (from webfetch.py Config class)
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
- **DEFAULT** 60.0 seconds (from ripgrep.py Config class)
- **RANGE** 1.0 - 300.0 seconds

#### Scenario: Memory tool configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    mem:
      search_limit: 25
  ```
- **WHEN** mem.* functions are called
- **THEN** they SHALL return up to 25 results
- **DEFAULT** 10 (from mem.py Config class)

#### Scenario: Database configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    db:
      max_chars: 8000
  ```
- **WHEN** db.* functions return results
- **THEN** they SHALL truncate at 8000 characters
- **DEFAULT** 4000 (from db.py Config class)
- **RANGE** 100 - 100000

#### Scenario: Package tool configuration
- **GIVEN** configuration with:
  ```yaml
  tools:
    package:
      timeout: 45.0
  ```
- **WHEN** package.* functions are called
- **THEN** they SHALL use 45 second timeout
- **DEFAULT** 30.0 seconds (from package.py Config class)
- **RANGE** 1.0 - 120.0 seconds

#### Scenario: Invalid tool configuration value
- **GIVEN** configuration with invalid value:
  ```yaml
  tools:
    brave:
      timeout: -5
  ```
- **WHEN** configuration is loaded
- **THEN** it SHALL fail with validation error from the tool's Config class
- **AND** error message SHALL indicate the field and constraint

### Removed: Cross-Platform Install Hints

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

### Removed: Secrets File Configuration

The system SHALL support a `secrets_file` field for loading secrets relative to the config file.

#### Scenario: Default secrets file
- **GIVEN** no `secrets_file` in configuration
- **WHEN** the server starts
- **THEN** it SHALL look for `secrets.yaml` in the `config/` subdirectory (same directory as `onetool.yaml`)

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

### Removed: Config Directory Tracking

The system SHALL track the directory containing the loaded configuration file.

#### Scenario: Config loaded from file
- **GIVEN** configuration loaded from `~/.onetool/config/onetool.yaml`
- **WHEN** relative paths are resolved
- **THEN** they SHALL resolve relative to `~/.onetool/config/`

#### Scenario: Config loaded from defaults
- **GIVEN** no configuration file exists
- **WHEN** the server starts with defaults
- **THEN** relative paths SHALL resolve relative to `get_effective_cwd() / ".onetool" / "config"`

#### Scenario: Config directory available
- **GIVEN** configuration is loaded
- **WHEN** code needs the config directory
- **THEN** it SHALL be available via a method on the config object

### Removed: Runtime Variable Expansion

The system SHALL expand `${VAR}` patterns at runtime when values are used, not during config load.

#### Scenario: Variable expansion in tool config
- **GIVEN** `${API_KEY}` in a tool configuration value
- **AND** `API_KEY: "secret123"` in secrets.yaml
- **WHEN** `get_tool_config()` is called
- **THEN** the value SHALL be expanded to "secret123" at runtime

#### Scenario: Variable sources and precedence
- **GIVEN** `${VAR}` in a tool configuration value
- **WHEN** expansion occurs
- **THEN** sources SHALL be checked in order:
  1. secrets.yaml (sensitive, user-specific)
  2. config env: section (non-sensitive, shared)
  3. Default value if ${VAR:-default} syntax used
  4. ValueError if not found

#### Scenario: No expansion during load_config
- **GIVEN** `${API_KEY}` in a config value
- **WHEN** `load_config()` is called
- **THEN** the raw value with `${API_KEY}` SHALL be stored
- **AND** no expansion SHALL occur

#### Scenario: Expansion at point of use
- **GIVEN** tool config with `api_url: "https://api.example.com/${API_VERSION}"`
- **AND** `API_VERSION: "v2"` in secrets.yaml
- **WHEN** `get_tool_config("mytool")` is called
- **THEN** returned config SHALL have `api_url: "https://api.example.com/v2"`

#### Scenario: Default value syntax
- **GIVEN** `${VAR:-default}` in a tool config value
- **AND** VAR not in secrets.yaml or env: section
- **WHEN** `get_tool_config()` is called
- **THEN** the value SHALL be expanded to "default"

#### Scenario: No os.environ reading
- **GIVEN** `${MY_VAR}` in a tool config value
- **AND** MY_VAR set in os.environ but NOT in secrets.yaml or env: section
- **WHEN** `get_tool_config()` is called
- **THEN** MY_VAR from os.environ SHALL NOT be used
- **AND** error or default SHALL apply

### Removed: Subprocess Environment Pass-through

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

### Removed: Logging Configuration in YAML

The system SHALL support logging settings in YAML config and environment variable overrides.

#### Scenario: Log level in config
- **GIVEN** configuration with `log_level: DEBUG`
- **WHEN** the server starts
- **THEN** it SHALL use DEBUG logging level
- **DEFAULT** INFO

#### Scenario: Log level via environment variable
- **GIVEN** `OT_LOG_LEVEL=DEBUG` environment variable
- **WHEN** the server starts
- **THEN** it SHALL use DEBUG logging level
- **AND** the env var SHALL take priority over `log_level` in YAML
- **VALID VALUES** DEBUG, INFO, WARNING, ERROR (invalid values are ignored)

#### Scenario: Log directory in config
- **GIVEN** configuration with `log_dir: custom/logs`
- **WHEN** the server starts
- **THEN** logs SHALL be written to the specified directory relative to `.onetool/`
- **DEFAULT** `logs` (logs written to `.onetool/logs/`)

#### Scenario: Log directory via environment variable
- **GIVEN** `OT_LOG_DIR=/tmp/my-logs` environment variable
- **WHEN** the server starts
- **THEN** logs SHALL be written to the specified path
- **AND** the env var SHALL take priority over `log_dir` in YAML

#### Scenario: Compact max length in config
- **GIVEN** configuration with `compact_max_length: 200`
- **WHEN** compact console output is used
- **THEN** values SHALL be truncated at 200 characters
- **DEFAULT** 120

#### Scenario: Compact max length via environment variable
- **GIVEN** `OT_COMPACT_MAX_LENGTH=200` environment variable
- **WHEN** compact console output is used
- **THEN** values SHALL be truncated at 200 characters
- **AND** the env var SHALL take priority over `compact_max_length` in YAML
- **AND** non-integer values SHALL be ignored (config default used instead)

### Removed: Remote GitHub MCP Server Configuration

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
- **AND** expose GitHub tools via the `github` pack

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

### Removed: Config Include

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

#### Scenario: Include path resolution
- **GIVEN** a relative path in `include:`
- **WHEN** the file is loaded
- **THEN** the path SHALL be resolved relative to the config file directory
- **AND** `~` SHALL expand to user home directory

#### Scenario: Nested includes with depth limit
- **GIVEN** `base.yaml` contains its own `include:` key
- **WHEN** the config is loaded
- **THEN** nested includes SHALL be processed recursively
- **AND** merge order SHALL be depth-first
- **AND** include depth SHALL be limited to 5 levels

#### Scenario: Include depth exceeded
- **GIVEN** includes nested more than 5 levels deep
- **WHEN** the config is loaded
- **THEN** an error SHALL be raised indicating depth exceeded

#### Scenario: Missing include file
- **GIVEN** `include:` references a file that does not exist
- **WHEN** the config is loaded
- **THEN** a warning SHALL be logged
- **AND** loading SHALL continue without that include

#### Scenario: No include key
- **GIVEN** configuration without `include:` key
- **WHEN** the config is loaded
- **THEN** loading SHALL proceed normally with no external files

### Removed: Security Configuration

The system SHALL support allowlist-based security configuration via security.yaml.

**IMPORTANT:** The security model provides defence-in-depth but is NOT a sandbox. Never run code you do not trust.

#### Scenario: Security section structure
- **GIVEN** configuration with:

  ```yaml
  security:
    validate_code: true
    enabled: true
    builtins:
      allow: [str, int, len, print]
    imports:
      allow: [json, re, math]
      warn: [yaml]
    calls:
      block: [pickle.*, yaml.load]
      warn: [random.seed]
    dunders:
      allow: [__format__, __sanitize__]
  ```

- **WHEN** code is validated
- **THEN** only explicitly allowed items SHALL pass validation

#### Scenario: Security disabled
- **GIVEN** configuration with `security.enabled: false`
- **WHEN** code is validated
- **THEN** security pattern checks SHALL be skipped

#### Scenario: Default security configuration
- **GIVEN** no security section in config
- **WHEN** code is validated
- **THEN** defaults embedded in Pydantic models SHALL be used
- **AND** defaults SHALL include safe builtins and standard library imports

#### Scenario: Wildcard patterns in security config
- **GIVEN** security patterns containing wildcards (*, ?, [seq])
- **WHEN** patterns are loaded
- **THEN** they SHALL be matched using fnmatch semantics
- **EXAMPLE** `pickle.*` matches `pickle.load`, `pickle.loads`, etc.

### Removed: Tool-Local Configuration Schema

Tools SHALL declare their configuration schema in the tool file itself using a Pydantic `Config` class.

#### Scenario: Tool with Config class
- **GIVEN** a tool file containing:
  ```python
  from pydantic import BaseModel, Field

  pack = "brave"

  class Config(BaseModel):
      timeout: float = Field(default=60.0, ge=1.0, le=300.0)
  ```
- **WHEN** the tool is discovered by the registry
- **THEN** the Config class SHALL be extracted via AST
- **AND** stored in `ToolInfo.config_schema`

#### Scenario: Tool without Config class
- **GIVEN** a tool file without a `class Config(BaseModel)`
- **WHEN** the tool is discovered
- **THEN** `ToolInfo.config_schema` SHALL be None
- **AND** the tool SHALL function normally without configuration

#### Scenario: Config class naming convention
- **GIVEN** a tool file with a config class
- **WHEN** the class is defined
- **THEN** it SHALL be named `Config` (not `BraveConfig`, `ToolConfig`, etc.)
- **AND** it SHALL inherit from `pydantic.BaseModel`

### Removed: Dynamic Tool Configuration Building

The system SHALL dynamically build `ToolsConfig` from discovered tool schemas.

#### Scenario: Build ToolsConfig from registry
- **GIVEN** multiple tools with Config classes are discovered
- **WHEN** configuration is loaded
- **THEN** `ToolsConfig` SHALL be dynamically generated
- **AND** each pack with a Config SHALL have a corresponding field

#### Scenario: Unknown tool config in YAML
- **GIVEN** a `tools.unknown_pack:` section in onetool.yaml
- **AND** no tool with pack "unknown_pack" is discovered
- **WHEN** configuration is loaded
- **THEN** the unknown section SHALL be ignored
- **AND** a debug log message SHALL be emitted

#### Scenario: Partial tool configuration
- **GIVEN** a tool has Config class with defaults
- **AND** onetool.yaml only specifies some fields
- **WHEN** configuration is loaded
- **THEN** specified fields SHALL override defaults
- **AND** unspecified fields SHALL use Config class defaults

### Removed: Runtime Tool Config Access

Tools SHALL access their configuration via `get_tool_config()` at runtime.

#### Scenario: Get tool config with schema
- **GIVEN** a tool needs its configuration
- **WHEN** `get_tool_config("brave", Config)` is called
- **THEN** it SHALL return a Config instance with merged values
- **AND** values from onetool.yaml SHALL override defaults

#### Scenario: Get tool config without schema
- **GIVEN** a tool calls `get_tool_config("brave")`
- **WHEN** no schema is provided
- **THEN** it SHALL return a dict with raw config values
- **OR** empty dict if no config exists

#### Scenario: Unknown tool in config
- **GIVEN** a `tools.unknown_pack:` section in onetool.yaml
- **AND** no tool with pack "unknown_pack" exists
- **WHEN** configuration is loaded
- **THEN** the section SHALL be preserved (extra="allow")
- **AND** no error SHALL occur

### Removed: Top-Level LLM Configuration

The config SHALL support a top-level `llm:` key providing shared defaults inherited by all LLM-using tools (`ot_llm`, `ot_image`, `mem`, `knowledge`).

```yaml
llm:
  model: ""            # default chat/completion model
  embedding_model: ""  # default embedding model (e.g. text-embedding-3-small)
  base_url: ""         # OpenAI-compatible API base URL
  api_key: ""          # API key (prefer secrets file)
```

#### Scenario: Tool-specific override
- **GIVEN** both `llm.model` and `tools.<pack>.model` are set
- **WHEN** the pack resolves its model
- **THEN** `tools.<pack>.model` SHALL take precedence over `llm.model`

#### Scenario: Base URL override
- **GIVEN** both `llm.base_url` and `tools.<pack>.base_url` are set
- **WHEN** the pack resolves its base URL
- **THEN** `tools.<pack>.base_url` SHALL take precedence over `llm.base_url`

#### Scenario: LLM section absent
- **GIVEN** no `llm:` section in onetool.yaml
- **WHEN** the server starts
- **THEN** it SHALL start without error
- **AND** each tool SHALL use its own tool-specific config directly

#### Scenario: Inherited fields
- **GIVEN** a top-level `llm:` section
- **WHEN** an LLM-using tool resolves its configuration
- **THEN** the following fields SHALL be inheritable: `model`, `base_url`, `api_key`

#### Scenario: Resolution order
- **GIVEN** an LLM-using tool needs a config field (e.g. `model`)
- **WHEN** the field is resolved
- **THEN** the resolution order SHALL be:
  1. Tool-specific config (`tools.<pack>.model`)
  2. Top-level LLM config (`llm.model`)
  3. Error if required and not found at either level

#### Scenario: API key always from secrets
- **GIVEN** `llm.api_key` is set in `onetool.yaml`
- **WHEN** a tool resolves its API key
- **THEN** the key SHALL be retrieved via `get_secret()` from `secrets.yaml`
- **AND** the `api_key` field in `llm:` config is for documentation/reference only
- **AND** secrets SHALL never be stored in plain-text YAML config

#### Scenario: Participating tools
- **GIVEN** the top-level `llm:` section
- **WHEN** tools resolve LLM configuration
- **THEN** the following tools SHALL participate in inheritance: `ot_llm`, `ot_image`, `mem`, `knowledge`
- **AND** tools that do not use an LLM SHALL ignore the `llm:` section

### Removed: Stats Configuration Location

Statistics configuration SHALL be at the root level.

#### Scenario: Stats config at root level
- **GIVEN** configuration with:
  ```yaml
  stats:
    enabled: true
    flush_interval_seconds: 60
  ```
- **WHEN** the server starts
- **THEN** it SHALL use the root-level `stats` configuration

#### Scenario: Default stats location
- **GIVEN** no stats configuration specified
- **WHEN** the server starts
- **THEN** stats SHALL use defaults from Pydantic model
- **DEFAULT** enabled: true, flush_interval_seconds: 30, persist_dir: stats

### Removed: Stats Directory Configuration

The system SHALL support a dedicated directory for statistics files.

#### Scenario: Stats directory default
- **GIVEN** no `stats.persist_dir` in configuration
- **WHEN** the server starts
- **THEN** stats SHALL be written to `.onetool/stats/`

#### Scenario: Custom stats directory
- **GIVEN** configuration with `stats.persist_dir: metrics`
- **WHEN** the server starts
- **THEN** stats SHALL be written to `.onetool/metrics/`

#### Scenario: Stats directory creation
- **GIVEN** the stats directory does not exist
- **WHEN** the server starts
- **THEN** the directory SHALL be created automatically

### Removed: Output Sanitisation Configuration

The system SHALL support configuration for output sanitisation in the security section.

#### Scenario: Configuration structure
- **GIVEN** onetool.yaml configuration
- **WHEN** security.sanitize section is defined
- **THEN** it SHALL support the following structure:

  ```yaml
  security:
    sanitize:
      enabled: true
  ```

#### Scenario: Default enabled state
- **GIVEN** no `security.sanitize` configuration
- **WHEN** defaults are applied
- **THEN** `enabled` SHALL default to `true`

### Removed: Output Configuration

The system SHALL support configuration for large output handling in the `output` section.

#### Scenario: Default output configuration
- **GIVEN** no `output:` section in config
- **WHEN** configuration is loaded
- **THEN** defaults SHALL be:
  - `max_inline_size`: 5000 (bytes)
  - `result_store_dir`: `tmp` (relative to `.onetool/`)
  - `result_ttl`: 3600 (seconds)
  - `preview_lines`: 10
  - `preview_max_chars`: 500
  - `compact`: `false`

#### Scenario: Custom max_inline_size
- **GIVEN** configuration:
  ```yaml
  output:
    max_inline_size: 100000
  ```
- **WHEN** configuration is loaded
- **THEN** large output threshold SHALL be 100000 bytes

#### Scenario: Custom result_store_dir
- **GIVEN** configuration:
  ```yaml
  output:
    result_store_dir: results
  ```
- **WHEN** configuration is loaded
- **THEN** results SHALL be stored in `.onetool/results/`

#### Scenario: Custom result_ttl
- **GIVEN** configuration:
  ```yaml
  output:
    result_ttl: 7200
  ```
- **WHEN** configuration is loaded
- **THEN** results SHALL expire after 7200 seconds (2 hours)

#### Scenario: Custom preview_lines
- **GIVEN** configuration:
  ```yaml
  output:
    preview_lines: 20
  ```
- **WHEN** a large output is stored
- **THEN** summary preview SHALL include first 20 lines

#### Scenario: Custom preview_max_chars
- **GIVEN** configuration:
  ```yaml
  output:
    preview_max_chars: 200
  ```
- **WHEN** a large output is stored
- **THEN** each preview line SHALL be truncated to 200 characters with `…` appended if truncated
- **AND** `preview_max_chars: 0` SHALL disable per-line truncation entirely

#### Scenario: Disabled large output handling
- **GIVEN** configuration:
  ```yaml
  output:
    max_inline_size: 0
  ```
- **WHEN** configuration is loaded
- **THEN** large output handling SHALL be disabled
- **AND** all outputs SHALL be returned inline

#### Scenario: Global compaction enabled
- **GIVEN** configuration:
  ```yaml
  output:
    compact: true
  ```
- **WHEN** configuration is loaded
- **THEN** all tool outputs SHALL be passed through ot_caveman text compaction by default
- **AND** per-call `__compact__ = False` SHALL override this and suppress compaction

#### Scenario: Per-call override of global compaction
- **GIVEN** `output.compact` is `true`
- **AND** code that sets `__compact__ = False`
- **WHEN** the result is returned
- **THEN** compaction SHALL NOT be applied for that call

### Removed: Root-Level Environment Configuration

The system SHALL support a root-level `env:` section for shared subprocess environment variables.

#### Scenario: Root env section
- **GIVEN** configuration with:
  ```yaml
  env:
    HOME: /home/user
    LANG: en_US.UTF-8
  ```
- **WHEN** a stdio MCP server is spawned
- **THEN** the subprocess SHALL inherit these environment variables

#### Scenario: Server env overrides root env
- **GIVEN** root `env:` with `LANG: en_US.UTF-8`
- **AND** server `env:` with `LANG: C.UTF-8`
- **WHEN** the server subprocess is spawned
- **THEN** `LANG` SHALL be `C.UTF-8` (server overrides root)

#### Scenario: Subprocess env build order
- **GIVEN** a stdio server configuration
- **WHEN** the subprocess environment is built
- **THEN** it SHALL be constructed in order:
  1. `PATH` from host os.environ (always included)
  2. Root `env:` section values
  3. Server-specific `env:` section values (overrides root)
  4. `${VAR}` expansion from secrets.yaml only

#### Scenario: Variable expansion in env values
- **GIVEN** env value containing `${API_KEY}`
- **AND** `API_KEY` defined in secrets.yaml
- **WHEN** the subprocess is spawned
- **THEN** the value SHALL be expanded from secrets.yaml
- **AND** os.environ SHALL NOT be consulted

#### Scenario: No root env section
- **GIVEN** configuration without `env:` section
- **WHEN** a stdio server is spawned
- **THEN** subprocess SHALL receive only `PATH` plus server-specific env

### Removed: DevTools Server Template Documentation

The `servers.yaml` global template SHALL include comprehensive inline documentation for the Chrome DevTools MCP server entry.

#### Scenario: Connection mode comments
- **GIVEN** a user reading the DevTools section of `servers.yaml`
- **WHEN** they inspect the comments
- **THEN** they find descriptions of isolated mode (default), remote mode (advanced), and autoConnect mode (experimental)
- **AND** instructions for switching between modes

#### Scenario: Remote mode setup instructions
- **GIVEN** a user wanting to use remote mode
- **WHEN** they read the DevTools section comments
- **THEN** they find platform-specific Chrome launch commands for macOS, Linux, and Windows
- **AND** a verification command (`curl http://localhost:9222/json/version`)
- **AND** a note about `--user-data-dir` being required since Chrome 136+

#### Scenario: Element highlighting reference
- **GIVEN** a user wanting to use element annotations via Chrome DevTools
- **WHEN** they read the DevTools section comments
- **THEN** they find a quick reference for `chrome_util` functions (inject, highlight, scan, clear)
- **AND** a note about Ctrl+I / Cmd+I for manual annotation

### Removed: Playwright Server Template

The `servers.yaml` global template SHALL include a commented-out Playwright MCP server entry.

#### Scenario: Playwright entry present
- **GIVEN** a user reading `servers.yaml`
- **WHEN** they look for browser automation options
- **THEN** they find a commented-out Playwright MCP server configuration
- **AND** setup instructions (install command)
- **AND** a brief comparison of when to use DevTools vs Playwright

#### Scenario: Playwright element highlighting reference
- **GIVEN** a user wanting to use element annotations via Playwright
- **WHEN** they read the Playwright section comments
- **THEN** they find a quick reference for `play_util` functions (inject, highlight, scan, clear)
- **AND** a note that `play_util` is the Playwright equivalent of `chrome_util`

### Removed: DevTools Server Instructions Field

The DevTools server entry SHALL include an `instructions` field summarising capabilities for AI assistants.

#### Scenario: DevTools instructions content
- **GIVEN** the DevTools server `instructions` field
- **WHEN** read by an AI assistant
- **THEN** it includes tool count, `chrome_util` element highlighting API, connection modes, and best-use-case guidance

### Removed: Playwright Server Instructions Field

The Playwright server entry SHALL include an `instructions` field summarising capabilities for AI assistants.

#### Scenario: Playwright instructions content
- **GIVEN** the Playwright server `instructions` field
- **WHEN** read by an AI assistant
- **THEN** it includes `play_util` element highlighting API and best-use-case guidance
- **AND** it notes that `play_util` is independent from `chrome_util` (no fallback between them)

### Removed: Transparent Per-Value Decryption of Secrets

The secrets loader SHALL transparently decrypt `age1enc:`-prefixed values in `secrets.yaml` using an age X25519 identity from the OS keychain, without requiring any change to the `--secrets` flag or file path.

#### Scenario: Plain secrets file loads unchanged
- **WHEN** `secrets.yaml` contains no `age1enc:` prefixed values
- **AND** the server starts with `--secrets secrets.yaml`
- **THEN** it SHALL load values exactly as before
- **AND** it SHALL NOT attempt to access the OS keychain
- **AND** startup behavior SHALL be identical to the current implementation

#### Scenario: Encrypted value is transparently decrypted
- **WHEN** `secrets.yaml` contains a value prefixed `age1enc:<base64-ciphertext>`
- **AND** an age identity is stored in the OS keychain under service `"onetool"`, key `"age_identity"`
- **WHEN** the server loads secrets
- **THEN** it SHALL decrypt the value in memory using the identity
- **AND** the decrypted plaintext SHALL be available via `${VAR}` expansion as normal
- **AND** the decrypted value SHALL NOT be written to disk

#### Scenario: Mixed file — encrypted and plain values coexist
- **WHEN** `secrets.yaml` contains a mix of `age1enc:` and plain values
- **WHEN** secrets are loaded
- **THEN** encrypted values SHALL be decrypted in memory
- **AND** plain values SHALL be passed through unchanged
- **AND** all values SHALL be available for `${VAR}` expansion

#### Scenario: Encrypted values present but identity not in keychain
- **WHEN** `secrets.yaml` contains at least one `age1enc:` value
- **AND** no age identity is found in the OS keychain
- **WHEN** secrets are loaded
- **THEN** loading SHALL fail with a clear error
- **AND** the error SHALL instruct the user to run `ot_secrets.init()`

#### Scenario: Decrypted values are never logged
- **WHEN** `age1enc:` values are decrypted
- **THEN** the plaintext values SHALL NOT appear in any log output (LogSpan, debug, error, or otherwise)
- **AND** the existing JSON-RPC isolation architecture SHALL be preserved (secrets not passed via env vars or process logs)

#### Scenario: Keychain access is lazy
- **WHEN** the secrets file is loaded
- **AND** no values start with `age1enc:`
- **THEN** `keyring.get_password()` SHALL NOT be called
- **AND** `keyring.get_password()` SHALL NOT be called for users without encrypted values

#### Scenario: Missing keyring package with encrypted values
- **WHEN** `secrets.yaml` contains at least one `age1enc:` value
- **AND** the `keyring` package is not installed
- **WHEN** secrets are loaded
- **THEN** it SHALL raise an error with an install hint: `"pip install onetool-mcp"`

#### Scenario: Missing pyrage package with encrypted values
- **WHEN** `secrets.yaml` contains at least one `age1enc:` value
- **AND** the `pyrage` package is not installed
- **WHEN** secrets are loaded
- **THEN** it SHALL raise an error with an install hint: `"pip install onetool-mcp"`
