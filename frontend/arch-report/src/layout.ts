import type { Node } from '@xyflow/react'
import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js'

import type { RolledGraph } from './types'

export type LayoutPosition = { x: number; y: number; width: number; height: number; parentId?: string }
export type Positions = Map<string, LayoutPosition>

export const NODE_WIDTH = 250
export const NODE_HEIGHT = 168

const elk = new ELK()
const cache = new Map<string, Promise<Positions>>()

export function unionLayout(graph: RolledGraph, cacheKey: string): Promise<Positions> {
  const cached = cache.get(cacheKey)
  if (cached) return cached
  const boundaryByKey = new Map(graph.boundaries.filter((boundary) => !boundary.stub).map((boundary) => [boundary.key, boundary]))
  const boundaryEntityKeys = new Set(boundaryByKey.values().map((boundary) => boundary.nodeKey))
  const edgeEndpoints = new Set(graph.edges.flatMap((edge) => [edge.a, edge.b]))
  const visibleNodes = graph.nodes.filter((node) => !boundaryEntityKeys.has(node.key) || edgeEndpoints.has(node.key))
  const visibleNodeKeys = new Set(visibleNodes.map((node) => node.key))
  const parentByChild = new Map<string, string>()
  for (const boundary of boundaryByKey.values()) {
    for (const child of boundary.childKeys) parentByChild.set(child, boundary.key)
  }
  const makeNode = (id: string): ElkNode => {
    const boundary = boundaryByKey.get(id)
    if (!boundary) return { id, width: NODE_WIDTH, height: NODE_HEIGHT }
    return {
      id,
      layoutOptions: { 'elk.padding': '[top=46,left=24,bottom=24,right=24]' },
      children: boundary.childKeys.filter((child) => boundaryByKey.has(child) || visibleNodeKeys.has(child)).map(makeNode),
    }
  }
  const rootIds = [
    ...[...boundaryByKey.values()].filter((boundary) => !boundary.parentKey).map((boundary) => boundary.key),
    ...visibleNodes.filter((node) => !parentByChild.has(node.key)).map((node) => node.key),
  ]
  const result = elk.layout({
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
      'elk.layered.crossingMinimization.semiInteractive': 'true',
      'elk.randomSeed': '1',
      'elk.spacing.nodeNode': '72',
      'elk.layered.spacing.nodeNodeBetweenLayers': '120',
    },
    children: rootIds.map(makeNode),
    edges: graph.edges.map((edge) => ({ id: edge.key, sources: [edge.a], targets: [edge.b] })),
  }).then((layout) => {
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
  return nodes.map((node) => {
    const layout = positions.get(node.id)
    if (!layout) return node
    return {
      ...node,
      position: { x: layout.x, y: layout.y },
      width: layout.width,
      height: layout.height,
      ...(layout.parentId ? { parentId: layout.parentId } : {}),
    }
  })
}
