# tool-arch-view-resolution Specification

## Purpose

Defines the shared typed selection grammar and deterministic state, comparison, focus, visibility, and offline view-resolution behavior.

## Requirements

### Requirement: Shared typed selection grammar
Saved views and ad hoc generation/export selections SHALL use the same typed
fields: `state`, `roadmap`, `through`, `order`, `compare_from`, `focus`,
`browse_by`, `subject`, `visibility`, `display_statuses`, `include_future`,
`system_set`, `interface_depth`, `projection`, `diagram`, `level`, `color_by`,
and `theme`. A system set SHALL union explicit systems, system groups, systems
impacted by changes, systems impacted by change groups, and system tags. Output
format SHALL NOT be stored as view state.

#### Scenario: Override a saved view selectively
- **WHEN** an ad hoc request references a saved view and overrides only
  `visibility`
- **THEN** the explicit visibility wins while all other saved values and then
  configured defaults remain in effect

#### Scenario: Reuse a selection for explorer and export
- **WHEN** the same saved or ad hoc selection is passed to `arch.generate` and
  `arch.export`
- **THEN** both operations resolve the same normalized state, comparison,
  focus, projection, diagram, filtering, and theme

#### Scenario: Preserve independent solution axes
- **WHEN** snapshot, system set, interface depth, architectural level, or
  coloring changes
- **THEN** every unchanged axis retains its current value and the normalized
  selection identity reflects every topology-affecting axis

### Requirement: Deterministic state and roadmap selection
`state` and `roadmap` SHALL be mutually exclusive; omission of both SHALL select
the configured default roadmap. `through` and `order` SHALL be alternatives.
Roadmap selection without either SHALL resolve the final change. `through`,
`order`, non-empty `focus`, and `include_future=true` SHALL require roadmap
resolution and be invalid with authored-state selection.

#### Scenario: Reject conflicting resolution selectors
- **WHEN** a selection supplies both `state` and `roadmap`, or both `through`
  and `order`
- **THEN** validation fails before generation or export

#### Scenario: Select the default roadmap endpoint
- **WHEN** a selection omits state, roadmap, through, and order
- **THEN** it resolves the final change on the configured default roadmap

### Requirement: Cumulative comparison and contributing history
`compare_from` SHALL accept `base`, an authored state ID, a selected-roadmap
change ID, or a numeric order at or before the resolved endpoint. Comparison
SHALL expose complete resolved state, cumulative net changes, removal
tombstones, replayed contributing changes, and source traces.

#### Scenario: Compare base to 2027
- **WHEN** a selection resolves through `2027` with `compare_from=base`
- **THEN** it returns the complete 2027 state, net additions/modifications/moves/
  removals, tombstones, contributing history, and source links

#### Scenario: Reject a later comparison origin
- **WHEN** `compare_from` identifies a point after the selected endpoint
- **THEN** validation fails with both comparison and endpoint identities

### Requirement: Focus does not change resolution
Focus SHALL highlight one or more contributing changes within the selected
resolved state without changing roadmap order, endpoint, or comparison range.
Later changes SHALL be focusable only with future context enabled, and later
overrides to focused contributions SHALL be disclosed.

#### Scenario: Focus 2027 in the 2028 state
- **WHEN** the selection resolves through `2028` with `focus=[2027]`
- **THEN** the complete 2028 state is retained, the 2027 contribution is
  highlighted, and the later 2028 modification to C is disclosed

#### Scenario: Reject future focus by default
- **WHEN** a selection at 2027 focuses change 2028 without future context
- **THEN** validation rejects the inapplicable focus

### Requirement: Browse canonical roadmap-wide selectors
`browse_by` SHALL accept `system`, `system_group`, `change`, `change_group`, or
`tag`. System subjects SHALL exist in the roadmap-wide selector index even when
not present at the selected snapshot. Change subjects SHALL occur on the
selected roadmap and SHALL use the impacted-system index; explicit focus values
add highlights without grouping or merging changes. Every selector kind SHALL
use union semantics and preserve the other solution axes.

#### Scenario: Browse stable and changed systems
- **WHEN** the user selects system browsing at the 2027 state
- **THEN** systems are indexed by stable identity with status, related changes,
  interfaces, and structural drill-down

#### Scenario: Browse year changes independently
- **WHEN** the roadmap contains changes 2027 and 2028
- **THEN** the change browser presents each as an independent entry with its
  order, metadata, affected systems, and net summary

#### Scenario: Browse a future system at an earlier snapshot
- **WHEN** system I exists later on the roadmap but base is selected
- **THEN** I remains selectable and the solution reports an empty, not-yet-present scope

### Requirement: Visibility and contextual status
The projection SHALL assign `out_of_scope`, `future`, `new`, `change`,
`no_change`, or `decommission` as contextual status and SHALL apply
`visibility` and `display_statuses` before layout. `all` SHALL show the complete
selected state plus explicitly requested future/tombstone context;
`changes_only` SHALL show mutations; `changes_with_context` SHALL add required
ancestors, endpoints, and immediate stable neighbors.

#### Scenario: Default system and change visibility
- **WHEN** no visibility is supplied
- **THEN** system browsing defaults to `all` while change browsing or explicit
  focus defaults to `changes_with_context`

#### Scenario: Hide stable systems without layout gaps
- **WHEN** the user selects `changes_only`
- **THEN** stable unrelated entities are removed before layout and the diagram
  has no orphaned containers, dangling edges, or hidden-node gaps

#### Scenario: Include useful stable context
- **WHEN** the user selects `changes_with_context`
- **THEN** required stable ancestors, endpoints, and immediate neighbors remain
  marked `no_change` while unrelated stable content is excluded

### Requirement: Exact transition status semantics
Every visible node and edge SHALL expose product status exactly as `No Change`,
`Changed`, `Added`, or `Removed`. Internal context such as future, focus, or
decommission SHALL remain separate and SHALL NOT replace product status. A
roadmap snapshot SHALL compare only with its immediate predecessor; unchanged
entities SHALL reset to `No Change` at the next transition.

#### Scenario: Reset status after a later unchanged transition
- **WHEN** system A changes at order 1 and is untouched at order 2
- **THEN** A is `Changed` at order 1 and `No Change` at order 2

#### Scenario: Preserve cascade removal status
- **WHEN** system removal cascades to a descendant and interface
- **THEN** the system, descendant, and interface are all `Removed` in that transition

### Requirement: Future and tombstone context are explicit
Entities added after the selected point SHALL be absent unless
`include_future=true`; removed content needed for comparisons or change focus
SHALL appear as source-traced tombstones rather than members of the complete
resolved state.

#### Scenario: Show I only as requested future context
- **WHEN** I is added in 2028 and the selected endpoint is 2027
- **THEN** I is absent by default and appears with status `future` only when
  future context is explicitly enabled

#### Scenario: Render a removed interface tombstone
- **WHEN** a comparison includes cascade removal of interface `A-to-D`
- **THEN** the resolved state excludes it while the comparison projection can
  display a source-traced `decommission` tombstone

### Requirement: Every included roadmap order is prepared offline
The generated selection set SHALL contain server-resolved `ViewGraph` data for
base and every included valid roadmap order. Browser selection SHALL NOT
reimplement replay. Explicitly restricted generation SHALL list unavailable
orders.

#### Scenario: Switch base, 2027, and 2028 offline
- **WHEN** the default explorer is generated for the canonical roadmap and
  network access is blocked
- **THEN** the user can switch among prepared base, 2027, and 2028 data without
  executing replay in the browser
