# tool-arch-model-centric-rendering Specification

## Purpose

Defines the model-centric architecture rendering contract for the `arch` tool.

## Requirements

### Requirement: Model-centric pipeline boundary
The `arch` tool SHALL execute architecture workflows using a strict two-stage boundary: `data -> model` and `model -> report`.

#### Scenario: Data normalized before reporting
- **WHEN** `arch.generate(...)` is called with workbook (`.xlsx` / `.xlsm`) or YAML (`.yaml` / `.yml`) sources
- **THEN** the tool SHALL normalize inputs into a canonical model before any report or render artifact is produced

### Requirement: Input format parity
The `arch` tool SHALL accept either an Excel workbook or a YAML model file as input to its `validate` and `generate` operations, normalized through the same canonical model path.

#### Scenario: YAML input to validate and generate
- **WHEN** `arch.validate(...)` or `arch.generate(...)` receives a `.yaml`/`.yml` model file as `input_path`
- **THEN** the tool SHALL ingest it through the canonical model path used for workbooks
- **AND** validation errors SHALL be reported the same way as for workbook input

#### Scenario: Renderers consume model context only
- **WHEN** rendering is executed for solution, system diagram, project diagram, or workbook-defined diagram targets
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

#### Scenario: Workbook-defined diagram target orchestration
- **WHEN** workbook-defined diagrams are provided through the `diagram` sheet
- **THEN** the tool SHALL resolve `tools.arch.profiles.<name>.diagram_engine` settings and run the configured command template for each diagram source

### Requirement: Strict argument and config validation
The `arch` tool SHALL enforce fail-fast validation for invalid values, unsupported values, and invalid configuration structure.

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
The `arch` tool SHALL maintain semantic equivalence across canonical round-trip paths and SHALL fail explicitly instead of silently dropping data.

#### Scenario: YAML to Excel to model equivalence
- **WHEN** data is processed through `YAML -> model -> Excel -> model`
- **THEN** the resulting model semantics SHALL remain equivalent without dropping rows or extension columns

#### Scenario: Excel to YAML to model equivalence
- **WHEN** data is processed through `Excel -> model -> YAML -> model`
- **THEN** the resulting model semantics SHALL remain equivalent without meaning-changing coercions

#### Scenario: Unknown YAML section rejected
- **WHEN** YAML input contains a top-level section that is not a known sheet name or alias
- **THEN** loading SHALL fail with an explicit error naming the unknown section

#### Scenario: Template import without matching columns rejected
- **WHEN** `arch.import_yaml(...)` receives row fields for which the template workbook sheet has no column (directly or via field aliases)
- **THEN** the import SHALL fail with an explicit error listing the unmapped fields

#### Scenario: Template import without matching sheet rejected
- **WHEN** `arch.import_yaml(...)` receives rows for an entity sheet that the template workbook does not contain
- **THEN** the import SHALL fail with an explicit error naming the missing sheet instead of silently dropping the rows

#### Scenario: Colliding workbook headers rejected
- **WHEN** a workbook sheet has two columns that normalize to the same header key
- **THEN** ingestion SHALL fail with an explicit error naming the colliding headers

#### Scenario: List-valued fields round-trip
- **WHEN** a field holds a list of values
- **THEN** the canonical model SHALL store it as a real list
- **AND** YAML SHALL represent it as a native list
- **AND** an Excel cell SHALL encode it as bracketed text using the configured `tools.arch.list_cell_separator` (default `;`), e.g. `[core;internal]`
- **AND** an Excel cell whose trimmed text is bracketed SHALL parse back into a list on ingest, while an unbracketed cell SHALL remain a scalar string

#### Scenario: Non-canonical sheets round-trip
- **WHEN** a workbook contains a sheet whose name is not a canonical entity or alias
- **THEN** it SHALL be preserved verbatim (headers and rows) through `Excel -> YAML -> Excel`
- **AND** it SHALL be carried in YAML under the reserved `_passthrough` key rather than as an unknown top-level section
- **AND** it SHALL NOT be validated or added to the canonical model

### Requirement: Entity reference integrity
Entity rows SHALL reference resolvable parents, and node identifiers SHALL be unique across node sheets.

#### Scenario: Component parent reference
- **WHEN** a component row is validated
- **THEN** it SHALL reference an existing application or, when no application is referenced, an existing system directly
- **AND** a component referencing neither SHALL fail validation

#### Scenario: Direct system components render
- **WHEN** a component references a system directly and Component View is rendered
- **THEN** the component SHALL render inside the owning system block
- **AND** interface endpoints resolving to that component SHALL connect to its rendered node

#### Scenario: Cross-sheet unique node ids
- **WHEN** the same id appears in more than one of the `sys`, `app`, `cmp`, or `usr` sheets
- **THEN** validation SHALL fail with a duplicate-id error naming the sheets

### Requirement: Workbook-defined diagrams at model boundary
Workbook-defined diagram rows from separate files/workbooks SHALL be joined and validated at the model boundary before rendering.

#### Scenario: Separate diagram source join
- **WHEN** diagram rows are provided separately from core entity sources
- **THEN** `arch` SHALL resolve and validate cross-references during model assembly before diagram rendering

### Requirement: Interface key field in solution context
Solution output context SHALL expose interface row identifiers through a `key` field.

#### Scenario: Interfaces table key column
- **WHEN** solution context is generated for interfaces
- **THEN** each interface entry SHALL expose the row key as `key`
- **AND** the interfaces table column SHALL use field `key`

### Requirement: Interface contract
Interface rows SHALL model interface contracts using provider and consumer endpoints.

#### Scenario: Provider and consumer are required
- **WHEN** an interface row is validated
- **THEN** it SHALL require `provider` and `consumer` endpoint fields
- **AND** unsupported endpoint aliases SHALL NOT be remapped silently

#### Scenario: Interaction type is extensible
- **WHEN** an interface row defines `interaction_type`
- **THEN** the value SHALL be preserved in model, diagram label, and solution table contexts
- **AND** user-defined non-empty values SHALL be valid

#### Scenario: Arrow direction is explicit
- **WHEN** `arrow_direction` is omitted
- **THEN** the diagram edge SHALL point from consumer to provider
- **WHEN** `arrow_direction` is `provider_to_consumer`
- **THEN** the diagram edge SHALL point from provider to consumer
- **WHEN** `arrow_direction` is `none`
- **THEN** the diagram edge SHALL have no arrowhead
- **WHEN** `arrow_direction` is `bidirectional`
- **THEN** the diagram edge SHALL be bidirectional
- **AND** `none` and `bidirectional` edges SHALL use neutral edge styling rather than focus-direction styling
- **AND** invalid arrow direction values SHALL fail validation

### Requirement: Interface canonical entity names and aliases
The canonical model entity for interface contracts SHALL be `interface`, with explicit short-form aliases for authoring.

#### Scenario: Workbook sheet aliases
- **WHEN** a workbook contains `interface` or `int` sheet names
- **THEN** the rows SHALL load into canonical `interface` model entities
- **AND** a workbook containing both aliases for the same canonical sheet SHALL fail explicitly

#### Scenario: YAML section aliases
- **WHEN** YAML contains `interface` or `int` sections
- **THEN** the rows SHALL load into canonical `interface` model entities
- **AND** YAML containing both aliases for the same canonical section SHALL fail explicitly

#### Scenario: Core entity long aliases
- **WHEN** workbook sheets or YAML sections use `system`, `application`, `component`, or `components`
- **THEN** the rows SHALL load into canonical `sys`, `app`, and `cmp` model entities

### Requirement: Project cross-system views
The solution output SHALL support project pages generated from `project` and `project_scope` model entities.

#### Scenario: Project entity validation
- **WHEN** project rows are validated
- **THEN** `id` and `name` SHALL be required
- **AND** `detail_level` SHALL allow `sys`, `app`, or `cmp`
- **AND** `connect_level` SHALL allow `sys`, `app`, `cmp`, or `lowest_visible`

#### Scenario: Project scope validation
- **WHEN** project scope rows are validated
- **THEN** `project`, `stage`, `item_type`, `item_id`, and `change_type` SHALL be required
- **AND** `project` SHALL reference an existing project
- **AND** `item_id` SHALL reference an existing entity compatible with `item_type`
- **AND** `change_type` SHALL allow `existing`, `new`, `changed`, `removed`, `impacted`, or `dependency`

#### Scenario: Project index navigation
- **WHEN** solution output is generated with project rows
- **THEN** the solution index SHALL include project navigation entries
- **AND** each project SHALL have its own HTML page

#### Scenario: Project stage diagrams
- **WHEN** a project has scoped rows across stages
- **THEN** its page SHALL show one diagram per first-seen `project_scope.stage`
- **AND** project diagrams SHALL have no primary system
- **AND** `project.detail_level` and `project.connect_level` SHALL apply to all included systems and interface endpoints

#### Scenario: Project extension fields
- **WHEN** project or project scope rows contain extension columns
- **THEN** those fields SHALL be preserved in YAML/model output
- **AND** generated project pages SHALL expose those fields in metadata or scope table contexts

### Requirement: Secondary system diagram detail
System diagrams SHALL allow profiles to control how secondary systems are rendered without changing the focused primary system detail level.

#### Scenario: Secondary system detail option
- **WHEN** `tools.arch.profiles.<name>.data.secondary_system_detail` is omitted
- **THEN** secondary systems SHALL render at `sys` detail
- **AND** the focused primary system SHALL continue to render at the current diagram detail (`sys`, `app`, or `cmp`)

#### Scenario: Secondary systems match primary detail
- **WHEN** `tools.arch.profiles.<name>.data.secondary_system_detail` is `match_primary`
- **THEN** secondary systems SHALL render at the current diagram detail (`sys` in System View, `app` in Application View, `cmp` in Component View)

#### Scenario: Secondary system endpoint connection level
- **WHEN** `tools.arch.profiles.<name>.data.secondary_system_connect_level` is omitted
- **THEN** secondary-system interface endpoints SHALL connect at `app` level when the interface endpoint resolves to an app or component and the app node is visible
- **AND** endpoints SHALL fall back to system level when the interface row does not contain enough detail or the referenced node is not visible

#### Scenario: Secondary connect level does not affect primary endpoints
- **WHEN** `secondary_system_connect_level` is configured
- **THEN** the option SHALL apply only to secondary-system interface endpoints
- **AND** primary-system endpoints SHALL continue to resolve from the current primary diagram detail and the interface endpoint IDs

### Requirement: Profile data default alignment
Code fallback defaults for profile data options SHALL equal the bundled `arch.yaml` profile values, so custom profiles behave like the shipped one when options are omitted.

#### Scenario: Custom profile inherits documented defaults
- **WHEN** a custom profile omits a documented `tools.arch.profiles.<name>.data` option
- **THEN** generation SHALL use the same value the bundled default profile ships with

### Requirement: Regenerated solution output
`arch.generate` SHALL fully own the solution output directory and SHALL update it
incrementally: output files are rewritten only when their content changes, diagram renders
are skipped when their inputs are unchanged, stale files are removed after a successful run,
and `force=True` restores full regeneration. Existing outputs SHALL NOT be bulk-deleted
before new outputs are produced.

#### Scenario: Stale outputs removed
- **WHEN** generation completes successfully into a solution directory containing files from
  a previous run that are not part of the current model's output set
- **THEN** those stale files SHALL be removed so the directory reflects only the current model

#### Scenario: Unchanged diagram render reused
- **WHEN** generation runs and a system or project diagram's generated `.d2` source is
  identical to the file from the previous run, its `.svg` output exists, and the svg's
  embedded draw.io state matches the run's `drawio_export` setting
- **THEN** the render engine SHALL NOT be re-invoked for that diagram
- **AND** the existing `.svg` SHALL be reused in the generated report pages

#### Scenario: Changed diagram re-rendered
- **WHEN** generation runs after a model change that alters a diagram's generated `.d2` source
- **THEN** that diagram SHALL be re-rendered through the configured engine and its outputs
  rewritten

#### Scenario: Forced full regeneration
- **WHEN** `arch.generate(..., force=True)` is called
- **THEN** every output file SHALL be rewritten and every diagram SHALL be re-rendered,
  regardless of unchanged inputs

#### Scenario: Render reuse reported
- **WHEN** generation completes successfully
- **THEN** the result `summary.renders` SHALL report the number of executed and skipped
  engine renders

#### Scenario: No destructive pre-clean on failure
- **WHEN** generation fails partway through a run
- **THEN** outputs from the previous successful run SHALL NOT have been bulk-deleted at the
  start of the failed run

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

#### Scenario: Engine command timeout
- **WHEN** engine command execution exceeds the render timeout
- **THEN** the command SHALL be terminated instead of blocking the tool call indefinitely
- **AND** the result SHALL include a timeout error code with the timeout duration in structured error details
