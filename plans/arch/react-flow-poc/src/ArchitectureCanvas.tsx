import {
  Background,
  BackgroundVariant,
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  getSmoothStepPath,
  useReactFlow,
  type EdgeProps,
  type NodeProps,
  type Viewport,
} from '@xyflow/react'
import { createContext, memo, useCallback, useContext, useMemo, useState } from 'react'

import {
  architectureEdges,
  architectureNodes,
  lensNodeIds,
  passports,
  routeNodeIds,
  type ArchitectureNode,
  type BoundaryNode,
  type DiagramMode,
  type PassportRecord,
  type SemanticEdge,
} from './data'
import { useDraggablePanel } from './useDraggablePanel'

const ROUTE_STEPS = ['buyers', 'edge-gateway', 'checkout-api', 'orders', 'payment-rail']
const EdgeSelectionContext = createContext<(id: string) => void>(() => undefined)

function ArchitectureNodeView({ data, selected }: NodeProps<ArchitectureNode>) {
  return (
    <article
      aria-label={`${data.kind}: ${data.label}, ${data.subtitle}`}
      className={`architecture-node tone-${data.tone}`}
      data-selected={selected ? 'true' : 'false'}
      tabIndex={0}
    >
      <span aria-hidden="true" className="node-icon">{data.icon}</span>
      <strong>{data.label}</strong>
      <span className="node-subtitle">{data.subtitle}</span>
      {data.status ? <span className="node-status">{data.status}</span> : null}
      <Handle className="semantic-handle" id="left-target" position={Position.Left} type="target" />
      <Handle className="semantic-handle" id="right-source" position={Position.Right} type="source" />
      <Handle className="semantic-handle" id="top-source" position={Position.Top} type="source" />
      <Handle className="semantic-handle" id="bottom-source" position={Position.Bottom} type="source" />
      <Handle className="semantic-handle" id="top-target" position={Position.Top} type="target" />
      <Handle className="semantic-handle" id="bottom-target" position={Position.Bottom} type="target" />
    </article>
  )
}

function BoundaryNodeView({ data }: NodeProps<BoundaryNode>) {
  return (
    <section aria-label={data.label} className={`boundary boundary-${data.tone}`}>
      <span>{data.label}</span>
    </section>
  )
}

function SemanticEdgeView({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
  selected,
}: EdgeProps<SemanticEdge>) {
  const onSelect = useContext(EdgeSelectionContext)
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 10,
    offset: 24,
  })
  const emphasized = data?.route || selected

  return (
    <>
      <BaseEdge
        id={id}
        markerEnd={markerEnd}
        path={edgePath}
        className="semantic-edge-path"
        style={{
          opacity: data?.dimmed ? 0.12 : 1,
          stroke: emphasized ? 'var(--route)' : 'var(--edge)',
          strokeWidth: emphasized ? 3.2 : 2.2,
        }}
      />
      <EdgeLabelRenderer>
        <button
          aria-label={`Select relationship ${data?.label ?? id}`}
          className="edge-label nodrag nopan"
          data-active={emphasized ? 'true' : 'false'}
          onClick={(event) => {
            event.stopPropagation()
            onSelect(id)
          }}
          style={{
            opacity: data?.dimmed ? 0.18 : 1,
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
          type="button"
        >
          {data?.label}
        </button>
      </EdgeLabelRenderer>
    </>
  )
}

const nodeTypes = {
  architecture: memo(ArchitectureNodeView),
  boundary: memo(BoundaryNodeView),
}

const edgeTypes = { semantic: memo(SemanticEdgeView) }

function ArchitectureStage({
  mode,
  onModeChange,
  onSelect,
  selectedId,
}: {
  mode: DiagramMode
  onModeChange: (mode: DiagramMode) => void
  onSelect: (passport: PassportRecord) => void
  selectedId?: string
}) {
  const { fitView, getZoom, setCenter, zoomIn, zoomOut } = useReactFlow()
  const [query, setQuery] = useState('')
  const [zoom, setZoom] = useState(72)
  const { dragHandleProps, panelRef } = useDraggablePanel<HTMLElement>('route probe')
  const selectEdge = useCallback((id: string) => {
    const passport = passports[id]
    if (passport) onSelect(passport)
  }, [onSelect])

  const visibleNodes = useMemo(() => architectureNodes.map((node) => {
    if (node.type === 'boundary') return node
    const inFocus = mode === 'map' || (mode === 'path' ? routeNodeIds.has(node.id) : lensNodeIds.has(node.id))
    return {
      ...node,
      selected: selectedId === node.id,
      style: { ...node.style, opacity: inFocus ? 1 : 0.16 },
    }
  }), [mode, selectedId])

  const visibleEdges = useMemo(() => architectureEdges.map((edge) => {
    const sourceInLens = lensNodeIds.has(edge.source)
    const targetInLens = lensNodeIds.has(edge.target)
    const route = mode === 'path' && Boolean(edge.data?.route)
    const dimmed = mode === 'path'
      ? !edge.data?.route
      : mode === 'lens' && !(sourceInLens && targetInLens)
    return {
      ...edge,
      selected: selectedId === edge.id,
      data: { ...edge.data, route, dimmed },
    }
  }), [mode, selectedId])

  const runSearch = useCallback(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return
    const match = architectureNodes.find((node) => (
      node.type === 'architecture'
      && `${node.data.label} ${node.data.subtitle}`.toLowerCase().includes(normalized)
    ))
    if (!match || match.type !== 'architecture') return
    onSelect(passports[match.id])
    void setCenter(match.position.x + 125, match.position.y + 65, { zoom: 1.05, duration: 500 })
  }, [onSelect, query, setCenter])

  const onMove = useCallback((_event: MouseEvent | TouchEvent | null, viewport: Viewport) => {
    setZoom(Math.round(viewport.zoom * 100))
  }, [])

  return (
    <div className="canvas-stage" data-mode={mode}>
      <EdgeSelectionContext.Provider value={selectEdge}>
        <ReactFlow
          aria-label="Interactive C4 container architecture"
          colorMode="light"
          defaultEdgeOptions={{ focusable: true }}
          defaultViewport={{ x: 40, y: 40, zoom: 0.72 }}
          edges={visibleEdges}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.12, minZoom: 0.5, maxZoom: 0.9 }}
          maxZoom={1.5}
          minZoom={0.35}
          nodes={visibleNodes}
          nodesConnectable={false}
          nodesDraggable={false}
          nodeTypes={nodeTypes}
          onEdgeClick={(_event, edge) => onSelect(passports[edge.id])}
          onMove={onMove}
          onNodeClick={(_event, node) => {
            const passport = passports[node.id]
            if (passport) onSelect(passport)
          }}
          panOnScroll
          proOptions={{ hideAttribution: true }}
          selectionOnDrag={false}
          zoomOnDoubleClick={false}
          zoomOnScroll={false}
        >
          <Background color="var(--grid-line)" gap={32} lineWidth={1} variant={BackgroundVariant.Lines} />
          <MiniMap
            ariaLabel="Semantic radar"
            className="semantic-radar"
            maskColor="color-mix(in srgb, var(--canvas) 74%, transparent)"
            nodeBorderRadius={5}
            nodeColor={(node) => {
              if (node.type === 'boundary') return 'transparent'
              const tone = (node.data as unknown as ArchitectureNode['data']).tone
              return {
                amber: '#c66a12',
                slate: '#58758a',
                teal: '#078b79',
                violet: '#7552ca',
              }[tone]
            }}
            nodeStrokeColor="#31566a"
            nodeStrokeWidth={2}
            pannable
            zoomable
          />
        </ReactFlow>
      </EdgeSelectionContext.Provider>

      <div className="canvas-context" aria-label="Diagram context">
        <span className="context-kicker">C4 · CONTAINER</span>
        <strong>Checkout Platform</strong>
        <span>8 nodes · 7 authored relations</span>
      </div>

      <form
        className="canvas-search"
        onSubmit={(event) => {
          event.preventDefault()
          runSearch()
        }}
      >
        <span aria-hidden="true">⌕</span>
        <input
          aria-label="Find a diagram element"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find service or data store"
          value={query}
        />
        <button type="submit">Find</button>
      </form>

      {mode === 'path' ? (
        <section aria-label="Route probe" className="draggable-panel route-probe" ref={panelRef}>
          <header>
            <div>
              <span className="panel-kicker">ROUTE PROBE</span>
              <strong>Buyers to Payment Rail</strong>
            </div>
            <div className="panel-header-actions">
              <button className="panel-drag-handle" type="button" {...dragHandleProps}><span aria-hidden="true">⠿</span></button>
              <button onClick={() => onModeChange('map')} type="button">Clear</button>
            </div>
          </header>
          <div className="route-steps">
            {ROUTE_STEPS.map((id, index) => (
              <span className="route-step-wrap" key={id}>
                <button onClick={() => onSelect(passports[id])} type="button">{passports[id].name}</button>
                {index < ROUTE_STEPS.length - 1 ? <span aria-hidden="true">→</span> : null}
              </span>
            ))}
          </div>
          <footer>5 nodes · 4 directed hops · shortest authored route</footer>
        </section>
      ) : null}

      <nav aria-label="Diagram navigation" className="navigation-rail">
        <div className="mode-switch">
          {(['path', 'map', 'lens'] as const).map((item) => (
            <button
              aria-pressed={mode === item}
              key={item}
              onClick={() => onModeChange(item)}
              type="button"
            >
              {item.toUpperCase()}
            </button>
          ))}
        </div>
        <span className="rail-separator" />
        <button aria-label="Fit diagram" onClick={() => void fitView({ duration: 450, padding: 0.12 })} type="button">⌖</button>
        <button aria-label="Zoom out" onClick={() => void zoomOut({ duration: 180 })} type="button">−</button>
        <output aria-label="Current zoom">READ {zoom}%</output>
        <button aria-label="Zoom in" onClick={() => void zoomIn({ duration: 180 })} type="button">+</button>
        <span className="sr-only">Actual zoom {Math.round(getZoom() * 100)} percent</span>
      </nav>
    </div>
  )
}

export function ArchitectureCanvas(props: {
  mode: DiagramMode
  onModeChange: (mode: DiagramMode) => void
  onSelect: (passport: PassportRecord) => void
  selectedId?: string
}) {
  return (
    <ReactFlowProvider>
      <ArchitectureStage {...props} />
    </ReactFlowProvider>
  )
}
