# field-level-provenance Specification

## Purpose
TBD - created by archiving change search-structured-extraction-and-field-provenance. Update Purpose after archive.
## Requirements
### Requirement: Field-level provenance metadata
Extraction results SHALL include provenance metadata per extracted field.

#### Scenario: Provenance attached to extracted field
- **WHEN** a field value is extracted
- **THEN** the field SHALL include provenance containing `source_url` and `snippet`

#### Scenario: Confidence when available
- **WHEN** provider confidence is available
- **THEN** the field provenance SHALL include `confidence`
- **AND** when unavailable, `confidence` SHALL be null or omitted per contract

### Requirement: Deterministic provenance structure
Field-level provenance SHALL use a stable, machine-readable structure.

#### Scenario: Stable key set
- **WHEN** extraction results are returned
- **THEN** all field provenance entries SHALL use the same key structure across result items

