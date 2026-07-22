import { type ComputedView, type DiagramView, LikeC4Styles, _stage, _type } from '@likec4/core'
import { GraphvizLayouter } from '@likec4/layouts'
import type { DiagramApi } from '@likec4/diagram'
import { Alert, Center, Loader } from '@mantine/core'
import { LikeC4Diagram } from 'likec4/react'
import { useEffect, useMemo, useRef, useState } from 'react'

import type { ViewGraph } from '../../data/types'
import { afterInteraction, BoundedCache, LatestRequestGate } from '../runtime'
import type { SolutionLayoutResult, SolutionRendererProps } from './types'

interface AdapterLayout {
  view: DiagramView
  result: SolutionLayoutResult
}
export interface AdapterDiagramGeometry {
  bounds: { x: number; y: number; width: number; height: number }
  nodes: readonly { id: string; parent: string | null; x: number; y: number; width: number; height: number }[]
  edges: readonly {
    id: string
    source: string
    target: string
    points: readonly (readonly [number, number])[]
  }[]
}
type AdapterDiagramApi = Pick<
  DiagramApi,
  | 'currentView'
  | 'unhighlightAll'
  | 'highlightNode'
  | 'centerViewportOnNode'
  | 'highlightEdge'
  | 'centerViewportOnEdge'
  | 'fitDiagram'
>

const layoutCache = new BoundedCache<string, AdapterLayout>(24)

export function layoutCacheStats() {
  return { size: layoutCache.size, hits: layoutCache.hits, misses: layoutCache.misses }
}

function metadataFor(
  id: string,
  status: string,
  contextStatus: string,
  properties: Record<string, unknown>,
  relatedChanges: string[],
  groups: string[] = [],
): Record<string, string | string[]> {
  const metadata: Record<string, string | string[]> = {
    canonicalId: id,
    contextStatus,
    status,
  }
  if (groups.length > 0) metadata.groups = groups
  if (relatedChanges.length > 0) metadata.relatedChanges = relatedChanges
  for (const [name, value] of Object.entries(properties)) {
    metadata[`property.${name}`] =
      typeof value === 'string' ? value : JSON.stringify(value)
  }
  return metadata
}

function nodeDepths(graph: ViewGraph): {
  ancestors: Map<string, number>
  descendants: Map<string, number>
} {
  const nodes = new Map(graph.nodes.map((node) => [node.id, node]))
  const children = new Map(graph.nodes.map((node) => [node.id, node.children]))
  const ancestors = new Map<string, number>()
  for (const node of graph.nodes) {
    const trail: string[] = []
    const seen = new Set<string>()
    let current = node
    while (current.parent && !ancestors.has(current.id) && !seen.has(current.id)) {
      trail.push(current.id)
      seen.add(current.id)
      current = nodes.get(current.parent) ?? current
      if (seen.has(current.id)) break
    }
    let depth = ancestors.get(current.id) ?? 0
    if (current.id !== node.id && !ancestors.has(current.id)) ancestors.set(current.id, depth)
    for (const id of trail.reverse()) {
      depth += 1
      ancestors.set(id, depth)
    }
  }
  const descendants = new Map<string, number>()
  const visiting = new Set<string>()
  const visit = (id: string): number => {
    const cached = descendants.get(id)
    if (cached !== undefined) return cached
    if (visiting.has(id)) return 0
    visiting.add(id)
    let depth = 0
    for (const child of children.get(id) ?? []) depth = Math.max(depth, visit(child) + 1)
    visiting.delete(id)
    descendants.set(id, depth)
    return depth
  }
  for (const node of graph.nodes) visit(node.id)
  return { ancestors, descendants }
}

function computedView(graph: ViewGraph, cacheKey: string): ComputedView {
  const inEdges = new Map<string, string[]>()
  const outEdges = new Map<string, string[]>()
  for (const edge of graph.edges) {
    inEdges.set(edge.target_id, [...(inEdges.get(edge.target_id) ?? []), edge.id])
    outEdges.set(edge.source_id, [...(outEdges.get(edge.source_id) ?? []), edge.id])
  }
  const depths = nodeDepths(graph)
  return {
    [_stage]: 'computed',
    [_type]: 'element',
    id: graph.id,
    title: null,
    description: null,
    hash: cacheKey,
    autoLayout: { direction: 'LR' },
    nodes: graph.nodes.map((node) => ({
      id: node.id,
      kind: node.entity_kind,
      modelRef: node.id,
      parent: node.parent ?? null,
      title: node.name,
      technology: node.status,
      children: node.children,
      inEdges: inEdges.get(node.id) ?? [],
      outEdges: outEdges.get(node.id) ?? [],
      shape: node.entity_kind === 'user' ? 'person' : 'rectangle',
      color: 'gray',
      style: {},
      tags: node.tags,
      metadata: metadataFor(
        node.id,
        node.status,
        node.context_status,
        node.properties,
        node.related_changes,
        node.groups,
      ),
      level: depths.ancestors.get(node.id) ?? 0,
      depth: depths.descendants.get(node.id) ?? 0,
    })),
    edges: graph.edges.map((edge) => ({
      id: edge.id,
      parent: null,
      source: edge.source_id,
      target: edge.target_id,
      label: edge.name,
      relations: [],
      technology: edge.integration_type ?? null,
      color: 'gray',
      line: 'solid',
      head: 'normal',
      tags: edge.tags,
    })),
  } as unknown as ComputedView
}

export function toSolutionLayout(
  graph: ViewGraph,
  requestId: string,
  diagram: AdapterDiagramGeometry,
): SolutionLayoutResult {
  const edges = new Map(graph.edges.map((edge) => [edge.id, edge]))
  return {
    requestId,
    graphId: graph.id,
    selectionId: graph.selection.id,
    bounds: {
      x: diagram.bounds.x,
      y: diagram.bounds.y,
      width: diagram.bounds.width,
      height: diagram.bounds.height,
    },
    nodes: diagram.nodes.map((node) => ({
      id: node.id,
      parent: node.parent ?? undefined,
      bounds: { x: node.x, y: node.y, width: node.width, height: node.height },
    })),
    edges: diagram.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      route: edge.points.map(([x, y]) => ({ x, y })),
      interfaceIds: edges.get(edge.id)?.interface_ids ?? [],
    })),
    diagnostics: [],
  }
}

export function LikeC4SolutionRenderer({
  cacheKey,
  graph,
  nodeColors,
  edgeColors,
  controls,
  selectedId,
  onCanvasClick,
  onLayout,
  onSelect,
}: SolutionRendererProps) {
  const [layout, setLayout] = useState<AdapterLayout | null>(
    () => layoutCache.get(cacheKey) ?? null,
  )
  const [error, setError] = useState<string>()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const diagramApi = useRef<AdapterDiagramApi | null>(null)
  const requestGate = useRef(new LatestRequestGate())
  const [apiVersion, setApiVersion] = useState(0)

  useEffect(() => {
    const cached = layoutCache.get(cacheKey)
    if (cached) {
      setLayout(cached)
      setError(undefined)
      onLayout?.({
        ...cached.result,
        graphId: graph.id,
        selectionId: graph.selection.id,
      })
      return
    }
    const requestId = requestGate.current.start()
    setLayout(null)
    setError(undefined)
    let layouter: GraphvizLayouter | undefined
    void (async () => {
      try {
        await afterInteraction()
        if (!requestGate.current.isCurrent(requestId)) return
        layouter = new GraphvizLayouter()
        const { diagram } = await layouter.layout({
          view: computedView(graph, cacheKey),
          styles: LikeC4Styles.DEFAULT,
        })
        if (!requestGate.current.isCurrent(requestId)) return
        const next = { view: diagram, result: toSolutionLayout(graph, cacheKey, diagram) }
        layoutCache.set(cacheKey, next)
        setLayout(next)
        setError(undefined)
        onLayout?.(next.result)
      } catch {
        if (requestGate.current.isCurrent(requestId)) {
          setError('The selected solution could not be laid out locally.')
        }
      } finally {
        layouter?.dispose()
      }
    })()
    return () => {
      requestGate.current.cancel(requestId)
    }
  }, [cacheKey, graph, onLayout])

  const coloredView = useMemo(() => {
    if (!layout) return null
    return {
      ...layout.view,
      nodes: layout.view.nodes.map((node) => ({
        ...node,
        color: nodeColors.get(node.id) ?? node.color,
      })),
      edges: layout.view.edges.map((edge) => ({
        ...edge,
        color: edgeColors.get(edge.id) ?? edge.color,
      })),
    } as DiagramView
  }, [edgeColors, layout, nodeColors])
  const viewId = coloredView?.id

  useEffect(() => {
    const api = diagramApi.current
    if (!api) return
    api.unhighlightAll()
    if (!selectedId) return
    if (graph.nodes.some((node) => node.id === selectedId)) {
      api.highlightNode(selectedId as never)
      api.centerViewportOnNode(selectedId as never)
    } else if (graph.edges.some((edge) => edge.id === selectedId)) {
      api.highlightEdge(selectedId as never)
      api.centerViewportOnEdge(selectedId as never)
    }
  }, [apiVersion, graph.edges, graph.nodes, selectedId])

  useEffect(() => {
    if (!viewId) return
    let frame: number | undefined
    let cancelled = false
    const fitWhenReady = () => {
      const api = diagramApi.current
      if (!api || api.currentView.id !== viewId) {
        frame = requestAnimationFrame(fitWhenReady)
        return
      }
      frame = requestAnimationFrame(() => {
        if (!cancelled) api.fitDiagram(0)
      })
    }
    frame = requestAnimationFrame(fitWhenReady)
    return () => {
      cancelled = true
      if (frame !== undefined) cancelAnimationFrame(frame)
    }
  }, [apiVersion, viewId])

  useEffect(() => {
    const container = containerRef.current
    if (!container || typeof ResizeObserver === 'undefined') return
    let frame: number | undefined
    const observer = new ResizeObserver(() => {
      if (frame !== undefined) cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        frame = requestAnimationFrame(() => diagramApi.current?.fitDiagram(0))
      })
    })
    observer.observe(container)
    return () => {
      observer.disconnect()
      if (frame !== undefined) cancelAnimationFrame(frame)
    }
  }, [apiVersion])

  if (error)
    return (
      <Alert color="red" title="Unable to lay out solution">
        {error}
      </Alert>
    )
  if (!coloredView)
    return (
      <Center h="100%">
        <Loader aria-label="Laying out solution" />
      </Center>
    )
  const edgeById = new Map(graph.edges.map((edge) => [edge.id, edge]))
  return (
    <div ref={containerRef} style={{ height: '100%', width: '100%' }}>
      <LikeC4Diagram
        background="dots"
        controls={controls}
        enableElementTags
        enableFocusMode
        enableSearch
        fitView
        onCanvasClick={onCanvasClick}
        onEdgeClick={(edge) =>
          onSelect({
            id: edge.id,
            kind: 'edge',
            interfaceIds: edgeById.get(edge.id)?.interface_ids ?? [],
          })
        }
        onInitialized={({ diagram }) => {
          diagramApi.current = diagram
          setApiVersion((version) => version + 1)
        }}
        onNodeClick={(node) => onSelect({ id: node.id, kind: 'node', interfaceIds: [] })}
        pannable
        view={coloredView}
        zoomable
      />
    </div>
  )
}
