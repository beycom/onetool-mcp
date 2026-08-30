import type { RolledGraph } from '../types'

export type LayoutMethod = 'layered' | 'radial' | 'grid'
export type LayoutPosition = { x: number; y: number; width: number; height: number; parentId?: string }
export type Positions = Map<string, LayoutPosition>
export type NodeSizes = ReadonlyMap<string, { width: number; height: number }>
export type LayoutSettings = {
  method: LayoutMethod
  direction: 'right' | 'down'
  spacing: { node: number; layer: number; boundary: number }
  ranking: 'auto' | `property:${string}`
}
export type LayoutContext = { aspectRatio: number; hub: string | null }

export interface LayoutEngine {
  layout(
    graph: RolledGraph,
    sizes: NodeSizes,
    settings: LayoutSettings,
    context: LayoutContext,
  ): Promise<Positions>
}
