# search-batch-structured-contract Specification

## Purpose

Defines the shared structured response shape for batch search tools, including
ordered per-item results, explicit status and error fields, and aggregate batch
metadata.
## Requirements
### Requirement: Structured batch response shape
Batch search tools SHALL return a JSON-serializable object instead of delimiter text.

#### Scenario: Top-level shape
- **WHEN** a batch search completes
- **THEN** the return value SHALL include top-level `results` and `meta` keys

#### Scenario: Per-item shape
- **WHEN** any result item is present
- **THEN** each item SHALL include `label`, `query`, `status`, `data`, and `error` fields

### Requirement: Deterministic ordering
Batch results SHALL preserve normalized input order.

#### Scenario: Ordered results
- **WHEN** queries are submitted in order `q1`, `q2`, `q3`
- **THEN** `results` SHALL appear in the same order

### Requirement: Explicit status and errors
Batch results SHALL represent success and failure explicitly.

#### Scenario: Success item
- **WHEN** a query succeeds
- **THEN** the item SHALL set `status="ok"`
- **AND** the item SHALL populate `data`

#### Scenario: Error item
- **WHEN** a query fails
- **THEN** the item SHALL set `status="error"`
- **AND** the item SHALL populate `error`

### Requirement: Batch metadata summary
Batch response metadata SHALL summarize aggregate outcomes.

#### Scenario: Meta totals
- **WHEN** batch processing completes
- **THEN** `meta` SHALL include totals for query count, success count, and error count
- **AND** `meta` SHALL indicate whether the outcome is partial success
