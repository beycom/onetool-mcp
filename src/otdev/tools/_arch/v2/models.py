"""Typed schema-v2 architecture, replay, selection, and presentation models."""

from __future__ import annotations

from datetime import date  # noqa: TC003 - Pydantic resolves this annotation at runtime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
EntityKind = Literal["system", "application", "component", "interface", "user", "relationship"]
OperationKind = Literal["add", "modify", "move", "remove"]
ArchitectureLevel = Literal["system", "application", "component"]
ColorBy = Literal["change_status", "integration_type", "tag"]
EdgeDirection = Literal[
    "provider_to_consumer",
    "consumer_to_provider",
    "forward",
    "reverse",
    "bidirectional",
]
ContextStatus = Literal[
    "out_of_scope",
    "future",
    "new",
    "change",
    "no_change",
    "decommission",
]
TransitionStatus = Literal["No Change", "Changed", "Added", "Removed"]
ImpactReasonCode = Literal[
    "system_patch",
    "application_owner",
    "component_owner",
    "interface_provider",
    "interface_consumer",
    "relationship_source",
    "relationship_target",
    "moved_from",
    "moved_to",
    "cascade_removal",
]


class StrictModel(BaseModel):
    """Base for typed schema objects that reject unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ExtensibleModel(BaseModel):
    """Base for authored objects that preserve extension metadata."""

    model_config = ConfigDict(extra="allow")


class SourceLocation(StrictModel):
    """Complete YAML, Excel, or generated-source location."""

    kind: Literal["yaml", "excel", "generated"]
    path: str
    yaml_path: str | None = None
    workbook: str | None = None
    sheet: str | None = None
    row: int | None = Field(default=None, ge=1)
    column: str | None = None
    generated_from: list[SourceLocation] = Field(default_factory=list)


class ElementStyle(StrictModel):
    """Supported typed element and view style fields."""

    icon: str | None = None
    shape: str | None = None
    color: str | None = None
    size: str | None = None
    position: str | None = None
    node_size: str | None = None
    padding: int | None = Field(default=None, ge=0)
    text_size: int | None = Field(default=None, ge=1)
    opacity: float | None = Field(default=None, ge=0, le=1)
    border: str | None = None
    multiple: bool | None = None


class EntityBase(ExtensibleModel):
    """Fields shared by complete architecture entities."""

    id: Identifier
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    icon: str | None = None
    style: ElementStyle | None = None
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    source: SourceLocation | None = None


class System(EntityBase):
    """Complete architecture system."""

    group: list[str] = Field(default_factory=list)


class Application(EntityBase):
    """Complete application contained by a system."""

    system: Identifier
    technology: str | None = None


class Component(EntityBase):
    """Complete component contained by an application."""

    application: Identifier
    technology: str | None = None


class User(EntityBase):
    """Complete user or actor."""

    kind: str | None = None


class Interface(EntityBase):
    """Complete directed interface between canonical endpoints."""

    provider: Identifier
    consumer: Identifier
    direction: Literal["provider_to_consumer", "consumer_to_provider", "bidirectional"] = (
        "provider_to_consumer"
    )
    type: str | None = None
    technology: str | None = None


class Relationship(EntityBase):
    """Complete non-interface relationship."""

    source_id: Identifier
    target_id: Identifier
    direction: Literal["forward", "reverse", "bidirectional"] = "forward"
    type: str | None = None


class CompleteState(ExtensibleModel):
    """Complete authored, resolved, materialized, or archived architecture state."""

    id: Identifier
    name: str | None = None
    description: str | None = None
    systems: list[System] = Field(default_factory=list)
    applications: list[Application] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
    users: list[User] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    source: SourceLocation | None = None


class PatchBase(ExtensibleModel):
    """Sparse patch common fields; omitted values are no-ops."""

    id: Identifier
    change_type: Literal["added", "changed", "removed"] | None = None
    unset: list[str] = Field(default_factory=list)
    change_note: str | None = None
    expected: dict[str, JsonValue] = Field(default_factory=dict)
    source: SourceLocation | None = None


class ElementPatch(PatchBase):
    """Sparse system, application, component, or user patch."""

    name: str | None = None
    description: str | None = None
    parent: Identifier | None = None
    technology: str | None = None
    tags: list[str] | None = None
    group: list[str] | None = None
    notes: str | None = None
    icon: str | None = None
    style: ElementStyle | None = None
    properties: dict[str, JsonValue] | None = None


class InterfacePatch(PatchBase):
    """Sparse interface patch."""

    name: str | None = None
    description: str | None = None
    provider: Identifier | None = None
    consumer: Identifier | None = None
    direction: Literal["provider_to_consumer", "consumer_to_provider", "bidirectional"] | None = (
        None
    )
    type: str | None = None
    technology: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    properties: dict[str, JsonValue] | None = None


class RelationshipPatch(PatchBase):
    """Sparse relationship patch."""

    name: str | None = None
    description: str | None = None
    source_id: Identifier | None = None
    target_id: Identifier | None = None
    direction: Literal["forward", "reverse", "bidirectional"] | None = None
    type: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    properties: dict[str, JsonValue] | None = None


class ChangePatches(StrictModel):
    """Sparse patches grouped by canonical entity kind."""

    systems: list[ElementPatch] = Field(default_factory=list)
    applications: list[ElementPatch] = Field(default_factory=list)
    components: list[ElementPatch] = Field(default_factory=list)
    interfaces: list[InterfacePatch] = Field(default_factory=list)
    users: list[ElementPatch] = Field(default_factory=list)
    relationships: list[RelationshipPatch] = Field(default_factory=list)


class Change(ExtensibleModel):
    """Stable metadata-bearing sparse delivery change."""

    id: Identifier
    name: str
    description: str | None = None
    deliver_date: date | None = None
    delivery_lead: str | None = None
    related_products: list[str] = Field(default_factory=list)
    owner: str | None = None
    status: str | None = None
    tags: list[str] = Field(default_factory=list)
    group: list[str] = Field(default_factory=list)
    depends_on: list[Identifier] = Field(default_factory=list)
    patches: ChangePatches = Field(default_factory=ChangePatches)
    source: SourceLocation | None = None


class RoadmapItem(StrictModel):
    """One explicitly ordered change in a linear roadmap."""

    change: Identifier
    order: int = Field(ge=1)
    source: SourceLocation | None = None


class Roadmap(ExtensibleModel):
    """Named linear roadmap over one complete base state."""

    id: Identifier
    name: str | None = None
    base: Identifier
    items: list[RoadmapItem]
    source: SourceLocation | None = None


class SystemSetSelector(StrictModel):
    """Union of reusable selectors that resolve to one canonical system set."""

    systems: list[Identifier] = Field(default_factory=list)
    system_groups: list[Identifier] = Field(default_factory=list)
    changes: list[Identifier] = Field(default_factory=list)
    change_groups: list[Identifier] = Field(default_factory=list)
    tags: list[Identifier] = Field(default_factory=list)


type BrowseKind = Literal["system", "system_group", "change", "change_group", "tag"]


class ViewSelection(StrictModel):
    """Shared selection grammar for saved and ad hoc views."""

    state: Identifier | None = None
    roadmap: Identifier | None = None
    through: Identifier | Literal["base"] | None = None
    order: int | None = Field(default=None, ge=0)
    compare_from: Identifier | Literal["base"] | int | None = None
    focus: list[Identifier] = Field(default_factory=list)
    browse_by: BrowseKind | None = None
    subject: Identifier | None = None
    system_set: SystemSetSelector = Field(default_factory=SystemSetSelector)
    interface_depth: int = Field(default=0, ge=0)
    visibility: Literal["all", "changes_only", "changes_with_context"] | None = None
    display_statuses: list[ContextStatus] = Field(default_factory=list)
    include_future: bool = False
    projection: str | None = None
    diagram: Identifier | None = None
    level: ArchitectureLevel = "system"
    color_by: ColorBy = "change_status"
    theme: Identifier | None = None

    @model_validator(mode="after")
    def validate_selector_combinations(self) -> ViewSelection:
        """Reject mutually exclusive and authored-state-only combinations."""
        if self.state is not None and self.roadmap is not None:
            raise ValueError("state and roadmap are mutually exclusive")
        if self.through is not None and self.order is not None:
            raise ValueError("through and order are mutually exclusive")
        if self.state is not None:
            invalid = []
            if self.through is not None:
                invalid.append("through")
            if self.order is not None:
                invalid.append("order")
            if self.focus:
                invalid.append("focus")
            if self.include_future:
                invalid.append("include_future")
            if invalid:
                raise ValueError(
                    "authored-state selection cannot use roadmap fields: " + ", ".join(invalid)
                )
        return self


class SavedView(ViewSelection):
    """Named reusable selection."""

    id: Identifier
    name: str | None = None
    description: str | None = None
    source: SourceLocation | None = None


class DiagramVariant(StrictModel):
    """One stable diagram representation variant."""

    id: Identifier
    kind: Literal["diagram", "sequence"]
    source: str | None = None


class DiagramCatalogEntry(ExtensibleModel):
    """Generated, view-only LikeC4, or local external diagram entry."""

    id: Identifier
    name: str
    kind: Literal["generated", "static", "dynamic", "external"]
    source: str | None = None
    likec4_view: Identifier | None = None
    variants: list[DiagramVariant] = Field(default_factory=list)
    folder: str | None = None
    systems: list[Identifier] = Field(default_factory=list)
    changes: list[Identifier] = Field(default_factory=list)
    source_location: SourceLocation | None = None


class Theme(StrictModel):
    """Typed workspace presentation theme."""

    id: Identifier
    name: str | None = None
    extends: Identifier | None = None
    elements: dict[str, ElementStyle] = Field(default_factory=dict)
    statuses: dict[ContextStatus, ElementStyle] = Field(default_factory=dict)


class ChangeStatusColors(StrictModel):
    """Colors for the four authored change states of one entity kind."""

    no_change: ElementStyle = Field(
        default_factory=lambda: ElementStyle(color="#D5E8D4", border="#82B366 solid")
    )
    changed: ElementStyle = Field(
        default_factory=lambda: ElementStyle(color="#FFF2CC", border="#D6B656 solid")
    )
    added: ElementStyle = Field(
        default_factory=lambda: ElementStyle(color="#DAE8FC", border="#6C8EBF double")
    )
    removed: ElementStyle = Field(
        default_factory=lambda: ElementStyle(color="#F8CECC", border="#B85450 double")
    )


class ChangeStatusPalette(StrictModel):
    """Per-kind change-status palette."""

    system: ChangeStatusColors = Field(default_factory=ChangeStatusColors)
    application: ChangeStatusColors = Field(default_factory=ChangeStatusColors)
    component: ChangeStatusColors = Field(default_factory=ChangeStatusColors)
    interface: ChangeStatusColors = Field(default_factory=ChangeStatusColors)


class ColorPalettes(StrictModel):
    """Configurable palettes for each diagram coloring mode."""

    change_status: ChangeStatusPalette = Field(default_factory=ChangeStatusPalette)
    integration_type: dict[str, ElementStyle] = Field(default_factory=dict)
    tag: dict[str, ElementStyle] = Field(default_factory=dict)


class TableColumnConfig(StrictModel):
    """Typed table-column default."""

    id: Identifier
    visible: bool = True
    pinned: Literal["left", "right"] | None = None
    width: int | None = Field(default=None, ge=40)
    order: int | None = Field(default=None, ge=0)


class TableConfig(StrictModel):
    """Typed table defaults persisted by schema version."""

    id: Identifier
    schema_version: int = Field(ge=1)
    density: Literal["comfortable", "compact"] = "comfortable"
    columns: list[TableColumnConfig] = Field(default_factory=list)


class Presentation(StrictModel):
    """Workspace presentation defaults and typed themes/tables."""

    title: str = "Architecture Explorer"
    default_roadmap: Identifier | None = None
    default_theme: Identifier = "clean"
    default_selection: ViewSelection = Field(default_factory=ViewSelection)
    palettes: ColorPalettes = Field(default_factory=ColorPalettes)
    themes: list[Theme] = Field(default_factory=list)
    tables: list[TableConfig] = Field(default_factory=list)


class ArchitectureWorkspace(StrictModel):
    """Complete schema-v2 architecture workspace."""

    schema_version: Literal[2]
    states: list[CompleteState]
    changes: list[Change] = Field(default_factory=list)
    roadmaps: list[Roadmap] = Field(default_factory=list)
    views: list[SavedView] = Field(default_factory=list)
    diagrams: list[DiagramCatalogEntry] = Field(default_factory=list)
    presentation: Presentation = Field(default_factory=Presentation)


class LoadedWorkspace(StrictModel):
    """Production-loaded workspace with a path-complete source index."""

    workspace: ArchitectureWorkspace
    format: Literal["yaml", "excel"]
    path: str
    sources: dict[str, SourceLocation] = Field(default_factory=dict)


class OperationPrecondition(StrictModel):
    """Replay precondition for a normalized operation."""

    kind: Literal["absent", "present", "field_equals", "parent_exists", "endpoint_exists"]
    field: str | None = None
    expected: JsonValue | None = None


class NormalizedOperation(StrictModel):
    """Format-independent normalized architecture mutation."""

    id: Identifier
    kind: OperationKind
    entity_kind: EntityKind
    entity_id: Identifier
    change_id: Identifier
    values: dict[str, JsonValue] = Field(default_factory=dict)
    unset: list[str] = Field(default_factory=list)
    from_parent: Identifier | None = None
    to_parent: Identifier | None = None
    preconditions: list[OperationPrecondition] = Field(default_factory=list)
    generated: bool = False
    initiating_ancestor: Identifier | None = None
    cascade_path: list[Identifier] = Field(default_factory=list)
    cause: str | None = None
    source: SourceLocation | None = None


class Tombstone(StrictModel):
    """Source-traced removed entity retained for comparison or focus."""

    entity_kind: EntityKind
    entity_id: Identifier
    value: dict[str, JsonValue]
    removed_by: Identifier
    operation_id: Identifier
    source: SourceLocation | None = None


class ContributingHistory(StrictModel):
    """Applied change and operation history for a resolved state."""

    roadmap_id: Identifier
    order: int = Field(ge=1)
    change_id: Identifier
    operations: list[NormalizedOperation]


class NormalizedChange(StrictModel):
    """Format-independent change operations and diagnostics input."""

    change_id: Identifier
    operations: list[NormalizedOperation]


class ResolvedState(StrictModel):
    """Complete state produced at a validated roadmap order."""

    state: CompleteState
    roadmap_id: Identifier
    order: int = Field(ge=0)
    through: Identifier | Literal["base"]
    history: list[ContributingHistory] = Field(default_factory=list)
    tombstones: list[Tombstone] = Field(default_factory=list)


class StateComparison(StrictModel):
    """Stable-ID net difference between two complete states."""

    base_state_id: Identifier
    target_state_id: Identifier
    change: NormalizedChange
    contributing_history: list[ContributingHistory] = Field(default_factory=list)
    canceled_history: list[NormalizedOperation] = Field(default_factory=list)


class ResolvedSelection(StrictModel):
    """Normalized selection with stable identity and explicit defaults."""

    id: Identifier
    selection: ViewSelection
    state_id: Identifier
    roadmap_id: Identifier | None = None
    order: int | None = None
    through: Identifier | Literal["base"] | None = None


class ViewGraphNode(StrictModel):
    """Renderer-neutral architecture node with stable canonical identity."""

    id: Identifier
    entity_kind: EntityKind
    name: str
    parent: Identifier | None = None
    children: list[Identifier] = Field(default_factory=list)
    status: TransitionStatus
    context_status: ContextStatus
    tombstone: bool = False
    future: bool = False
    tags: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    icon: str | None = None
    style: ElementStyle | None = None
    related_changes: list[Identifier] = Field(default_factory=list)
    source: SourceLocation | None = None
    properties: dict[str, JsonValue] = Field(default_factory=dict)


class ViewGraphEdge(StrictModel):
    """Renderer-neutral interface or relationship with stable endpoints."""

    id: Identifier
    entity_kind: Literal["interface", "relationship"]
    name: str
    description: str | None = None
    source_id: Identifier
    target_id: Identifier
    direction: EdgeDirection
    status: TransitionStatus
    context_status: ContextStatus
    tombstone: bool = False
    future: bool = False
    tags: list[str] = Field(default_factory=list)
    integration_type: str | None = None
    interface_ids: list[Identifier] = Field(default_factory=list)
    related_changes: list[Identifier] = Field(default_factory=list)
    style: ElementStyle | None = None
    source: SourceLocation | None = None
    properties: dict[str, JsonValue] = Field(default_factory=dict)


class SystemImpactReason(StrictModel):
    """One deterministic reason a roadmap change affects a system."""

    code: ImpactReasonCode
    change_id: Identifier
    operation_id: Identifier
    entity_kind: EntityKind
    entity_id: Identifier


class ChangeBrowseEntry(StrictModel):
    """Independent roadmap change entry for navigation and reporting."""

    id: Identifier
    name: str
    order: int = Field(ge=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    affected_systems: list[Identifier] = Field(default_factory=list)
    impact_reasons: dict[Identifier, list[SystemImpactReason]] = Field(default_factory=dict)
    operation_counts: dict[OperationKind, int] = Field(default_factory=dict)
    source: SourceLocation | None = None


class ViewGraph(StrictModel):
    """Deterministic renderer boundary prepared fully in Python."""

    id: Identifier
    selection: ResolvedSelection
    resolved_state: CompleteState
    nodes: list[ViewGraphNode] = Field(default_factory=list)
    containers: list[Identifier] = Field(default_factory=list)
    edges: list[ViewGraphEdge] = Field(default_factory=list)
    changes: list[ChangeBrowseEntry] = Field(default_factory=list)
    comparison: StateComparison | None = None
    tombstones: list[Tombstone] = Field(default_factory=list)
    focus: list[Identifier] = Field(default_factory=list)
    focus_overrides: list[NormalizedOperation] = Field(default_factory=list)
    diagram_ids: list[Identifier] = Field(default_factory=list)
    hints: dict[str, JsonValue] = Field(default_factory=dict)


class PreparedViewGraphs(StrictModel):
    """Server-prepared roadmap orders and any explicitly unavailable points."""

    roadmap_id: Identifier
    graphs: dict[str, ViewGraph]
    unavailable_orders: list[int] = Field(default_factory=list)


class SolutionSelectionIndexes(StrictModel):
    """Snapshot-aware indexes used to resolve arbitrary system sets locally."""

    systems: list[Identifier] = Field(default_factory=list)
    system_groups: dict[str, list[Identifier]] = Field(default_factory=dict)
    changes: dict[str, list[Identifier]] = Field(default_factory=dict)
    change_groups: dict[str, list[Identifier]] = Field(default_factory=dict)
    change_impacts: dict[str, dict[Identifier, list[SystemImpactReason]]] = Field(
        default_factory=dict
    )
    change_group_impacts: dict[str, dict[Identifier, list[SystemImpactReason]]] = Field(
        default_factory=dict
    )
    tags: dict[str, list[Identifier]] = Field(default_factory=dict)


class PreparedSolutionSnapshots(StrictModel):
    """Validated full-graph roadmap snapshots plus reusable selection indexes."""

    roadmap_id: Identifier
    snapshots: dict[str, ViewGraph]
    indexes: dict[str, SolutionSelectionIndexes]
    system_presence: dict[Identifier, list[int]] = Field(default_factory=dict)
    unavailable_orders: list[int] = Field(default_factory=list)


class BoundaryInterface(StrictModel):
    """Interface touching the projected boundary without expanding its system."""

    interface: ViewGraphEdge
    inside_system: Identifier
    inside_endpoint: Identifier
    outside_system: Identifier | None = None
    outside_endpoint: Identifier


class CollapsedInterface(StrictModel):
    """Canonical interface retained after both endpoints roll up to one node."""

    interface: ViewGraphEdge
    visible_node: Identifier
    reason: Literal["collapsed_within_visible_node"] = "collapsed_within_visible_node"


class ProjectionDiagnostic(StrictModel):
    """Renderer-neutral projection warning with canonical identity."""

    code: Literal["unresolved_interface_endpoint", "unresolved_relationship_endpoint"]
    message: str
    entity_id: Identifier
    endpoint_id: Identifier


class AbsentSelectedSystem(StrictModel):
    """Stable selected system that is not present in the snapshot after-state."""

    system_id: Identifier
    state: Literal["not_yet_present", "no_longer_present", "not_present"]
    message: str = "not present at this snapshot"


class SolutionProjection(StrictModel):
    """One locally derivable system-set/snapshot/depth/level projection."""

    cache_key: str
    snapshot_id: Identifier
    selector: SystemSetSelector
    selected_systems: list[Identifier]
    included_systems: list[Identifier]
    system_distances: dict[Identifier, int] = Field(default_factory=dict)
    absent_systems: list[AbsentSelectedSystem] = Field(default_factory=list)
    interface_depth: int = Field(ge=0)
    level: ArchitectureLevel
    graph: ViewGraph
    internal_interfaces: list[ViewGraphEdge] = Field(default_factory=list)
    boundary_interfaces: list[BoundaryInterface] = Field(default_factory=list)
    collapsed_interfaces: list[CollapsedInterface] = Field(default_factory=list)
    diagnostics: list[ProjectionDiagnostic] = Field(default_factory=list)


class LayoutPoint(StrictModel):
    """Renderer-neutral absolute layout coordinate."""

    x: float
    y: float


class LayoutBounds(LayoutPoint):
    """Renderer-neutral absolute rectangular bounds."""

    width: float = Field(ge=0)
    height: float = Field(ge=0)


class SolutionLayoutNode(StrictModel):
    """Canonical node geometry independent of the active renderer."""

    id: Identifier
    parent: Identifier | None = None
    bounds: LayoutBounds


class SolutionLayoutEdge(StrictModel):
    """Renderer-neutral routed edge geometry with canonical membership when known."""

    id: Identifier
    source: Identifier
    target: Identifier
    route: list[LayoutPoint]
    interface_ids: list[Identifier] = Field(default_factory=list)
    label: str | None = None


class SolutionLayoutResult(StrictModel):
    """Canonical renderer-neutral geometry for one normalized solution."""

    request_id: Identifier
    graph_id: Identifier
    selection_id: Identifier
    nodes: list[SolutionLayoutNode]
    edges: list[SolutionLayoutEdge]
    bounds: LayoutBounds
    diagnostics: list[str] = Field(default_factory=list)


SelectionInput = str | dict[str, Any] | ViewSelection
