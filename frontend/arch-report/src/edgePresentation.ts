import type { ReadingDepth } from './zoom'
import type { Aspect, GraphEdge, ReportRow, RowKind } from './types'
import type { EdgeAnchorPair, EdgePoint } from './edgeAnchors'

export type SplineDirection = 'forward' | 'reverse'
export type DirectionalMember = {
  kind: 'interfaces' | 'relationships'
  providerKey: string | null
  row: ReportRow
}
export type DirectionalSpline = {
  direction: SplineDirection
  id: string
  label: string
  members: DirectionalMember[]
  source: string
  target: string
}
export type NodeEmphasis = 'normal' | 'emphasized' | 'neighbor' | 'unrelated'
export type EdgeEmphasis = 'normal' | 'outgoing' | 'incoming' | 'neighbor' | 'unrelated'
export type EmphasisResult = {
  edges: Record<string, EdgeEmphasis>
  nodes: Record<string, NodeEmphasis>
}
export type InterfacePort = { count: number; label: string; point: EdgePoint }

function rowLabel(row: ReportRow): string {
  return row.name ?? row.action ?? row.id
}

function storedDirection(edge: GraphEdge, from: string, to: string): SplineDirection | null {
  if (from === edge.a && to === edge.b) return 'forward'
  if (from === edge.b && to === edge.a) return 'reverse'
  return null
}

export function splitEdgeDirections(edge: GraphEdge, aspect: Aspect): DirectionalSpline[] {
  const rows: Record<'interfaces' | 'relationships', Map<string, ReportRow>> = {
    interfaces: new Map(edge.interfaceRows.map((row) => [row.id, row])),
    relationships: new Map(edge.relationshipRows.map((row) => [row.id, row])),
  }
  const groups = new Map<SplineDirection, Map<string, DirectionalMember>>([
    ['forward', new Map()],
    ['reverse', new Map()],
  ])
  const add = (direction: SplineDirection, member: DirectionalMember) => {
    groups.get(direction)!.set(`${member.kind}:${member.row.id}`, member)
  }

  for (const orientation of edge.orientations) {
    const row = rows[orientation.kind].get(orientation.id)
    const base = storedDirection(edge, orientation.from, orientation.to)
    if (!row || !base) continue
    const member: DirectionalMember = {
      kind: orientation.kind,
      providerKey: orientation.kind === 'interfaces' ? orientation.from : null,
      row,
    }
    if (aspect === 'ownership' || orientation.kind === 'relationships') {
      add(base, member)
      continue
    }
    const field = aspect === 'call-direction' ? 'call_direction' : 'data_flow_direction'
    const configured = row[field] ?? (aspect === 'call-direction' ? 'consumer_to_provider' : 'provider_to_consumer')
    if (configured === 'provider_to_consumer' || configured === 'bidirectional') add(base, member)
    if (configured === 'consumer_to_provider' || configured === 'bidirectional') {
      add(base === 'forward' ? 'reverse' : 'forward', member)
    }
  }

  return (['forward', 'reverse'] as const).flatMap((direction) => {
    const members = [...groups.get(direction)!.values()]
    if (!members.length) return []
    const source = direction === 'forward' ? edge.a : edge.b
    const target = direction === 'forward' ? edge.b : edge.a
    return [{
      direction,
      id: `${edge.key}:${direction}`,
      label: rowLabel(members[0].row),
      members,
      source,
      target,
    }]
  })
}

export function edgeLabelVisible(depth: ReadingDepth, selected: boolean, hovered: boolean): boolean {
  return depth !== 'far' || selected || hovered
}

export function edgeStrokeToken(emphasis: EdgeEmphasis | 'selected', statuses: string[]): string {
  if (emphasis === 'outgoing' || emphasis === 'incoming' || emphasis === 'selected') return 'var(--accent)'
  if (statuses.includes('removed')) return 'var(--diff-removed)'
  if (statuses.includes('changed')) return 'var(--diff-changed)'
  if (statuses.includes('added')) return 'var(--diff-edge-added)'
  return 'var(--edge)'
}

export function classifyEmphasis(
  nodeKeys: string[],
  splines: Array<Pick<DirectionalSpline, 'id' | 'source' | 'target'>>,
  selectedKey: string | null,
  tagMatches: ReadonlySet<string>,
): EmphasisResult {
  const nodes: Record<string, NodeEmphasis> = {}
  const edges: Record<string, EdgeEmphasis> = {}
  if (selectedKey) {
    const neighbors = new Set(splines.flatMap((spline) => spline.source === selectedKey
      ? [spline.target] : spline.target === selectedKey ? [spline.source] : []))
    for (const key of nodeKeys) nodes[key] = key === selectedKey
      ? 'emphasized' : neighbors.has(key) ? 'neighbor' : 'unrelated'
    for (const spline of splines) edges[spline.id] = spline.source === selectedKey
      ? 'outgoing' : spline.target === selectedKey ? 'incoming' : 'unrelated'
    return { edges, nodes }
  }
  if (tagMatches.size) {
    for (const key of nodeKeys) nodes[key] = tagMatches.has(key) ? 'emphasized' : 'unrelated'
    for (const spline of splines) edges[spline.id] = tagMatches.has(spline.source) || tagMatches.has(spline.target)
      ? 'neighbor' : 'unrelated'
    return { edges, nodes }
  }
  for (const key of nodeKeys) nodes[key] = 'normal'
  for (const spline of splines) edges[spline.id] = 'normal'
  return { edges, nodes }
}

export function interfacePort(spline: DirectionalSpline, anchors: EdgeAnchorPair): InterfacePort | null {
  const interfaces = [...new Map(spline.members.filter((member) => member.kind === 'interfaces')
    .map((member) => [member.row.id, member])).values()]
  const first = interfaces[0]
  if (!first) return null
  return {
    count: interfaces.length,
    label: rowLabel(first.row),
    point: first.providerKey === spline.source ? anchors.sourcePoint : anchors.targetPoint,
  }
}
