# tool-arch-multi-format-export Specification

## Purpose

Defines deterministic multi-format architecture exports, shared selection semantics, artifact ownership, fidelity reporting, and partial-failure behavior.

## Requirements

### Requirement: Shared typed batch export contract
The tool SHALL implement `arch.export(input_path, output_path, formats,
selections=None, drawio_mode="per-view", continue_on_error=False, force=False)` to accept
saved view IDs or complete typed view selections and SHALL use the same
normalization, resolution, filtering, layout, icon, and theme data as
`arch.generate`. Identical normalized selections SHALL be deduplicated.

#### Scenario: Export one normalized view in multiple formats
- **WHEN** a request selects the 2027 comparison and asks for SVG, Draw.io, and
  LikeC4 source
- **THEN** every artifact represents the same state, comparison, entities,
  relationships, filtering, diagram, level, and theme

#### Scenario: Deduplicate equivalent batch selections
- **WHEN** two saved/ad hoc inputs normalize to the same resolved view
- **THEN** layout/export work is reused and the manifest records each request
  against the shared artifact identity

### Requirement: Production direct SVG export
The tool SHALL export SVG directly from the layouted `ViewGraph` and LikeC4
geometry. SVG SHALL preserve stable view, entity, and interface IDs, hierarchy,
node and edge geometry, labels, arrow direction, contextual status, supported
styles and resolved icons, links, and dynamic or sequence layout.

#### Scenario: Parse and compare direct SVG
- **WHEN** generated and authored LikeC4 diagram-class fixtures are exported to SVG
- **THEN** an independent SVG parser succeeds and semantic golden checks match
  the same layouted view used by the explorer

#### Scenario: Reject placeholder SVG
- **WHEN** an exporter emits a screenshot, renamed intermediate, placeholder,
  or content that omits selected semantics
- **THEN** production-path export verification fails

### Requirement: Canonical editable Draw.io export
Draw.io export SHALL consume the normalized selection, projected `ViewGraph`,
and renderer-neutral `SolutionLayoutResult` used by the active solution. It
SHALL support one editable file per solution and one multi-tab file. Node and
edge cells SHALL retain canonical IDs, aggregate interface members, visible
endpoints, containment, geometry, routes, kind, status, snapshot, selection,
colors, and supported styles. Boundary interfaces SHALL NOT invent outside
nodes. Unsupported React-only presentation SHALL be listed precisely as a
fidelity difference.

#### Scenario: Export per-view and multi-tab Draw.io
- **WHEN** the same selections use `drawio_mode=per-view` and the multi-tab mode
- **THEN** independent Draw.io readers parse the outputs and each page maps to
  the expected stable view and semantic content

#### Scenario: Name Draw.io pages from normalized selections
- **WHEN** API or browser export writes a Draw.io page for a normalized solution
- **THEN** its deterministic page name identifies the snapshot, selected scope,
  architectural level, and interface depth using the same naming rules

#### Scenario: Download the active browser projection offline
- **WHEN** the user changes system set, snapshot, depth, level, and color and selects **Export → Draw.io**
- **THEN** the browser locally downloads editable XML whose nodes, edges, IDs, containment, routes, and selection metadata match the active diagram without a network request

#### Scenario: Preserve aggregate membership
- **WHEN** one visible edge aggregates multiple canonical interfaces
- **THEN** its Draw.io cell stores the stable aggregate edge ID and every contributing interface ID

#### Scenario: Produce deterministic editable bytes
- **WHEN** an identical normalized solution is exported twice
- **THEN** stable ordering, page identity, and modified timestamp produce byte-identical XML with no embedded SVG image

#### Scenario: Report Draw.io presentation differences
- **WHEN** a custom React node field has no supported Draw.io representation
- **THEN** the manifest identifies that field, affected elements, and fidelity
  limitation while preserving editable semantics

### Requirement: State, source, image, and document formats
The tool SHALL export complete resolved YAML and Excel states, generated LikeC4
source, and every supported image/document format from the same normalized
selection. It SHALL either preserve resolved icon/style semantics supported by
the format or report exact limitations; it SHALL NOT silently downgrade to a
different renderer or format.

Local external attachments SHALL remain explorer/bundle artifacts. When an
external diagram is selected, SVG, Draw.io, and LikeC4 export SHALL fail that
artifact explicitly instead of silently substituting the generated
Architecture view. Independent YAML or Excel state artifacts MAY continue only
under `continue_on_error=true` and SHALL make the result partial.

#### Scenario: Export equivalent resolved state files
- **WHEN** a selected roadmap point is exported as YAML state and Excel state
- **THEN** both normalize to the identical complete architecture and stable ID

#### Scenario: Export generated LikeC4 source
- **WHEN** LikeC4 source is requested
- **THEN** it contains deterministic generated logical IDs, selected standard
  or catalogued views, and a disclosed canonical-ID mapping

#### Scenario: Reject unsupported output path
- **WHEN** requested semantics cannot be represented by a format and the
  contract does not define a fidelity warning
- **THEN** that artifact fails with a structured diagnostic instead of silent
  omission or renderer substitution

#### Scenario: Reject visual export of an external diagram
- **WHEN** a selected external diagram is requested as SVG alongside YAML with
  `continue_on_error=true`
- **THEN** SVG fails with an external-diagram diagnostic, YAML is generated from
  the resolved state, and the operation reports partial failure

### Requirement: Deterministic paths and ownership manifest
Exports SHALL stage and validate outputs, then atomically replace only files
owned by the operation manifest. Without `force`, an existing user-owned
destination SHALL be an error. Names, ordering, and content hashes SHALL be
deterministic. The manifest SHALL list requested, generated, reused, skipped,
failed, removed-stale artifacts and exact normalized selections.

#### Scenario: Reuse unchanged artifacts
- **WHEN** export is repeated with identical normalized input, dependency
  versions, layout, and exporter version
- **THEN** content-addressed artifacts are reused and recorded without changing
  their content or deterministic paths

#### Scenario: Remove stale owned output safely
- **WHEN** a later successful export no longer requests an artifact owned by the
  prior manifest
- **THEN** the stale owned artifact is removed and reported while unrelated
  user files remain untouched

#### Scenario: Protect a user-owned destination
- **WHEN** an output path exists but is not owned by the operation manifest and
  `force` is false
- **THEN** export fails before replacement

### Requirement: Explicit partial failure
By default, any export failure SHALL make the operation unsuccessful. With
`continue_on_error=true`, independent artifacts MAY continue, but the result
SHALL explicitly report partial success, preserve every error, and reconcile
summary and manifest counts. Validation failure SHALL never produce an
apparently successful artifact.

#### Scenario: Continue after one format fails
- **WHEN** one selected format fails and another succeeds with
  `continue_on_error=true`
- **THEN** the result is marked partial, the manifest lists both outcomes, and
  `issues.errors` retains the failed artifact diagnostic

#### Scenario: Stop after validation failure
- **WHEN** the selected view or required asset is invalid
- **THEN** no apparently valid output replaces the destination

### Requirement: D2-free export pipeline
The tool SHALL keep public formats, dependencies, configuration, templates,
generated artifacts, and runtime free of any D2 renderer or D2-based Draw.io/SVG path. SVG SHALL
not be produced by converting Draw.io.

#### Scenario: Verify removal of obsolete exporters
- **WHEN** repository cleanup checks search runtime, config, templates, tests,
  fixtures, docs, and generated paths
- **THEN** no active D2 or embedded-Draw.io-in-SVG contract remains
