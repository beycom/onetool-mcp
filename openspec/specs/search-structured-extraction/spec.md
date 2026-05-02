# search-structured-extraction Specification

## Purpose
TBD - created by archiving change search-structured-extraction-and-field-provenance. Update Purpose after archive.
## Requirements
### Requirement: Schema-constrained extraction mode
Search workflows SHALL support an explicit schema-constrained extraction mode.

#### Scenario: Valid schema accepted
- **WHEN** a caller provides a valid extraction schema
- **THEN** the search workflow SHALL return structured extracted data conforming to that schema

#### Scenario: Invalid schema rejected
- **WHEN** a caller provides an invalid schema
- **THEN** the workflow SHALL return an explicit validation error

### Requirement: Required and optional fields
Extraction mode SHALL enforce required/optional field semantics.

#### Scenario: Required field missing
- **WHEN** a required field cannot be extracted
- **THEN** the workflow SHALL return an explicit required-field failure in the structured result

#### Scenario: Optional field missing
- **WHEN** an optional field cannot be extracted
- **THEN** the workflow SHALL return a null or empty value per contract without failing the full extraction

