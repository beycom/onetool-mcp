# tool-arch-validation-warnings Specification

## Purpose

Defines the non-blocking validation warnings channel for the `arch` tool: which
data-quality conditions produce warnings (`orphan_system`, `duplicate_name`,
`self_interface`), their payload shape, and the guarantee that warnings never
affect validity or block generation.

## Requirements

### Requirement: Non-blocking validation warnings
`arch.validate` and `arch.generate` SHALL report non-blocking data-quality findings in the
`issues.warnings` channel of their structured payloads. Each warning SHALL carry the same
shape as validation errors: a machine-readable `code`, a human-readable `message`, and
structured `details` (including `sheet` and `row`/`id` where applicable).
`summary.warnings` SHALL equal the number of warnings. Warnings SHALL NOT affect `valid`
and SHALL NOT block generation.

#### Scenario: Warnings do not block validation or generation
- **WHEN** input entities produce warnings but no errors
- **THEN** `arch.validate` SHALL return `ok=true` and `valid=true` with the warnings listed
  in `issues.warnings`
- **AND** `arch.generate` SHALL proceed to produce outputs

#### Scenario: Warning count in summary
- **WHEN** validation produces N warnings
- **THEN** `summary.warnings` SHALL equal N

#### Scenario: Warnings alongside errors
- **WHEN** input entities produce both errors and warnings
- **THEN** the payload SHALL report `valid=false` with errors in `issues.errors` and the
  warnings still listed in `issues.warnings`

### Requirement: Orphan system warning
Validation SHALL emit an `orphan_system` warning for each `sys` row whose id is referenced
by no interface endpoint (neither directly nor through one of its owned applications or
components) and by no project scope row.

#### Scenario: Disconnected system flagged
- **WHEN** a system has no interface where it (or any of its apps/components) is provider or
  consumer, and appears in no project scope
- **THEN** validation SHALL emit a warning with code `orphan_system` identifying the system id

#### Scenario: Connected system not flagged
- **WHEN** a system's owned application is the provider or consumer of an interface
- **THEN** no `orphan_system` warning SHALL be emitted for that system

### Requirement: Duplicate display name warning
Validation SHALL emit a `duplicate_name` warning when two or more rows within the same node
sheet (`sys`, `app`, `cmp`, or `usr`) share the same case-insensitive, whitespace-trimmed
`name` under distinct ids.

#### Scenario: Same name in one sheet flagged
- **WHEN** two `app` rows with different ids both have name "Billing" (any casing)
- **THEN** validation SHALL emit a warning with code `duplicate_name` listing the sheet,
  name, and colliding ids

#### Scenario: Same name across different sheets not flagged
- **WHEN** a `sys` row and an `app` row share the same name
- **THEN** no `duplicate_name` warning SHALL be emitted

### Requirement: Self-referencing interface warning
Validation SHALL emit a `self_interface` warning for each `interface` row whose provider and
consumer resolve to the same id.

#### Scenario: Self-loop flagged
- **WHEN** an interface row has `provider` equal to `consumer`
- **THEN** validation SHALL emit a warning with code `self_interface` identifying the
  interface row
