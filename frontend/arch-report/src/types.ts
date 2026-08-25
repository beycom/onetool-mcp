export const KINDS = [
  'systems',
  'containers',
  'components',
  'code',
  'users',
  'interfaces',
  'relationships',
] as const

export const ENTITY_KINDS = ['systems', 'containers', 'components', 'code', 'users'] as const

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
export type Level = 'systems' | 'containers' | 'components'
export type Aspect = 'ownership' | 'call-direction' | 'data-flow'
export type DiagramMode = 'MAP' | 'PATH' | 'LENS'
export type Theme = 'light' | 'dark'
export type CompareMode = 'off' | 'base' | 'position'

export type ReportPayload = {
  payload: 'arch-report/v1'
  schema_version: 3
  source: string
  milestones: Array<Omit<ReportRow, 'intervals'>>
  timelines: Timeline[]
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
  state: ScopedState
}

export type View = {
  timeline: number
  position: number
  level: Level
  scope: ScopeSelection
  compare: CompareMode
  comparePosition: number
  aspect: Aspect
  mode: DiagramMode
  theme: Theme
}

export type ProjectedView = RolledGraph & {
  rawState: ProjectedState
}
