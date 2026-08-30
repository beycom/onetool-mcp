import type { RolledGraph } from '../types'
import { gridPack } from './grid'
import {
  adjacency,
  graphParts,
  positionBounds,
  RADIAL_CLEARANCE,
  RADIAL_LABEL_CLEARANCE,
  rectClearance,
  sizeFor,
  starHub,
} from './shared'
import type { LayoutEngine, LayoutPosition, LayoutSettings, NodeSizes, Positions } from './types'

function nodeName(node: RolledGraph['nodes'][number]): string {
  return node.row.name ?? node.row.id
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
    const shiftX = oneHop.length > 1 ? -(ringBounds.minX + ringBounds.maxX) / 2 : 0
    const shiftY = oneHop.length > 1 ? -(ringBounds.minY + ringBounds.maxY) / 2 : 0
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

export function radialLayout(
  graph: RolledGraph,
  sizes: NodeSizes,
  settings: LayoutSettings,
  preferredHub: string | null = null,
): Positions {
  if (graph.boundaries.some((boundary) => !boundary.stub)) {
    const packed = gridPack(graph, sizes, settings)
    const { boundaryByKey, parentByChild, rootIds } = graphParts(graph)
    const rootFor = (key: string): string => {
      let root = key
      while (parentByChild.has(root)) root = parentByChild.get(root)!
      return root
    }
    const nodeByKey = new Map(graph.nodes.map((node) => [node.key, node]))
    const rootGraph: RolledGraph = {
      ...graph,
      boundaries: [],
      nodes: rootIds.map((key) => {
        const node = nodeByKey.get(key)
        if (node) return node
        const boundary = boundaryByKey.get(key)!
        return { key, kind: boundary.kind, row: boundary.row, boundary: true, members: [] }
      }),
      edges: [...graph.edges.reduce((result, edge) => {
        const a = rootFor(edge.a)
        const b = rootFor(edge.b)
        if (a === b) return result
        const pair = [a, b].sort().join('|')
        if (!result.has(pair)) result.set(pair, { ...edge, key: pair, a, b })
        return result
      }, new Map<string, RolledGraph['edges'][number]>()).values()],
    }
    const rootSizes = new Map(rootIds.map((key) => {
      const position = packed.get(key)!
      return [key, { width: position.width, height: position.height }] as const
    }))
    const rootPositions = radialLayout(
      rootGraph,
      rootSizes,
      settings,
      preferredHub ? rootFor(preferredHub) : null,
    )
    for (const [key, position] of rootPositions) packed.set(key, position)
    return packed
  }
  const neighbors = adjacency(graph)
  const hub = preferredHub ?? starHub(graph) ?? [...graph.nodes]
    .sort((left, right) => (neighbors.get(right.key)?.size ?? 0) - (neighbors.get(left.key)?.size ?? 0) || left.key.localeCompare(right.key))[0]?.key
  if (!hub) return new Map()
  if (!graph.nodes.some((node) => node.key === hub)) throw new RangeError(`Radial hub ${hub} is not present in the graph`)
  const { positions, connected } = radialComponent(graph, hub, sizes, neighbors)
  const disconnected = graph.nodes.filter((node) => !connected.has(node.key))
  if (!disconnected.length) return positions

  const packed = gridPack({ ...graph, nodes: disconnected, edges: [], boundaries: [] }, sizes, settings)
  const connectedBounds = positionBounds(positions)
  const packedBounds = positionBounds(packed)
  const offsetX = (connectedBounds.minX + connectedBounds.maxX - packedBounds.minX - packedBounds.maxX) / 2
  const offsetY = connectedBounds.maxY + RADIAL_CLEARANCE - packedBounds.minY
  for (const [key, position] of packed) positions.set(key, { ...position, x: position.x + offsetX, y: position.y + offsetY })
  return positions
}

export const radialEngine: LayoutEngine = {
  async layout(graph, sizes, settings, context) {
    return radialLayout(graph, sizes, settings, context.hub)
  },
}
