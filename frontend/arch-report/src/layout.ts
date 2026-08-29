import type { Node } from '@xyflow/react'
import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js'

import type { RolledGraph } from './types'

export type LayoutPosition = { x: number; y: number; width: number; height: number; parentId?: string }
export type Positions = Map<string, LayoutPosition>
export type NodeSizes = ReadonlyMap<string, { width: number; height: number }>

export const NODE_WIDTH = 250
export const NODE_HEIGHT = 168

const NODE_SPACING = 40
const RADIAL_CLEARANCE = 48
const RADIAL_LABEL_CLEARANCE = 180
const LAYER_SPACING = 72
const BOUNDARY_HEADER_HEIGHT = 38
const BOUNDARY_PADDING = { top: BOUNDARY_HEADER_HEIGHT + 12, side: 20, bottom: 48 }
const elk = new ELK()
const cache = new Map<string, Promise<Positions>>()

export function makeLayoutKey(view: { timeline: number; expand: readonly string[] }): string {
  return `${view.timeline}:${[...new Set(view.expand)].sort().join(',')}`
}

function graphParts(graph: RolledGraph) {
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
  return { boundaryByKey, rootIds, visibleNodeKeys }
}

function sizeFor(id: string, sizes: NodeSizes): { width: number; height: number } {
  return sizes.get(id) ?? { width: NODE_WIDTH, height: NODE_HEIGHT }
}

export function buildLayoutInput(graph: RolledGraph, sizes: NodeSizes, aspectRatio: number): ElkNode {
  const { boundaryByKey, rootIds, visibleNodeKeys } = graphParts(graph)
  const makeNode = (id: string): ElkNode => {
    const boundary = boundaryByKey.get(id)
    if (!boundary) return { id, ...sizeFor(id, sizes) }
    return {
      id,
      layoutOptions: {
        'elk.padding': `[top=${BOUNDARY_PADDING.top},left=${BOUNDARY_PADDING.side},bottom=${BOUNDARY_PADDING.bottom},right=${BOUNDARY_PADDING.side}]`,
      },
      children: boundary.childKeys.filter((child) => boundaryByKey.has(child) || visibleNodeKeys.has(child)).map(makeNode),
    }
  }
  return {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.aspectRatio': String(Math.max(1.2, Math.min(2, aspectRatio))),
      'elk.direction': 'RIGHT',
      'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
      'elk.layered.crossingMinimization.semiInteractive': 'true',
      'elk.randomSeed': '1',
      'elk.spacing.nodeNode': String(NODE_SPACING),
      'elk.layered.spacing.nodeNodeBetweenLayers': String(LAYER_SPACING),
    },
    children: rootIds.map(makeNode),
    edges: graph.edges.map((edge) => ({ id: edge.key, sources: [edge.a], targets: [edge.b] })),
  }
}

export function gridPack(graph: RolledGraph, sizes: NodeSizes): Positions {
  const { boundaryByKey, rootIds, visibleNodeKeys } = graphParts(graph)
  const positions: Positions = new Map()

  const pack = (ids: string[], parentId?: string): { width: number; height: number } => {
    const items = ids.map((id) => {
      const boundary = boundaryByKey.get(id)
      if (!boundary) return { id, ...sizeFor(id, sizes) }
      const children = boundary.childKeys.filter((child) => boundaryByKey.has(child) || visibleNodeKeys.has(child))
      const content = pack(children, id)
      return {
        id,
        width: Math.max(NODE_WIDTH, content.width + BOUNDARY_PADDING.side * 2),
        height: Math.max(NODE_HEIGHT, content.height + BOUNDARY_PADDING.top + BOUNDARY_PADDING.bottom),
      }
    })
    if (!items.length) return { width: 0, height: 0 }

    const columns = Math.ceil(Math.sqrt(items.length))
    const rows = Math.ceil(items.length / columns)
    const columnWidths = Array.from({ length: columns }, () => 0)
    const rowHeights = Array.from({ length: rows }, () => 0)
    items.forEach((item, index) => {
      const column = index % columns
      const row = Math.floor(index / columns)
      columnWidths[column] = Math.max(columnWidths[column], item.width)
      rowHeights[row] = Math.max(rowHeights[row], item.height)
    })
    const columnX = columnWidths.map((_, column) => columnWidths.slice(0, column).reduce((sum, value) => sum + value, 0) + column * NODE_SPACING)
    const rowY = rowHeights.map((_, row) => rowHeights.slice(0, row).reduce((sum, value) => sum + value, 0) + row * NODE_SPACING)
    items.forEach((item, index) => {
      const column = index % columns
      const row = Math.floor(index / columns)
      positions.set(item.id, {
        x: columnX[column] + (columnWidths[column] - item.width) / 2 + (parentId ? BOUNDARY_PADDING.side : 0),
        y: rowY[row] + (rowHeights[row] - item.height) / 2 + (parentId ? BOUNDARY_PADDING.top : 0),
        width: item.width,
        height: item.height,
        ...(parentId ? { parentId } : {}),
      })
    })
    return {
      width: columnWidths.reduce((sum, value) => sum + value, 0) + (columns - 1) * NODE_SPACING,
      height: rowHeights.reduce((sum, value) => sum + value, 0) + (rows - 1) * NODE_SPACING,
    }
  }

  pack(rootIds)
  return positions
}

function nodeName(node: RolledGraph['nodes'][number]): string {
  return node.row.name ?? node.row.id
}

function adjacency(graph: RolledGraph): Map<string, Set<string>> {
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

type Bounds = { minX: number; minY: number; maxX: number; maxY: number }

function positionBounds(positions: Positions, ids: Iterable<string> = positions.keys()): Bounds {
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

function rectClearance(left: LayoutPosition, right: LayoutPosition): number {
  const x = Math.max(left.x - right.x - right.width, right.x - left.x - left.width, 0)
  const y = Math.max(left.y - right.y - right.height, right.y - left.y - left.height, 0)
  return Math.hypot(x, y)
}

function separated(positions: Positions, ids: string[]): boolean {
  for (let left = 0; left < ids.length; left += 1) {
    for (let right = left + 1; right < ids.length; right += 1) {
      if (rectClearance(positions.get(ids[left])!, positions.get(ids[right])!) < RADIAL_CLEARANCE) return false
    }
  }
  return true
}

function centeredPosition(id: string, center: { x: number; y: number }, sizes: NodeSizes): LayoutPosition {
  const size = sizeFor(id, sizes)
  return { x: center.x - size.width / 2, y: center.y - size.height / 2, ...size }
}

function radialNodeOrder(graph: RolledGraph, neighbors: Map<string, Set<string>>) {
  const byKey = new Map(graph.nodes.map((node) => [node.key, node]))
  return (leftKey: string, rightKey: string): number => {
    const left = byKey.get(leftKey)!
    const right = byKey.get(rightKey)!
    return left.kind.localeCompare(right.kind)
      || (neighbors.get(rightKey)?.size ?? 0) - (neighbors.get(leftKey)?.size ?? 0)
      || nodeName(left).localeCompare(nodeName(right))
      || leftKey.localeCompare(rightKey)
  }
}

function ringAngles(
  oneHop: string[],
  graph: RolledGraph,
  compareNodes: (left: string, right: string) => number,
): Map<string, number> {
  const byKey = new Map(graph.nodes.map((node) => [node.key, node]))
  const slots = oneHop.map((_, index) => ({ angle: -Math.PI / 2 + index * Math.PI * 2 / oneHop.length, index }))
  const topFirst = [...slots].sort((left, right) => {
    const leftDistance = Math.min(left.index, oneHop.length - left.index)
    const rightDistance = Math.min(right.index, oneHop.length - right.index)
    return leftDistance - rightDistance || left.index - right.index
  })
  const users = oneHop.filter((key) => byKey.get(key)?.kind === 'users').sort(compareNodes)
  const others = oneHop.filter((key) => byKey.get(key)?.kind !== 'users').sort(compareNodes)
  const userSlots = new Set(topFirst.slice(0, users.length).map((slot) => slot.index))
  const remainingSlots = slots.filter((slot) => !userSlots.has(slot.index)).sort((left, right) => left.index - right.index)
  return new Map([
    ...users.map((key, index) => [key, topFirst[index].angle] as const),
    ...others.map((key, index) => [key, remainingSlots[index].angle] as const),
  ])
}

function radialComponent(
  graph: RolledGraph,
  hub: string,
  sizes: NodeSizes,
  neighbors: Map<string, Set<string>>,
): { positions: Positions; connected: Set<string> } {
  const compareNodes = radialNodeOrder(graph, neighbors)
  const oneHop = [...(neighbors.get(hub) ?? [])].sort(compareNodes)
  const angles = ringAngles(oneHop, graph, compareNodes)
  const connected = new Set([hub, ...oneHop])
  const depth = new Map<string, number>([[hub, 0], ...oneHop.map((key) => [key, 1] as const)])
  const anchor = new Map(oneHop.map((key) => [key, key]))
  const queue = [...oneHop]
  while (queue.length) {
    const current = queue.shift()!
    for (const next of [...(neighbors.get(current) ?? [])].sort(compareNodes)) {
      if (connected.has(next)) continue
      connected.add(next)
      depth.set(next, depth.get(current)! + 1)
      anchor.set(next, anchor.get(current)!)
      queue.push(next)
    }
  }

  const deeperByAnchorDepth = new Map<string, string[]>()
  for (const key of [...connected].filter((item) => (depth.get(item) ?? 0) >= 2).sort(compareNodes)) {
    const group = `${anchor.get(key)}:${depth.get(key)}`
    deeperByAnchorDepth.set(group, [...(deeperByAnchorDepth.get(group) ?? []), key])
  }
  const maxDimension = Math.max(...[...connected].map((key) => {
    const size = sizeFor(key, sizes)
    return Math.hypot(size.width, size.height)
  }))
  const hubPosition = centeredPosition(hub, { x: 0, y: 0 }, sizes)

  for (let ringRadius = maxDimension; ringRadius < 100_000; ringRadius += 1) {
    const positions: Positions = new Map([[hub, hubPosition]])
    for (const key of oneHop) {
      const angle = angles.get(key)!
      positions.set(key, centeredPosition(key, { x: Math.cos(angle) * ringRadius, y: Math.sin(angle) * ringRadius }, sizes))
    }
    for (const [group, keys] of [...deeperByAnchorDepth].sort(([left], [right]) => left.localeCompare(right))) {
      const separator = group.lastIndexOf(':')
      const anchorKey = group.slice(0, separator)
      const nodeDepth = Number(group.slice(separator + 1))
      const baseAngle = angles.get(anchorKey)!
      const wedge = Math.PI * 1.4 / Math.max(1, oneHop.length)
      for (const [index, key] of keys.entries()) {
        const angle = baseAngle + (index - (keys.length - 1) / 2) * wedge / Math.max(1, keys.length)
        let radius = ringRadius + (nodeDepth - 1) * (maxDimension + RADIAL_CLEARANCE + RADIAL_LABEL_CLEARANCE)
        let candidate = centeredPosition(key, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }, sizes)
        while ([...positions.values()].some((position) => rectClearance(position, candidate) < RADIAL_CLEARANCE)) {
          radius += 1
          candidate = centeredPosition(key, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }, sizes)
        }
        positions.set(key, candidate)
      }
    }

    const ringBounds = positionBounds(positions, oneHop)
    const shiftX = -(ringBounds.minX + ringBounds.maxX) / 2
    const shiftY = -(ringBounds.minY + ringBounds.maxY) / 2
    for (const key of [...connected].filter((item) => item !== hub)) {
      const position = positions.get(key)!
      positions.set(key, { ...position, x: position.x + shiftX, y: position.y + shiftY })
    }
    if (!separated(positions, [...connected])) continue

    const bounds = positionBounds(positions, connected)
    for (const [key, position] of positions) {
      positions.set(key, { ...position, x: position.x - bounds.minX, y: position.y - bounds.minY })
    }
    return { positions, connected }
  }
  throw new RangeError('Unable to construct a non-overlapping radial layout')
}

export function radialLayout(graph: RolledGraph, sizes: NodeSizes, preferredHub: string | null = null): Positions {
  const hub = preferredHub ?? starHub(graph)
  if (!hub) throw new RangeError('Radial layout requires an eligible star graph')
  if (!graph.nodes.some((node) => node.key === hub)) throw new RangeError(`Radial hub ${hub} is not present in the graph`)
  const neighbors = adjacency(graph)
  const { positions, connected } = radialComponent(graph, hub, sizes, neighbors)
  const disconnected = graph.nodes.filter((node) => !connected.has(node.key))
  if (!disconnected.length) return positions

  const disconnectedGraph = { ...graph, nodes: disconnected, edges: [], boundaries: [] }
  const packed = gridPack(disconnectedGraph, sizes)
  const connectedBounds = positionBounds(positions)
  const packedBounds = positionBounds(packed)
  const offsetX = (connectedBounds.minX + connectedBounds.maxX - packedBounds.minX - packedBounds.maxX) / 2
  const offsetY = connectedBounds.maxY + RADIAL_CLEARANCE - packedBounds.minY
  for (const [key, position] of packed) positions.set(key, { ...position, x: position.x + offsetX, y: position.y + offsetY })
  return positions
}

export function unionLayout(
  graph: RolledGraph,
  cacheKey: string,
  sizes: NodeSizes = new Map(),
  aspectRatio = 1.6,
  preferredHub: string | null = null,
  fresh = false,
): Promise<Positions> {
  const cached = fresh ? undefined : cache.get(cacheKey)
  if (cached) return cached
  const hub = preferredHub ?? starHub(graph)
  const result = hub
    ? Promise.resolve(radialLayout(graph, sizes, hub))
    : graph.edges.length === 0
    ? Promise.resolve(gridPack(graph, sizes))
    : elk.layout(buildLayoutInput(graph, sizes, aspectRatio)).then((layout) => {
      const positions: Positions = new Map()
      const visit = (nodes: typeof layout.children, parentId?: string) => {
        for (const node of nodes ?? []) {
          positions.set(node.id, {
            x: node.x ?? 0,
            y: node.y ?? 0,
            width: node.width ?? NODE_WIDTH,
            height: node.height ?? NODE_HEIGHT,
            ...(parentId ? { parentId } : {}),
          })
          visit(node.children, node.id)
        }
      }
      visit(layout.children)
      return positions
    })
  cache.set(cacheKey, result)
  return result
}

function sameParent(position: LayoutPosition, parentId: string | undefined): boolean {
  return position.parentId === parentId
}

function overlapsWithClearance(left: LayoutPosition, right: LayoutPosition): boolean {
  return rectClearance(left, right) < RADIAL_CLEARANCE
}

function shifted(position: LayoutPosition, dx: number, dy: number): LayoutPosition {
  return { ...position, x: position.x + dx, y: position.y + dy }
}

function minimumShift(position: LayoutPosition, obstacle: LayoutPosition, vector: { x: number; y: number }): LayoutPosition {
  let high = 1
  while (overlapsWithClearance(shifted(position, vector.x * high, vector.y * high), obstacle)) high *= 2
  let low = 0
  for (let step = 0; step < 40; step += 1) {
    const middle = (low + high) / 2
    if (overlapsWithClearance(shifted(position, vector.x * middle, vector.y * middle), obstacle)) low = middle
    else high = middle
  }
  return shifted(position, vector.x * high, vector.y * high)
}

export function stableExpansionLayout(previous: Positions, fresh: Positions, anchorKey: string): Positions {
  const oldAnchor = previous.get(anchorKey)
  const nextAnchor = fresh.get(anchorKey)
  if (!oldAnchor || !nextAnchor) return fresh
  const result: Positions = new Map()
  for (const [key, position] of previous) if (fresh.has(key)) result.set(key, { ...position })

  const descendants = new Set([anchorKey])
  let changed = true
  while (changed) {
    changed = false
    for (const [key, position] of fresh) {
      if (position.parentId && descendants.has(position.parentId) && !descendants.has(key)) {
        descendants.add(key)
        changed = true
      }
    }
  }
  for (const key of descendants) {
    const position = fresh.get(key)
    if (position) result.set(key, { ...position })
  }
  result.set(anchorKey, {
    ...nextAnchor,
    parentId: oldAnchor.parentId,
    x: oldAnchor.x + (oldAnchor.width - nextAnchor.width) / 2,
    y: oldAnchor.y + (oldAnchor.height - nextAnchor.height) / 2,
  })

  const pushApart = (changedKey: string) => {
    const anchor = result.get(changedKey)!
    const anchorCenter = { x: anchor.x + anchor.width / 2, y: anchor.y + anchor.height / 2 }
    const candidates = [...result.entries()]
      .filter(([key, position]) => key !== changedKey && sameParent(position, anchor.parentId))
      .sort(([leftKey, left], [rightKey, right]) => {
        const leftDistance = Math.hypot(left.x + left.width / 2 - anchorCenter.x, left.y + left.height / 2 - anchorCenter.y)
        const rightDistance = Math.hypot(right.x + right.width / 2 - anchorCenter.x, right.y + right.height / 2 - anchorCenter.y)
        return leftDistance - rightDistance || leftKey.localeCompare(rightKey)
      })
    const displaced: LayoutPosition[] = [anchor]
    for (const [key, original] of candidates) {
      let position = original
      let moved = false
      for (;;) {
        const obstacle = displaced.find((item) => overlapsWithClearance(position, item))
        if (!obstacle) break
        const dx = position.x + position.width / 2 - anchorCenter.x
        const dy = position.y + position.height / 2 - anchorCenter.y
        const length = Math.hypot(dx, dy)
        const vector = length ? { x: dx / length, y: dy / length } : { x: key.localeCompare(changedKey) < 0 ? -1 : 1, y: 0 }
        position = minimumShift(position, obstacle, vector)
        moved = true
      }
      if (moved) {
        result.set(key, position)
        displaced.push(position)
      }
    }
  }

  pushApart(anchorKey)
  let parentId = oldAnchor.parentId
  while (parentId) {
    const parent = result.get(parentId)
    if (!parent) break
    const childKeys = [...result.entries()].filter(([, position]) => position.parentId === parentId).map(([key]) => key)
    const childBounds = positionBounds(result, childKeys)
    const shiftX = Math.max(0, BOUNDARY_PADDING.side - childBounds.minX)
    const shiftY = Math.max(0, BOUNDARY_PADDING.top - childBounds.minY)
    if (shiftX || shiftY) {
      for (const key of childKeys) result.set(key, shifted(result.get(key)!, shiftX, shiftY))
    }
    const grown = {
      ...parent,
      x: parent.x - shiftX,
      y: parent.y - shiftY,
      width: Math.max(parent.width, childBounds.maxX + shiftX + BOUNDARY_PADDING.side),
      height: Math.max(parent.height, childBounds.maxY + shiftY + BOUNDARY_PADDING.bottom),
    }
    result.set(parentId, grown)
    pushApart(parentId)
    parentId = parent.parentId
  }
  return result
}

export function applyPositions(nodes: Node[], positions: Positions): Node[] {
  const nodeIds = new Set(nodes.map((node) => node.id))
  return nodes.map((node) => {
    const layout = positions.get(node.id)
    if (!layout) return node
    const parentId = layout.parentId && nodeIds.has(layout.parentId) ? layout.parentId : undefined
    return {
      ...node,
      position: { x: layout.x, y: layout.y },
      width: layout.width,
      height: layout.height,
      ...(parentId ? { parentId } : {}),
    }
  })
}
