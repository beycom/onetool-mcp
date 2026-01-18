# tool-diagram Specification

## Purpose
TBD - created by archiving change add-diagram-tool. Update Purpose after archive.
## Requirements
### Requirement: Generate Source

The `diagram.generate_source()` function SHALL create diagram source code and save to file.

#### Scenario: Basic source generation
- **GIVEN** diagram source code
- **WHEN** `diagram.generate_source(source="graph TD; A-->B", provider="mermaid")` is called
- **THEN** it SHALL save the source to a file with appropriate extension
- **AND** it SHALL return the source file path and playground URL

#### Scenario: Explicit output file
- **GIVEN** an output_file parameter
- **WHEN** `diagram.generate_source(source="...", provider="mermaid", output_file="docs/diagrams/flow.mmd")` is called
- **THEN** it SHALL save to the specified path
- **AND** parent directories SHALL be created if needed

#### Scenario: Source from file
- **GIVEN** source_type="file" and a file path
- **WHEN** `diagram.generate_source(source="path/to/diagram.mmd", provider="mermaid", source_type="file")` is called
- **THEN** it SHALL read source from the file
- **AND** it SHALL validate basic syntax for the provider

#### Scenario: Auto-naming
- **GIVEN** no output_file specified
- **WHEN** `diagram.generate_source(source="...", provider="mermaid")` is called
- **THEN** it SHALL generate filename using output.naming pattern from config
- **AND** file SHALL be saved to output.dir from config

#### Scenario: Playground URL generation
- **GIVEN** a supported provider (mermaid, plantuml, d2)
- **WHEN** source is generated
- **THEN** response SHALL include playground_url for interactive editing

### Requirement: Render Diagram

The `diagram.render_diagram()` function SHALL render source to image via Kroki.

#### Scenario: Basic render
- **GIVEN** diagram source code
- **WHEN** `diagram.render_diagram(source="graph TD; A-->B", provider="mermaid")` is called
- **THEN** it SHALL POST source to Kroki API
- **AND** it SHALL save rendered image to file
- **AND** it SHALL return output file path

#### Scenario: Render from file
- **GIVEN** source_type="file"
- **WHEN** `diagram.render_diagram(source="diagram.mmd", provider="mermaid", source_type="file")` is called
- **THEN** it SHALL read source from file
- **AND** it SHALL render via Kroki

#### Scenario: Output format selection
- **GIVEN** output_format parameter
- **WHEN** `diagram.render_diagram(source="...", provider="mermaid", output_format="png")` is called
- **THEN** it SHALL render to PNG format
- **AND** default format SHALL be "svg"

#### Scenario: Synchronous render (default)
- **GIVEN** wait=True (default)
- **WHEN** `diagram.render_diagram(source="...", provider="mermaid")` is called
- **THEN** it SHALL wait for rendering to complete
- **AND** it SHALL return output_file path

#### Scenario: Asynchronous render
- **GIVEN** wait=False
- **WHEN** `diagram.render_diagram(source="...", provider="mermaid", wait=False)` is called
- **THEN** it SHALL return immediately with task_id
- **AND** status SHALL be "pending"

#### Scenario: Kroki error handling
- **GIVEN** invalid diagram source
- **WHEN** Kroki returns an error
- **THEN** it SHALL return error message from Kroki
- **AND** it SHALL include playground URL for debugging

### Requirement: Batch Render (Self-Hosted Only)

The `diagram.batch_render()` function SHALL render multiple diagrams concurrently.

#### Scenario: Batch with list of sources
- **GIVEN** self-hosted Kroki is configured
- **WHEN** `diagram.batch_render(sources=[{source, provider}, ...])` is called
- **THEN** it SHALL render all sources concurrently
- **AND** it SHALL return task_id for progress tracking

#### Scenario: Remote backend restriction
- **GIVEN** remote Kroki (kroki.io) is configured
- **WHEN** `diagram.batch_render()` is called
- **THEN** it SHALL return "Error: batch_render requires self-hosted Kroki"

#### Scenario: Concurrency control
- **GIVEN** concurrency parameter
- **WHEN** `diagram.batch_render(sources=[...], concurrency=5)` is called
- **THEN** it SHALL limit concurrent requests to 5
- **AND** default concurrency SHALL be 10

### Requirement: Render Directory (Self-Hosted Only)

The `diagram.render_directory()` function SHALL render all diagram sources in a directory.

#### Scenario: Basic directory render
- **GIVEN** a directory with diagram source files
- **WHEN** `diagram.render_directory(directory="docs/diagrams")` is called
- **THEN** it SHALL discover all source files by extension
- **AND** it SHALL render each to the same directory

#### Scenario: Recursive discovery
- **GIVEN** recursive=True
- **WHEN** `diagram.render_directory(directory="docs", recursive=True)` is called
- **THEN** it SHALL discover files in subdirectories

#### Scenario: Pattern filtering
- **GIVEN** pattern parameter
- **WHEN** `diagram.render_directory(directory="...", pattern="*.mmd")` is called
- **THEN** it SHALL only render files matching the pattern
- **AND** default pattern SHALL be "*.mmd,*.puml,*.d2"

#### Scenario: Remote backend restriction
- **GIVEN** remote Kroki is configured
- **WHEN** `diagram.render_directory()` is called
- **THEN** it SHALL return "Error: render_directory requires self-hosted Kroki"

### Requirement: Get Render Status

The `diagram.get_render_status()` function SHALL report async render progress.

#### Scenario: Running task
- **GIVEN** an active batch render task
- **WHEN** `diagram.get_render_status(task_id="batch-xyz")` is called
- **THEN** it SHALL return status, total, completed, and failed counts

#### Scenario: Completed task
- **GIVEN** a completed batch render
- **WHEN** `diagram.get_render_status(task_id="batch-xyz")` is called
- **THEN** status SHALL be "completed"
- **AND** results SHALL include output file paths

#### Scenario: Unknown task
- **GIVEN** an invalid task_id
- **WHEN** `diagram.get_render_status(task_id="invalid")` is called
- **THEN** it SHALL return "Error: Unknown task ID"

### Requirement: Get Diagram Policy

The `diagram.get_diagram_policy()` function SHALL return diagram usage policy.

#### Scenario: Policy retrieval
- **WHEN** `diagram.get_diagram_policy()` is called
- **THEN** it SHALL return policy rules, preferred_format, preferred_types, and when_to_diagram from config

#### Scenario: Anti-patterns included
- **WHEN** `diagram.get_diagram_policy()` is called
- **THEN** response SHALL include anti_patterns guidance
- **AND** anti_patterns SHALL list common mistakes to avoid (too many nodes, crossing lines, missing legends, inconsistent naming, outdated diagrams, ASCII art fallback)

### Requirement: Get Diagram Instructions

The `diagram.get_diagram_instructions()` function SHALL return provider-specific guidance.

#### Scenario: Provider instructions
- **GIVEN** a supported provider
- **WHEN** `diagram.get_diagram_instructions(provider="mermaid")` is called
- **THEN** it SHALL return when_to_use, style_tips, syntax_guide, and example

#### Scenario: Quoting rules included
- **GIVEN** a focus provider (mermaid, plantuml, d2)
- **WHEN** `diagram.get_diagram_instructions(provider="mermaid")` is called
- **THEN** style_tips SHALL include provider-specific quoting rules
- **AND** rules SHALL explain when to use quotes vs not use quotes

#### Scenario: General instructions
- **GIVEN** no provider specified
- **WHEN** `diagram.get_diagram_instructions()` is called
- **THEN** it SHALL return general diagram guidance
- **AND** it SHALL list available providers

#### Scenario: Provider support matrix
- **GIVEN** no provider specified
- **WHEN** `diagram.get_diagram_instructions()` is called
- **THEN** response SHALL include support_matrix showing which providers support which diagram types (sequence, flowchart, c4, class, state, gantt, mindmap)

#### Scenario: Unknown provider
- **GIVEN** an unknown provider
- **WHEN** `diagram.get_diagram_instructions(provider="unknown")` is called
- **THEN** it SHALL return "No custom instructions for 'unknown'. Refer to Kroki documentation."

### Requirement: Get Output Config

The `diagram.get_output_config()` function SHALL return output configuration.

#### Scenario: Output config retrieval
- **WHEN** `diagram.get_output_config()` is called
- **THEN** it SHALL return output_dir, naming_pattern, default_format, and save_source settings

#### Scenario: Default output directory value
- **GIVEN** no custom config
- **WHEN** `diagram.get_output_config()` is called
- **THEN** output_dir SHALL default to `"diagrams"` (not `"../diagrams"`)

### Requirement: Get Template

The `diagram.get_template()` function SHALL return diagram starter templates.

#### Scenario: Template by name
- **GIVEN** a template name
- **WHEN** `diagram.get_template(name="api-flow")` is called
- **THEN** it SHALL return provider, diagram_type, description, and source content

#### Scenario: Unknown template
- **GIVEN** an unknown template name
- **WHEN** `diagram.get_template(name="unknown")` is called
- **THEN** it SHALL return "Template 'unknown' not found"
- **AND** it SHALL list available templates

### Requirement: List Providers

The `diagram.list_providers()` function SHALL return available Kroki providers.

#### Scenario: Provider listing
- **WHEN** `diagram.list_providers()` is called
- **THEN** it SHALL return all Kroki-supported providers
- **AND** each provider SHALL include supported formats and description

### Requirement: Backend Configuration

The diagram tool SHALL support remote and self-hosted Kroki backends.

#### Scenario: Remote backend (default)
- **GIVEN** backend.prefer="remote"
- **WHEN** diagrams are rendered
- **THEN** it SHALL use kroki.io API
- **AND** batch operations SHALL be disabled

#### Scenario: Self-hosted backend
- **GIVEN** backend.prefer="self_hosted" and self_hosted_url configured
- **WHEN** diagrams are rendered
- **THEN** it SHALL use the self-hosted URL
- **AND** batch operations SHALL be enabled

#### Scenario: Auto backend selection
- **GIVEN** backend.prefer="auto"
- **WHEN** diagrams are rendered
- **THEN** it SHALL try self-hosted first
- **AND** it SHALL fall back to remote if unavailable

#### Scenario: Health check
- **GIVEN** a configured backend
- **WHEN** tool initialises
- **THEN** it SHALL verify Kroki is reachable
- **AND** it SHALL log backend status

### Requirement: Diagram Logging

The diagram tool SHALL log all operations using LogSpan.

#### Scenario: Generate logging
- **GIVEN** a generate operation
- **WHEN** the operation completes
- **THEN** it SHALL log:
  - `span: "diagram.generate_source"`
  - `provider`: Diagram provider
  - `outputFile`: Generated file path

#### Scenario: Render logging
- **GIVEN** a render operation
- **WHEN** the operation completes
- **THEN** it SHALL log:
  - `span: "diagram.render"`
  - `provider`: Diagram provider
  - `format`: Output format
  - `backend`: "remote" or "self_hosted"
  - `durationMs`: Render time

#### Scenario: Batch logging
- **GIVEN** a batch render operation
- **WHEN** the operation completes
- **THEN** it SHALL log:
  - `span: "diagram.batch"`
  - `total`: Total diagrams
  - `successCount`: Successful renders
  - `failCount`: Failed renders

### Requirement: Project-Relative Output Path Resolution

The diagram tool SHALL resolve output paths relative to the project working directory.

#### Scenario: Default output directory
- **GIVEN** no explicit output_dir specified
- **AND** config `tools.diagram.output.dir` is `"diagrams"` (default)
- **WHEN** a diagram is generated or rendered
- **THEN** output SHALL be saved to `{project_path}/diagrams/`

#### Scenario: Relative output directory
- **GIVEN** output_dir is `"docs/diagrams"`
- **WHEN** a diagram is generated or rendered
- **THEN** output SHALL be saved to `{project_path}/docs/diagrams/`

#### Scenario: Absolute output directory
- **GIVEN** output_dir is `/tmp/diagrams`
- **WHEN** a diagram is generated or rendered
- **THEN** output SHALL be saved to `/tmp/diagrams/` (unchanged)

### Requirement: Config-Relative Template Path Resolution

The diagram tool SHALL resolve template file paths relative to the config directory.

#### Scenario: Relative template file
- **GIVEN** template config `templates.flow.file` is `"templates/flow.mmd"`
- **WHEN** `diagram.get_template(name="flow")` is called
- **THEN** it SHALL load from `{config_dir}/templates/flow.mmd`

#### Scenario: Absolute template file
- **GIVEN** template config `templates.flow.file` is `/etc/templates/flow.mmd`
- **WHEN** `diagram.get_template(name="flow")` is called
- **THEN** it SHALL load from `/etc/templates/flow.mmd` (unchanged)

