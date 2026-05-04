## ADDED Requirements

### Requirement: Model-centric pipeline boundary
The `arch` tool SHALL execute architecture workflows using a strict two-stage boundary: `data -> model` and `model -> report`.

#### Scenario: Data normalized before reporting
- **WHEN** `arch.generate(...)` is called with workbook (`.xlsx` / `.xlsm`) sources
- **THEN** the tool SHALL normalize inputs into a canonical model before any report or render artifact is produced

#### Scenario: Renderers consume model context only
- **WHEN** rendering is executed for `solution` outputs
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
- **WHEN** `arch.generate(...)` is called
- **THEN** the tool SHALL resolve `tools.arch.profiles.<name>.system_engine` settings and run the configured command template with resolved render context paths
- **AND** command execution SHALL use argv execution (`shell=False`) after template rendering
- **AND** rendered command strings SHALL NOT be executed through a shell

#### Scenario: Generation is solution-only
- **WHEN** `arch.generate(...)` completes successfully
- **THEN** the structured `summary.formats` SHALL be exactly `["solution"]`

### Requirement: Strict per-surface template context contracts
The `arch` tool SHALL inject explicit context allowlists per template surface.

#### Scenario: Engine command context allowlist
- **WHEN** `system_engine` or `diagram_engine` templates are rendered
- **THEN** the context SHALL include only `input`, `output`, and `profile_data`
- **AND** legacy broad context variables (for example `paths`, `engine`, `report`, `context`) SHALL NOT be available

#### Scenario: D2 template context allowlist
- **WHEN** `system.d2.j2` is rendered
- **THEN** the context SHALL include `model` and `profile_data`
- **AND** built-in D2 presentation data SHALL be exposed under `model.system_view`

#### Scenario: Legacy top-level D2 variables rejected
- **WHEN** `system.d2.j2` references legacy top-level names (for example `title_name`)
- **THEN** rendering SHALL fail with an explicit configuration error
- **AND** the error SHALL direct template authors to use `model.system_view.*`

#### Scenario: Integration label template context allowlist
- **WHEN** `tools.arch.profiles.<name>.data.integration_labels` or `arrowhead_labels` templates are rendered
- **THEN** the context SHALL include a canonical integration row object under `row`
- **AND** legacy flat row keys at top-level SHALL NOT be available

#### Scenario: HTML report template context allowlist
- **WHEN** `system.html.j2` and `index.html.j2` are rendered
- **THEN** the context SHALL include explicit page fields, plus `model` and `profile_data`
- **AND** template rendering SHALL NOT depend on implicit top-level expansion of `profile_data`

### Requirement: Strict render-input path validation
The `arch` tool SHALL validate workbook-driven path fragments before render execution.

#### Scenario: Unsafe system identifier in output-path fragments
- **WHEN** a system identifier contains characters outside `[A-Za-z0-9._-]`
- **THEN** generation SHALL fail with a structured validation error before rendering

#### Scenario: Unsafe diagram source path fragment
- **WHEN** a workbook `diagram.file` value contains unsafe shell/metachar fragments
- **THEN** generation SHALL fail with a structured validation error before rendering

### Requirement: Strict argument and config validation
The `arch` tool SHALL enforce fail-fast validation for invalid values, removed values, and invalid configuration structure.

#### Scenario: Removed format parameter rejected
- **WHEN** `arch.generate(..., format=...)` is called
- **THEN** the call SHALL fail explicitly because `format` is not an accepted parameter

#### Scenario: Removed orchestration shape rejected
- **WHEN** removed orchestration-style config keys (for example `tools.arch.orchestration`) are supplied
- **THEN** the tool SHALL fail with an explicit configuration error

#### Scenario: Missing required template variable rejected
- **WHEN** a command template references a required variable that is absent from render context
- **THEN** the tool SHALL fail with an explicit template-variable error

#### Scenario: Conflicting profile selectors rejected
- **WHEN** `arch.generate(...)` is called with both `profile` and `profile_yaml`
- **THEN** the tool SHALL fail with an explicit configuration error

### Requirement: No backward compatibility aliases
The `arch` tool SHALL NOT accept removed parameters, removed enum values, or legacy aliases.

#### Scenario: Removed key rejected
- **WHEN** a removed config key or removed parameter is supplied
- **THEN** the tool SHALL fail explicitly and SHALL NOT remap it silently

### Requirement: Single profile-source selection for generate
`arch.generate(...)` SHALL use exactly one profile source for each run: default profile, explicit named profile, or inline profile YAML.

#### Scenario: Default profile source
- **WHEN** `arch.generate(...)` is called without `profile` and without `profile_yaml`
- **THEN** the active profile SHALL be `tools.arch.default_profile`

#### Scenario: Explicit profile source
- **WHEN** `arch.generate(..., profile=\"<name>\")` is called without `profile_yaml`
- **THEN** the active profile SHALL be `tools.arch.profiles.<name>`

#### Scenario: Inline profile YAML source
- **WHEN** `arch.generate(..., profile_yaml=\"...\")` is called without `profile`
- **THEN** the active profile SHALL be parsed from `profile_yaml` and used for that run only
- **AND** the inline profile SHALL be validated against `ArchProfileConfig`

#### Scenario: Invalid inline profile YAML
- **WHEN** `profile_yaml` is not valid YAML or does not validate as `ArchProfileConfig`
- **THEN** `arch.generate(...)` SHALL fail with an explicit configuration error

### Requirement: No-loss YAML and Excel round-trip semantics
The `arch` tool SHALL maintain semantic equivalence across canonical round-trip paths.

#### Scenario: YAML to Excel to model equivalence
- **WHEN** data is processed through `YAML -> model -> Excel -> model`
- **THEN** the resulting model semantics SHALL remain equivalent without dropping rows or extension columns

#### Scenario: Excel to YAML to model equivalence
- **WHEN** data is processed through `Excel -> model -> YAML -> model`
- **THEN** the resulting model semantics SHALL remain equivalent without meaning-changing coercions

### Requirement: Workbook diagram rendering at model boundary
Workbook `diagram` rows SHALL be resolved, validated, and rendered at the model boundary before system-page output is written.

#### Scenario: Workbook-relative diagram resolution
- **WHEN** a `diagram` row defines `file`, `name`, `sys`, and `description`
- **THEN** `arch` SHALL resolve `file` relative to the workbook that contains that row and validate that the target file exists

#### Scenario: Diagram engine rendering and page insertion
- **WHEN** `arch.generate(...)` runs with valid `diagram` rows
- **THEN** `arch` SHALL render each diagram using `tools.arch.profiles.<name>.diagram_engine`
- **AND** built-in `System` / `Application` / `Component` diagrams SHALL remain in the primary `Diagrams` section
- **AND** workbook-defined diagrams SHALL be rendered in a separate `Additional Diagrams` section with tabbed navigation and collapse/expand behavior

#### Scenario: Diagram tab groups switch independently
- **WHEN** both primary `Diagrams` and workbook-defined `Additional Diagrams` sections are present on a system page
- **THEN** tab changes in one section SHALL only show/hide panels in that same section
- **AND** tab changes in one section SHALL NOT hide panels from the other section

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

### Requirement: Template-driven integration labels and key-based numbering
The `arch` tool SHALL drive integration table numbering and diagram integration labels from model row fields, using template-configurable profile options.

#### Scenario: Integration table numbering uses key field
- **WHEN** solution HTML integration tables are generated
- **THEN** the `#` column SHALL be sourced from each integration row `key` field

#### Scenario: Integration edge label template
- **WHEN** `tools.arch.profiles.<name>.data.show_integration_labels` is `true`
- **AND** `tools.arch.profiles.<name>.data.integration_labels` is set to a Jinja template string
- **THEN** each integration edge label SHALL be rendered from that template using `row` fields (for example `row.key`, `row.name`, `row.id`, `row.src`, `row.dst`, `row.type`)

#### Scenario: Integration edge label disabled
- **WHEN** `tools.arch.profiles.<name>.data.show_integration_labels` is `false`
- **THEN** integration edge labels SHALL be omitted

#### Scenario: Arrowhead label template
- **WHEN** `tools.arch.profiles.<name>.data.show_arrowhead_labels` is `true`
- **AND** `tools.arch.profiles.<name>.data.arrowhead_labels` is set to a Jinja template string
- **THEN** source and target arrowhead labels SHALL be rendered from that template using `row` fields

#### Scenario: Arrowhead label disabled
- **WHEN** `tools.arch.profiles.<name>.data.show_arrowhead_labels` is `false`
- **THEN** source and target arrowhead labels SHALL be omitted
