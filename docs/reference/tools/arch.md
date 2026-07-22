# Architecture (`arch`)

Schema-v2 architecture workflows use complete states, sparse changes, ordered
roadmaps, reusable views, and one shared result envelope. YAML and Excel are
semantically equivalent; removed revision-set, project-scope, deployment,
and legacy renderer contracts are not accepted.

## Operations

| Operation | Purpose |
| --- | --- |
| `arch.init(output_path, template="solution")` | Create a canonical paired YAML/Excel workspace with safe local asset folders. |
| `arch.validate(input_path, roadmaps=None, views=None)` | Validate schema, replay, selections, LikeC4, themes, icons, attachments, and exporter prerequisites. |
| `arch.convert(input_path, output_path)` | Convert a complete schema-v2 workspace between YAML and Excel. |
| `arch.resolve(input_path, output_path, ...)` | Materialize one complete state selected by state or roadmap endpoint. |
| `arch.diff(base_path, target_path, output_path=None, change_id=None)` | Compare complete states and optionally write a replayable derived change. |
| `arch.generate(input_path, output_path, selections=None, force=False)` | Generate one self-contained offline OneTool solution explorer. |
| `arch.export(input_path, output_path, formats, ...)` | Export semantic SVG, native Draw.io, LikeC4, YAML, or Excel artifacts with an ownership manifest. |
| `arch.bundle(input_path, output_path, include_generated=False)` | Create a deterministic portable workspace archive. |

## Selection

A selection chooses either `state` or `roadmap`; roadmap endpoints use
`through` or `order`. It may also specify `compare_from`, `focus`,
`browse_by`, `subject`, `visibility`, `display_statuses`, `include_future`,
`system_set`, `interface_depth`, `projection`, `diagram`, `level`, `color_by`,
and `theme`. A system set is the union of selected systems, system groups,
changes, change groups, and tags. Saved view IDs and ad hoc
selection objects share this grammar and normalize to a stable identity.
`browse_by` accepts exactly `system`, `system_group`, `change`, `change_group`,
or `tag`. A browse `subject` is unioned into the matching `system_set` field;
change subjects select impacted systems and never add to `focus`. Subjects are
validated against roadmap-wide indexes, so systems introduced by later changes
remain valid selections at earlier snapshots.

## Diagram catalog

Every explorer includes its generated **Architecture** view. A workspace can
also declare static or dynamic view-only LikeC4 diagrams and local external
attachments. Selecting `diagram` in a saved or ad hoc selection restores that
diagram when the explorer opens; the **Diagram view** control switches between
applicable entries without changing the active solution selection.

Authored LikeC4 sources must use `.c4`, contain only view declarations, and
reference canonical nodes as `@{stable-id}`. External attachments support
PlantUML (`.puml`, `.plantuml`), Mermaid (`.mmd`, `.mermaid`), SVG, PDF, and
HTML. Sources must be workspace-relative local files. SVG and HTML markup is
sanitized, external content is embedded into the single-file report, duplicate
content is stored once, each file is limited to 10 MiB, and distinct embedded
attachments are limited to 25 MiB in total.

## Example

```python
arch.validate(input_path="architecture.yaml")

arch.generate(
    input_path="architecture.yaml",
    output_path="generated/architecture",
)

arch.export(
    input_path="architecture.yaml",
    output_path="generated/exports",
    formats=["svg", "drawio", "yaml", "excel"],
    selections=[{"roadmap": "preferred", "order": 1}],
)
```

Generated explorers are single-file, locally bundled, and perform no browser
roadmap mutation replay. They embed validated snapshots and selection indexes,
then project and lay out the chosen system set locally for the selected
snapshot, interface depth, System/Application/Component level, and coloring.
System, group, impacted-change, change-group, and tag selectors use union
semantics across the roadmap. A system that is not yet or is no longer present
remains a valid scope and is reported explicitly.
The explorer title defaults to the input filename stem. Excel uses domain
sheets only; presentation defaults, palettes, themes, and tables belong under
`tools.arch.presentation` rather than a `model` worksheet:

```yaml
tools:
  arch:
    presentation:
      title: Payments solution  # optional; otherwise the input filename stem
      default_roadmap: preferred
      default_theme: clean
      default_selection:
        system_set:
          system_groups: [payments]
        interface_depth: 1
        level: system
        color_by: change_status
      palettes:
        integration_type:
          api: {color: "#3B82F6"}
        tag:
          critical: {color: "#DC2626"}
```

System and change `group` columns are lists using the same Excel form as tags,
for example `[payments;core-platform]`. An Excel `properties` cell accepts a
JSON object or `name:value` entries separated by semicolons or newlines. Names
and values are trimmed, empty values are retained, and malformed or duplicate
names fail with the cell location.

The full-screen explorer lays out projections locally and reads properties and
relationships from the active canonical graph. Changing only `color_by` reuses
the existing topology and geometry. Requests are stale-safe and bounded; empty
and oversized projections show accessible recovery states. Solution navigation
retains at most 100 history entries. Process-wide compiled LikeC4 artifacts use
an LRU bounded to 32 entries and 64 MiB, with oversized entries left uncached.

The solution toolbar includes **Export → Draw.io**. Browser export is entirely
local and uses the active canonical graph and fitted renderer-neutral geometry.
API and browser Draw.io preserve canonical node/interface IDs, aggregate
members, containment, routes, status, color, snapshot, and normalized selection
metadata. Page names deterministically identify the snapshot, selected scope,
architectural level, and interface depth in both API and browser exports.
Boundary interfaces do not create external nodes. API filenames use
`<source>-<scope>-<snapshot>-n<depth>-<level>.drawio`; per-view and multi-tab
modes are deterministic and editable rather than embedded SVG images.

LikeC4 is the current pinned canvas/layout adapter, not the solution contract.
OneTool owns selection, projection, history, URL state, inspectors, tables,
canonical events, and export geometry. The adapter allowlist and migration
review are documented in `dev/project/arch/solution-renderer-boundary.md`.
Export and generation refuse invalid workspaces and protect
user-owned destinations unless `force=True` is explicit.
