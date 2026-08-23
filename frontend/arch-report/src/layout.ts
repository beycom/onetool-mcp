import type { Node } from '@xyflow/react'
import ELK from 'elkjs/lib/elk.bundled.js'

import type { RolledGraph } from './types'

export type Positions = Map<string, { x: number; y: number }>

export const NODE_WIDTH = 240
export const NODE_HEIGHT = 112

const elk = new ELK()
const cache = new Map<string, Promise<Positions>>()

export function unionLayout(graph: RolledGraph, cacheKey: string): Promise<Positions> {
  const cached = cache.get(cacheKey)
  if (cached) return cached
  const result = elk.layout({
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.layered.crossingMinimization.semiInteractive': 'true',
      'elk.randomSeed': '1',
      'elk.spacing.nodeNode': '72',
      'elk.layered.spacing.nodeNodeBetweenLayers': '120',
    },
    children: graph.nodes.map((node) => ({ id: node.key, width: NODE_WIDTH, height: NODE_HEIGHT })),
    edges: graph.edges.map((edge) => ({ id: edge.key, sources: [edge.a], targets: [edge.b] })),
  }).then((layout) => new Map(
    (layout.children ?? []).map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }]),
  ))
  cache.set(cacheKey, result)
  return result
}

export function applyPositions(nodes: Node[], positions: Positions): Node[] {
  return nodes.map((node) => ({ ...node, position: positions.get(node.id) ?? node.position }))
}
