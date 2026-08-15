## ADDED Requirements

### Requirement: Strict worker telemetry configuration

`tools.worker.telemetry` SHALL accept exactly `enabled`, `retention_days`, and
`max_records`. `enabled` SHALL be a strict boolean defaulting to `false`.
`retention_days` SHALL be a strict integer from 1 through 365 defaulting to `30`.
`max_records` SHALL be a strict integer from 100 through 1,000,000 defaulting to
`10000`. Unknown or invalid fields SHALL be rejected.

#### Scenario: Telemetry configuration is omitted
- **WHEN** `tools.worker.telemetry` is absent
- **THEN** telemetry collection SHALL be disabled with 30-day and 10000-record bounds

#### Scenario: Telemetry configuration is invalid
- **WHEN** a value has the wrong strict type, is outside its range, or an unknown field is present
- **THEN** configuration validation SHALL fail before worker startup
