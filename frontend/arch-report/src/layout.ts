import type { Edge, Node } from '@xyflow/react'
import ELK from 'elkjs/lib/elk.bundled.js'
import type { ElkNode } from 'elkjs/lib/elk-api'

import type { ReportPayload } from './types'

const elk = new ELK()

export async function unionLayout(payload: ReportPayload): Promise<Map<string, { x: number; y: number }>> {
  const systems = [...new Map(payload.rows.systems.map((row) => [row.id, row])).values()]
  const ids = new Set(systems.map((row) => row.id))
  const connections = [...payload.rows.interfaces, ...payload.rows.relationships]
    .map((row) => ({ id: row.id, source: row.provider ?? row.source, target: row.consumer ?? row.target }))
    .filter((edge) => edge.source && edge.target && ids.has(edge.source) && ids.has(edge.target))
  const graph = await elk.layout({
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.layered.crossingMinimization.semiInteractive': 'true',
      'elk.randomSeed': '1',
      'elk.spacing.nodeNode': '72',
      'elk.layered.spacing.nodeNodeBetweenLayers': '120',
    },
    children: systems.map((row) => ({ id: row.id, width: 240, height: 112 })),
    edges: connections.map((edge) => ({ id: edge.id, sources: [edge.source!], targets: [edge.target!] })),
  })
  return new Map((graph.children ?? []).map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }]))
}

export function applyPositions(nodes: Node[], positions: Map<string, { x: number; y: number }>): Node[] {
  return nodes.map((node) => ({ ...node, position: positions.get(node.id) ?? node.position }))
}

export function connectionEdges(payload: ReportPayload): Edge[] {
  const ids = new Set(payload.rows.systems.map((row) => row.id))
  return [...payload.rows.interfaces, ...payload.rows.relationships]
    .map((row) => ({
      id: row.id,
      source: row.provider ?? row.source ?? '',
      target: row.consumer ?? row.target ?? '',
      label: row.name ?? row.action ?? row.id,
      type: 'semantic',
    }))
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
}
