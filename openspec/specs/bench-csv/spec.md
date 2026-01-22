# bench-csv Specification

## Purpose

Defines CSV results export functionality for ot-bench.

---

## Requirements

### Requirement: CSV Results Export

The harness SHALL support exporting detailed results to CSV format.

#### Scenario: Enable CSV export
- **GIVEN** user runs `ot-bench run <file> --csv`
- **WHEN** the benchmark completes
- **THEN** results SHALL be written to `tmp/result-{timestamp}.csv`
- **AND** timestamp format SHALL be `YYYYMMDD-HHMM`

#### Scenario: Include task summary in CSV
- **GIVEN** CSV export is enabled
- **WHEN** results are written
- **THEN** each row SHALL include: `scenario`, `task`, `model`, `server`, `result`, `total_input`, `total_output`, `llm_calls`, `tool_calls`, `duration_s`, `cost_usd`

#### Scenario: Include context analysis in CSV
- **GIVEN** CSV export is enabled
- **WHEN** results are written
- **THEN** columns SHALL include `base_context` and `context_growth_avg`

#### Scenario: Create CSV directory automatically
- **GIVEN** CSV export is enabled
- **AND** `tmp/` directory does not exist
- **WHEN** results are written
- **THEN** the directory SHALL be created automatically
