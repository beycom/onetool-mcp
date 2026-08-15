## ADDED Requirements

### Requirement: Strict worker configuration

The `tools.worker` configuration SHALL accept only optional `model`, `effort`,
and `context_max_kb` fields. `model` and `effort` SHALL be nonblank when set.
`context_max_kb` SHALL be a strict positive integer and SHALL default to `16`.

#### Scenario: Worker configuration is omitted
- **WHEN** `tools.worker` is absent or omits `context_max_kb`
- **THEN** the worker context limit SHALL default to 16 KB

#### Scenario: Valid worker configuration
- **WHEN** `tools.worker` contains a nonblank model, nonblank effort, and positive integer `context_max_kb`
- **THEN** OneTool SHALL preserve those values for worker execution

#### Scenario: Invalid worker configuration
- **WHEN** `tools.worker` contains an unknown field or invalid configured value
- **THEN** strict tool configuration validation SHALL reject it

### Requirement: Per-call worker routing overrides configuration

Explicit `worker.run` model and effort values SHALL take precedence over the
corresponding `tools.worker` values. When neither source provides a value, the
installed Codex app-server default SHALL apply. OneTool SHALL pass configured or
explicit values unchanged.

#### Scenario: Per-call selection is present
- **GIVEN** `tools.worker` configures model or effort
- **WHEN** `worker.run` supplies the corresponding value
- **THEN** the explicit call value SHALL be used

#### Scenario: Only configured selection is present
- **WHEN** `worker.run` omits model or effort and `tools.worker` supplies it
- **THEN** the configured value SHALL be used

#### Scenario: Selection is rejected by installed Codex
- **WHEN** the installed app-server rejects the effective model or effort
- **THEN** `worker.run` SHALL return `failed`
