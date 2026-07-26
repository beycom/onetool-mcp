# Arch

Architecture workflows for Excel ingestion, validation, generation, round-trip conversion, and solution bundling.

## Highlights

- Accepts either an Excel workbook (`.xlsx`/`.xlsm`, one file/directory/glob) or a single YAML model file (`.yaml`/`.yml`) as input to `validate` and `generate`
- Ingests `sys`, `app`, `cmp`, `interface`, `usr`, `project`, and `project_scope` sheets/sections
- Accepts explicit short/long aliases for entity sheets: `sys`/`system`, `app`/`application`, `cmp`/`component`/`components`, `interface`/`int`, `usr`/`user`/`users`, `project_scope`/`project_scopes`, and `diagram`/`diagrams`; reference columns likewise accept aliases (for example `sys`/`system`/`system_id`/`sys_id`, `app`/`application`/`app_id`/`application_id`)
- Round-trips list-valued fields losslessly: native lists in YAML, bracketed text in Excel cells (`[core;internal]`, separator configurable via `list_cell_separator`)
- Round-trips non-canonical worksheets verbatim (preserved under the reserved `_passthrough` YAML key)
- Optionally ingests a `diagram` sheet (`file`, `name`, `sys`, `description`) for workbook-defined extra diagrams
- Validates required fields, duplicates (including ids duplicated across `sys`/`app`/`cmp`/`usr` sheets), and reference integrity with structured issue payloads
- Components reference an owning application (`app`), or a system directly (`sys`) for system-level components
- `arch.generate` produces solution outputs only (always HTML single-file)
- Solution HTML includes rich AG Grid tables and embedded SVG diagrams
- Solution HTML lists project pages when `project` and `project_scope` rows are present
- Delegates rendering to configured engine command templates for system diagrams and workbook-defined diagrams
- Diagram sheet `file` values resolve relative to the workbook containing that row; rendered SVGs are shown in a separate `Additional Diagrams` tabbed/collapsible section on the mapped system page
- Emits canonical model payloads with `model.version` and model-derived render context
- Supports Excel-to-YAML and YAML-to-Excel round-trip flows plus distributable solution ZIP bundles
- Project stage diagrams and scope tables visualize `project_scope.change_type` with dedicated colors per value
- System and project diagram edges express recognized `interaction_type` values as distinct stroke patterns, independent of focus-direction coloring
- Diagram nodes (systems, apps, components) carry D2 `link` attributes so generated SVGs navigate to the owning system's page on click
- Every system and project page links back to the solution index; system pages list the projects that scope them; scope-table items link to their owning system page
- System and project pages include a collapsible legend describing node classes, edge direction colors, interaction-type patterns, and (project pages) change-type styles
- The solution index shows aggregate summary cards and five searchable global entity tables (systems, applications, components, interfaces, projects)
- Every generated system and project diagram SVG doubles as an editable draw.io file (an embedded `mxfile` model laid out exactly as rendered); report pages offer an "Export to draw.io" download button per diagram, controlled by the `drawio_export` profile toggle (default on)

## Functions

| Function | Description |
|----------|-------------|
| `arch.validate(input_path)` | Validate workbook entities and return structured issues/summary |
| `arch.generate(input_path, ...)` | Generate solution outputs from workbook input |
| `arch.export_yaml(input_path, output_path)` | Export entity sheets to YAML |
| `arch.import_yaml(input_path, template_path, output_path)` | Import YAML entity data into a workbook template and revalidate |
| `arch.bundle_solution(directory, ...)` | Inline SVG references in solution HTML and build ZIP bundle |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `input_path` | str | Excel workbook (file, directory, or glob for `.xlsx`/`.xlsm`) or a single YAML model file (`.yaml`/`.yml`) |
| `output_dir` | str | Output root directory for generated files |
| `profile` | str | Optional profile name override for `arch.generate` |
| `profile_yaml` | str | Optional inline YAML profile block for `arch.generate` (mutually exclusive with `profile`) |
| `title` | str | Optional title for the generated solution index page |
| `output_path` | str | Output file path for `export_yaml` / `import_yaml`, or optional ZIP target for `bundle_solution` |
| `include_tags` | list[str] | Keep only entities matching included tags |
| `exclude_tags` | list[str] | Omit entities matching excluded tags |
| `force` | bool | Re-render every diagram and rewrite every output file in `arch.generate`, bypassing incremental reuse (default `false`) |
| `template_path` | str | Excel template workbook used by `import_yaml` |
| `directory` | str | Solution directory passed to `bundle_solution` |
| `include` | str | Optional file, directory, or glob pattern of extra files to add under `data/` in bundle ZIP |

<!-- BEGIN GENERATED:PACK_REQUIREMENTS -->
## Runtime requirements

Pack distribution: OneTool `[dev]`.

| Kind | Requirement | Purpose | Availability |
|---|---|---|---|
| `lib` | `openpyxl` (import `openpyxl`, OneTool `[dev]`) | Read and write architecture workbooks | Required |
| `cli` | [D2](https://d2lang.com/tour/install) (executable `d2`) | Render generated architecture diagrams | Optional |

Use `ot.help(query='<pack>', topic='setup')` for current readiness and non-mutating setup guidance.
<!-- END GENERATED:PACK_REQUIREMENTS -->

## Configuration

### Required

- None - no secrets required.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.arch.output_dir` | str | `"arch"` | Default generation output directory. |
| `tools.arch.default_profile` | str | `"simple"` | Profile used when no profile override is provided. |
| `tools.arch.list_cell_separator` | str | `";"` | Separator between items when a list-valued field is encoded into a single Excel cell as bracketed text (e.g. `[core;internal]`). Applies only to the Excel cell encoding; YAML uses native lists. List items must not contain this character. |
| `tools.arch.profiles.<name>.solution_report` | str | `"templates/arch/solution/default/index.html.j2"` | Jinja template file for the solution index report (supports `base.html`, `styles.css`, `scripts.js` in same directory). |
| `tools.arch.profiles.<name>.system_report` | str | `"templates/arch/solution/default/system.html.j2"` | Jinja template file for each system page. |
| `tools.arch.profiles.<name>.project_report` | str | `"templates/arch/solution/default/project.html.j2"` | Jinja template file for each project page. |
| `tools.arch.profiles.<name>.system_diagram` | str | `"templates/arch/d2/system.d2.j2"` | Jinja template file for system D2 source. The same directory must include `styles.d2`. |
| `tools.arch.profiles.<name>.project_diagram` | str | `"templates/arch/d2/project.d2.j2"` | Jinja template file for project D2 source. The same directory must include `styles.d2`. |
| `tools.arch.profiles.<name>.system_engine` | str | `d2 {{ input }} {{ output }} --layout elk` | Jinja command template for system SVG rendering. |
| `tools.arch.profiles.<name>.diagram_engine` | str | `d2 {{ input }} {{ output }} --layout elk` | Jinja command template for workbook-defined diagram SVG rendering. |
| `tools.arch.profiles.<name>.data` | map[str, any] | `{}` | Extra values available to templates under `profile_data`. |
| `tools.arch.profiles.<name>.data.merge_interfaces` | bool | `true` | Merge multiple interfaces between the same rendered endpoints into a single edge. |
| `tools.arch.profiles.<name>.data.show_interface_labels` | bool | `true` | Toggle interface edge labels from template mode. |
| `tools.arch.profiles.<name>.data.interface_labels` | str | `"[{{ row.key }}] {{ row.name }} ({{ row.interaction_type }})"` | Interface edge-label template rendered against `row` fields (`row.key`, `row.name`, `row.id`, `row.provider`, `row.consumer`, `row.interaction_type`, `row.arrow_direction`, etc). |
| `tools.arch.profiles.<name>.data.show_arrowhead_labels` | bool | `true` | Toggle arrowhead labels from template mode. |
| `tools.arch.profiles.<name>.data.arrowhead_labels` | str | `"{{ row.key }}"` | Arrowhead-label template rendered against interface row fields via `row`. |
| `tools.arch.profiles.<name>.data.direction` | str | `"up"` | Diagram direction (`up`, `right`, `down`, `left`). |
| `tools.arch.profiles.<name>.data.secondary_system_detail` | str | `"sys"` | Detail level for secondary systems in each primary system diagram (`sys`, `app`, `cmp`, `match_primary`). |
| `tools.arch.profiles.<name>.data.secondary_system_connect_level` | str | `"app"` | Connection level for secondary-system interface endpoints (`sys`, `app`, `cmp`, `lowest_visible`). |
| `tools.arch.profiles.<name>.data.drawio_export` | bool | `true` | Embed an editable draw.io model in every generated system/project diagram SVG and show an "Export to draw.io" button on report pages. Set `false` to disable. A non-boolean value fails generation with an explicit configuration error. See [Editable diagram export (draw.io)](#editable-diagram-export-drawio). |

```yaml
tools:
  arch:
    output_dir: arch
    default_profile: simple
    list_cell_separator: ";"
    profiles:
      simple:
        solution_report: templates/arch/solution/default/index.html.j2
        system_report: templates/arch/solution/default/system.html.j2
        project_report: templates/arch/solution/default/project.html.j2
        system_diagram: templates/arch/d2/system.d2.j2
        project_diagram: templates/arch/d2/project.d2.j2
        system_engine: d2 {{ input }} {{ output }} --layout elk
        diagram_engine: d2 {{ input }} {{ output }} --layout elk
        data:
          merge_interfaces: true
          show_interface_labels: true
          interface_labels: "[{{ row.key }}] {{ row.name }} ({{ row.interaction_type }})"
          show_arrowhead_labels: true
          arrowhead_labels: "{{ row.key }}"
          direction: up
          secondary_system_detail: sys
          secondary_system_connect_level: app
      acme:
        solution_report: templates/arch/solution/default/index.html.j2
        system_report: templates/arch/solution/default/system.html.j2
        project_report: templates/arch/solution/default/project.html.j2
        system_diagram: templates/arch/d2/system.d2.j2
        project_diagram: templates/arch/d2/project.d2.j2
        system_engine: d2 {{ input }} {{ output }} --layout elk --theme 200
        diagram_engine: d2 {{ input }} {{ output }} --layout elk --theme 200
        data:
          merge_interfaces: true
          show_interface_labels: true
          interface_labels: "[{{ row.key }}] {{ row.name }} ({{ row.interaction_type }})"
          show_arrowhead_labels: true
          arrowhead_labels: "{{ row.key }}"
          direction: up
          secondary_system_detail: match_primary
          secondary_system_connect_level: lowest_visible
```

### Defaults

- If `tools.arch` is omitted, generation writes to `arch/` in the effective project cwd.
- Exactly one profile source is used per `arch.generate` run:
  - `profile_yaml` when provided
  - otherwise explicit `profile` when provided
  - otherwise `tools.arch.default_profile`
- Relative template/style paths first resolve under the active config directory; default `templates/arch/` paths fall back to bundled `global_templates/arch-templates` assets when no editable override exists.
- Interface table `Key` values come from the interface row `key` field.
- Each generated system page has three primary-system diagrams: System View renders the primary system at `sys` detail, Application View at `app` detail, and Component View at `cmp` detail.
- `secondary_system_detail` controls only secondary systems. `match_primary` makes secondary systems use the current diagram's primary detail level.
- `secondary_system_connect_level` controls only secondary-system interface endpoints. It uses the configured level when the interface row contains enough detail and the referenced node is visible; otherwise it falls back toward system level.
- Each generated project page has one diagram per `project_scope.stage`. Project diagrams have no primary system; `project.detail_level` and `project.connect_level` apply to all scoped systems and interfaces.
- Code fallback defaults for `data` options equal the bundled default profile values, so a custom profile that omits an option behaves like the shipped `simple` profile.
- `arch.generate` fully owns the `solution/` output directory and updates it incrementally: files are rewritten only when content changes, diagram renders are skipped when the `.d2` source is unchanged (and the SVG's draw.io-embed state matches the run's `drawio_export` setting), and stale files from prior runs are removed after a successful run. `force=true` re-renders everything. `summary.renders` reports executed vs skipped engine renders.
- Engine command templates run via argv execution (`shell=False`) after rendering.
- Legacy placeholder aliases in engine commands (for example `${{input_file}}`) are not supported. Use Jinja placeholders only: `{{ input }}` and `{{ output }}`.
- Unknown/removed config keys, removed values, invalid enum values, and missing required command-template variables fail fast with explicit structured errors.
- Ingestion and round-trip fail explicitly instead of silently dropping data: unknown YAML sections, workbook columns that collide after header normalization, and `import_yaml` row fields without a matching template column are all rejected.
- Input may be an Excel workbook or a single YAML model file. `arch.validate` and `arch.generate` accept `.yaml`/`.yml` and normalize it through the same canonical model path as workbooks.
- List-valued fields round-trip losslessly: real lists in the model, native lists in YAML, and bracketed text in Excel cells using `list_cell_separator` (e.g. `[core;internal]`). A bracketed cell parses back into a list on ingest; an unbracketed cell stays a scalar string. List items must not contain the separator character.
- Non-canonical worksheets round-trip verbatim: they are captured on Excel ingest, emitted to YAML under the reserved `_passthrough` key, and written back into the workbook on `import_yaml` (created if missing). They are preserved but not validated or added to the canonical model.

### Interface Contract

The canonical sheet/section is `interface`. The compact `int` sheet/section name is accepted as an explicit alias for authoring.

Required columns:
- `id`: stable interface identifier.
- `provider`: system, app, component, or user that owns or provides the interface contract.
- `consumer`: system, app, component, or user that consumes the interface contract.

Optional columns:
- `interaction_type`: free-form type such as `api_call`, `event`, `queue`, `batch`, `pubsub`, `file_transfer`, or a domain-specific value.
- `arrow_direction`: one of `consumer_to_provider`, `provider_to_consumer`, `none`, or `bidirectional`. When omitted, diagrams use `consumer_to_provider`. `none` and `bidirectional` edges render with neutral edge styling (no from/to-focus coloring).

### Project Scope

The `project` and `project_scope` sheets define cross-system architecture views.

`project` required columns:
- `id`
- `name`

`project` optional standard columns:
- `status`
- `owner`
- `sponsor`
- `start_date`
- `target_date`
- `detail_level`: `sys`, `app`, or `cmp`; defaults to `app`.
- `connect_level`: `sys`, `app`, `cmp`, or `lowest_visible`; defaults to `app`.
- `description`
- `tags`

`project_scope` required columns:
- `project`: project id.
- `stage`: free-form view/release/snapshot label such as `current`, `wip`, `target`, `v1`, `Q1`, or `Q2`.
- `item_type`: `system`, `application`, `component`, or `interface`.
- `item_id`: id of the scoped item.
- `change_type`: `existing`, `new`, `changed`, `removed`, `impacted`, or `dependency`.

`project_scope` optional standard columns:
- `name`
- `description`
- `owner`
- `status`
- `tags`

Extra columns on both sheets are preserved in YAML/model output and shown in generated project metadata/scope tables.

## Diagram Styling and Navigation

Solution output is fully navigable and visually distinguishes change-type and interaction-type data. All colors/labels below come from a single source (`src/otdev/tools/_arch/render_styles.py`) shared by diagram D2 classes, HTML badges, and the legend, so they never drift apart.

### Change-type colors (project stage diagrams and scope-table badges)

| `change_type` | Color | D2 class |
|----------------|---------|-----------------|
| `new` | `#2E7D32` (green) | `ChangeNew` |
| `changed` | `#F9A825` (amber) | `ChangeChanged` |
| `removed` | `#C62828` (red, dashed stroke) | `ChangeRemoved` |
| `impacted` | `#6A1B9A` (purple) | `ChangeImpacted` |
| `dependency` | `#546E7A` (slate) | `ChangeDependency` |
| `existing` | neutral (pre-existing styling, no dedicated class) | — |

Change-type styling appears only on project stage diagrams (not system diagrams): a system/app/component scoped in the current stage's `project_scope` with a non-`existing` `change_type` gets the matching D2 class; the same interface edge gets it too when its `change_type` is non-`existing`. The same item can carry a different `change_type` — and therefore a different color — in each stage it appears in. Scope-table `Change Type` cells render as a colored badge using the same color/label; `existing` renders as plain text.

### Interaction-type stroke patterns (system and project diagram edges)

| `interaction_type` (normalized) | Stroke dash | Stroke width | D2 class |
|----------------------------------|-------------|--------------|-----------|
| `api` | solid (`0`) | `3` | `IntApi` |
| `event` | `3` | `2` | `IntEvent` |
| `queue` | `5` | `2` | `IntQueue` |
| `batch` | `8` | `2` | `IntBatch` |
| `file` | `1` | `2` | `IntFile` |
| `pubsub` | `4` | `3` | `IntPubsub` |

`interaction_type` values are matched case-insensitively with non-alphanumeric characters stripped (`"Pub/Sub"` -> `pubsub`, `"API"` -> `api`). Unrecognized or absent values (for example `"REST"`) fall back to a solid neutral edge and never fail generation. The interaction-type stroke pattern is independent of the edge's focus-direction color (`Interface`/`InterfaceFromFocus`/`InterfaceToFocus`) — both apply simultaneously via a D2 class array, for example `class: [InterfaceToFocus; IntBatch]`. The interfaces table on each system page renders recognized values as a badge; unrecognized values render as plain text. `Int*` classes set only `stroke-dash`/`stroke-width`, never color, so they compose cleanly with direction or change-type color classes.

### Clickable diagram nodes

System, app, and component nodes carry a D2 `link` attribute pointing at the relative URL of the owning system's HTML page (`./{system_id}.html`), on both system and project diagrams — including secondary/focus systems on system diagrams. Person (`usr`) nodes and nodes synthesized from an unresolved interface endpoint carry no link. D2 renders `link` as an SVG `<a href="...">` wrapper around the node, so clicking a node in a generated page navigates to that system's page. A capture-phase click handler in `scripts.js` distinguishes a drag (panzoom) from a click: it cancels navigation only when the pointer moved more than 5px between `pointerdown` and `click`, so dragging the diagram never navigates and a clean click always does.

### Navigation chrome

- Every system and project page shows a "Solution Index" back-link in the page header (the index page itself does not, via the `is_index` template flag).
- A system page shows a "Projects" section listing every project whose `project_scope` rows reference that system or any of its apps/components, each linking to its project page; the section is omitted entirely when no project references the system.
- Project scope-table `Item ID` cells link to the owning system's page when the item resolves to a system/app/component; interfaces, users, and unresolved ids render as plain text.

### Legend

System and project pages each include a collapsible "Legend" section (above the first diagram) with: node classes (person, external system, system, app, component types), edge direction colors (the three existing focus-direction hexes), and interaction-type stroke patterns. Project page legends additionally show the five change-type swatches described above; system page legends omit that group.

### Index summary cards and entity tables

The solution index (`index.html`) shows:
- Aggregate `stats` cards: total counts of systems, applications, components, interfaces, and projects, plus breakdowns of systems by type, projects by status, and interfaces by normalized interaction type (unrecognized interaction-type values are grouped under their literal text). Zero-count totals and empty breakdowns are omitted rather than shown as zero.
- Five collapsible, searchable AG Grid tables — Systems, Applications, Components, Interfaces, Projects — each with a quick-search input that filters rows client-side (wired to AG Grid's `quickFilterText`) and an XLSX export button. Name/id cells link to the relevant system or project page; interface rows link both their provider and consumer system pages.

### Editable diagram export (draw.io)

Every generated system-level (`sys`/`app`/`cmp`) and project-stage diagram SVG doubles as an editable [draw.io](https://www.diagrams.net/) file: alongside the visible rendered shapes, the SVG carries a `content` attribute holding a full `mxfile` model (nodes, container nesting, and interface edges) laid out to match the rendered geometry. Browsers and image viewers ignore that attribute entirely, so the diagram looks and behaves exactly the same as before — it just happens to also be an editable file.

**Exporting a diagram**: each diagram panel on a system or project page has an "Export to draw.io" button next to the Zoom/Print controls. It downloads that diagram's standalone SVG file with a `.drawio.svg` extension (for example `sys_core-app.drawio.svg`), which draw.io desktop, the VS Code draw.io extension, and app.diagrams.net all recognize automatically. Workbook-supplied diagrams (from the `diagram` sheet) have no export control — free-form D2 sources have no canonical-model structure to embed.

**Opening the exported file**:
- **app.diagrams.net**: open the site, then File → Open From → Device, and pick the downloaded `.drawio.svg`.
- **draw.io desktop**: File → Open, pick the downloaded `.drawio.svg` directly — no import step needed.
- **VS Code**: install the "Draw.io Integration" extension, then open the `.drawio.svg` file; it renders as an editable canvas in the editor.

Boxes can be dragged; connected edges stay attached because containers (systems containing apps/components) and edges reference their vertices by id, and edges use draw.io's orthogonal routing style so they re-route automatically as boxes move.

**One-way snapshot**: the embedded model is a snapshot taken at generation time. Edits made in a draw.io editor do not flow back into the workbook or model — re-running `arch.generate` after a model change (or with `force=true`) overwrites the SVG (and its embedded model) from scratch. Save edited copies under a different filename if you want to keep them.

**Restyle on first edit**: draw.io renders its own shape styling (chosen to approximate the D2 color scheme) rather than reusing the rendered SVG's visuals, and it replaces the visuals with its own rendering as soon as you make and save an edit. The pristine, unedited export always matches the report's D2 styling exactly; edited copies will look visually different from the report going forward.

**Disabling the feature**: set the `drawio_export` profile `data` option to `false` (default `true`) to stop embedding models and showing export buttons entirely:

```yaml
tools:
  arch:
    profiles:
      simple:
        data:
          drawio_export: false
```

## Template Context Contracts

`arch` uses strict, per-surface context allowlists. Template variables outside these contracts fail with `StrictUndefined`.

| Surface | Available Context |
|---------|-------------------|
| `system_engine`, `diagram_engine` command templates | `input`, `output`, `profile_data` |
| `system.d2.j2`, `project.d2.j2` | `model` (only `model.system_view` / `model.project_view`), `profile_data`, plus the `class_attr()` and `quote_d2()` globals |
| `interface_labels`, `arrowhead_labels` | `row` |
| `system.html.j2`, `project.html.j2`, `index.html.j2`, `base.html` | explicit page fields (`system` or `project`, table/diagram fields, `styles`, `scripts`, `generated_at`, `title`, `systems`, `projects`) + `model` + `profile_data` |

Notes:
- Legacy broad engine variables (for example `paths`, `engine`, `report`, `context`) are not available in command templates.
- Legacy top-level D2 variables (for example `{{ title_name }}`) are not available; use `{{ model.system_view.title_name }}` and other `model.system_view.*` fields.
- Interface label templates must use `row.<field>` style access.

## Model Contract

`model` is the canonical template data surface and extension point.

Top-level keys (HTML report templates only — in the D2 diagram templates `model` contains only the render-time view below):
- `model.model.version` and `model.model.generated_at`
- `model.entities` — canonical entity lists (`sys`, `app`, `cmp`, `interface`, `usr`, `project`, `project_scope`, `diagram`) with internal keys removed
- `model.diagrams` — cleaned workbook `diagram` rows (internal keys removed)
- `model.filters.include_tags` and `model.filters.exclude_tags`

Render-time view:
- `model.system_view` is available to `system.d2.j2` and includes:
  - `title_name`, `level_name`
  - `user_nodes`, `external_nodes`
  - `system_blocks`
  - `interface_edges`
- `model.project_view` is available to `project.d2.j2` and includes:
  - `title_name`, `stage_name`
  - `detail_level`, `connect_level`
  - `user_nodes`, `external_nodes`
  - `system_blocks`
  - `interface_edges`

Extension fields:
- Extra YAML/Excel columns on entity rows are preserved in `model.entities` and available to templates.
- Generated table/column metadata for HTML reports is exposed through explicit page fields in `system.html.j2` context (`*_data` and `*_columns` payloads).

## Examples

```python
# Validate one workbook
arch.validate(input_path="architecture.xlsx")

# Generate using a non-default profile
arch.generate(
    input_path="input/",
    profile="acme",
    output_dir="build/arch",
    title="ACME Architecture",
    include_tags=["core"],
)

# Generate with an inline YAML profile block
arch.generate(
    input_path="input/",
    profile_yaml="""
system_engine: d2 {{ input }} {{ output }} --layout elk
diagram_engine: d2 {{ input }} {{ output }} --layout elk
data:
  direction: left
  show_interface_labels: true
  interface_labels: "[{{ row.key }}] {{ row.name }} ({{ row.interaction_type }})"
  secondary_system_detail: sys
  secondary_system_connect_level: app
""",
    output_dir="build/arch",
)

# Export workbook data to YAML for text-first edits
arch.export_yaml(input_path="architecture.xlsx", output_path="tmp/architecture.yaml")

# Import YAML back into an Excel template and run validation on result
arch.import_yaml(
    input_path="tmp/architecture.yaml",
    template_path="templates/architecture-template.xlsx",
    output_path="tmp/architecture-updated.xlsx",
)

# Bundle generated solution output to a zip archive
arch.bundle_solution(directory="arch/solution")

# Bundle with extra source files (file, dir, or glob)
arch.bundle_solution(
    directory="arch/solution",
    include="input/*.xlsx",
)
```
