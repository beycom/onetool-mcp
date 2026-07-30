# harness-launcher Specification

## Purpose

Defines deterministic process-replacement launching of official Claude Code and
Codex clients through exact proxy routes or direct Codex profiles.

## Requirements

### Requirement: Configured harness targets

OneTool SHALL launch official harnesses through an exact configured proxy route or
an exact configured direct profile supported by that harness.

#### Scenario: Claude proxy launch
- **WHEN** Claude selects a compatible configured proxy model
- **THEN** OneTool SHALL launch the configured Claude executable through
  `code.proxy`
- **AND** it SHALL send the model record's exact effective id

#### Scenario: Codex proxy launch
- **WHEN** Codex selects a compatible configured proxy model
- **THEN** OneTool SHALL launch the configured Codex executable with the
  invocation-scoped `onetool_proxy` provider

#### Scenario: Direct Codex profile
- **WHEN** Codex selects an exact configured profile and model
- **THEN** OneTool SHALL pass that profile and exact model directly to Codex
- **AND** it SHALL not resolve a proxy secret or construct proxy provider settings

#### Scenario: Model omitted
- **WHEN** a harness command is invoked without a model
- **THEN** OneTool SHALL use a compatible configured default
- **AND** it SHALL fail actionably or offer interactive selection when no default
  exists

#### Scenario: Harness binary missing
- **WHEN** the configured executable is unavailable
- **THEN** launch SHALL fail before secret resolution, network I/O, or process
  replacement

### Requirement: Harness and route compatibility

Claude SHALL support `claude_subscription`, `codex_subscription`, and `openrouter`
proxy routes. Codex SHALL support `codex_subscription` and `openrouter` proxy
routes plus configured direct Codex profiles.

#### Scenario: Unsupported combination
- **WHEN** Codex is asked to use `claude_subscription`
- **THEN** OneTool SHALL reject the route without substituting another route

#### Scenario: Direct profile offered to Claude
- **WHEN** Claude is asked to use a direct profile
- **THEN** OneTool SHALL reject it without translating it into a proxy route

#### Scenario: Claude subscription warning
- **WHEN** Claude selects a configured `claude_subscription` model
- **THEN** OneTool SHALL always display the Anthropic terms, account, and billing
  warning, including in quiet mode

### Requirement: Deterministic model matching

OneTool SHALL resolve launcher models by exact full id or exact configured
shortcut. Routes and profiles SHALL use exact canonical identifiers.

#### Scenario: Exact full id
- **WHEN** the input exactly equals one compatible configured model id
- **THEN** that record SHALL be selected

#### Scenario: Exact shortcut
- **WHEN** the input exactly equals one compatible configured shortcut
- **THEN** that record SHALL be selected

#### Scenario: Unknown selection
- **WHEN** input is not an exact configured id or shortcut
- **THEN** launch SHALL fail and list valid exact choices
- **AND** it SHALL not normalize or partially match the input

#### Scenario: Same id under multiple targets
- **WHEN** the selected id exists under multiple compatible routes or profiles
- **THEN** OneTool SHALL require an exact `--route` or `--profile`

#### Scenario: Globally unique shortcut
- **WHEN** two launcher records configure the same shortcut
- **THEN** strict configuration validation SHALL reject the configuration

### Requirement: Normal launch is discovery-independent

Normal and dry-run invocation construction SHALL depend only on local
configuration, executable resolution, and the named inference secret when the
target is a proxy route.

#### Scenario: No launch-time discovery
- **WHEN** OneTool constructs a normal or dry-run harness invocation
- **THEN** it SHALL NOT call `/v1/models`, `--version`, or `--help`

#### Scenario: No CLIProxyAPI config dependency
- **WHEN** a launcher invocation is constructed
- **THEN** OneTool SHALL NOT read, locate, parse, or mutate a CLIProxyAPI YAML file
- **AND** it SHALL NOT require a CLIProxyAPI management key

#### Scenario: Exact proxy wire identity
- **WHEN** a configured proxy model is launched without a Claude context policy
- **THEN** its `id` SHALL be passed unchanged as the proxy-facing model identity
- **AND** OneTool SHALL NOT translate it through aliases or live discovery

### Requirement: Invocation-scoped configuration

Proxy, profile, model, and Claude context changes SHALL affect only the launched
process.

#### Scenario: Claude proxy environment
- **WHEN** a Claude proxy invocation is constructed
- **THEN** conflicting inherited Anthropic gateway, model, description, and context
  variables SHALL be removed
- **AND** `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, and all three default model
  slots SHALL use the selected proxy and effective model id
- **AND** argv SHALL contain exactly one OneTool-owned `--model`

#### Scenario: Claude one-million-token context
- **WHEN** the selected record configures Claude context `1m`
- **THEN** the effective model SHALL use the documented `[1m]` suffix
- **AND** an optional configured auto-compaction threshold SHALL be set only for
  the launched process

#### Scenario: Claude standard context
- **WHEN** the selected record configures Claude context `standard`
- **THEN** the base model id SHALL be used
- **AND** one-million-token context SHALL be explicitly disabled for the launched
  process

#### Scenario: Claude policy omitted
- **WHEN** the selected record has no Claude context policy
- **THEN** the base model id SHALL be used
- **AND** inherited OneTool-owned context overrides SHALL be removed

#### Scenario: Codex proxy provider
- **WHEN** a Codex proxy invocation is constructed
- **THEN** argv SHALL define `onetool_proxy` with the configured base URL,
  `wire_api = "responses"`, and private `ONETOOL_CODE_PROVIDER_KEY`
- **AND** the selected exact model id SHALL follow one OneTool-owned `--model`

#### Scenario: Codex direct profile
- **WHEN** a Codex direct invocation is constructed
- **THEN** argv SHALL contain one OneTool-owned `--profile` and one `--model`
- **AND** no proxy provider, proxy base URL, or proxy credential SHALL be added

#### Scenario: Working directory
- **WHEN** a client working directory is configured
- **THEN** OneTool SHALL change to that directory immediately before replacing the
  process

#### Scenario: User files remain unchanged
- **WHEN** any invocation is constructed or launched
- **THEN** OneTool SHALL NOT write Claude, Codex, CLIProxyAPI, authentication,
  profile, catalog, or settings files

#### Scenario: Secret isolation
- **WHEN** an invocation requires the named proxy secret
- **THEN** its value SHALL appear only in the launched environment
- **AND** it SHALL not appear in argv, summaries, dry runs, logs, or errors

### Requirement: Permission modes

OneTool SHALL support `normal` and `bypass` through one `--permission` option.

#### Scenario: Normal mode
- **WHEN** `normal` is selected
- **THEN** OneTool SHALL add no permission-bypass flag

#### Scenario: Bypass mode
- **WHEN** `bypass` is selected
- **THEN** OneTool SHALL add only the verified bypass flag for that harness

### Requirement: Opaque upstream passthrough

OneTool SHALL preserve every token after the first real `--` delimiter as an
ordered upstream tail without interpreting upstream commands or option values,
except to reject syntactic forms of OneTool-owned options.

#### Scenario: Model omitted before boundary
- **WHEN** `onetool codex -- exec` is invoked
- **THEN** `exec` SHALL remain passthrough and SHALL NOT become the launcher model

#### Scenario: Upstream commands and aliases
- **WHEN** the tail contains Codex `exec`, `e`, `apply`, or `a`, or Claude `plugins`
  or `upgrade`
- **THEN** those tokens SHALL pass through unchanged and in order

#### Scenario: Arbitrary option values
- **WHEN** an upstream option or its value is not a OneTool-owned long or short
  option form
- **THEN** OneTool SHALL preserve it without partially reimplementing the upstream
  parser

#### Scenario: Owned flag conflict
- **WHEN** configured arguments or passthrough contain a model, route/profile,
  Codex provider, or permission-bypass option owned by OneTool
- **AND** that option uses a long form, a long form with `=`, a separated short
  form, or an attached short form
- **THEN** launch SHALL reject the conflict before replacing the process

#### Scenario: Route and profile conflict
- **WHEN** both `--route` and `--profile` are supplied
- **THEN** launch SHALL reject the mutually exclusive target selectors

#### Scenario: Argument order
- **WHEN** an invocation is built
- **THEN** argv SHALL contain the executable, OneTool-owned arguments, configured
  additional arguments, then the explicit passthrough tail

### Requirement: Foreground lifecycle and diagnostics

OneTool SHALL hand terminal ownership directly to the selected harness through
process replacement and provide bounded, redacted pre-launch presentation.

#### Scenario: Process replacement
- **WHEN** a non-dry-run invocation passes all pre-launch validation
- **THEN** OneTool SHALL replace itself with the configured harness executable and
  environment
- **AND** it SHALL not supervise a child or emit a post-exit summary

#### Scenario: Dry run
- **WHEN** `--dry-run` is selected
- **THEN** OneTool SHALL show the redacted target, argv, and environment delta
  without replacing the process

#### Scenario: Pre-launch summary
- **WHEN** lifecycle output is enabled
- **THEN** it SHALL identify harness, configured model id or label, target, and
  permission without exposing secrets
- **AND** any transformed wire selector such as Claude's `[1m]` form SHALL remain
  visible only in redacted verbose or dry-run argv
