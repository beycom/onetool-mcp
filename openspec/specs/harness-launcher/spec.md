# harness-launcher Specification

## Purpose

Defines deterministic foreground launching of official Claude Code and Codex
clients through typed model routes, checked client capabilities, isolated
invocation configuration, explicit permissions, and redacted diagnostics.

## Requirements
### Requirement: Harness launch commands
OneTool SHALL launch the official Claude Code and Codex interactive harnesses from a
typed configured route.

#### Scenario: Launch Claude Code
- **WHEN** `onetool claude sol` resolves to a compatible configured route
- **THEN** OneTool SHALL launch the installed Claude Code executable with that model,
  source, and transport

#### Scenario: Launch Codex
- **WHEN** `onetool codex luna` resolves to a compatible configured route
- **THEN** OneTool SHALL launch the installed Codex executable with that model,
  source, and transport

#### Scenario: Model omitted
- **WHEN** a harness command is invoked without a model
- **THEN** OneTool SHALL use the configured default route and model for that harness
- **AND** it SHALL fail actionably when no default exists

#### Scenario: Harness binary missing
- **WHEN** the resolved harness executable is unavailable
- **THEN** OneTool SHALL fail before any external login, network route, or child
  process begins

### Requirement: Direct and proxied route matrix
OneTool SHALL support only explicitly configured and verified harness, source, and
transport combinations.

#### Scenario: Native Claude route
- **WHEN** Claude Code selects its native Claude subscription route
- **THEN** the child SHALL use direct native authentication
- **AND** inherited gateway variables SHALL not accidentally proxy the route

#### Scenario: Claude through Codex subscription
- **WHEN** Claude Code selects a Codex-subscription model through CLIProxyAPI
- **THEN** the child SHALL use the configured Anthropic-compatible proxy endpoint,
  inference credential, and selected proxy alias or model id

#### Scenario: Claude through OpenRouter
- **WHEN** Claude Code selects an OpenRouter model through CLIProxyAPI
- **THEN** the same bounded proxy adapter SHALL be used with the configured
  OpenRouter-backed alias

#### Scenario: Native Codex route
- **WHEN** Codex selects its native Codex subscription route with direct transport
- **THEN** the child SHALL preserve the user's native Codex authentication and
  unrelated configuration

#### Scenario: Codex subscription through proxy
- **WHEN** Codex selects a Codex subscription route with CLIProxyAPI transport
- **THEN** invocation-scoped Responses-compatible settings SHALL point at the
  configured proxy

#### Scenario: Codex through OpenRouter
- **WHEN** Codex selects an OpenRouter route
- **THEN** invocation-scoped Codex provider/profile/catalog settings SHALL use the
  configured OpenRouter secret and model

#### Scenario: Unsupported combination
- **WHEN** no verified adapter exists for the selected harness, source, and transport
- **THEN** OneTool SHALL reject the route before starting the child
- **AND** it SHALL not infer another combination

### Requirement: Deterministic route resolution
Model, route, source, and transport selection SHALL be explicit and deterministic.

#### Scenario: Shortcut resolution
- **WHEN** a unique configured shortcut is supplied
- **THEN** it SHALL resolve to the configured model metadata and compatible selected
  route

#### Scenario: Full model id resolution
- **WHEN** a configured full model id is supplied
- **THEN** it SHALL resolve to the same model entry as its shortcut

#### Scenario: Explicit route
- **WHEN** a route option is supplied
- **THEN** it SHALL take precedence over the harness default only when compatible
  with the selected model

#### Scenario: Unknown or ambiguous selection
- **WHEN** a model or route is unknown or ambiguous
- **THEN** launch SHALL fail with compatible configured suggestions
- **AND** it SHALL not substitute another model, source, transport, or provider

### Requirement: Permission modes
OneTool SHALL support safe and bypass modes for each harness.

#### Scenario: Safe mode
- **WHEN** safe mode is selected
- **THEN** no harness permission-bypass argument SHALL be present

#### Scenario: Bypass mode
- **WHEN** bypass mode is selected
- **THEN** only the current verified bypass mechanism for that harness SHALL be used
- **AND** the starting summary SHALL label the mode prominently

#### Scenario: Contradictory permission options
- **WHEN** safe and bypass modes are both requested
- **THEN** OneTool SHALL reject the invocation before starting the child

### Requirement: Invocation-scoped configuration
Provider and model changes SHALL affect only the launched process.

#### Scenario: Claude environment isolation
- **WHEN** a Claude route is constructed
- **THEN** conflicting inherited gateway, credential, model, and context variables
  SHALL be removed
- **AND** only values required by the selected route SHALL be added

#### Scenario: Proxied Claude invocation
- **WHEN** a proxied Claude route is constructed
- **THEN** its child environment SHALL contain the selected
  `ANTHROPIC_BASE_URL`, named-secret value as `ANTHROPIC_AUTH_TOKEN`, and all three
  verified Claude Code 2.x default model-slot variables
- **AND** its argv SHALL contain exactly one route-owned `--model` selection
- **AND** the resolved credential SHALL not appear in argv

#### Scenario: Native Claude invocation
- **WHEN** a native Claude subscription route is constructed
- **THEN** inherited Anthropic gateway, API credential, auth-token, and proxy model
  slot values SHALL not redirect or reclassify the child
- **AND** no CLIProxyAPI credential SHALL be resolved

#### Scenario: Claude subrequest cannot escape
- **WHEN** a proxied Claude session issues a background, subagent, Opus, Sonnet, or
  Haiku model-slot request
- **THEN** the child environment SHALL keep that request on the aliases validated for
  the selected proxy route
- **AND** an omitted slot mapping SHALL use the selected proxy alias for every slot

#### Scenario: Codex configuration isolation
- **WHEN** a non-native Codex route is constructed
- **THEN** provider and catalog settings SHALL be invocation-scoped
- **AND** unrelated global Codex configuration SHALL not be rewritten

#### Scenario: Non-native Codex invocation
- **WHEN** a proxied Codex or direct OpenRouter Codex route is constructed
- **THEN** argv SHALL contain invocation-scoped Codex overrides selecting one
  dedicated custom provider with `base_url`, `env_key`, and
  `wire_api = "responses"`
- **AND** the named-secret value SHALL exist only in the private child environment
  variable referenced by `env_key`
- **AND** no resolved credential SHALL appear in argv or generated TOML

#### Scenario: Native Codex invocation
- **WHEN** a native direct Codex subscription route is constructed
- **THEN** OneTool SHALL not override `model_provider` or inject a provider
  credential
- **AND** the user's normal supported Codex authentication and configuration SHALL
  remain in effect

#### Scenario: Global config remains byte-identical
- **WHEN** any Claude or Codex child succeeds, fails, or is interrupted
- **THEN** pre-existing user and project settings, config, profile, catalog, auth, and
  CLIProxyAPI files SHALL remain byte-identical

#### Scenario: Secret isolation
- **WHEN** a child environment or adapter requires a credential
- **THEN** only the selected named secret SHALL be resolved
- **AND** it SHALL not appear in display output, logs, errors, or route markers

### Requirement: Foreground harness lifecycle presentation
OneTool SHALL present clear starting and ending information while preserving the
interactive harness.

#### Scenario: Starting summary
- **WHEN** a harness is ready to start
- **THEN** an interactive terminal SHALL show a polished summary containing harness,
  model, source, transport, safe endpoint display, permission mode, and warnings
- **AND** secrets SHALL be omitted

#### Scenario: Harness remains interactive
- **WHEN** the foreground child is running
- **THEN** it SHALL inherit the terminal's standard input, output, and error streams
- **AND** OneTool SHALL preserve terminal resize and termination behavior

#### Scenario: Ending summary
- **WHEN** the harness exits
- **THEN** OneTool SHALL show harness, model, route, elapsed time, and success, exit
  code, or terminating signal
- **AND** OneTool SHALL return the corresponding child outcome

#### Scenario: Plain or quiet presentation
- **WHEN** output is non-interactive, color is disabled, or quiet mode is selected
- **THEN** presentation SHALL use concise plain text or suppress decorative summaries
- **AND** warnings and errors SHALL remain visible

#### Scenario: Dry run
- **WHEN** dry-run is selected
- **THEN** OneTool SHALL show the redacted resolved route, environment delta, and
  command without starting the proxy or harness

#### Scenario: Passthrough
- **WHEN** arguments follow `--`
- **THEN** they SHALL be passed to the harness unchanged and in order
- **AND** route-owned conflicts SHALL be rejected before launch

### Requirement: Provider responsibility and warnings
OneTool SHALL explain its configuration boundary without guaranteeing upstream
provider behavior.

#### Scenario: General route notice
- **WHEN** setup, route documentation, or detailed route output is shown
- **THEN** it SHALL state that OneTool does not guarantee terms compliance, model
  availability, subscription classification, included usage, rate limits, or billing
- **AND** it SHALL assign route choice to the user and proxy authentication/routing to
  CLIProxyAPI

#### Scenario: Claude subscription proxy disabled
- **WHEN** Claude subscription through CLIProxyAPI has not been explicitly enabled
- **THEN** that route SHALL not be selectable

#### Scenario: Claude subscription proxy warning
- **WHEN** an enabled Claude subscription proxy route is selected
- **THEN** config guidance and the starting summary SHALL warn that the path is not an
  approved Anthropic subscription route and may breach terms, restrict the account,
  or change billing treatment

#### Scenario: No billing guarantee
- **WHEN** any subscription-backed route is displayed
- **THEN** OneTool SHALL not claim that its requests are covered by included usage or
  cannot incur charges
