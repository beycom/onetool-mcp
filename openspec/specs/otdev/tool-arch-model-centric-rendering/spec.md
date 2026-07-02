# tool-arch-model-centric-rendering Specification

## Purpose

Defines the model-centric architecture rendering contract for the `arch` tool.

## Requirements

### Requirement: Model-centric pipeline boundary
The `arch` tool SHALL execute architecture workflows using a strict two-stage boundary: `data -> model` and `model -> report`.

#### Scenario: Data normalized before reporting
- **WHEN** `arch.generate(...)` is called with workbook (`.xlsx` / `.xlsm`) sources
- **THEN** the tool SHALL normalize inputs into a canonical model before any report or render artifact is produced

#### Scenario: Renderers consume model context only
- **WHEN** rendering is executed for `solution` or `seq` targets
- **THEN** renderer/template execution SHALL use model-derived render context and SHALL NOT parse source YAML/Excel directly

### Requirement: Canonical model metadata contract
The canonical model payload SHALL include explicit model version metadata and preserve extension fields used for round-trip compatibility.

#### Scenario: Required model version
- **WHEN** a model payload is emitted or persisted by `arch`
- **THEN** `model.version` SHALL be present

#### Scenario: Extension field preservation
- **WHEN** source rows contain non-core extension columns
- **THEN** those fields SHALL be preserved through model conversion and round-trip operations

### Requirement: Delegated rendering orchestration
The `arch` tool SHALL resolve render target/profile/engine/template configuration and execute configured engine command templates.

#### Scenario: Solution target orchestration
- **WHEN** generation is requested for `solution`
- **THEN** the tool SHALL resolve `tools.arch.profiles.<name>.system_engine` settings and run the configured command template with resolved render context paths

#### Scenario: Sequence target orchestration
- **WHEN** generation is requested for `seq`
- **THEN** the tool SHALL resolve `tools.arch.profiles.<name>.sequence_engine` settings and run the configured command template for sequence output

### Requirement: Strict argument and config validation
The `arch` tool SHALL enforce fail-fast validation for invalid values, unsupported values, and invalid configuration structure.

#### Scenario: Unsupported format rejected
- **WHEN** `arch.generate(...)` is called with an unsupported `format` value
- **THEN** the tool SHALL fail with an explicit invalid-format error

#### Scenario: Unsupported orchestration shape rejected
- **WHEN** unsupported orchestration-style config keys are supplied
- **THEN** the tool SHALL fail with an explicit configuration error

#### Scenario: Missing required template variable rejected
- **WHEN** a command template references a required variable that is absent from render context
- **THEN** the tool SHALL fail with an explicit template-variable error

### Requirement: Current API only
The `arch` tool SHALL NOT accept unsupported parameters, unsupported enum values, or alias parameters outside the current public API.

#### Scenario: Unsupported key rejected
- **WHEN** an unsupported config key or parameter is supplied
- **THEN** the tool SHALL fail explicitly and SHALL NOT remap it silently

### Requirement: No-loss YAML and Excel round-trip semantics
The `arch` tool SHALL maintain semantic equivalence across canonical round-trip paths.

#### Scenario: YAML to Excel to model equivalence
- **WHEN** data is processed through `YAML -> model -> Excel -> model`
- **THEN** the resulting model semantics SHALL remain equivalent without dropping rows or extension columns

#### Scenario: Excel to YAML to model equivalence
- **WHEN** data is processed through `Excel -> model -> YAML -> model`
- **THEN** the resulting model semantics SHALL remain equivalent without meaning-changing coercions

### Requirement: Sequence integration at model boundary
Sequence entities from separate files/workbooks SHALL be joined and validated at the model boundary before sequence rendering.

#### Scenario: Separate sequence source join
- **WHEN** sequence entities are provided separately from core entity sources
- **THEN** `arch` SHALL resolve and validate cross-references during model assembly before `seq` rendering

### Requirement: Integration key field in solution context
Solution output context SHALL expose integration row identifiers through a `key` field.

#### Scenario: Integrations table key column
- **WHEN** solution context is generated for integrations
- **THEN** each integration entry SHALL expose the row key as `key`
- **AND** the integrations table column SHALL use field `key`

### Requirement: Structured operation results and errors
The `arch` tool SHALL return stable structured payloads for success and failure across validate, generate, round-trip, and bundling operations.

#### Scenario: Structured success payload
- **WHEN** an `arch` operation completes successfully
- **THEN** the result SHALL include operation status and produced artifact summary fields

#### Scenario: Structured failure payload
- **WHEN** an `arch` operation fails
- **THEN** the result SHALL include machine-readable error code, human-readable message, and structured details

### Requirement: Engine execution failure reporting
The `arch` tool SHALL return explicit execution diagnostics when delegated engine commands fail.

#### Scenario: Engine command failure
- **WHEN** engine command execution exits non-zero
- **THEN** the result SHALL include exit diagnostics with stderr/stdout context in structured error details
