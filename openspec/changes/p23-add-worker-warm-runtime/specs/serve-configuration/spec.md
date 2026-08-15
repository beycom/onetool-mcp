## ADDED Requirements

### Requirement: Strict warm-runtime configuration

`tools.worker.warm_runtime_enabled` SHALL be a strict boolean and SHALL default
to `false`. `tools.worker.warm_runtime_idle_seconds` SHALL be a strict integer
from 1 through 3600 and SHALL default to `300`. Unknown or invalid values SHALL
be rejected by configuration validation.

#### Scenario: Warm runtime settings are omitted
- **WHEN** worker configuration omits warm-runtime fields
- **THEN** each episode SHALL use a cold process and the idle limit SHALL be 300 seconds

#### Scenario: Warm runtime is enabled
- **WHEN** `warm_runtime_enabled` is `true` with a valid idle duration
- **THEN** eligible serialized episodes SHALL reuse a healthy matching runtime

#### Scenario: Idle duration is invalid
- **WHEN** the value is a boolean, non-integer, less than 1, or greater than 3600
- **THEN** configuration validation SHALL fail
