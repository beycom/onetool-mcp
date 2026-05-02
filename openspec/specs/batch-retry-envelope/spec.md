# batch-retry-envelope Specification

## Purpose
TBD - created by archiving change search-batch-error-envelope-and-retry-policy-ground-brave-tavily. Update Purpose after archive.
## Requirements
### Requirement: Per-query batch error envelope
Batch search operations SHALL return a per-query envelope with explicit success/error state.

#### Scenario: Successful item envelope
- **WHEN** a batch query completes successfully
- **THEN** the item SHALL include `status="ok"`
- **AND** the item SHALL include `attempts` and `retried` metadata

#### Scenario: Failed item envelope
- **WHEN** a batch query fails after all attempts
- **THEN** the item SHALL include `status="error"`
- **AND** the item SHALL include `error_code` and `error_message`
- **AND** the item SHALL include `final_failure=true`

### Requirement: Shared retry controls
Batch search operations SHALL expose shared retry controls across providers.

#### Scenario: Retry controls accepted
- **WHEN** a caller provides `retries` and `retry_delay_ms`
- **THEN** each provider batch tool SHALL apply those controls to transient failures

#### Scenario: Retries disabled by default
- **WHEN** no retry controls are provided
- **THEN** the batch operation SHALL run with default retry settings documented by the pack

### Requirement: Transient failure classification
Batch retry logic SHALL classify transient failures consistently across providers.

#### Scenario: Transient HTTP/server failure retried
- **WHEN** a query returns timeout, connection error, HTTP 429, or HTTP 5xx
- **THEN** the batch operation SHALL retry up to the configured retry count

#### Scenario: Non-transient error not retried
- **WHEN** a query fails with a non-transient class
- **THEN** the batch operation SHALL return an error envelope without retrying

### Requirement: Partial success handling
Batch search operations SHALL return successful items even when other items fail.

#### Scenario: Mixed batch outcomes
- **WHEN** some queries succeed and some fail
- **THEN** successful items SHALL remain present in results
- **AND** failed items SHALL include their error envelopes

