import type { RolledGraph } from '../types'
import { gridEngine } from './grid'
import { layeredEngine } from './layered'
import { radialEngine } from './radial'
import { starHub } from './shared'
import type { LayoutEngine, LayoutMethod } from './types'

export const layoutEngines = {
  layered: layeredEngine,
  radial: radialEngine,
  grid: gridEngine,
} satisfies Record<LayoutMethod, LayoutEngine>

export const registeredLayoutMethods = Object.freeze(Object.keys(layoutEngines) as LayoutMethod[])

export function defaultLayoutMethod(graph: RolledGraph, preferredHub: string | null): LayoutMethod {
  if (preferredHub ?? starHub(graph)) return 'radial'
  if (graph.edges.length === 0) return 'grid'
  return 'layered'
}
