## ADDED Requirements

### Requirement: Strict autonomous continuation limits

`tools.worker.max_turns` SHALL be a strict integer from 1 through 10 and SHALL
default to `3`. `tools.worker.episode_timeout_seconds` SHALL be a strict integer
from 1 through 3600 and SHALL default to `900`. Unknown or out-of-range values
SHALL be rejected by configuration validation.

#### Scenario: Continuation settings are omitted
- **WHEN** worker configuration omits both continuation fields
- **THEN** an episode SHALL allow at most 3 turns and 900 seconds

#### Scenario: Continuation settings are invalid
- **WHEN** either setting is a boolean, non-integer, or outside its permitted range
- **THEN** configuration validation SHALL fail before a worker starts
