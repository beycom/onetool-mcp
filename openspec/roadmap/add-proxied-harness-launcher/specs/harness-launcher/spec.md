## ADDED Requirements

### Requirement: Harness launch commands
OneTool SHALL launch the official Claude Code and Codex interactive harnesses with
the interface `onetool {harness} {model}`.

#### Scenario: Launch Claude Code
- **WHEN** `onetool claude sol` resolves `sol` to a valid configured route
- **THEN** OneTool SHALL launch the installed Claude Code executable with that
  route

#### Scenario: Launch Codex
- **WHEN** `onetool codex k3` resolves `k3` to a valid configured route
- **THEN** OneTool SHALL launch the installed Codex executable with that route

#### Scenario: Model omitted
- **WHEN** a harness command is invoked without a model
- **THEN** OneTool SHALL use the configured default model for that harness
- **AND** it SHALL fail actionably if no compatible default exists

#### Scenario: Harness binary missing
- **WHEN** the resolved harness executable is not available
- **THEN** OneTool SHALL exit before proxy launch or process replacement
- **AND** it SHALL name the missing harness and provide an installation hint

### Requirement: Proxy-only routing
Every harness session launched by OneTool SHALL send model traffic through
CLIProxyAPI.

#### Scenario: Claude subscription route
- **WHEN** a supported harness launches a model whose source is `claude`
- **THEN** the route SHALL be `harness -> CLIProxyAPI -> Claude subscription`
- **AND** OneTool SHALL NOT provide a direct Claude subscription alternative

#### Scenario: ChatGPT subscription route
- **WHEN** a supported harness launches a model whose source is `chatgpt`
- **THEN** the route SHALL be `harness -> CLIProxyAPI -> ChatGPT/Codex subscription`
- **AND** OneTool SHALL NOT provide a direct ChatGPT/Codex subscription alternative

#### Scenario: OpenRouter route
- **WHEN** a supported harness launches a model whose source is `openrouter`
- **THEN** the route SHALL be `harness -> CLIProxyAPI -> OpenRouter`

#### Scenario: Proxy unavailable
- **WHEN** the configured CLIProxyAPI endpoint is unhealthy and cannot be started
- **THEN** OneTool SHALL fail before launching the harness
- **AND** it SHALL NOT fall back to a direct provider endpoint

### Requirement: Harness and source compatibility
OneTool SHALL support configured Claude Code and Codex routes for Claude
subscription, ChatGPT/Codex subscription, and OpenRouter sources when CLIProxyAPI
advertises compatible models.

#### Scenario: Compatible cross-provider route
- **WHEN** a configured harness/model/source combination appears in live proxy
  discovery as compatible
- **THEN** OneTool SHALL allow the route regardless of whether the model source is
  native to that harness

#### Scenario: Unsupported combination
- **WHEN** the selected harness/model/source combination is not supported by the
  installed CLIProxyAPI or live model registry
- **THEN** OneTool SHALL reject it before launch
- **AND** the error SHALL identify the harness, model, source, proxy version, and
  corrective setup or model command

#### Scenario: Model choice filtering
- **WHEN** OneTool displays interactive or non-interactive model choices
- **THEN** it SHALL show only models configured for the selected harness and
  supported by the current proxy route

### Requirement: Shared route resolution
Interactive and non-interactive launch paths SHALL use the same typed resolver and
produce equivalent launch specifications.

#### Scenario: Shortcut resolution
- **WHEN** a unique configured model shortcut is supplied
- **THEN** OneTool SHALL resolve it to its configured model id, source, proxy alias,
  harness compatibility, context metadata, and capabilities

#### Scenario: Full model id resolution
- **WHEN** a configured full model id is supplied
- **THEN** OneTool SHALL resolve the same route as its shortcut

#### Scenario: Unknown model
- **WHEN** an unknown shortcut or model id is supplied
- **THEN** OneTool SHALL fail with compatible configured suggestions
- **AND** it SHALL NOT silently select a different model

#### Scenario: Invalid registry
- **WHEN** the configured model registry is missing or invalid
- **THEN** OneTool SHALL fail with the active config path and validation error
- **AND** it SHALL NOT use hidden Python model definitions as a fallback

### Requirement: Permission modes
OneTool SHALL support safe and bypass permission modes for every supported
harness.

#### Scenario: Safe mode
- **WHEN** `--safe` or `-S` is selected
- **THEN** the launch specification SHALL use the harness's normal approval and
  sandbox behavior
- **AND** it SHALL NOT contain a permission-bypass argument

#### Scenario: Bypass mode
- **WHEN** `--bypass` is selected or configured as the default
- **THEN** the launch summary SHALL label the mode prominently as `BYPASS`
- **AND** the launch specification SHALL use only the selected harness's current
  bypass mechanism

#### Scenario: Contradictory modes
- **WHEN** both safe and bypass modes are requested
- **THEN** OneTool SHALL reject the invocation before launching the proxy or harness

### Requirement: Invocation-scoped harness configuration
OneTool SHALL apply provider, proxy, model, context, and permission settings to the
launched process without rewriting global harness configuration for each launch.

#### Scenario: Claude environment isolation
- **WHEN** Claude Code is launched
- **THEN** inherited gateway and context variables that conflict with the resolved
  route SHALL be removed
- **AND** the Anthropic-compatible CLIProxyAPI endpoint, proxy credential, selected
  model, and verified context policy SHALL be applied to the child environment

#### Scenario: Codex adapter isolation
- **WHEN** Codex is launched
- **THEN** invocation-scoped Codex provider/catalog settings SHALL point to the
  CLIProxyAPI Responses-compatible route
- **AND** OneTool SHALL NOT rewrite unrelated user Codex settings

#### Scenario: Route observation markers
- **WHEN** any supported harness is launched
- **THEN** the child environment SHALL include non-secret OneTool markers for
  harness, configured model, source, route id, and permission mode
- **AND** it SHALL NOT include OAuth or management credentials as observation
  metadata

### Requirement: Interactive process handoff
OneTool SHALL preserve the official harness's terminal and process semantics.

#### Scenario: Successful handoff
- **WHEN** route preparation and validation succeed
- **THEN** OneTool SHALL use process replacement for the final harness launch
- **AND** the harness SHALL retain the current TTY, signals, colors, session
  behavior, and exit status

#### Scenario: Argument passthrough
- **WHEN** arguments follow `--` on a harness launch command
- **THEN** OneTool SHALL pass them to the selected harness unchanged and in order

#### Scenario: Dry run
- **WHEN** `--dry-run` is supplied
- **THEN** OneTool SHALL show the redacted command, resolved route, warnings, and
  environment additions/removals
- **AND** it SHALL NOT start or replace the harness process

### Requirement: Claude subscription billing warning
OneTool SHALL warn that Claude subscription routing through CLIProxyAPI can incur
extra charges and depends on third-party and upstream behavior.

#### Scenario: Claude-source launch summary
- **WHEN** a selected model source is `claude`
- **THEN** the launch summary and dry-run output SHALL prominently warn that
  requests may be classified as extra usage and incur additional charges
- **AND** it SHALL identify CLIProxyAPI as a required third-party dependency

#### Scenario: No billing guarantee
- **WHEN** OneTool reports a Claude subscription route
- **THEN** it SHALL NOT claim that requests are covered by included subscription
  allowance

#### Scenario: Warning remains redacted
- **WHEN** the warning is displayed or logged
- **THEN** it SHALL not include account identifiers, OAuth tokens, proxy keys, or
  other credential values
