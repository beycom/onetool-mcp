import type { Node } from '@xyflow/react'
import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js'

import type { Level, RolledGraph } from './types'

export type LayoutPosition = { x: number; y: number; width: number; height: number; parentId?: string }
export type Positions = Map<string, LayoutPosition>
export type NodeSizes = ReadonlyMap<string, { width: number; height: number }>

export const NODE_WIDTH = 250
export const NODE_HEIGHT = 168

const NODE_SPACING = 40
const LAYER_SPACING = 72
const BOUNDARY_HEADER_HEIGHT = 38
const BOUNDARY_PADDING = { top: BOUNDARY_HEADER_HEIGHT + 12, side: 20, bottom: 20 }
const elk = new ELK()
const cache = new Map<string, Promise<Positions>>()

export function makeLayoutKey(view: { timeline: number; level: Level; drill: string | null }): string {
  return `${view.timeline}:${view.level}:${view.drill ?? 'map'}`
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

export function unionLayout(
  graph: RolledGraph,
  cacheKey: string,
  sizes: NodeSizes = new Map(),
  aspectRatio = 1.6,
): Promise<Positions> {
  const cached = cache.get(cacheKey)
  if (cached) return cached
  const result = graph.edges.length === 0
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
