# Arch

Architecture workflows for Excel ingestion, validation, generation, round-trip conversion, and solution bundling.

## Highlights

- Ingests `sys`, `app`, `cmp`, `int`, and `usr` sheets from one workbook, a directory, or a glob
- Optionally ingests a `diagram` sheet (`file`, `name`, `sys`, `description`) for workbook-defined extra diagrams
- Validates required fields, duplicates, and reference integrity with structured issue payloads
- `arch.generate` produces solution outputs only (always HTML single-file)
- Solution HTML includes rich AG Grid tables and embedded SVG diagrams
- Delegates rendering to configured engine command templates for system diagrams and workbook-defined diagrams
- Diagram sheet `file` values resolve relative to the workbook containing that row; rendered SVGs are shown in a separate `Additional Diagrams` tabbed/collapsible section on the mapped system page
- Emits canonical model payloads with `model.version` and model-derived render context
- Supports Excel-to-YAML and YAML-to-Excel round-trip flows plus distributable solution ZIP bundles

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
| `input_path` | str | Workbook file, directory, or glob pattern for `.xlsx` / `.xlsm` inputs |
| `output_dir` | str | Output root directory for generated files |
| `profile` | str | Optional profile name override for `arch.generate` |
| `profile_yaml` | str | Optional inline YAML profile block for `arch.generate` (mutually exclusive with `profile`) |
| `title` | str | Optional title for the generated solution index page |
| `output_path` | str | Output file path for `export_yaml` / `import_yaml`, or optional ZIP target for `bundle_solution` |
| `include_tags` | list[str] | Keep only entities matching included tags |
| `exclude_tags` | list[str] | Omit entities matching excluded tags |
| `template_path` | str | Excel template workbook used by `import_yaml` |
| `directory` | str | Solution directory passed to `bundle_solution` |
| `include` | str | Optional file, directory, or glob pattern of extra files to add under `data/` in bundle ZIP |

## Requires

- `openpyxl` (Excel ingest and round-trip)
- `markdown` (rich markdown-to-HTML rendering in solution tables/pages)
- `beautifulsoup4` and `lxml` (SVG inlining for `bundle_solution`)
- `d2` CLI on `PATH` for default `system_engine` and `diagram_engine` rendering
- Install D2 from <https://github.com/terrastruct/d2> (for example, `brew install d2` on macOS)
- all included in `onetool-mcp[dev]`

## Configuration

### Required

- None - no secrets required.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.arch.output_dir` | str | `"architecture-output"` | Default generation output directory. |
| `tools.arch.default_profile` | str | `"simple"` | Profile used when no profile override is provided. |
| `tools.arch.profiles.<name>.solution_report` | str | `"arch-templates/solution/default/index.html.j2"` | Jinja template file for the solution index report (supports `base.html`, `styles.css`, `scripts.js` in same directory). |
| `tools.arch.profiles.<name>.system_report` | str | `"arch-templates/solution/default/system.html.j2"` | Jinja template file for each system page. |
| `tools.arch.profiles.<name>.system_diagram` | str | `"arch-templates/d2/system.d2.j2"` | Jinja template file for system D2 source. The same directory must include `styles.d2`. |
| `tools.arch.profiles.<name>.system_engine` | str | `d2 {{ input }} {{ output }} --layout elk` | Jinja command template for system SVG rendering. |
| `tools.arch.profiles.<name>.diagram_engine` | str | `d2 {{ input }} {{ output }} --layout elk` | Jinja command template for workbook-defined diagram SVG rendering. |
| `tools.arch.profiles.<name>.data` | map[str, any] | `{}` | Extra values available to templates under `profile_data`. |
| `tools.arch.profiles.<name>.data.merge_integrations` | bool | `true` | Merge multiple integrations between the same rendered endpoints into a single edge. |
| `tools.arch.profiles.<name>.data.show_integration_labels` | bool | `true` | Toggle integration edge labels from template mode. |
| `tools.arch.profiles.<name>.data.integration_labels` | str | `"[{{ row.key }}] {{ row.name }} ({{ row.type }})"` | Integration edge-label template rendered against `row` fields (`row.key`, `row.name`, `row.id`, `row.src`, `row.dst`, `row.type`, etc). |
| `tools.arch.profiles.<name>.data.show_arrowhead_labels` | bool | `true` | Toggle arrowhead labels from template mode. |
| `tools.arch.profiles.<name>.data.arrowhead_labels` | str | `"{{ row.key }}"` | Arrowhead-label template rendered against integration row fields via `row`. |
| `tools.arch.profiles.<name>.data.direction` | str | `"up"` | Diagram direction (`up`, `right`, `down`, `left`). |

```yaml
tools:
  arch:
    output_dir: architecture-output
    default_profile: simple
    profiles:
      simple:
        solution_report: arch-templates/solution/default/index.html.j2
        system_report: arch-templates/solution/default/system.html.j2
        system_diagram: arch-templates/d2/system.d2.j2
        system_engine: d2 {{ input }} {{ output }} --layout elk
        diagram_engine: d2 {{ input }} {{ output }} --layout elk
        data:
          merge_integrations: true
          show_integration_labels: true
          integration_labels: "[{{ row.key }}] {{ row.name }} ({{ row.type }})"
          show_arrowhead_labels: true
          arrowhead_labels: "{{ row.key }}"
          direction: up
      acme:
        solution_report: arch-templates/solution/default/index.html.j2
        system_report: arch-templates/solution/default/system.html.j2
        system_diagram: arch-templates/d2/system.d2.j2
        system_engine: d2 {{ input }} {{ output }} --layout elk --theme 200
        diagram_engine: d2 {{ input }} {{ output }} --layout elk --theme 200
        data:
          merge_integrations: true
          show_integration_labels: true
          integration_labels: "[{{ row.key }}] {{ row.name }} ({{ row.type }})"
          show_arrowhead_labels: true
          arrowhead_labels: "{{ row.key }}"
          direction: up
```

### Defaults

- If `tools.arch` is omitted, generation writes to `architecture-output/` in the effective project cwd.
- Exactly one profile source is used per `arch.generate` run:
  - `profile_yaml` when provided
  - otherwise explicit `profile` when provided
  - otherwise `tools.arch.default_profile`
- Relative template/style paths first resolve under the active config directory; missing relative paths fall back to bundled `global_templates/arch-templates` assets.
- Integration table `Key` values come from the integration row `key` field.
- Engine command templates run via argv execution (`shell=False`) after rendering.
- Legacy placeholder aliases in engine commands (for example `${{input_file}}`) are not supported. Use Jinja placeholders only: `{{ input }}` and `{{ output }}`.
- Unknown/removed config keys, removed values, invalid enum values, and missing required command-template variables fail fast with explicit structured errors.

## Template Context Contracts

`arch` uses strict, per-surface context allowlists. Template variables outside these contracts fail with `StrictUndefined`.

| Surface | Available Context |
|---------|-------------------|
| `system_engine`, `diagram_engine` command templates | `input`, `output`, `profile_data` |
| `system.d2.j2` | `model`, `profile_data` |
| `integration_labels`, `arrowhead_labels` | `row` |
| `system.html.j2`, `index.html.j2`, `base.html` | explicit page fields (`system`, table/diagram fields, `styles`, `scripts`, `generated_at`, `title`, `systems`) + `model` + `profile_data` |

Notes:
- Legacy broad engine variables (for example `paths`, `engine`, `report`, `context`) are not available in command templates.
- Legacy top-level D2 variables (for example `{{ title_name }}`) are not available; use `{{ model.system_view.title_name }}` and other `model.system_view.*` fields.
- Integration label templates must use `row.<field>` style access.

## Model Contract

`model` is the canonical template data surface and extension point.

Top-level keys:
- `model.model.version` and `model.model.generated_at`
- `model.entities` — canonical entity lists (`sys`, `app`, `cmp`, `int`, `usr`, `diagram`) with internal keys removed
- `model.diagrams` — cleaned workbook `diagram` rows (internal keys removed)
- `model.filters.include_tags` and `model.filters.exclude_tags`

Render-time view:
- `model.system_view` is available to `system.d2.j2` and includes:
  - `title_name`, `level_name`
  - `user_nodes`, `external_nodes`
  - `system_blocks`
  - `integration_edges`

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
  show_integration_labels: true
  integration_labels: "[{{ row.key }}] {{ row.name }} ({{ row.type }})"
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
arch.bundle_solution(directory="architecture-output/solution")

# Bundle with extra source files (file, dir, or glob)
arch.bundle_solution(
    directory="architecture-output/solution",
    include="input/*.xlsx",
)
```
