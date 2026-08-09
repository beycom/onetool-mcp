# harness-launcher Specification

## Purpose

Defines minimal process-replacement launching of official Claude Code and Codex
clients through CLIProxyAPI with live model selection, explicit context, opaque
harness arguments, and read-only diagnostics.

## Requirements

### Requirement: Configured harness targets

OneTool SHALL launch Claude Code or Codex through CLIProxyAPI using one required
model query resolved from the live inference inventory and an optional explicit
context policy supplied before the model.

#### Scenario: Claude proxy launch
- **WHEN** `onetool code claude MODEL` resolves `MODEL` to one inventory ID
- **THEN** OneTool SHALL launch `claude` through the environment-configured proxy
- **AND** it SHALL use the resolved selector through `claude --model` and
  `ANTHROPIC_MODEL` with the explicit Claude context policy
- **AND** it SHALL keep `CLAUDE_CODE_SUBAGENT_MODEL` aligned with that selector
- **AND** inherited Opus, Sonnet, and Haiku default-model overrides SHALL be
  removed without replacements

#### Scenario: Codex proxy launch
- **WHEN** `onetool code codex MODEL` resolves `MODEL` to one inventory ID
- **THEN** OneTool SHALL launch `codex` with an invocation-scoped proxy provider
- **AND** it SHALL pass the resolved ID through an explicit `--model` with the
  explicit Codex context policy

#### Scenario: Codex model catalog boundary
- **WHEN** OneTool is about to replace itself with Codex CLI
- **THEN** it SHALL display the resolved proxy model
- **AND** it SHALL explain that Codex `/model` displays Codex's native catalog
  and proxy models are changed through `onetool code`

#### Scenario: Codex session model scope
- **WHEN** OneTool is about to replace itself with Codex CLI
- **THEN** it SHALL explain that the invocation-scoped proxy provider and model
  apply to new, resumed, and forked sessions opened in that Codex process
- **AND** it SHALL direct users to plain `codex` when they want to preserve a
  saved session's native model

#### Scenario: Codex MCP startup verification
- **WHEN** OneTool is about to replace itself with Codex CLI
- **THEN** it SHALL explain that an interrupted-server startup message can precede
  a runtime refresh
- **AND** it SHALL direct users to wait for refresh and use Codex `/mcp` to verify
  the final MCP server state

#### Scenario: Codex App model boundary
- **WHEN** a user wants to launch a custom CLIProxyAPI model
- **THEN** OneTool SHALL direct that launch through Codex CLI
- **AND** it SHALL NOT add a custom-model management surface to Codex App, which
  remains native-model-only for this integration

#### Scenario: Model omitted
- **WHEN** a nested harness command is invoked without `MODEL`
- **THEN** it SHALL fail with the explicit syntax without launching a harness

#### Scenario: Harness binary missing
- **WHEN** process replacement cannot resolve the official harness on `PATH`
- **THEN** launch SHALL fail without trying another executable

### Requirement: Interactive launcher selection

Bare `onetool code` SHALL prompt for one harness, one model from the live
CLIProxyAPI inventory, and one explicit context policy before launching.

#### Scenario: Alphabetical model list
- **WHEN** the interactive launcher displays the live model inventory
- **THEN** it SHALL present the exact model IDs in deterministic,
  case-insensitive alphabetical order
- **AND** model selection SHALL use the same list-style interaction as harness
  selection

#### Scenario: Reusable command
- **WHEN** all interactive selections are valid
- **THEN** OneTool SHALL print a shell-safe `onetool code` command containing the
  selected harness, explicit context, and exact model ID before launch
- **AND** the displayed command SHALL NOT contain credentials or internal harness
  provider overrides

### Requirement: Deterministic model matching

OneTool SHALL resolve launch model queries only against one fresh bounded
CLIProxyAPI inventory and SHALL NOT use a static registry, compatibility alias,
route, profile, provider, subscription, or capability metadata.

#### Scenario: Exact match
- **WHEN** a query exactly matches an advertised model ID
- **THEN** OneTool SHALL select that ID before considering partial matches

#### Scenario: Unique partial match
- **WHEN** a case-insensitive token, suffix, or substring query identifies
  exactly one advertised model ID
- **THEN** OneTool SHALL select that ID

#### Scenario: Ambiguous match
- **WHEN** a non-exact query matches more than one advertised model ID
- **THEN** launch SHALL fail and list the candidate IDs without selecting one

#### Scenario: Missing match
- **WHEN** a query matches no advertised model ID
- **THEN** launch SHALL fail without substituting another model

### Requirement: Invocation-scoped configuration

Proxy, credential, resolved model, and explicit context changes SHALL affect
only the launched process.

#### Scenario: Claude automatic context
- **WHEN** a Claude invocation uses `--context auto` or omits the option
- **THEN** conflicting inherited context controls SHALL be removed
- **AND** the resolved model SHALL be used without a context suffix

#### Scenario: Claude 1M context
- **WHEN** a Claude invocation uses `--context 1m`
- **THEN** its generated selector and child model variables SHALL use
  `<resolved-model>[1m]`

#### Scenario: Claude standard context
- **WHEN** a Claude invocation uses `--context 200k`
- **THEN** it SHALL use the resolved model without a suffix
- **AND** the child SHALL set `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`

#### Scenario: Unsupported Claude context
- **WHEN** a Claude invocation supplies another positive numeric context
- **THEN** launch SHALL fail without approximating or silently clamping it

#### Scenario: Codex automatic context
- **WHEN** a Codex invocation uses `--context auto` or omits the option
- **THEN** it SHALL not generate context-window or auto-compact overrides

#### Scenario: Codex numeric context
- **WHEN** a Codex invocation supplies a positive numeric context
- **THEN** argv SHALL define invocation-scoped `model_context_window` and
  `model_auto_compact_token_limit` values
- **AND** the compact limit SHALL be 90 percent of the context window

#### Scenario: User files remain unchanged
- **WHEN** any invocation is constructed or launched
- **THEN** OneTool SHALL NOT write harness, proxy, model catalog, profile, alias,
  configuration, or settings files

#### Scenario: Secret isolation
- **WHEN** the bootstrap credential is used
- **THEN** it SHALL appear only in the target-specific child auth variable
- **AND** the bootstrap variable SHALL be removed from the final child
  environment

### Requirement: Bounded launcher status diagnostics

OneTool SHALL provide read-only status diagnostics for the environment-owned
CLIProxyAPI connection and official harness executables without reading or
mutating management configuration.

#### Scenario: Successful status
- **WHEN** `onetool code status` runs with a reachable authenticated inference
  endpoint
- **THEN** it SHALL display the normalized origin and its environment/default
  provenance, credential presence, every discovered model ID with available
  `owned_by` provider metadata and count, the derived `/management.html` URL and
  reachability, and installed harness/proxy executable versions
- **AND** model rows SHALL use deterministic case-insensitive order by complete
  ID, including any prefix, without inferring missing provider metadata
- **AND** it SHALL not display any credential value or raw HTTP body

#### Scenario: Required readiness failure
- **WHEN** the inference credential is missing or inventory discovery is
  unauthorized, unavailable, oversized, malformed, or timed out
- **THEN** status SHALL continue safe independent checks and exit non-zero with
  a bounded actionable diagnostic

#### Scenario: Optional diagnostic failure
- **WHEN** a harness executable, management page, or version probe is unavailable
- **THEN** status SHALL report a warning without exposing sensitive content

#### Scenario: Open management page
- **WHEN** `onetool code status --open` is invoked
- **THEN** OneTool SHALL ask the platform browser to open only the management URL
  derived from the normalized proxy origin after displaying status
- **AND** plain `status` SHALL never open a browser

#### Scenario: No administration
- **WHEN** status runs
- **THEN** it SHALL NOT read a management key or proxy YAML, call the management
  API, initiate OAuth, manage service lifecycle, or write user files

### Requirement: Opaque upstream passthrough

After consuming harness, launcher options, and `MODEL`, OneTool SHALL append
every remaining token unchanged and in order without parsing or validation.

#### Scenario: Separator not required
- **WHEN** `onetool code claude MODEL --continue` is invoked
- **THEN** `--continue` SHALL be forwarded unchanged

#### Scenario: Subcommands and unknown options
- **WHEN** remaining tokens contain subcommands, short forms, or unknown options
- **THEN** every token SHALL be forwarded unchanged and the harness SHALL validate
  them

#### Scenario: Conflicting option
- **WHEN** remaining tokens conflict with generated model, provider, permission,
  or config arguments
- **THEN** OneTool SHALL still forward them unchanged

#### Scenario: Literal delimiter
- **WHEN** remaining tokens include `--`
- **THEN** that token and every following token SHALL be preserved

#### Scenario: Option-like model ID
- **WHEN** a full model ID beginning with `-` follows a pre-model `--` delimiter
- **THEN** OneTool SHALL consume that delimiter and use the following token as
  `MODEL`
- **AND** every token after `MODEL` SHALL still be forwarded unchanged

### Requirement: Foreground lifecycle and diagnostics

OneTool SHALL replace itself with the selected harness without supervising it or
adding a post-launch presentation lifecycle.

#### Scenario: Process replacement
- **WHEN** required inputs are present
- **THEN** OneTool SHALL call process replacement with the ordered argv and child
  environment

#### Scenario: Harness-owned error
- **WHEN** the harness rejects a forwarded argument
- **THEN** its normal error and exit behaviour SHALL be presented directly
