import {
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from '@xyflow/react'
import { memo, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'

import { fitViewport, initialViewport, shiftViewport, type Rect } from './camera'
import { cardSize, measureCardText } from './cardSize'
import { KIND_LABEL, levelForKind, rowLabel } from './display'
import { edgeAnchors, type EdgeAnchorPair, type EdgeRect } from './edgeAnchors'
import {
  classifyEmphasis,
  edgeLabelVisible,
  edgeStrokeToken,
  interfacePort,
  portLabelPlacement,
  splitEdgeDirections,
  type DirectionalSpline,
  type EdgeEmphasis,
  type InterfacePort,
  type SplineDirection,
} from './edgePresentation'
import { GlobalSearch, type SearchResult } from './GlobalSearch'
import { GridPanel } from './GridPanel'
import { InfoPanel, selectionKey, type Selection } from './InfoPanel'
import { FitIcon, MapIcon, SearchIcon } from './Icons'
import { applyPositions, defaultLayoutMethod, makeLayoutKey, NODE_HEIGHT, NODE_WIDTH, stableExpansionLayout, starHub, unionLayout, type LayoutMethod, type Positions } from './layout'
import { configuredLayoutMethod, layoutSettings, loadLayoutMethod, queryLayoutMethod, resolveLayoutMethod, saveLayoutMethod } from './layoutConfig'
import { loadLayout, saveLayout, type DockName, type LayoutPreferences } from './layoutPreferences'
import { readPayload } from './payload'
import { diffStates, legendEntries, mergeRemovedBoundaries, projectState, unionGraph } from './projection'
import { ResizablePanel } from './ResizablePanel'
import { endpointsNearViewport, intersects, splinePath, type SplinePath } from './splinePath'
import { kindPresentationStyle, themeStyle } from './theme'
import {
  type Aspect,
  type GraphEdge,
  type GraphBoundary,
  type GraphNode,
  type EntityKind,
  type ReportPayload,
  type ReportRow,
  type RowRef,
  type RowKind,
  type StateDiff,
  type View,
} from './types'
import { containmentIndex, copyViewLink, decodeView, expansionPath, persistView } from './view'
import { ViewDock } from './ViewDock'
import { readingDepth } from './zoom'

type DiffStatus = 'added' | 'removed' | 'changed'
type ArchitectureData = {
  boundary: boolean
  childCount: number
  connectionCount: number
  context: string
  description: string
  expandable: boolean
  emphasis: 'normal' | 'emphasized' | 'neighbor' | 'unrelated'
  facts: Array<[string, string]>
  kind: EntityKind
  label: string
  members: RowRef[]
  onExpand: () => void
  row: ReportRow
  statuses: DiffStatus[]
}
type ArchitectureNode = Node<ArchitectureData, 'architecture'>
type BoundaryData = { boundary: GraphBoundary; description: string; ghost: boolean; label: string; onCollapse: () => void }
type BoundaryNode = Node<BoundaryData, 'boundary'>
type CanvasNode = ArchitectureNode | BoundaryNode
type SemanticData = {
  anchors: EdgeAnchorPair
  direction: SplineDirection
  edge: GraphEdge
  emphasis: EdgeEmphasis | 'selected'
  hovered: boolean
  label: string
  labelPoint: SplinePath['point']
  portLabel: SplinePath['point'] | null
  memberCount: number
  onSelect: () => void
  onHover: (hovered: boolean) => void
  port: InterfacePort | null
  path: string
  selected: boolean
  showLabel: boolean
  statuses: DiffStatus[]
  zoom: number
}
type SemanticFlowEdge = Edge<SemanticData, 'semantic'>
const payload = readPayload()
const reportStorageId = `${globalThis.location?.pathname ?? ''}:${payload.source}`
const STATUS_ORDER: DiffStatus[] = ['added', 'removed', 'changed']
const STATUS_ICON: Record<DiffStatus, string> = { added: '+', removed: '−', changed: 'Δ' }

function ExpandIcon() {
  return <svg aria-hidden="true" viewBox="0 0 16 16"><path d="M7 2a5 5 0 1 0 3.2 8.8L14 14l1-1-3.8-3.2A5 5 0 0 0 7 2Zm0 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6Z" /></svg>
}

export function ArchitectureNodeView({ data, selected }: NodeProps<ArchitectureNode>) {
  return (
    <article
      className="architecture-node"
      data-boundary={data.boundary ? 'true' : 'false'}
      data-member-count={data.members.length}
      data-emphasis={data.emphasis}
      data-kind={data.kind}
      data-selected={selected ? 'true' : 'false'}
      data-status={data.statuses.join(' ')}
      style={kindPresentationStyle(data.kind, selected)}
    >
      <div className="node-heading"><span className="kind-pill" data-kind={data.kind}>{KIND_LABEL[data.kind]}</span>{data.boundary ? <span className="external-pill">External</span> : null}</div>
      <strong className="node-name" title={data.label}>{data.label}</strong>
      <p className="node-description">{data.description}</p>
      <span className="node-context">{data.context}</span>
      <dl className="node-facts">{data.facts.map(([key, value]) => <div key={key} title={`${key}: ${value}`}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
      <div className="node-counts">
        {data.childCount ? <span title={`${data.childCount} children`}>{data.childCount} children</span> : null}
        {data.connectionCount ? <span title={`${data.connectionCount} connections`}>{data.connectionCount} connections</span> : null}
      </div>
      {data.expandable ? <button aria-label={`Expand ${data.label}, ${data.childCount} children`} className="expand-button" onClick={(event) => { event.stopPropagation(); data.onExpand() }} title="Expand direct children" type="button"><ExpandIcon /><span>{data.childCount}</span></button> : null}
      {data.statuses.length ? (
        <span aria-label={`Changes: ${data.statuses.join(', ')}`} className="diff-badges">
          {data.statuses.map((status) => <b data-status={status} key={status}>{STATUS_ICON[status]}</b>)}
        </span>
      ) : null}
      <Handle position={Position.Left} type="target" />
      <Handle position={Position.Right} type="source" />
    </article>
  )
}

export function BoundaryNodeView({ data, selected }: NodeProps<BoundaryNode>) {
  return (
    <section className="containment-boundary" data-ghost={data.ghost ? 'true' : 'false'} data-kind={data.boundary.kind} data-selected={selected ? 'true' : 'false'} data-stub={data.boundary.stub ? 'true' : 'false'} style={kindPresentationStyle(data.boundary.kind, selected)}>
      <header><span className="boundary-title"><span className="kind-pill" data-kind={data.boundary.kind}>{KIND_LABEL[data.boundary.kind]}</span><strong>{data.label}</strong></span>{data.ghost ? null : <button aria-label={`Collapse ${data.label}`} className="boundary-collapse" onClick={(event) => { event.stopPropagation(); data.onCollapse() }} title="Collapse" type="button">−</button>}</header>
      {data.description ? <p className="boundary-description">{data.description}</p> : null}
      <Handle position={Position.Left} type="target" />
      <Handle position={Position.Right} type="source" />
    </section>
  )
}

export function SemanticEdge({
  data,
  id,
}: EdgeProps<SemanticFlowEdge>) {
  if (!data) return null
  const path = data.path
  const statuses = data?.statuses ?? []
  const emphasis = data?.emphasis ?? 'normal'
  const markerId = `arrow-${id.replace(/[^a-zA-Z0-9_-]/g, '-')}`
  const arrowSize = Math.max(6.4, 6.4 / Math.max(data.zoom, 0.2))
  const strokeWidth = Math.max(1.5, 1.5 / Math.max(data.zoom, 0.2))
  const emphasized = ['outgoing', 'incoming', 'neighbor', 'selected'].includes(emphasis)
  const accented = ['outgoing', 'incoming', 'selected'].includes(emphasis)
  const diffIncrement = statuses.includes('added') || statuses.includes('changed') ? 0.25 : 0
  const stroke = edgeStrokeToken(emphasis, statuses)
  const edgeStyle = { stroke, strokeWidth: strokeWidth + (emphasized ? 0.8 : diffIncrement) } as CSSProperties
  const focusStyle = { strokeWidth: strokeWidth + 5 } as CSSProperties
  const expandedPort = data.portLabel !== null
  return (
    <>
      <defs>
        <marker id={markerId} markerHeight={arrowSize} markerUnits="userSpaceOnUse" markerWidth={arrowSize} orient="auto" refX="10" refY="5" viewBox="0 0 10 10">
          <path className={`semantic-arrow is-${emphasis} ${statuses.map((status) => `is-${status}`).join(' ')}`} d="M 0 0 L 10 5 L 0 10 z" style={{ fill: stroke }} />
        </marker>
      </defs>
      <BaseEdge className={`semantic-edge-focus is-${emphasis}`} id={`${id}:focus`} interactionWidth={0} path={path} style={focusStyle} />
      <BaseEdge
        className={`semantic-edge is-${emphasis} ${statuses.map((status) => `is-${status}`).join(' ')}`}
        id={id}
        interactionWidth={24}
        markerEnd={`url(#${markerId})`}
        path={path}
        style={edgeStyle}
      />
      <EdgeLabelRenderer>
        {data.showLabel ? <button className="edge-label" data-direct-reveal={data.selected || data.hovered ? 'true' : 'false'} data-emphasis={emphasis} data-status={statuses.join(' ')} onClick={data.onSelect} onMouseEnter={() => data.onHover(true)} onMouseLeave={() => data.onHover(false)} style={{ transform: `translate(-50%, -50%) translate(${data.labelPoint.x}px,${data.labelPoint.y}px)` }} title={data.label} type="button">
          {data.label}
          {data.memberCount > 1 ? <i>{data.memberCount}</i> : null}
          {statuses.map((status) => <b data-status={status} key={status}>{STATUS_ICON[status]}</b>)}
        </button> : null}
        {[data.anchors.sourcePoint, data.anchors.targetPoint].map((point, index) => <span aria-hidden="true" className="edge-port" data-accent={accented ? 'true' : 'false'} key={index} style={{ transform: `translate(-50%, -50%) translate(${point.x}px,${point.y}px)` }} />)}
        {data.port ? <button aria-label={`Interface port ${data.port.label}`} className="interface-port" data-accent={accented ? 'true' : 'false'} data-direct-reveal={expandedPort && (data.selected || data.hovered) ? 'true' : 'false'} data-expanded={expandedPort ? 'true' : 'false'} onClick={data.onSelect} onMouseEnter={() => data.onHover(true)} onMouseLeave={() => data.onHover(false)} style={{ transform: `translate(-50%, -50%) translate(${(data.portLabel ?? data.port.point).x}px,${(data.portLabel ?? data.port.point).y}px)` }} title={data.port.label} type="button">
          {expandedPort ? <>{data.port.label}{data.port.count > 1 ? <i>{data.port.count}</i> : null}</> : null}
        </button> : null}
      </EdgeLabelRenderer>
    </>
  )
}

const nodeTypes = { architecture: memo(ArchitectureNodeView), boundary: memo(BoundaryNodeView) }
const edgeTypes = { semantic: memo(SemanticEdge) }

function statusesForNode(node: GraphNode, diff: StateDiff | null): DiffStatus[] {
  if (!diff) return []
  const keys = new Set([node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)])
  const found = new Set<DiffStatus>()
  if (diff.added.some((item) => keys.has(`${item.kind}:${item.id}`))) found.add('added')
  if (diff.removed.some((item) => keys.has(`${item.kind}:${item.id}`))) found.add('removed')
  if (diff.changed.some((item) => keys.has(`${item.kind}:${item.id}`))) found.add('changed')
  return STATUS_ORDER.filter((status) => found.has(status))
}

function statusesForMembers(members: DirectionalSpline['members'], diff: StateDiff | null): DiffStatus[] {
  if (!diff) return []
  const keys = new Set(members.map((member) => `${member.kind}:${member.row.id}`))
  const includes = (kind: string, id: string) => keys.has(`${kind}:${id}`)
  const found = new Set<DiffStatus>()
  if (diff.added.some((item) => includes(item.kind, item.id))) found.add('added')
  if (diff.removed.some((item) => includes(item.kind, item.id))) found.add('removed')
  if (diff.changed.some((item) => includes(item.kind, item.id))) found.add('changed')
  return STATUS_ORDER.filter((status) => found.has(status))
}

function statusesForEdge(edge: GraphEdge, diff: StateDiff | null): DiffStatus[] {
  return statusesForMembers([
    ...edge.interfaceRows.map((row) => ({ kind: 'interfaces' as const, providerKey: null, row })),
    ...edge.relationshipRows.map((row) => ({ kind: 'relationships' as const, providerKey: null, row })),
  ], diff)
}

function flowEdge(
  edge: GraphEdge,
  spline: DirectionalSpline,
  anchors: EdgeAnchorPair,
  route: SplinePath,
  statuses: DiffStatus[],
  emphasis: SemanticData['emphasis'],
  selected: boolean,
  hovered: boolean,
  showLabel: boolean,
  port: InterfacePort | null,
  portLabel: SplinePath['point'] | null,
  zoom: number,
  onSelect: () => void = () => {},
  onHover: (hovered: boolean) => void = () => {},
): SemanticFlowEdge {
  return {
    data: {
      anchors,
      direction: spline.direction,
      edge,
      emphasis,
      hovered,
      label: spline.label || edge.key,
      labelPoint: route.point,
      memberCount: spline.members.length,
      onHover,
      onSelect,
      port,
      portLabel,
      path: route.path,
      selected,
      showLabel,
      statuses,
      zoom,
    },
    id: spline.id,
    source: spline.source,
    target: spline.target,
    type: 'semantic',
  }
}

function absoluteRect(key: string, positions: Positions): EdgeRect | null {
  const position = positions.get(key)
  if (!position) return null
  let x = position.x
  let y = position.y
  let parentId = position.parentId
  const visited = new Set([key])
  while (parentId && !visited.has(parentId)) {
    visited.add(parentId)
    const parent = positions.get(parentId)
    if (!parent) break
    x += parent.x
    y += parent.y
    parentId = parent.parentId
  }
  return { x, y, width: position.width, height: position.height }
}

function nodeTags(node: GraphNode): string[] {
  return [...new Set([...(node.row.tags ?? []), ...node.members.flatMap((member) => member.row.tags ?? [])])].sort()
}

function DependencyView({
  aspect,
  focusKey,
  onClose,
  onFocus,
  onSelect,
  projected,
}: {
  aspect: Aspect
  focusKey: string
  onClose: () => void
  onFocus: (key: string) => void
  onSelect: (kind: RowKind, row: ReportRow, members?: RowRef[]) => void
  projected: ReturnType<typeof projectState>
}) {
  const visibleNodes = [
    ...projected.nodes,
    ...projected.boundaries.filter((boundary) => !boundary.stub).map((boundary): GraphNode => ({
      key: boundary.key,
      kind: boundary.kind,
      row: boundary.row,
      boundary: false,
      members: [{ kind: boundary.kind, row: boundary.row }],
    })),
  ]
  const focus = visibleNodes.find((node) => node.key === focusKey)
  if (!focus) return <div className="empty-state"><p>The focused entity is not in this projection.</p><button onClick={onClose} type="button">Return to map</button></div>
  const incoming: Array<{ edge: GraphEdge; node: GraphNode }> = []
  const outgoing: Array<{ edge: GraphEdge; node: GraphNode }> = []
  for (const edge of projected.edges.filter((item) => item.a === focusKey || item.b === focusKey)) {
    const neighbor = visibleNodes.find((node) => node.key === (edge.a === focusKey ? edge.b : edge.a))
    if (!neighbor) continue
    const splines = splitEdgeDirections(edge, aspect)
    if (splines.some((spline) => spline.target === focusKey)) incoming.push({ edge, node: neighbor })
    if (splines.some((spline) => spline.source === focusKey)) outgoing.push({ edge, node: neighbor })
  }
  const column = (label: string, entries: Array<{ edge: GraphEdge; node: GraphNode }>) => (
    <section aria-label={`${label} dependencies`} className="dependency-column">
      <h3>{label} <span>{entries.length}</span></h3>
      {entries.map(({ edge, node }) => <button key={`${label}:${edge.key}`} onClick={() => { onFocus(node.key); onSelect(node.kind, node.row, node.members) }} type="button"><strong>{rowLabel(node.row)}</strong><span>{edge.interfaces.length + edge.relationships.length} connections</span></button>)}
    </section>
  )
  return (
    <section className="dependency-view">
      <header><div><span className="panel-kicker">DEPENDENCY FOCUS</span><h2>{rowLabel(focus.row)}</h2><p>{incoming.length} incoming · {outgoing.length} outgoing · {new Set([...incoming, ...outgoing].flatMap(({ edge }) => [...edge.interfaces, ...edge.relationships])).size} connections</p><label>Focus <select aria-label="Dependency focus" onChange={(event) => { const node = visibleNodes.find((item) => item.key === event.target.value); if (node) { onFocus(node.key); onSelect(node.kind, node.row, node.members) } }} value={focusKey}>{visibleNodes.map((node) => <option key={node.key} value={node.key}>{rowLabel(node.row)}</option>)}</select></label></div><button aria-label="Close dependency view" onClick={onClose} type="button">×</button></header>
      <div className="dependency-columns">
        {column('Incoming', incoming)}
        <button className="dependency-focus-node" data-kind={focus.kind} onClick={() => onSelect(focus.kind, focus.row, focus.members)} style={kindPresentationStyle(focus.kind, true)} type="button"><span className="kind-pill" data-kind={focus.kind}>{KIND_LABEL[focus.kind]}</span><strong>{rowLabel(focus.row)}</strong></button>
        {column('Outgoing', outgoing)}
      </div>
    </section>
  )
}

const EMPTY_POSITIONS: Positions = new Map()

export default function App() {
  const [initial] = useState(() => decodeView(payload, globalThis.location?.hash ?? ''))
  const [view, setViewState] = useState<View>(initial.view)
  const queryLayout = queryLayoutMethod(globalThis.location?.search ?? '', import.meta.env.DEV)
  const [layoutMethod, setLayoutMethod] = useState<LayoutMethod | null>(() => resolveLayoutMethod({
    query: queryLayout,
    hash: initial.view.layout,
    stored: loadLayoutMethod(window.localStorage, reportStorageId),
    config: configuredLayoutMethod(payload.layout),
  }))
  const [selected, setSelected] = useState<Selection | null>(null)
  const [selectionHistory, setSelectionHistory] = useState<Selection[]>([])
  const [restoreSelect, setRestoreSelect] = useState<string | null>(initial.select)
  const [layoutResult, setLayoutResult] = useState<{ key: string; positions: Positions }>({ key: '', positions: new Map() })
  const [flow, setFlow] = useState<ReactFlowInstance<CanvasNode, SemanticFlowEdge> | null>(null)
  const [layout, setLayout] = useState<LayoutPreferences>(() => loadLayout(window.localStorage))
  const [copyStatus, setCopyStatus] = useState('')
  const [diagnostic, setDiagnostic] = useState('')
  const [canvasViewport, setCanvasViewport] = useState({ x: 0, y: 0, zoom: 1 })
  const [mapOpen, setMapOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [autoViewCollapsed, setAutoViewCollapsed] = useState(false)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
  const framedLayout = useRef('')
  const positionCache = useRef(new Map<string, Positions>())
  const layoutIntent = useRef<{ anchor: string; previous: Positions; target: string } | null>(null)
  const cameraFrame = useRef(0)
  const searchTrigger = useRef<HTMLButtonElement>(null)
  const selectedRef = useRef<Selection | null>(null)
  const legacyLevelPending = useRef(initial.legacyLevel)
  const setView = useCallback((change: Partial<View>, push = false) => setViewState((current) => {
    const next = { ...current, ...change }
    if (push) persistView(next, true)
    return next
  }), [])
  const revealInfo = useCallback((selection: Selection) => {
    const current = selectedRef.current
    if (current && selectionKey(current) !== selectionKey(selection)) {
      setSelectionHistory((history) => [...history, current].slice(-20))
    }
    selectedRef.current = selection
    setSelected(selection)
    if (window.innerWidth <= 1024 && !layout.docks.view.collapsed) setAutoViewCollapsed(true)
    setLayout((current) => ({
        ...current,
        docks: {
          ...current.docks,
          info: { ...current.docks.info, collapsed: false },
        },
      }))
  }, [layout.docks.view.collapsed])
  const closeInfo = useCallback(() => {
    selectedRef.current = null
    setSelected(null)
    setSelectionHistory([])
    setAutoViewCollapsed(false)
    setLayout((current) => ({ ...current, docks: { ...current.docks, info: { ...current.docks.info, collapsed: true } } }))
  }, [])
  const goBack = useCallback(() => {
    setSelectionHistory((history) => {
      const previous = history.at(-1)
      if (!previous) return history
      selectedRef.current = previous
      setSelected(previous)
      return history.slice(0, -1)
    })
  }, [])
  const zoom = canvasViewport.zoom
  const depth = readingDepth(zoom)

  const projected = useMemo(() => projectState(payload, view), [view])
  const previousPosition = view.position > 0 ? view.position - 1 : null
  const diff = useMemo(() => previousPosition === null
    ? null
    : diffStates(payload, view.timeline, previousPosition, view.position), [previousPosition, view.position, view.timeline])
  const compared = useMemo(() => previousPosition === null
    ? null
    : projectState(payload, { ...view, position: previousPosition }), [previousPosition, view])
  const union = useMemo(() => unionGraph(payload, view.timeline, view.expand), [view.expand, view.timeline])
  const projectedHub = useMemo(() => starHub(projected), [projected])
  const engineSettings = useMemo(() => layoutSettings(payload.layout, layoutMethod), [layoutMethod])
  const layoutConfigKey = JSON.stringify(engineSettings)
  const layoutKey = `${makeLayoutKey(view)}|${layoutConfigKey}`
  const displayedLayoutMethod = layoutMethod ?? defaultLayoutMethod(union, projectedHub)
  const cardSizes = useMemo(() => new Map(union.nodes.map((node) => [node.key, cardSize(node, levelForKind(node.kind), measureCardText)])), [union])
  // A layout computed for a different projection must never apply
  // (INT-STATE-06): stale positions carry parentIds for boundaries that no
  // longer exist in the current graph.
  const positions = layoutResult.key === layoutKey ? layoutResult.positions : EMPTY_POSITIONS
  const legend = useMemo(() => legendEntries(projected), [projected])

  const selectedKey = selected?.type === 'row' ? `${selected.kind}:${selected.row.id}` : null
  const selectedDisplayKey = useMemo(() => {
    if (!selectedKey) return null
    const exact = projected.nodes.find((node) => node.key === selectedKey)?.key
      ?? projected.boundaries.find((boundary) => boundary.nodeKey === selectedKey)?.key
    if (exact) return exact
    return projected.nodes.find((node) => node.members.some((member) => `${member.kind}:${member.row.id}` === selectedKey))?.key ?? null
  }, [projected.boundaries, projected.nodes, selectedKey])
  const selectedEmphasisKeys = useMemo(() => {
    const keys = new Set<string>()
    if (!selectedDisplayKey) return keys
    keys.add(selectedDisplayKey)
    const boundaryByKey = new Map(projected.boundaries.map((boundary) => [boundary.key, boundary]))
    const addBoundaryChildren = (key: string) => {
      for (const childKey of boundaryByKey.get(key)?.childKeys ?? []) {
        keys.add(childKey)
        if (boundaryByKey.has(childKey)) addBoundaryChildren(childKey)
      }
    }
    if (boundaryByKey.has(selectedDisplayKey)) addBoundaryChildren(selectedDisplayKey)
    if (selectedKey && selectedKey !== selectedDisplayKey) keys.add(selectedKey)
    return keys
  }, [projected.boundaries, selectedDisplayKey, selectedKey])
  const selectedSplineId = useMemo(() => {
    if (selected?.type === 'edge') return `${selected.edge.key}:${selected.direction}`
    if (selected?.type !== 'row' || !['interfaces', 'relationships'].includes(selected.kind)) return null
    for (const edge of projected.edges) {
      const spline = splitEdgeDirections(edge, view.aspect).find((item) => item.members.some((member) => member.kind === selected.kind && member.row.id === selected.row.id))
      if (spline) return spline.id
    }
    return null
  }, [projected.edges, selected, view.aspect])
  useEffect(() => {
    for (const message of initial.diagnostics) console.warn(message)
  }, [initial])
  useEffect(() => {
    persistView(view, legacyLevelPending.current, selectedKey)
    legacyLevelPending.current = false
  }, [selectedKey, view])
  useEffect(() => {
    const restore = () => {
      const decoded = decodeView(payload, globalThis.location?.hash ?? '')
      for (const message of decoded.diagnostics) console.warn(message)
      setViewState(decoded.view)
      setLayoutMethod(resolveLayoutMethod({
        query: queryLayout,
        hash: decoded.view.layout,
        stored: loadLayoutMethod(window.localStorage, reportStorageId),
        config: configuredLayoutMethod(payload.layout),
      }))
      setRestoreSelect(decoded.select)
      if (!decoded.select) closeInfo()
    }
    window.addEventListener('popstate', restore)
    return () => window.removeEventListener('popstate', restore)
  }, [closeInfo, queryLayout])
  useEffect(() => { saveLayout(window.localStorage, layout) }, [layout])
  useEffect(() => {
    let active = true
    const rect = canvasRef.current?.getBoundingClientRect()
    const aspectRatio = rect?.height ? rect.width / rect.height : 1.6
    const intent = layoutIntent.current?.target === layoutKey ? layoutIntent.current : null
    const cached = positionCache.current.get(layoutKey)
    const request = cached
      ? Promise.resolve(cached)
      : unionLayout(union, layoutKey, cardSizes, aspectRatio, projectedHub, false, engineSettings)
        .then((fresh) => intent ? stableExpansionLayout(intent.previous, fresh, intent.anchor, engineSettings ?? undefined) : fresh)
    void request
      .then((next) => {
        if (!active) return
        positionCache.current.set(layoutKey, next)
        if (layoutIntent.current?.target === layoutKey) layoutIntent.current = null
        setLayoutResult({ key: layoutKey, positions: next })
      })
      .catch(() => { if (active) setDiagnostic('Layout failed. The report remains available with fallback positions.') })
    return () => { active = false }
  }, [cardSizes, engineSettings, layoutKey, projectedHub, union])

  const changeExpansion = useCallback((key: string, expand: boolean) => {
    const next = new Set(view.expand)
    if (expand) next.add(key)
    else {
      const { parentByKey } = containmentIndex(payload)
      for (const candidate of next) {
        let cursor: string | undefined = candidate
        while (cursor) {
          if (cursor === key) { next.delete(candidate); break }
          cursor = parentByKey.get(cursor)
        }
      }
    }
    const expansion = [...next].sort()
    const target = `${makeLayoutKey({ timeline: view.timeline, expand: expansion })}|${layoutConfigKey}`
    layoutIntent.current = { anchor: key, previous: positions, target }
    framedLayout.current = target
    setView({ deps: null, expand: expansion }, true)
  }, [layoutConfigKey, positions, setView, view.expand, view.timeline])

  const graphNodes = useMemo(() => {
    const merged = new Map(projected.nodes.map((node) => [node.key, { node, ghost: false }]))
    for (const node of compared?.nodes ?? []) {
      const statuses = statusesForNode(node, diff)
      if (!merged.has(node.key) && statuses.includes('removed')) merged.set(node.key, { node, ghost: true })
    }
    return [...merged.values()]
  }, [compared, diff, projected.nodes])
  const graphBoundaries = useMemo(() => mergeRemovedBoundaries(
    projected.boundaries,
    compared?.boundaries ?? null,
    new Set((diff?.removed ?? []).map((item) => `${item.kind}:${item.id}`)),
  ), [compared, diff, projected.boundaries])
  const nodes = useMemo<CanvasNode[]>(() => {
    const byId = new Map(Object.entries(projected.rawState.rows).flatMap(([kind, rows]) => rows.map((row) => [row.id, { kind: kind as RowKind, row }] as const)))
    const propertyCounts = new Map<string, number>()
    for (const { node } of graphNodes) for (const key of Object.keys(node.row.properties ?? {})) propertyCounts.set(key, (propertyCounts.get(key) ?? 0) + 1)
    const factKeys = [...propertyCounts].sort(([leftKey, leftCount], [rightKey, rightCount]) => rightCount - leftCount || leftKey.localeCompare(rightKey)).slice(0, 3).map(([key]) => key)
    const memberKeys = (node: GraphNode) => new Set([node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)])
    const lensMatched = new Set(graphNodes.filter(({ node }) => nodeTags(node).some((tag) => view.lens.includes(tag))).map(({ node }) => node.key))
    const directionalEdges = projected.edges.flatMap((edge) => splitEdgeDirections(edge, view.aspect))
    const visibleKeys = [...graphNodes.map(({ node }) => node.key), ...graphBoundaries.map(({ boundary }) => boundary.key)]
    const classified = classifyEmphasis(visibleKeys, directionalEdges, selectedEmphasisKeys, lensMatched)
    const neighborKeys = (keys: Set<string>) => new Set(projected.edges.flatMap((edge) => keys.has(edge.a) ? [edge.b] : keys.has(edge.b) ? [edge.a] : []))
    const selectedNodes = new Set(graphNodes.filter(({ node }) => selectedKey && memberKeys(node).has(selectedKey)).map(({ node }) => node.key))
    const hoverNodes = new Set(hoveredKey ? [hoveredKey] : [])
    const hoverNeighbors = neighborKeys(hoverNodes)
    const emphasis = (key: string): ArchitectureData['emphasis'] => {
      if (selectedEmphasisKeys.size) return classified.nodes[key]
      if (selected?.type === 'edge') return key === selected.edge.a || key === selected.edge.b ? 'neighbor' : 'unrelated'
      if (view.lens.length) return classified.nodes[key]
      if (hoverNodes.size) return hoverNodes.has(key) ? 'emphasized' : hoverNeighbors.has(key) ? 'neighbor' : 'unrelated'
      return 'normal'
    }
    const architectureNodes: ArchitectureNode[] = graphNodes.map(({ ghost, node }, index) => {
      const parentId = node.row.parent ?? node.row.container ?? node.row.component
      const parent = parentId ? byId.get(parentId)?.row : undefined
      const childCount = Object.values(projected.rawState.rows).flat().filter((row) => [row.parent, row.container, row.component].includes(node.row.id)).length
      const rolledMemberIds = new Set(node.members.map((member) => member.row.id))
      const connectionCount = (['interfaces', 'relationships'] as const).flatMap((kind) => projected.rawState.rows[kind]
        .filter((row) => [row.provider ?? row.source, row.consumer ?? row.target].some((id) => id && rolledMemberIds.has(id)))
        .map((row) => `${kind}:${row.id}`)).length
      const size = cardSizes.get(node.key) ?? { width: NODE_WIDTH, height: NODE_HEIGHT }
      return {
        data: {
          boundary: node.boundary,
          childCount,
          connectionCount,
          context: parent ? rowLabel(parent) : KIND_LABEL[node.kind],
          description: node.row.description ?? '',
          expandable: childCount > 0,
          emphasis: emphasis(node.key),
          facts: factKeys.flatMap((key) => {
            const value = node.row.properties?.[key]
            return value === undefined ? [] : [[key, Array.isArray(value) ? value.join(', ') : value] as [string, string]]
          }),
          kind: node.kind,
          label: rowLabel(node.row),
          members: node.members,
          onExpand: () => changeExpansion(node.key, true),
          row: node.row,
          statuses: ghost ? ['removed'] : statusesForNode(node, diff),
        },
        height: size.height,
        id: node.key,
        position: { x: index * 280, y: 0 },
        selected: selectedNodes.has(node.key),
        type: 'architecture',
        width: size.width,
      }
    })
    const boundaryByKey = new Map(graphBoundaries.map(({ boundary }) => [boundary.key, boundary]))
    const boundaryDepth = (boundary: GraphBoundary): number => {
      const parent = boundary.parentKey ? boundaryByKey.get(boundary.parentKey) : undefined
      return parent ? 1 + boundaryDepth(parent) : 0
    }
    const boundaryNodes: BoundaryNode[] = graphBoundaries.filter(({ boundary }) => !boundary.stub)
      .sort((left, right) => boundaryDepth(left.boundary) - boundaryDepth(right.boundary) || left.boundary.key.localeCompare(right.boundary.key)).map(({ boundary, ghost }) => ({
      data: {
        boundary,
        description: boundary.row.description ?? '',
        ghost,
        label: rowLabel(boundary.row),
        onCollapse: () => changeExpansion(boundary.nodeKey, false),
      },
      id: boundary.key,
      position: { x: 0, y: 0 },
      selectable: true,
      selected: selectedKey === boundary.nodeKey,
      style: { zIndex: -1 },
      type: 'boundary',
    }))
    return applyPositions([...boundaryNodes, ...architectureNodes], positions) as CanvasNode[]
  }, [cardSizes, changeExpansion, diff, graphBoundaries, graphNodes, hoveredKey, positions, projected, selected, selectedDisplayKey, selectedEmphasisKeys, selectedKey, view.aspect, view.lens])

  const graphEdges = useMemo(() => {
    const merged = new Map(projected.edges.map((edge) => [edge.key, { edge, ghost: false }]))
    for (const edge of compared?.edges ?? []) {
      const statuses = statusesForEdge(edge, diff)
      if (!merged.has(edge.key) && statuses.includes('removed')) merged.set(edge.key, { edge, ghost: true })
    }
    return [...merged.values()]
  }, [compared, diff, projected.edges])
  const edges = useMemo(() => {
    const lensMatched = new Set(projected.nodes.filter((node) => nodeTags(node).some((tag) => view.lens.includes(tag))).map((node) => node.key))
    const rendered = graphEdges.flatMap(({ edge, ghost }) => splitEdgeDirections(edge, view.aspect)
      .map((spline) => ({ edge, ghost, spline })))
    const obstacleRects = nodes.flatMap((node) => {
      const rect = absoluteRect(node.id, positions)
      return rect ? [rect] : []
    })
    const labelObstacles = nodes.flatMap((node) => {
      const rect = absoluteRect(node.id, positions)
      if (!rect) return []
      return node.type === 'boundary' ? [{ ...rect, height: Math.min(38, rect.height) }] : [rect]
    })
    const canvas = canvasRef.current
    const viewportRect = canvas && canvasViewport.zoom > 0 ? {
      x: -canvasViewport.x / canvasViewport.zoom,
      y: -canvasViewport.y / canvasViewport.zoom,
      width: canvas.clientWidth / canvasViewport.zoom,
      height: canvas.clientHeight / canvasViewport.zoom,
    } : null
    const classified = classifyEmphasis([
      ...graphNodes.map(({ node }) => node.key),
      ...graphBoundaries.map(({ boundary }) => boundary.key),
    ], rendered.map(({ spline }) => spline), selectedEmphasisKeys, lensMatched)
    const edgeEmphasis = (spline: DirectionalSpline): SemanticData['emphasis'] => {
      if (selectedSplineId) return spline.id === selectedSplineId ? 'selected' : 'unrelated'
      if (selectedEmphasisKeys.size || view.lens.length) return classified.edges[spline.id]
      if (hoveredEdgeId) return spline.id === hoveredEdgeId ? 'selected' : 'unrelated'
      if (hoveredKey) return spline.source === hoveredKey || spline.target === hoveredKey ? 'neighbor' : 'unrelated'
      return 'normal'
    }
    const routable = rendered.flatMap(({ edge, ghost, spline }) => {
      const sourceRect = absoluteRect(spline.source, positions)
      const targetRect = absoluteRect(spline.target, positions)
      if (!sourceRect || !targetRect) return []
      return [{ edge, ghost, sourceRect, spline, targetRect }]
    })
    const anchorsById = edgeAnchors(routable.map(({ sourceRect, spline, targetRect }) => ({
      id: spline.id,
      sourceId: spline.source,
      sourceRect,
      targetId: spline.target,
      targetRect,
    })))
    const occupiedLabels: EdgeRect[] = []
    return routable.map(({ edge, ghost, sourceRect, spline, targetRect }, index) => {
      const anchors = anchorsById.get(spline.id)!
      const isSelected = spline.id === selectedSplineId
      const isHovered = spline.id === hoveredEdgeId
      const emphasis = edgeEmphasis(spline)
      const selectionReveal = selectedEmphasisKeys.size > 0 && (emphasis === 'outgoing' || emphasis === 'incoming')
      const directReveal = isSelected || isHovered
      const labelEligible = edgeLabelVisible(depth, isSelected || selectionReveal, isHovered)
      const labelWidth = Math.min(180, Math.max(48, spline.label.length * 6 + 20 + (spline.members.length > 1 ? 24 : 0)))
      const route = splinePath(anchors, obstacleRects, occupiedLabels, labelWidth, index % 2 === 0, labelObstacles)
      const endpointVisible = !viewportRect || endpointsNearViewport(sourceRect, targetRect, viewportRect, 120 / canvasViewport.zoom)
      const showLabel = endpointVisible && labelEligible && (directReveal || route.labelPlaced)
        && ((!hoveredEdgeId && !selectedSplineId) || directReveal)
      if (showLabel && !directReveal) occupiedLabels.push(route.rect)
      const port = interfacePort(spline, anchors)
      let portLabel: SplinePath['point'] | null = null
      if (port && (depth === 'full' || directReveal) && endpointVisible
        && ((!hoveredEdgeId && !selectedSplineId) || directReveal)) {
        const placement = portLabelPlacement(port)
        if (directReveal) {
          portLabel = placement.point
        } else if (labelObstacles.every((rect) => !intersects(placement.rect, rect))
          && occupiedLabels.every((rect) => !intersects(placement.rect, rect))) {
          portLabel = placement.point
          occupiedLabels.push(placement.rect)
        }
      }
      return flowEdge(
        edge,
        spline,
        anchors,
        route,
        ghost ? ['removed'] : statusesForMembers(spline.members, diff),
        emphasis,
        isSelected,
        isHovered,
        showLabel,
        port,
        portLabel,
        zoom,
        () => revealInfo({ type: 'edge', direction: spline.direction, edge }),
        (hovered) => setHoveredEdgeId(hovered ? spline.id : null),
      )
    })
  }, [canvasViewport, depth, diff, graphBoundaries, graphEdges, graphNodes, hoveredEdgeId, hoveredKey, nodes, positions, projected.nodes, revealInfo, selectedEmphasisKeys, selectedSplineId, view.aspect, view.lens, zoom])

  const visibleCanvas = useCallback((): Rect | null => {
    const element = canvasRef.current
    if (!element || element.clientWidth === 0 || element.clientHeight === 0) return null
    return { x: 0, y: 0, width: element.clientWidth, height: element.clientHeight }
  }, [])
  const focusSelection = useCallback((allowNeighborhoodFit: boolean) => {
    const visible = visibleCanvas()
    if (!flow || !visible || !selectedDisplayKey) return
    const neighbors = projected.edges.flatMap((edge) => edge.a === selectedDisplayKey
      ? [edge.b] : edge.b === selectedDisplayKey ? [edge.a] : [])
    const neighborhood = [...new Set([selectedDisplayKey, ...neighbors])]
    const neighborhoodBounds = flow.getNodesBounds(neighborhood)
    const viewport = flow.getViewport()
    const neighborhoodFits = neighborhoodBounds.width * viewport.zoom <= visible.width
      && neighborhoodBounds.height * viewport.zoom <= visible.height
    let next = viewport
    if (neighborhoodFits) next = shiftViewport(viewport, visible, neighborhoodBounds)
    else if (allowNeighborhoodFit) next = fitViewport(neighborhoodBounds, visible)
    else next = shiftViewport(viewport, visible, flow.getNodesBounds([selectedDisplayKey]))
    if (next !== viewport) void flow.setViewport(next, { duration: 180 })
  }, [flow, projected.edges, selectedDisplayKey, visibleCanvas])
  const focusSelectionRef = useRef(focusSelection)
  focusSelectionRef.current = focusSelection

  useEffect(() => {
    if (!flow || !positions.size || framedLayout.current === layoutKey) return
    const frame = requestAnimationFrame(() => {
      const visible = visibleCanvas()
      const flowNodes = flow.getNodes()
      const nodeIds = flowNodes.filter((node) => node.type !== 'architecture'
        || !(node.data as ArchitectureData).statuses.includes('removed')).map((node) => node.id)
      if (!visible || !nodeIds.length) return
      framedLayout.current = layoutKey
      void flow.setViewport(initialViewport(flow.getNodesBounds(nodeIds), visible), { duration: 250 })
    })
    return () => cancelAnimationFrame(frame)
  }, [flow, layoutKey, positions, visibleCanvas])

  const previousSelection = useRef<string | null>(null)
  useEffect(() => {
    if (previousSelection.current === selectedDisplayKey) return
    previousSelection.current = selectedDisplayKey
    if (!selectedDisplayKey) return
    const frame = requestAnimationFrame(() => focusSelectionRef.current(true))
    return () => cancelAnimationFrame(frame)
  }, [selectedDisplayKey])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(cameraFrame.current)
      cameraFrame.current = requestAnimationFrame(() => focusSelectionRef.current(false))
    })
    observer.observe(canvas)
    return () => {
      observer.disconnect()
      cancelAnimationFrame(cameraFrame.current)
    }
  }, [])

  const setDock = (name: DockName, dock: LayoutPreferences['docks'][DockName]) => {
    setLayout((current) => ({ ...current, docks: { ...current.docks, [name]: dock } }))
  }
  const selectRow = useCallback((kind: RowKind, row: ReportRow, members: RowRef[] = []) => {
    revealInfo({ type: 'row', kind, members, row })
  }, [revealInfo])
  const selectById = useCallback((kind: RowKind, id: string) => {
    const row = projected.rawState.rows[kind].find((item) => item.id === id)
      ?? payload.rows[kind].find((item) => item.id === id)
    if (!row) return
    const canonicalKey = `${kind}:${id}`
    const node = projected.nodes.find((item) => [item.key, ...item.members.map((member) => `${member.kind}:${member.row.id}`)].includes(canonicalKey))
    selectRow(kind, row, node?.members)
  }, [projected, selectRow])
  useEffect(() => {
    if (!restoreSelect) return
    const [kind, ...id] = restoreSelect.split(':')
    selectById(kind as RowKind, id.join(':'))
    setRestoreSelect(null)
  }, [restoreSelect, selectById])
  useEffect(() => {
    setSelected((current) => {
      if (current?.type !== 'row') return current
      const row = projected.rawState.rows[current.kind].find((item) => item.id === current.row.id)
        ?? projected.rawState.clips[current.kind].get(current.row.id)?.row
      if (!row || row === current.row) return current
      const next = { ...current, row }
      selectedRef.current = next
      return next
    })
  }, [projected.rawState])
  const searchResults = useMemo<SearchResult[]>(() => {
    const diagrams: SearchResult[] = [{ id: 'canvas', kind: 'diagram', label: 'Canvas', meta: 'Architecture', onChoose: () => setView({ deps: null }) }]
    const rows = (['systems', 'subsystems', 'containers', 'components', 'code', 'users', 'interfaces'] as RowKind[])
      .flatMap((kind) => projected.rawState.rows[kind].map((row) => ({
        id: row.id,
        kind,
        label: rowLabel(row),
        meta: KIND_LABEL[kind],
        onChoose: () => selectById(kind, row.id),
      })))
    return [...diagrams, ...rows]
  }, [projected.rawState.rows, selectById, setView])
  const copyLink = async () => {
    try {
      await copyViewLink({ ...view, layout: layoutMethod }, selectedKey)
      setCopyStatus('Link copied')
    } catch {
      setCopyStatus('Copy unavailable')
    }
  }
  const chooseLayout = (method: LayoutMethod) => {
    if (queryLayout) return
    saveLayoutMethod(window.localStorage, reportStorageId, method)
    setLayoutMethod(method)
    framedLayout.current = ''
    setView({ layout: method }, true)
  }
  const closeSearch = useCallback(() => {
    setSearchOpen(false)
    requestAnimationFrame(() => searchTrigger.current?.focus())
  }, [])

  const openDependencies = (key: string) => {
    const displayKey = projected.nodes.find((node) => [node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)].includes(key))?.key ?? key
    setView({ deps: displayKey }, true)
  }
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      const target = event.target
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
        return
      }
      if (target instanceof HTMLElement && target.matches('input, textarea, select, [contenteditable="true"]')) return
      if (event.key === 'Escape') {
        event.preventDefault()
        if (searchOpen) closeSearch()
        else {
          const menu = document.querySelector<HTMLDetailsElement>('.table-menu[open]')
          if (menu) menu.open = false
          else if (selected) closeInfo()
        }
        return
      }
      if (!(event.ctrlKey || event.metaKey) || !flow) return
      if (event.key === '+' || event.key === '=') { event.preventDefault(); void flow.zoomIn({ duration: 120 }) }
      if (event.key === '-') { event.preventDefault(); void flow.zoomOut({ duration: 120 }) }
      if (event.key === '0') { event.preventDefault(); void flow.fitView({ duration: 120, padding: 0.2 }) }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [closeInfo, closeSearch, flow, searchOpen, selected])

  return (
    <div className="app" data-hover={hoveredKey || hoveredEdgeId ? 'active' : 'off'} data-lens={view.lens.length ? 'active' : 'off'} data-selection={selected ? 'active' : 'off'} style={themeStyle(payload.theme)}>
      <header className="app-header">
        <div className="brand-lockup"><span className="brand-mark">OT</span><div><span>OneTool Architecture</span><strong>{payload.source}</strong></div></div>
        <button className="search-trigger" onClick={() => setSearchOpen(true)} ref={searchTrigger} type="button"><SearchIcon /><span>Search</span><kbd>⌘K</kbd></button>
      </header>

      <main className="workspace">
        <div className="dock-row">
          <ResizablePanel className="view-dock" label="View" layout={autoViewCollapsed ? { ...layout.docks.view, collapsed: true } : layout.docks.view} name="view" onChange={(dock) => { setAutoViewCollapsed(false); setDock('view', dock) }}>
            <ViewDock canvasActive={!view.deps} copyStatus={copyStatus} layoutMethod={displayedLayoutMethod} legend={legend} onCanvas={() => setView({ deps: null }, true)} onCopy={() => void copyLink()} onLayout={chooseLayout} onView={setView} payload={payload} view={view} />
          </ResizablePanel>

          <div className={`canvas-root depth-${depth}`} data-reading-depth={depth} ref={canvasRef}>
            {view.deps ? <DependencyView aspect={view.aspect} focusKey={view.deps} onClose={() => setView({ deps: null }, true)} onFocus={(key) => setView({ deps: key }, true)} onSelect={selectRow} projected={projected} /> : !projected.nodes.length && !projected.boundaries.length ? <div className="empty-state"><p>No entities match the current projection.</p><button onClick={() => setView({ deps: null, expand: [], lens: [] })} type="button">Show the full architecture</button></div> : <ReactFlow
              colorMode="light"
              edges={edges}
              edgeTypes={edgeTypes}
              minZoom={0.2}
              nodes={nodes}
              nodesConnectable={false}
              nodesDraggable={false}
              nodeTypes={nodeTypes}
              onEdgeClick={(_event, edge) => {
                const data = edge.data as SemanticData | undefined
                if (data) revealInfo({ type: 'edge', direction: data.direction, edge: data.edge })
              }}
              onEdgeMouseEnter={(_event, edge) => setHoveredEdgeId(edge.id)}
              onEdgeMouseLeave={() => setHoveredEdgeId(null)}
              onInit={(instance) => { setFlow(instance); setCanvasViewport(instance.getViewport()) }}
              onNodeClick={(_event, node) => {
                if (node.type === 'boundary') {
                  const boundary = (node.data as BoundaryData).boundary
                  selectRow(boundary.kind, boundary.row)
                } else {
                  const data = node.data as ArchitectureData
                  selectRow(data.kind, data.row, data.members)
                }
              }}
              onNodeDoubleClick={(_event, node) => {
                if (node.type !== 'architecture') return
                const data = node.data as ArchitectureData
                if (data.expandable) data.onExpand()
              }}
              onNodeMouseEnter={(_event, node) => { if (node.type !== 'boundary') setHoveredKey(node.id) }}
              onNodeMouseLeave={() => setHoveredKey(null)}
              onViewportChange={(viewport) => setCanvasViewport(viewport)}
              proOptions={{ hideAttribution: true }}
            >
              {mapOpen ? <MiniMap className="semantic-radar" pannable zoomable /> : null}
            </ReactFlow>}

            <div className="map-cluster-wrap">
              {mapOpen ? <span className="map-label">Map</span> : null}
              <div aria-label="Map, fit, and zoom" className="map-cluster" role="group">
                <button aria-label="Toggle map" aria-pressed={mapOpen} onClick={() => setMapOpen((open) => !open)} title="Map" type="button"><MapIcon /><span>Map</span></button>
                <button aria-label="Fit canvas" onClick={() => { if (flow) void flow.fitView({ duration: 150, padding: 0.2 }) }} title="Fit" type="button"><FitIcon /><span>Fit</span></button>
                <button aria-label="Zoom out" onClick={() => { if (flow) void flow.zoomOut({ duration: 120 }) }} title="Zoom out" type="button">−</button>
                <output aria-live="polite"><strong>{Math.round(zoom * 100)}%</strong><span>{depth}</span></output>
                <button aria-label="Zoom in" onClick={() => { if (flow) void flow.zoomIn({ duration: 120 }) }} title="Zoom in" type="button">+</button>
              </div>
              {!positions.size ? <span className="layout-indicator">Laying out</span> : null}
            </div>
          </div>

          <ResizablePanel className="info-dock" label="Info" layout={layout.docks.info} name="info" onChange={(dock) => setDock('info', dock)}>
            {selected ? <InfoPanel aspect={view.aspect} diff={diff} hasBack={selectionHistory.length > 0} key={selectionKey(selected)} onBack={goBack} onClose={closeInfo} onDependencyView={openDependencies} onSelect={selectRow} payload={payload} projected={projected} selection={selected} timeline={view.timeline} /> : <div className="info-empty"><span>Nothing selected</span><p>Select an item on Canvas or in Data.</p></div>}
          </ResizablePanel>
        </div>

        <ResizablePanel className="data-dock" label="Data" layout={layout.docks.data} name="data" onChange={(dock) => setDock('data', dock)}>
          <GridPanel
            density={layout.density}
            diff={diff}
            layouts={layout.tableLayouts}
            onDensity={(density) => setLayout((current) => ({ ...current, density }))}
            onDiagnostic={setDiagnostic}
            onLayout={(table, tableLayout) => setLayout((current) => ({ ...current, tableLayouts: { ...current.tableLayouts, [table]: tableLayout } }))}
            onSelect={selectById}
            onShowOnCanvas={(kind, id) => {
              const key = `${kind}:${id}`
              const expand = expansionPath(payload, key, false)
              setView({ deps: null, expand, scope: null }, true)
              selectById(kind, id)
            }}
            payload={payload}
            projected={projected}
            selectedKey={selectedKey}
            selectedOnCanvas={selectedDisplayKey !== null}
            timeline={view.timeline}
          />
        </ResizablePanel>
      </main>

      <div className="visually-hidden" aria-live="polite">
        <span><b data-testid="rendered-node-count">{projected.nodes.length}</b> nodes, {edges.length} connections</span>
      </div>
      <span aria-hidden="true" className="visually-hidden" data-testid="rendered-node-ids">{projected.nodes.map((node) => node.key).join(',')}</span>
      {searchOpen ? <GlobalSearch onClose={closeSearch} results={searchResults} /> : null}
      {diagnostic ? <div aria-live="polite" className="diagnostic"><span>{diagnostic}</span><button aria-label="Dismiss diagnostic" onClick={() => setDiagnostic('')} type="button">×</button></div> : null}
    </div>
  )
}
