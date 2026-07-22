import type { ViewGraph } from '../../data/types'

export interface LayoutPoint {
  x: number
  y: number
}

export interface LayoutBounds extends LayoutPoint {
  width: number
  height: number
}

export interface SolutionLayoutNode {
  id: string
  parent?: string
  bounds: LayoutBounds
}

export interface SolutionLayoutEdge {
  id: string
  source: string
  target: string
  route: LayoutPoint[]
  interfaceIds: string[]
  label?: string
}

export interface SolutionLayoutResult {
  requestId: string
  graphId: string
  selectionId: string
  nodes: SolutionLayoutNode[]
  edges: SolutionLayoutEdge[]
  bounds: LayoutBounds
  diagnostics: string[]
}

export interface RendererSelectionEvent {
  id: string
  kind: 'node' | 'edge'
  interfaceIds: string[]
}

export interface SolutionRendererProps {
  cacheKey: string
  graph: ViewGraph
  nodeColors: ReadonlyMap<string, string>
  edgeColors: ReadonlyMap<string, string>
  controls: boolean
  selectedId?: string
  onCanvasClick?: () => void
  onLayout?: (layout: SolutionLayoutResult) => void
  onSelect: (event: RendererSelectionEvent) => void
}
