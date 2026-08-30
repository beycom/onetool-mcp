import type { RolledGraph } from '../types'
import type { LayoutPosition, LayoutSettings, NodeSizes, Positions } from './types'

export const NODE_WIDTH = 250
export const NODE_HEIGHT = 168
export const RADIAL_CLEARANCE = 48
export const RADIAL_LABEL_CLEARANCE = 180
export const BOUNDARY_HEADER_HEIGHT = 38
export const BOUNDARY_TOP_PADDING = BOUNDARY_HEADER_HEIGHT + 12
export const BOUNDARY_BOTTOM_PADDING = 48

export const DEFAULT_LAYOUT_SETTINGS: LayoutSettings = {
  method: 'layered',
  direction: 'right',
  spacing: { node: 40, layer: 72, boundary: 20 },
  ranking: 'auto',
}

export function boundaryTopPadding(settings: LayoutSettings): number {
  return Math.max(BOUNDARY_TOP_PADDING, settings.spacing.boundary)
}

export function boundaryBottomPadding(settings: LayoutSettings): number {
  return Math.max(BOUNDARY_BOTTOM_PADDING, settings.spacing.boundary)
}

export function graphParts(graph: RolledGraph) {
  const boundaryByKey = new Map(graph.boundaries.filter((boundary) => !boundary.stub).map((boundary) => [boundary.key, boundary]))
  const boundaryEntityKeys = new Set(boundaryByKey.values().map((boundary) => boundary.nodeKey))
  const edgeEndpoints = new Set(graph.edges.flatMap((edge) => [edge.a, edge.b]))
  const visibleNodes = graph.nodes.filter((node) => !boundaryEntityKeys.has(node.key) || edgeEndpoints.has(node.key))
  const visibleNodeKeys = new Set(visibleNodes.map((node) => node.key))
  const parentByChild = new Map<string, string>()
  for (const boundary of boundaryByKey.values()) {
    for (const child of boundary.childKeys) parentByChild.set(child, boundary.key)
  }
  const rootIds = [
    ...[...boundaryByKey.values()].filter((boundary) => !boundary.parentKey).map((boundary) => boundary.key),
    ...visibleNodes.filter((node) => !parentByChild.has(node.key)).map((node) => node.key),
  ]
  return { boundaryByKey, parentByChild, rootIds, visibleNodeKeys }
}

export function sizeFor(id: string, sizes: NodeSizes): { width: number; height: number } {
  return sizes.get(id) ?? { width: NODE_WIDTH, height: NODE_HEIGHT }
}

export type Bounds = { minX: number; minY: number; maxX: number; maxY: number }

export function positionBounds(positions: Positions, ids: Iterable<string> = positions.keys()): Bounds {
  const selected = [...ids].flatMap((id) => {
    const position = positions.get(id)
    return position ? [position] : []
  })
  if (!selected.length) return { minX: 0, minY: 0, maxX: 0, maxY: 0 }
  return {
    minX: Math.min(...selected.map((position) => position.x)),
    minY: Math.min(...selected.map((position) => position.y)),
    maxX: Math.max(...selected.map((position) => position.x + position.width)),
    maxY: Math.max(...selected.map((position) => position.y + position.height)),
  }
}

export function rectClearance(left: LayoutPosition, right: LayoutPosition): number {
  const x = Math.max(left.x - right.x - right.width, right.x - left.x - left.width, 0)
  const y = Math.max(left.y - right.y - right.height, right.y - left.y - left.height, 0)
  return Math.hypot(x, y)
}

export function adjacency(graph: RolledGraph): Map<string, Set<string>> {
  const result = new Map(graph.nodes.map((node) => [node.key, new Set<string>()]))
  for (const edge of graph.edges) {
    result.get(edge.a)?.add(edge.b)
    result.get(edge.b)?.add(edge.a)
  }
  return result
}

export function starHub(graph: RolledGraph): string | null {
  if (graph.boundaries.some((boundary) => !boundary.stub) || graph.nodes.length < 6 || !graph.edges.length) return null
  const neighbors = adjacency(graph)
  const eligible = graph.nodes.filter((node) => (neighbors.get(node.key)?.size ?? 0) / graph.edges.length >= 0.4)
  eligible.sort((left, right) => (
    (neighbors.get(right.key)?.size ?? 0) - (neighbors.get(left.key)?.size ?? 0)
    || left.key.localeCompare(right.key)
  ))
  return eligible[0]?.key ?? null
}
