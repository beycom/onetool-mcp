# tool-arch-diagram-catalog Specification

## Purpose

Defines the architecture diagram catalog, view-only LikeC4 sources, diagram variants, applicability validation, and portable local assets.

## Requirements

### Requirement: Unified diagram catalog
The explorer SHALL catalog generated landscape/system/change/comparison views,
authored view-only LikeC4 static and dynamic views, sequence variants, and safe
local external PlantUML, Mermaid, SVG, PDF, or HTML attachments. Catalog entries
SHALL retain stable ID, name, source, LikeC4 view ID, variants, folders, and
applicable systems/changes. The explorer's Diagram view control SHALL list
applicable entries by stable ID and name; catalog metadata SHALL remain
available in the embedded payload even when it is not part of the control label.

#### Scenario: Browse every supported diagram class
- **WHEN** a workspace contains standard, custom static, dynamic/sequence, and
  external diagrams
- **THEN** the Diagram view control lists every applicable entry and the
  embedded catalog retains its type, variants, folder, and applicability

#### Scenario: Keep external attachment non-canonical
- **WHEN** an external attachment depicts systems or relationships
- **THEN** it remains presentation-only and does not add or modify architecture
  entities

### Requirement: View-only LikeC4 source
Authored `.c4` sources SHALL be limited to the version-pinned allowlist of
view predicates, groups, layout instructions, notes, navigation, view-local
styles, and static or dynamic interaction statements. Logical `model`,
`specification`, and `deployment` declarations SHALL be rejected. References
SHALL resolve against deterministic generated LikeC4 identifiers and mappings.

#### Scenario: Compile the canonical dynamic source
- **WHEN** the canonical `platform_delivery` dynamic view references generated
  identifiers A, B, and C
- **THEN** it compiles with the generated logical model and validation reports
  its canonical identifier mapping

#### Scenario: Reject a second logical model
- **WHEN** the same view-only source declares `model`, `specification`, or
  `deployment` content
- **THEN** validation rejects the declaration with exact file location

#### Scenario: Reject an unknown generated identifier
- **WHEN** a view predicate or interaction references an identifier absent from
  the generated mapping
- **THEN** validation reports the source location, diagram ID, and identifier

### Requirement: Static, dynamic, and sequence behavior
The supported LikeC4 subset SHALL include computed static predicates and
layouts plus nested, parallel, noted, navigable dynamic interactions. Declared
diagram/sequence variants SHALL remain stable catalog metadata under one
diagram identity. Selecting or clearing that diagram SHALL preserve roadmap
endpoint, comparison, and browse/focus context. Dynamic interaction
leaf-participant rules SHALL be validated.

#### Scenario: Select a catalogued flow
- **WHEN** the user selects or clears `platform-delivery-flow`
- **THEN** its resolved state, comparison, and change/system context remain
  unchanged and its declared variants remain in catalog metadata

#### Scenario: Reject invalid sequence participant
- **WHEN** a sequence variant uses a participant disallowed by the pinned
  LikeC4 subset
- **THEN** validation fails with source step and participant information

### Requirement: Catalog references and applicability are validated
The tool SHALL validate diagram sources, view IDs, variants, folders, applicable
changes/systems, and external attachments before generation/export. Attachment
paths SHALL be local, contained, present, supported, and safe to embed. Each
attachment SHALL be at most 10 MiB; distinct embedded attachment content SHALL
be content-addressed, stored once, and limited to 25 MiB in aggregate.

#### Scenario: Reject an inapplicable diagram
- **WHEN** a selection requests a diagram whose catalog applicability excludes
  the selected system/change context
- **THEN** validation fails before generation or export with both identities

#### Scenario: Reject an unsafe attachment
- **WHEN** an attachment is remote, missing, unsupported, path-traversing, or
  outside the workspace
- **THEN** validation rejects it with catalog and source locations

#### Scenario: Reject excessive attachment payload
- **WHEN** one attachment exceeds 10 MiB or distinct attachments exceed 25 MiB
- **THEN** validation fails before reading or serializing the excessive payload
  and identifies the responsible diagram and path

### Requirement: Diagram sources and variants remain portable
View-only `.c4` source and catalogued attachment metadata SHALL round-trip
between YAML and Excel and SHALL be included in deterministic workspace
bundles. Every generated explorer SHALL use local compiled data and assets,
restore a selected external diagram, and render it without network access.

#### Scenario: Bundle dynamic and external diagrams
- **WHEN** a workspace with a dynamic source and local external attachment is
  bundled and moved offline
- **THEN** both catalog entries resolve and render without changing stable IDs
