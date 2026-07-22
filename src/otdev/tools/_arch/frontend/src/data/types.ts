export type ContextStatus =
  | 'out_of_scope'
  | 'future'
  | 'new'
  | 'change'
  | 'no_change'
  | 'decommission'
export type TransitionStatus = 'No Change' | 'Changed' | 'Added' | 'Removed'

export type BrowseGroup = 'system' | 'system_group' | 'change' | 'change_group' | 'tag'
export type ArchitectureLevel = 'system' | 'application' | 'component'
export type ColorBy = 'change_status' | 'integration_type' | 'tag'
export type Density = 'comfortable' | 'compact'

export interface SourceLocation {
  kind: 'yaml' | 'excel' | 'generated'
  path: string
  yaml_path?: string
  workbook?: string
  sheet?: string
  row?: number
  column?: string
}

export interface ElementStyle {
  color?: string
  border?: string
  shape?: string
  opacity?: number
}

export interface ResolvedThemeConfig {
  elements: Record<string, ElementStyle>
  statuses: Record<ContextStatus, ElementStyle>
}

export interface ViewGraphNode {
  id: string
  entity_kind: 'system' | 'application' | 'component' | 'user'
  name: string
  parent?: string
  children: string[]
  status: TransitionStatus
  context_status: ContextStatus
  tombstone: boolean
  future: boolean
  tags: string[]
  groups: string[]
  icon?: string
  style?: ElementStyle
  related_changes: string[]
  source?: SourceLocation
  properties: Record<string, unknown>
}

export interface ViewGraphEdge {
  id: string
  entity_kind: 'interface' | 'relationship'
  name: string
  description?: string
  source_id: string
  target_id: string
  direction: 'provider_to_consumer' | 'consumer_to_provider' | 'forward' | 'reverse' | 'bidirectional'
  status: TransitionStatus
  context_status: ContextStatus
  tombstone: boolean
  future: boolean
  tags: string[]
  integration_type?: string
  interface_ids: string[]
  related_changes: string[]
  style?: ElementStyle
  source?: SourceLocation
  properties: Record<string, unknown>
}

export interface ViewSelection {
  state?: string
  roadmap?: string
  through?: string
  order?: number
  compare_from?: string | number
  focus: string[]
  browse_by?: BrowseGroup
  subject?: string
  system_set: SystemSetSelector
  interface_depth: number
  visibility?: 'all' | 'changes_only' | 'changes_with_context'
  display_statuses: ContextStatus[]
  include_future: boolean
  projection?: string
  diagram?: string
  level: ArchitectureLevel
  color_by: ColorBy
  theme?: string
}

export interface ChangeEntry {
  id: string
  name: string
  order: number
  metadata: Record<string, unknown>
  affected_systems: string[]
  impact_reasons: Record<string, SystemImpactReason[]>
  operation_counts: Partial<Record<'add' | 'modify' | 'move' | 'remove', number>>
  source?: SourceLocation
}

export type ImpactReasonCode =
  | 'system_patch'
  | 'application_owner'
  | 'component_owner'
  | 'interface_provider'
  | 'interface_consumer'
  | 'relationship_source'
  | 'relationship_target'
  | 'moved_from'
  | 'moved_to'
  | 'cascade_removal'

export interface SystemImpactReason {
  code: ImpactReasonCode
  change_id: string
  operation_id: string
  entity_kind: 'system' | 'application' | 'component' | 'interface' | 'user' | 'relationship'
  entity_id: string
}

export interface ViewGraph {
  id: string
  selection: {
    id: string
    state_id: string
    roadmap_id?: string
    order?: number
    through?: string
    selection: ViewSelection
  }
  resolved_state: { id: string }
  nodes: ViewGraphNode[]
  containers: string[]
  edges: ViewGraphEdge[]
  changes: ChangeEntry[]
  focus: string[]
  focus_overrides: unknown[]
  diagram_ids: string[]
  hints: Record<string, unknown>
}

export interface TableColumnConfig {
  id: string
  visible?: boolean
  pinned?: 'left' | 'right'
  width?: number
  order?: number
}

export interface TableConfig {
  id: string
  schema_version: number
  density: Density
  columns: TableColumnConfig[]
}

export interface DiagramVariant {
  id: string
  kind: 'diagram' | 'sequence'
  source?: string
}

export interface DiagramCatalogItem {
  id: string
  name: string
  kind: 'generated' | 'static' | 'dynamic' | 'external'
  source?: string
  likec4View?: string
  variants: DiagramVariant[]
  folder?: string
  systems: string[]
  changes: string[]
  attachmentId?: string
}

export interface DiagramAttachment {
  mediaType: string
  dataUrl: string
  size: number
}

export interface ExplorerData {
  schemaVersion: 1
  title: string
  initialGraphId: string
  graphs: ViewGraph[]
  likec4ViewByGraph: Record<string, string>
  canonicalToLikec4ByGraph: Record<string, Record<string, string>>
  likec4EdgeToCanonicalByGraph: Record<string, Record<string, string[]>>
  diagramCatalogByGraph: Record<string, DiagramCatalogItem[]>
  attachments: Record<string, DiagramAttachment>
  tableConfigs: TableConfig[]
  solutionSnapshots: Record<string, PreparedSolutionSnapshots>
  presentation: PresentationConfig
  unavailableOrders: number[]
  diagnostics: string[]
}

export interface SystemSetSelector {
  systems: string[]
  system_groups: string[]
  changes: string[]
  change_groups: string[]
  tags: string[]
}

export interface SolutionSelectionIndexes {
  systems: string[]
  system_groups: Record<string, string[]>
  changes: Record<string, string[]>
  change_groups: Record<string, string[]>
  change_impacts: Record<string, Record<string, SystemImpactReason[]>>
  change_group_impacts: Record<string, Record<string, SystemImpactReason[]>>
  tags: Record<string, string[]>
}

export interface PreparedSolutionSnapshots {
  roadmap_id: string
  snapshots: Record<string, ViewGraph>
  indexes: Record<string, SolutionSelectionIndexes>
  system_presence: Record<string, number[]>
  unavailable_orders: number[]
}

export interface AbsentSelectedSystem {
  system_id: string
  state: 'not_yet_present' | 'no_longer_present' | 'not_present'
  message: 'not present at this snapshot'
}

export interface BoundaryInterface {
  interface: ViewGraphEdge
  inside_system: string
  inside_endpoint: string
  outside_system?: string
  outside_endpoint: string
}

export interface CollapsedInterface {
  interface: ViewGraphEdge
  visible_node: string
  reason: 'collapsed_within_visible_node'
}

export interface ProjectionDiagnostic {
  code: 'unresolved_interface_endpoint' | 'unresolved_relationship_endpoint'
  message: string
  entity_id: string
  endpoint_id: string
}

export interface PresentationConfig {
  title: string
  default_roadmap?: string
  default_theme: string
  palettes: {
    change_status: Record<
      'system' | 'application' | 'component' | 'interface',
      Record<'no_change' | 'changed' | 'added' | 'removed', ElementStyle>
    >
    integration_type: Record<string, ElementStyle>
    tag: Record<string, ElementStyle>
  }
  resolved_themes: Record<string, ResolvedThemeConfig>
}
