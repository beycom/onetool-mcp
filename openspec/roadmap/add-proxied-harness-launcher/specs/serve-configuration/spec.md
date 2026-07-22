## ADDED Requirements

### Requirement: Harness configuration section
OneTool configuration SHALL support a typed top-level `harness` section for
proxy-only Claude Code and Codex launch behavior.

#### Scenario: Supported harness section
- **GIVEN** a version 2 config containing `harness`
- **WHEN** OneTool loads configuration
- **THEN** it SHALL validate launcher defaults, CLIProxyAPI settings, source
  settings, and the model registry

#### Scenario: Harness section omitted
- **WHEN** `harness` is omitted
- **THEN** normal OneTool MCP server behavior SHALL remain unchanged
- **AND** harness launch commands SHALL report that setup is required

#### Scenario: Unknown harness field
- **WHEN** `harness` or any nested harness model contains an unknown field
- **THEN** configuration validation SHALL reject it
- **AND** it SHALL not treat a removed or renamed field as an alias

### Requirement: Harness defaults
The harness configuration SHALL define explicit default harness, model, and
permission behavior.

#### Scenario: Valid defaults
- **WHEN** configured defaults reference a supported harness, permission mode, and
  compatible model
- **THEN** omitted launch selections SHALL use those values

#### Scenario: Invalid default model
- **WHEN** a configured default model does not exist or is incompatible with its
  harness
- **THEN** configuration or launch validation SHALL fail instead of selecting
  another model

#### Scenario: Permission values
- **WHEN** `default_permission_mode` is configured
- **THEN** only `safe` and `bypass` SHALL be accepted

### Requirement: CLIProxyAPI configuration
The harness section SHALL define managed or external CLIProxyAPI behavior without
embedding secret values.

#### Scenario: Managed configuration
- **WHEN** `harness.cliproxy.managed` is true
- **THEN** executable, loopback base URL, auto-start, startup timeout, shutdown
  timeout, model cache TTL, and generated state settings SHALL be validated

#### Scenario: External configuration
- **WHEN** `harness.cliproxy.managed` is false
- **THEN** a base URL SHALL be required
- **AND** lifecycle ownership SHALL remain external

#### Scenario: Named secrets
- **WHEN** proxy client or management authentication is configured
- **THEN** config SHALL store OneTool secret names rather than resolved values
- **AND** missing required names or secret values SHALL produce actionable errors
  only when the relevant operation requires them

#### Scenario: Unsafe broad bind
- **WHEN** generated managed proxy configuration would bind inference or management
  endpoints beyond loopback
- **THEN** validation SHALL reject it in v1

### Requirement: Supported model sources
Harness configuration SHALL support `claude`, `chatgpt`, and `openrouter` model
sources.

#### Scenario: Claude source
- **WHEN** a model declares `source: claude`
- **THEN** it SHALL be resolved through CLIProxyAPI Claude OAuth state

#### Scenario: ChatGPT source
- **WHEN** a model declares `source: chatgpt`
- **THEN** it SHALL be resolved through CLIProxyAPI Codex OAuth state

#### Scenario: OpenRouter source
- **WHEN** a model declares `source: openrouter`
- **THEN** it SHALL reference the configured OpenRouter secret name and route
  through CLIProxyAPI

#### Scenario: Unknown source
- **WHEN** a model declares any other source
- **THEN** typed configuration validation SHALL reject it

### Requirement: Typed model registry
The harness section SHALL contain the authoritative configured model registry.

#### Scenario: Model entry validation
- **WHEN** a model entry is loaded
- **THEN** it SHALL validate shortcut, label, model id, source, proxy alias,
  supported harnesses, context window, Claude context class, modalities, and
  declared capability metadata

#### Scenario: Unique shortcut
- **WHEN** two model entries use the same shortcut or an ambiguous id/alias
- **THEN** configuration validation SHALL reject the registry

#### Scenario: Supported harnesses
- **WHEN** a model entry declares harness compatibility
- **THEN** only `claude` and `codex` SHALL be accepted
- **AND** at least one harness SHALL be required

#### Scenario: No embedded fallback
- **WHEN** the configured registry is empty or missing after setup is expected
- **THEN** launcher commands SHALL fail actionably
- **AND** runtime code SHALL not supply hidden model definitions

### Requirement: Harness configuration materialisation
OneTool SHALL support an optional user-owned `harness.yaml` include without making
it mandatory for the MCP server.

#### Scenario: Materialised include
- **WHEN** the user selects harness configuration during guided init or code setup
- **THEN** `harness.yaml` SHALL be written under the config directory
- **AND** `onetool.yaml` SHALL include it through normal include behavior

#### Scenario: Existing harness include
- **WHEN** materialisation would overwrite an existing `harness.yaml`
- **THEN** the normal confirmation, `--force`, and `.bak` backup behavior SHALL
  apply

#### Scenario: Inline configuration
- **WHEN** users place `harness` directly in `onetool.yaml`
- **THEN** it SHALL validate and behave equivalently to an included section

### Requirement: Harness state ownership
Generated harness, proxy, and adapter files SHALL follow the canonical OneTool
config-relative layout.

#### Scenario: Generated runtime state
- **WHEN** OneTool creates proxy config, PID state, model cache, or a Codex catalog
- **THEN** it SHALL place them under `{OT_DIR}/runtime/code/` in their designated
  subdirectories

#### Scenario: Proxy logs
- **WHEN** a managed proxy writes logs
- **THEN** they SHALL be stored under `{OT_DIR}/runtime/logs/`

#### Scenario: OAuth state
- **WHEN** CLIProxyAPI creates Claude or Codex OAuth state
- **THEN** its auth directory SHALL be under `{OT_DIR}/auth/cliproxy/`

#### Scenario: Alternative active config
- **WHEN** a harness command uses an alternative OneTool config path
- **THEN** all generated state and auth paths SHALL resolve relative to that config
  directory
- **AND** no state SHALL silently fall back to a default user's config directory

### Requirement: Generated artifacts are not user configuration
OneTool SHALL keep generated proxy and harness adapter artifacts derived from the
typed harness section.

#### Scenario: Generated config display
- **WHEN** effective configuration is shown
- **THEN** generated artifact paths and freshness MAY be reported
- **AND** secret-bearing generated content SHALL not be displayed

#### Scenario: Generated artifact edited
- **WHEN** a generated artifact is changed independently
- **THEN** the next regeneration SHALL replace it from effective OneTool config
- **AND** OneTool SHALL not merge its unrecognised edits back into user config

#### Scenario: Atomic replacement
- **WHEN** a generated artifact is updated
- **THEN** OneTool SHALL use an atomic replacement and appropriate private file
  permissions
