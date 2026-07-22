# tool-arch-yaml-excel-parity Specification

## Purpose

Defines semantic parity, conversion, sparse-intent preservation, and complete source tracing between YAML and Excel architecture workspaces.

## Requirements

### Requirement: Equivalent workspace structures
The tool SHALL map YAML `states`, `changes`, `roadmaps`, `views`, and `diagrams`
to the Excel `change`, `roadmap`, `view`, `diagram`, `sys`, `app`, `cmp`,
`interface`, and `usr` domain sheets without changing semantics. Excel SHALL
not require or emit a `model` worksheet. Blank `change` entity rows SHALL form
the complete base, whose identity is inferred from the repeated `state` column
or roadmap base. Presentation SHALL come from strict `tools.arch` configuration.
When presentation configuration does not set `title`, the runtime title SHALL be
the input filename stem and SHALL NOT become portable YAML/Excel semantics.

#### Scenario: Normalize canonical YAML and Excel inputs
- **WHEN** the paired canonical workspaces are loaded
- **THEN** they produce identical states, changes, normalized operations,
  roadmaps, view selections, and diagram entries when loaded with the same
  `tools.arch` presentation configuration

#### Scenario: Load and generate without a model worksheet
- **WHEN** an Excel workspace contains only domain sheets
- **THEN** it loads successfully, and subsequent Excel generation does not
  create a `model` worksheet

#### Scenario: Derive the runtime title
- **WHEN** `customer-payments.xlsx` or `customer-payments.yaml` is loaded without
  a configured presentation title
- **THEN** the explorer title is `customer-payments`, while conversion does not
  author a title or presentation block in either workspace format

#### Scenario: Read inline changes for every entity sheet
- **WHEN** `sys`, `app`, `cmp`, `interface`, and `usr` contain base and named
  change rows
- **THEN** the same blank-base and sparse-patch rules apply to every sheet

### Requirement: Preserve sparse intent and scalar identity
Conversion SHALL preserve blank versus explicit `unset`, explicit removal,
`change_note`, ordering, notes, tags, list values, source references, diagram
metadata, and extension properties or columns. Numeric Excel cells containing
year-like IDs SHALL normalize deterministically to strings.

System and change `group` SHALL be list-valued and use the same bracketed
semicolon representation as `tags`. Excel `properties` cells SHALL accept a
JSON object, semicolon-delimited `name:value` entries, or newline-delimited
`name:value` entries. Compact entries SHALL trim names and values, preserve
empty values, split on only the first colon, and reject blank names, malformed
entries, and duplicate names.

#### Scenario: Preserve year-like IDs and lists
- **WHEN** Excel stores change ID 2027 as a numeric cell and related products as
  `[wallet;payments]`
- **THEN** the canonical model contains change ID `"2027"` and the ordered list
  values `wallet` and `payments`

#### Scenario: Preserve blank and unset through conversion
- **WHEN** a workbook contains one blank property mutation and one explicit
  property in its `unset` column
- **THEN** YAML conversion omits the blank mutation and records the explicit
  unset, and converting back preserves that distinction

#### Scenario: Preserve extension fields
- **WHEN** a YAML change property or Excel change/entity column is not a typed
  schema field
- **THEN** both conversion directions preserve it as extension metadata

#### Scenario: Read compact property entries
- **WHEN** an Excel properties cell contains `owner:payments;tier:one` or the
  same entries on separate lines
- **THEN** both forms produce the same two-property map

#### Scenario: Reject ambiguous property entries
- **WHEN** a compact or JSON properties cell contains a duplicate name, a blank
  name, or an entry without a colon
- **THEN** loading fails with the workbook sheet, row, and column

#### Scenario: Round-trip system and change groups
- **WHEN** systems and changes contain multiple ordered group values
- **THEN** YAML-to-Excel-to-YAML and Excel-to-YAML-to-Excel conversion preserves
  those lists and emits no `model` worksheet

#### Scenario: Derive identical impacted-system indexes
- **WHEN** equivalent YAML and Excel changes move containment, retarget endpoints, or trigger cascades
- **THEN** roadmap-wide change and change-group system indexes and their impact reasons are identical

### Requirement: Bidirectional semantic conversion
`arch.convert(input_path, output_path)` SHALL convert YAML workspaces or complete
states to Excel and Excel workspaces or complete states to YAML. Equivalence
SHALL be evaluated after semantic normalization rather than file formatting.

#### Scenario: YAML to Excel to YAML golden round trip
- **WHEN** the canonical YAML workspace is converted to Excel and back
- **THEN** the final normalized model is semantically identical to the input

#### Scenario: Excel to YAML to Excel golden round trip
- **WHEN** the canonical Excel workspace is converted to YAML and back
- **THEN** the final normalized model is semantically identical to the input

### Requirement: Complete format-specific source locations
YAML and Excel loaders SHALL retain source locations for every normalized value
and operation. YAML issues SHALL identify file and data path/location; Excel
issues SHALL identify workbook, sheet, row, and column.

#### Scenario: Locate an invalid Excel endpoint
- **WHEN** an interface row refers to a missing provider
- **THEN** the diagnostic identifies the workbook, `interface` sheet, row,
  provider column, interface ID, and relevant change or base state

#### Scenario: Locate an invalid YAML selector
- **WHEN** a saved YAML view contains an invalid selector combination
- **THEN** the diagnostic identifies the file, view path/location, and view ID

### Requirement: Canonical examples use production conversion
The tool SHALL source paired initialization and proposal/design examples from
the same fixtures exercised through the
production loader, normalization, conversion, and validation paths.

#### Scenario: Detect example drift
- **WHEN** a documented schema example differs semantically from the canonical
  conversion fixture
- **THEN** an automated fixture or golden check fails
