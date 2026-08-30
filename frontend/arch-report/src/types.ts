export const KINDS = [
  'systems',
  'subsystems',
  'containers',
  'components',
  'code',
  'users',
  'interfaces',
  'relationships',
] as const

export const ENTITY_KINDS = ['systems', 'subsystems', 'containers', 'components', 'code', 'users'] as const

export type Bound = number | null
export type LiveSegment = [number, Bound]
export type ClipSegment = { start: number; end: Bound; by: string }
export type RowIntervals = { live: LiveSegment[]; clips: ClipSegment[] }

export type ReportRow = {
  id: string
  name?: string
  action?: string
  description?: string
  tags?: string[]
  properties?: Record<string, string | string[]>
  start_in?: string
  end_in?: string
  parent?: string
  container?: string
  component?: string
  provider?: string
  consumer?: string
  source?: string
  target?: string
  call_direction?: string
  data_flow_direction?: string
  intervals: RowIntervals[]
}

export type Timeline = { id: string | null; milestones: string[] }
export type RowKind = typeof KINDS[number]
export type EntityKind = typeof ENTITY_KINDS[number]
export type Level = 'systems' | 'subsystems' | 'containers' | 'components'
export type Aspect = 'ownership' | 'call-direction' | 'data-flow'
export type Theme = 'light' | 'dark'
export type CompareMode = 'off' | 'base' | 'position'
export type ThemeKind = 'system' | 'subsystem' | 'container' | 'component' | 'code' | 'user'
export type PresentationTheme = { kinds?: Partial<Record<ThemeKind, string>> }
export type LayoutMethod = 'layered' | 'radial' | 'grid'
export type AuthoredLayout = {
  method?: unknown
  direction?: unknown
  spacing?: unknown
  ranking?: unknown
  user_choice?: unknown
  [key: string]: unknown
}

export type ReportPayload = {
  payload: 'arch-report/v1'
  schema_version: 3
  source: string
  milestones: Array<Omit<ReportRow, 'intervals'>>
  timelines: Timeline[]
  theme: PresentationTheme
  layout?: AuthoredLayout
  rows: Record<RowKind, ReportRow[]>
}

export type RowRef = { kind: RowKind; row: ReportRow }
export type ClipRef = RowRef & { by: string }
export type ProjectedState = {
  rows: Record<RowKind, ReportRow[]>
  clips: Record<RowKind, Map<string, ClipRef>>
}

export type DiffItem = { kind: RowKind; id: string; name: string }
export type RemovedItem = DiffItem & { clipped_by: string | null }
export type FieldChange = { field: string; old: unknown; new: unknown }
export type ChangedItem = { kind: RowKind; id: string; changes: FieldChange[] }
export type StateDiff = {
  added: DiffItem[]
  removed: RemovedItem[]
  changed: ChangedItem[]
}

export type ScopeSelection = { systems: string[]; hops: number } | null
export type ScopedState = ProjectedState & {
  boundaryStubs: Map<string, RowRef>
  entityLookup: Map<string, RowRef>
  keptRepresentatives: Set<string>
}

export type GraphNode = {
  key: string
  kind: EntityKind
  row: ReportRow
  boundary: boolean
  members: RowRef[]
}

export type GraphBoundary = {
  key: string
  nodeKey: string
  kind: EntityKind
  row: ReportRow
  parentKey: string | null
  childKeys: string[]
  stub: boolean
}

export type GraphEdge = {
  key: string
  a: string
  b: string
  interfaces: string[]
  relationships: string[]
  interfaceRows: ReportRow[]
  relationshipRows: ReportRow[]
  orientations: Array<{ kind: 'interfaces' | 'relationships'; id: string; from: string; to: string }>
}

export type RolledGraph = {
  nodes: GraphNode[]
  edges: GraphEdge[]
  boundaries: GraphBoundary[]
  state: ScopedState
}

export type View = {
  timeline: number
  position: number
  expand: string[]
  scope: ScopeSelection
  compare: CompareMode
  comparePosition: number
  aspect: Aspect
  deps: string | null
  lens: string[]
  theme: Theme
  layout: LayoutMethod | null
}

export type ProjectedView = RolledGraph & {
  rawState: ProjectedState
}
