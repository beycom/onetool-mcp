## ADDED Requirements

### Requirement: Worker telemetry uses a fixed metric catalog

Telemetry schema version 1 SHALL support whole-episode duration, first-event
latency, turn count, terminal status, runtime start mode, Context bytes and
revisions before and after, Context validation failures, and rejected Context
bytes. Per-turn records SHALL support duration and provider-reported input,
output, and cached tokens.

#### Scenario: Provider reports token usage
- **WHEN** the provider supplies reliable input, output, or cached token values
- **THEN** telemetry SHALL record each value with token unit and `measured` availability

#### Scenario: Provider omits a measurement
- **WHEN** a catalog measurement is unavailable
- **THEN** telemetry SHALL record `unavailable` without a numeric value or fabricated zero

#### Scenario: Context bytes are recorded
- **WHEN** telemetry records persisted Context size
- **THEN** it SHALL label the value as Context bytes
- **AND** it SHALL NOT identify the value as total prompt, input, or model tokens

### Requirement: Per-turn and whole-episode records remain distinct

Each turn observation SHALL carry a positive turn ordinal and only per-turn
metrics. Each episode observation SHALL contain final status, actual turn count,
runtime mode, and whole-episode metrics. Aggregation SHALL NOT add per-turn first
event values as though they were episode duration.

#### Scenario: Continued episode is measured
- **WHEN** an episode completes after multiple turns
- **THEN** telemetry SHALL store one bounded per-turn observation for each turn and one episode observation
- **AND** the episode observation SHALL contain the final actual turn count

### Requirement: Telemetry excludes sensitive and high-cardinality content

Telemetry SHALL NOT store Context names, descriptions, tags, prompts, agent
messages, paths, labels, error text, Context bodies, Console identifiers or
bodies, file contents, diffs, tool results, credentials, secrets, or other
unapproved high-cardinality values. Observation IDs SHALL be opaque and SHALL not
permit reconstruction of named Context activity.

#### Scenario: Episode handles sensitive content
- **WHEN** a worker prompt, Console message, file, or error contains sensitive text
- **THEN** no telemetry field SHALL contain or derive that text

### Requirement: Telemetry is an isolated opt-in channel

Telemetry collection SHALL be disabled by default. Stored observations and
aggregates SHALL never become automatic worker or main-agent input and SHALL not
be copied into Chat, Context, Console, Status, History, or Local Changes records.

#### Scenario: Telemetry is disabled
- **WHEN** an episode runs with telemetry collection disabled
- **THEN** no telemetry observation SHALL be written
- **AND** the episode outcome SHALL otherwise be unchanged

#### Scenario: Later worker starts
- **WHEN** telemetry exists for earlier episodes
- **THEN** none of it SHALL be injected into worker startup

### Requirement: Telemetry retention is bounded and explicit

The telemetry store SHALL prune observations older than configured retention and
oldest observations beyond the configured record limit. Disabling collection
SHALL stop new observations but SHALL NOT delete stored observations. Explicit
clear SHALL own deletion and report its count.

#### Scenario: Retention bound is crossed
- **WHEN** collection would leave expired or excess records
- **THEN** the store SHALL remove oldest out-of-policy records before completing the append

#### Scenario: Records are explicitly cleared
- **WHEN** `telemetry_clear` receives a valid bounded UTC interval
- **THEN** it SHALL delete matching observations and return the deleted count

### Requirement: Telemetry queries return bounded aggregates only

`telemetry_query` SHALL require a bounded UTC interval, allow only approved
low-cardinality status and runtime-mode filters, and return counts, availability
counts, min/max/mean, and fixed histogram buckets. It SHALL NOT return raw rows or
unapproved labels.

#### Scenario: Aggregate query succeeds
- **WHEN** a caller queries a valid interval and approved filters
- **THEN** the result SHALL contain bounded aggregates and measurement availability
- **AND** it SHALL contain no observation body or high-cardinality identifier

#### Scenario: Telemetry store is malformed
- **WHEN** query encounters malformed persisted telemetry
- **THEN** it SHALL fail with a bounded diagnostic rather than fabricate aggregates

### Requirement: Telemetry failure does not change episode outcomes

A telemetry collection, prune, or persistence failure SHALL NOT change or undo
the known worker, Console, Context, Local Changes, Status, or History outcome.

#### Scenario: Telemetry append fails
- **WHEN** an episode outcome is known but telemetry cannot be stored
- **THEN** the episode SHALL finish through the normal foundation lifecycle
- **AND** an operational warning SHALL identify telemetry unavailability without sensitive content
