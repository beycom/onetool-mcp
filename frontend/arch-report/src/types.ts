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
  from?: string
  until?: string
  system?: string
  subsystem?: string
  provider?: string
  consumer?: string
  source?: string
  target?: string
  call_direction?: string
  data_flow?: string
  intervals: RowIntervals[]
}

export type Timeline = { id: string | null; milestones: string[] }
export type RowKind = 'systems' | 'subsystems' | 'components' | 'users' | 'interfaces' | 'relationships'
export type ReportPayload = {
  payload: 'arch-report/v1'
  schema_version: 3
  source: string
  milestones: Array<Omit<ReportRow, 'intervals'>>
  timelines: Timeline[]
  rows: Record<RowKind, ReportRow[]>
}

export type View = { timeline: number; position: number; level: 'systems' }
export type ProjectedState = {
  systems: ReportRow[]
  interfaces: ReportRow[]
  relationships: ReportRow[]
}
