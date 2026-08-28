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
import { edgeAnchors, type EdgeAnchorPair, type EdgeRect } from './edgeAnchors'
import {
  classifyEmphasis,
  edgeLabelVisible,
  interfacePort,
  splitEdgeDirections,
  type DirectionalSpline,
  type EdgeEmphasis,
  type InterfacePort,
  type SplineDirection,
} from './edgePresentation'
import { GlobalSearch, type SearchResult } from './GlobalSearch'
import { GridPanel } from './GridPanel'
import { FitIcon, MapIcon, SearchIcon } from './Icons'
import { applyPositions, makeLayoutKey, NODE_HEIGHT, NODE_WIDTH, unionLayout, type Positions } from './layout'
import { loadLayout, saveLayout, type DockName, type LayoutPreferences } from './layoutPreferences'
import { readPayload } from './payload'
import { diffStates, legendEntries, projectState, unionGraph } from './projection'
import { ResizablePanel } from './ResizablePanel'
import { splinePath, type SplinePath } from './splinePath'
import {
  type Aspect,
  type FieldChange,
  type GraphEdge,
  type GraphBoundary,
  type GraphNode,
  type EntityKind,
  type Level,
  type ReportPayload,
  type ReportRow,
  type RowRef,
  type RowKind,
  type StateDiff,
  type View,
} from './types'
import { copyViewLink, decodeView, persistView } from './view'
import { ViewDock } from './ViewDock'
import { READING_DEPTH, readingDepth } from './zoom'

type DiffStatus = 'added' | 'removed' | 'changed'
type ArchitectureData = {
  boundary: boolean
  changes: FieldChange[]
  childCount: number
  connectionCount: number
  context: string
  description: string
  drillable: boolean
  emphasis: 'normal' | 'emphasized' | 'neighbor' | 'unrelated'
  facts: Array<[string, string]>
  kind: EntityKind
  label: string
  members: RowRef[]
  onDrill: () => void
  row: ReportRow
  statuses: DiffStatus[]
  tags: string[]
}
type ArchitectureNode = Node<ArchitectureData, 'architecture'>
type BoundaryData = { boundary: GraphBoundary; label: string; onDrill: () => void }
type BoundaryNode = Node<BoundaryData, 'boundary'>
type CanvasNode = ArchitectureNode | BoundaryNode
type SemanticData = {
  anchors: EdgeAnchorPair
  direction: SplineDirection
  edge: GraphEdge
  emphasis: EdgeEmphasis | 'selected'
  hovered: boolean
  label: string
  labelPoint: SplinePath['labelPoint']
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
type Selection =
  | { type: 'row'; kind: RowKind; members: RowRef[]; row: ReportRow }
  | { type: 'edge'; direction: SplineDirection; edge: GraphEdge }

const payload = readPayload()
const STATUS_ORDER: DiffStatus[] = ['added', 'removed', 'changed']
const STATUS_ICON: Record<DiffStatus, string> = { added: '+', removed: '−', changed: 'Δ' }
const KIND_LABEL: Record<RowKind, string> = {
  systems: 'System',
  subsystems: 'Subsystem',
  containers: 'Container',
  components: 'Component',
  code: 'Code',
  users: 'User',
  interfaces: 'Interface',
  relationships: 'Relationship',
}

function rowLabel(row: ReportRow): string {
  return row.name ?? row.action ?? row.id
}

function connectionLabel(row: ReportRow, aspect: Aspect): string {
  const direction = aspect === 'data-flow' ? row.data_flow_direction ?? 'provider_to_consumer' : row.call_direction ?? 'consumer_to_provider'
  if (direction === 'bidirectional') return `${row.provider} ↔ ${row.consumer}`
  return direction === 'provider_to_consumer' ? `${row.provider} → ${row.consumer}` : `${row.consumer} → ${row.provider}`
}

function DrillIcon() {
  return <svg aria-hidden="true" viewBox="0 0 16 16"><path d="M3 3h5v2H5v6h6V8h2v5H3z" /><path d="M8 3h5v5h-2V6.4l-4.3 4.3-1.4-1.4L9.6 5H8z" /></svg>
}

function ArchitectureNodeView({ data, selected }: NodeProps<ArchitectureNode>) {
  return (
    <article
      className="architecture-node"
      data-boundary={data.boundary ? 'true' : 'false'}
      data-member-count={data.members.length}
      data-emphasis={data.emphasis}
      data-selected={selected ? 'true' : 'false'}
      data-status={data.statuses.join(' ')}
    >
      <div className="node-heading"><span className="kind-pill">{KIND_LABEL[data.kind]}</span>{data.boundary ? <span className="external-pill">External</span> : null}</div>
      <strong className="node-name" title={data.label}>{data.label}</strong>
      <p className="node-description">{data.description}</p>
      <span className="node-context">{data.context}</span>
      <dl className="node-facts">{data.facts.map(([key, value]) => <div key={key} title={`${key}: ${value}`}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
      <div className="node-counts">
        {data.childCount ? <span title={`${data.childCount} children`}>{data.childCount} children</span> : null}
        {data.connectionCount ? <span title={`${data.connectionCount} connections`}>{data.connectionCount} connections</span> : null}
      </div>
      {data.drillable ? <button aria-label={`Drill into ${data.label}`} className="drill-button" onClick={(event) => { event.stopPropagation(); data.onDrill() }} title="Drill into direct children" type="button"><DrillIcon /></button> : null}
      {data.statuses.length ? (
        <span aria-label={`Changes: ${data.statuses.join(', ')}`} className="diff-badges">
          {data.statuses.map((status) => <b data-status={status} key={status}>{STATUS_ICON[status]}</b>)}
        </span>
      ) : null}
      {data.changes.length ? (
        <details className="change-popover">
          <summary aria-label={`Show ${data.label} field changes`}>Δ</summary>
          <ul>{data.changes.map((change, index) => (
            <li key={`${change.field}:${index}`}>
              <strong>{change.field}</strong>
              <span>{JSON.stringify(change.old)} → {JSON.stringify(change.new)}</span>
            </li>
          ))}</ul>
        </details>
      ) : null}
      <Handle position={Position.Left} type="target" />
      <Handle position={Position.Right} type="source" />
    </article>
  )
}

function BoundaryNodeView({ data, selected }: NodeProps<BoundaryNode>) {
  return (
    <section className="containment-boundary" data-selected={selected ? 'true' : 'false'} data-stub={data.boundary.stub ? 'true' : 'false'}>
      <header><span className="kind-pill">{KIND_LABEL[data.boundary.kind]}</span><strong>{data.label}</strong><button aria-label={`Drill into ${data.label}`} onClick={(event) => { event.stopPropagation(); data.onDrill() }} type="button"><DrillIcon /></button></header>
    </section>
  )
}

function SemanticEdge({
  data,
  id,
}: EdgeProps<SemanticFlowEdge>) {
  if (!data) return null
  const path = data.path
  const statuses = data?.statuses ?? []
  const emphasis = data?.emphasis ?? 'normal'
  const markerId = `arrow-${id.replace(/[^a-zA-Z0-9_-]/g, '-')}`
  const arrowSize = Math.max(8, 8 / Math.max(data.zoom, 0.2))
  const strokeWidth = Math.max(1.5, 1.5 / Math.max(data.zoom, 0.2))
  const emphasized = ['outgoing', 'incoming', 'neighbor', 'selected'].includes(emphasis)
  const diffIncrement = statuses.includes('added') || statuses.includes('changed') ? 0.25 : 0
  const edgeStyle = { strokeWidth: strokeWidth + (emphasized ? 0.8 : diffIncrement) } as CSSProperties
  const focusStyle = { strokeWidth: strokeWidth + 5 } as CSSProperties
  const expandedPort = data.showLabel
  return (
    <>
      <defs>
        <marker id={markerId} markerHeight={arrowSize} markerUnits="userSpaceOnUse" markerWidth={arrowSize} orient="auto" refX="9" refY="5" viewBox="0 0 10 10">
          <path className={`semantic-arrow is-${emphasis} ${statuses.map((status) => `is-${status}`).join(' ')}`} d="M 0 0 L 10 5 L 0 10 z" />
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
        {data.showLabel ? <button className="edge-label" data-emphasis={emphasis} data-status={statuses.join(' ')} onClick={data.onSelect} onMouseEnter={() => data.onHover(true)} onMouseLeave={() => data.onHover(false)} style={{ transform: `translate(-50%, -50%) translate(${data.labelPoint.x}px,${data.labelPoint.y}px)` }} type="button">
          {data.label}
          {data.memberCount > 1 ? <i>{data.memberCount}</i> : null}
          {statuses.map((status) => <b data-status={status} key={status}>{STATUS_ICON[status]}</b>)}
        </button> : null}
        {data.port ? <button aria-label={`Interface port ${data.port.label}`} className="interface-port" data-expanded={expandedPort ? 'true' : 'false'} onClick={data.onSelect} onMouseEnter={() => data.onHover(true)} onMouseLeave={() => data.onHover(false)} style={{ transform: `translate(-50%, -50%) translate(${data.port.point.x}px,${data.port.point.y}px)` }} title={data.port.label} type="button">
          {expandedPort ? <>{data.port.label}{data.port.count > 1 ? <i>{data.port.count}</i> : null}</> : null}
        </button> : null}
      </EdgeLabelRenderer>
    </>
  )
}

const nodeTypes = { architecture: memo(ArchitectureNodeView), boundary: memo(BoundaryNodeView) }
const edgeTypes = { semantic: memo(SemanticEdge) }

function SidePanel({
  aspect,
  onClose,
  onDependencyView,
  onSelect,
  projected,
  selection,
}: {
  aspect: Aspect
  onClose: () => void
  onDependencyView: (key: string) => void
  onSelect: (kind: RowKind, row: ReportRow) => void
  projected: ReturnType<typeof projectState>
  selection: Selection
}) {
  const [tab, setTab] = useState<'details' | 'connections'>('details')
  const rowsById = useMemo(() => new Map(Object.entries(projected.rawState.rows).flatMap(([kind, rows]) => rows.map((row) => [row.id, { kind: kind as RowKind, row }] as const))), [projected])
  const edge = selection.type === 'edge' ? selection.edge : null
  const row = selection.type === 'row' ? selection.row : null
  const kind = selection.type === 'row' ? selection.kind : null
  const targetIds = edge
    ? new Set([edge.a.split(':').slice(1).join(':'), edge.b.split(':').slice(1).join(':')])
    : new Set(kind === 'interfaces' ? [row?.provider, row?.consumer] : kind === 'relationships' ? [row?.source, row?.target] : [row?.id, ...(selection.type === 'row' ? selection.members.map((member) => member.row.id) : [])])
  const selectedNodeKey = selection.type === 'row' && selection.kind !== 'interfaces' && selection.kind !== 'relationships'
    ? `${selection.kind}:${selection.row.id}` : null
  const selectedEdges = selectedNodeKey ? projected.edges.filter((item) => item.a === selectedNodeKey || item.b === selectedNodeKey) : []
  const connections = [...new Map([
    ...selectedEdges.flatMap((item) => item.interfaceRows),
    ...projected.rawState.rows.interfaces.filter((item) => targetIds.has(item.provider) || targetIds.has(item.consumer)),
  ].map((item) => [item.id, item])).values()]
  const groupedConnections = { incoming: [] as ReportRow[], outgoing: [] as ReportRow[] }
  if (selectedNodeKey) for (const item of selectedEdges) {
    for (const spline of splitEdgeDirections(item, aspect)) {
      const interfaces = spline.members.filter((member) => member.kind === 'interfaces').map((member) => member.row)
      if (spline.target === selectedNodeKey) groupedConnections.incoming.push(...interfaces)
      if (spline.source === selectedNodeKey) groupedConnections.outgoing.push(...interfaces)
    }
  } else if (row && kind !== 'interfaces' && kind !== 'relationships') for (const item of connections) {
    const direction = aspect === 'data-flow' ? item.data_flow_direction ?? 'provider_to_consumer' : item.call_direction ?? 'consumer_to_provider'
    const pairs = direction === 'provider_to_consumer' ? [[item.provider, item.consumer]]
      : direction === 'bidirectional' ? [[item.provider, item.consumer], [item.consumer, item.provider]]
        : [[item.consumer, item.provider]]
    if (pairs.some(([, to]) => to === row.id)) groupedConnections.incoming.push(item)
    if (pairs.some(([from]) => from === row.id)) groupedConnections.outgoing.push(item)
  }
  const members = edge ? [...edge.interfaceRows, ...edge.relationshipRows] : []
  const parentId = row?.parent ?? row?.container ?? row?.component
  const clip = kind && row ? projected.rawState.clips[kind].get(row.id) : undefined
  const ordinaryFields = row ? Object.entries(row).filter(([key, value]) => (
    !['id', 'name', 'action', 'description', 'tags', 'properties', 'intervals', 'parent', 'container', 'component'].includes(key) && value !== undefined
  )) : []
  const firstMember = members[0]
  const title = row ? rowLabel(row) : firstMember
    ? `${rowLabel(firstMember)}${members.length > 1 ? ` and ${members.length - 1} more` : ''}` : 'Connection'
  return (
    <div className="side-panel-body">
      <header>
        <div><span className="panel-kicker">{kind ? KIND_LABEL[kind].toUpperCase() : 'CONNECTION'}</span><h2>{title}</h2>{row ? <code>{row.id}</code> : null}</div>
        <button aria-label="Close details" className="icon-button" onClick={onClose} type="button">×</button>
      </header>
      <nav aria-label="Selection details"><button aria-pressed={tab === 'details'} onClick={() => setTab('details')} type="button">Details</button><button aria-pressed={tab === 'connections'} onClick={() => setTab('connections')} type="button">Connections</button></nav>
      {tab === 'details' ? <div className="side-panel-scroll">
        {row?.description ? <p>{row.description}</p> : null}
        {row ? <dl>
          <div><dt>Status</dt><dd>{clip ? `Retired, clipped by ${clip.by}` : 'Live at this position'}</dd></div>
          {parentId ? <div><dt>Belongs to</dt><dd><button onClick={() => { const parent = rowsById.get(parentId); if (parent) onSelect(parent.kind, parent.row) }} type="button">{rowsById.get(parentId)?.row.name ?? parentId}</button></dd></div> : null}
          <div><dt>Contains</dt><dd>{[...rowsById.values()].filter((item) => [item.row.parent, item.row.container, item.row.component].includes(row.id)).length}</dd></div>
          {ordinaryFields.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}
          {Object.entries(row.properties ?? {}).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{Array.isArray(value) ? value.join(', ') : value}</dd></div>)}
        </dl> : <ul className="member-list">{members.map((member) => <li key={member.id}><button onClick={() => onSelect(edge?.interfaceRows.includes(member) ? 'interfaces' : 'relationships', member)} type="button">{rowLabel(member)} <code>{member.id}</code></button></li>)}</ul>}
        {row?.tags?.length ? <div className="passport-chips">{row.tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
      </div> : <div className="side-panel-scroll">
        {edge ? <p>{edge.a} ↔ {edge.b} · {edge.interfaceRows.length} interfaces · {edge.relationshipRows.length} relationships</p> : null}
        {(Object.entries(groupedConnections) as Array<['incoming' | 'outgoing', ReportRow[]]>).map(([direction, items]) => <div key={direction}><h3>{direction}</h3><ul className="connection-list">{items.map((item) => <li key={item.id}><button onClick={() => onSelect('interfaces', item)} type="button"><strong>{rowLabel(item)}</strong><span>{connectionLabel(item, aspect)}</span></button></li>)}</ul></div>)}
        {members.length ? <><h3>Canonical members</h3><ul className="member-list">{members.map((member) => <li key={member.id}><button onClick={() => onSelect(edge?.interfaceRows.includes(member) ? 'interfaces' : 'relationships', member)} type="button">{rowLabel(member)}</button></li>)}</ul></> : null}
        <button disabled={!selectedNodeKey} onClick={() => { if (selectedNodeKey) onDependencyView(selectedNodeKey) }} type="button">Open dependency view</button>{!selectedNodeKey ? <p>Choose an entity to open its dependency view.</p> : null}
      </div>}
    </div>
  )
}

function statusesForNode(node: GraphNode, diff: StateDiff | null): DiffStatus[] {
  if (!diff) return []
  const keys = new Set([node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)])
  const found = new Set<DiffStatus>()
  if (diff.added.some((item) => keys.has(`${item.kind}:${item.id}`))) found.add('added')
  if (diff.removed.some((item) => keys.has(`${item.kind}:${item.id}`))) found.add('removed')
  if (diff.changed.some((item) => keys.has(`${item.kind}:${item.id}`))) found.add('changed')
  return STATUS_ORDER.filter((status) => found.has(status))
}

function changesForNode(node: GraphNode, diff: StateDiff | null): FieldChange[] {
  if (!diff) return []
  const keys = new Set([node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)])
  return diff.changed.filter((item) => keys.has(`${item.kind}:${item.id}`)).flatMap((item) => item.changes)
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
      labelPoint: route.labelPoint,
      memberCount: spline.members.length,
      onHover,
      onSelect,
      port: interfacePort(spline, anchors),
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
  const focus = projected.nodes.find((node) => node.key === focusKey)
  if (!focus) return <div className="empty-state"><p>The focused entity is not in this projection.</p><button onClick={onClose} type="button">Return to map</button></div>
  const incoming: Array<{ edge: GraphEdge; node: GraphNode }> = []
  const outgoing: Array<{ edge: GraphEdge; node: GraphNode }> = []
  for (const edge of projected.edges.filter((item) => item.a === focusKey || item.b === focusKey)) {
    const neighbor = projected.nodes.find((node) => node.key === (edge.a === focusKey ? edge.b : edge.a))
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
      <header><div><span className="panel-kicker">DEPENDENCY FOCUS</span><h2>{rowLabel(focus.row)}</h2><p>{incoming.length} incoming · {outgoing.length} outgoing · {new Set([...incoming, ...outgoing].flatMap(({ edge }) => [...edge.interfaces, ...edge.relationships])).size} connections</p><label>Focus <select aria-label="Dependency focus" onChange={(event) => { const node = projected.nodes.find((item) => item.key === event.target.value); if (node) { onFocus(node.key); onSelect(node.kind, node.row, node.members) } }} value={focusKey}>{projected.nodes.map((node) => <option key={node.key} value={node.key}>{rowLabel(node.row)}</option>)}</select></label></div><button aria-label="Close dependency view" onClick={onClose} type="button">×</button></header>
      <div className="dependency-columns">
        {column('Incoming', incoming)}
        <button className="dependency-focus-node" onClick={() => onSelect(focus.kind, focus.row, focus.members)} type="button"><span className="kind-pill">{KIND_LABEL[focus.kind]}</span><strong>{rowLabel(focus.row)}</strong></button>
        {column('Outgoing', outgoing)}
      </div>
    </section>
  )
}

const EMPTY_POSITIONS: Positions = new Map()

export default function App() {
  const [initial] = useState(() => decodeView(payload, globalThis.location?.hash ?? ''))
  const [view, setViewState] = useState<View>(initial.view)
  const [selected, setSelected] = useState<Selection | null>(null)
  const [restoreSelect, setRestoreSelect] = useState<string | null>(initial.select)
  const [layoutResult, setLayoutResult] = useState<{ key: string; positions: Positions }>({ key: '', positions: new Map() })
  const [flow, setFlow] = useState<ReactFlowInstance<CanvasNode, SemanticFlowEdge> | null>(null)
  const [layout, setLayout] = useState<LayoutPreferences>(() => loadLayout(window.localStorage))
  const [copyStatus, setCopyStatus] = useState('')
  const [diagnostic, setDiagnostic] = useState('')
  const [zoom, setZoom] = useState(1)
  const [mapOpen, setMapOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [autoViewCollapsed, setAutoViewCollapsed] = useState(false)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
  const framedLayout = useRef('')
  const cameraFrame = useRef(0)
  const searchTrigger = useRef<HTMLButtonElement>(null)
  const setView = useCallback((change: Partial<View>, push = false) => setViewState((current) => {
    const next = { ...current, ...change }
    if (push) persistView(next, true)
    return next
  }), [])
  const revealInfo = useCallback((selection: Selection) => {
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
    setSelected(null)
    setAutoViewCollapsed(false)
    setLayout((current) => ({ ...current, docks: { ...current.docks, info: { ...current.docks.info, collapsed: true } } }))
  }, [])
  const depth = readingDepth(zoom)

  const projected = useMemo(() => projectState(payload, view), [view])
  const previousPosition = view.position > 0 ? view.position - 1 : null
  const diff = useMemo(() => previousPosition === null
    ? null
    : diffStates(payload, view.timeline, previousPosition, view.position), [previousPosition, view.position, view.timeline])
  const compared = useMemo(() => previousPosition === null
    ? null
    : projectState(payload, { ...view, position: previousPosition }), [previousPosition, view])
  const union = useMemo(() => unionGraph(payload, view.timeline, view.level, view.drill), [view.drill, view.level, view.timeline])
  const layoutKey = makeLayoutKey(view)
  const cardSizes = useMemo(() => new Map(union.nodes.map((node) => [node.key, cardSize(node, view.level, measureCardText)])), [union, view.level])
  // A layout computed for a different projection must never apply
  // (INT-STATE-06): stale positions carry parentIds for boundaries that no
  // longer exist in the current graph.
  const positions = layoutResult.key === layoutKey ? layoutResult.positions : EMPTY_POSITIONS
  const legend = useMemo(() => legendEntries(projected), [projected])

  const selectedKey = selected?.type === 'row' ? `${selected.kind}:${selected.row.id}` : null
  const selectedDisplayKey = useMemo(() => projected.nodes.find((node) => selectedKey
    && [node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)].includes(selectedKey))?.key ?? null, [projected.nodes, selectedKey])
  const selectedSplineId = selected?.type === 'edge' ? `${selected.edge.key}:${selected.direction}` : null
  useEffect(() => {
    for (const message of initial.diagnostics) console.warn(message)
  }, [initial])
  useEffect(() => persistView(view, false, selectedKey), [selectedKey, view])
  useEffect(() => {
    const restore = () => {
      const decoded = decodeView(payload, globalThis.location?.hash ?? '')
      for (const message of decoded.diagnostics) console.warn(message)
      setViewState(decoded.view)
      setRestoreSelect(decoded.select)
      if (!decoded.select) closeInfo()
    }
    window.addEventListener('popstate', restore)
    return () => window.removeEventListener('popstate', restore)
  }, [closeInfo])
  useEffect(() => { saveLayout(window.localStorage, layout) }, [layout])
  useEffect(() => {
    let active = true
    const rect = canvasRef.current?.getBoundingClientRect()
    const aspectRatio = rect?.height ? rect.width / rect.height : 1.6
    void unionLayout(union, layoutKey, cardSizes, aspectRatio)
      .then((next) => { if (active) setLayoutResult({ key: layoutKey, positions: next }) })
      .catch(() => { if (active) setDiagnostic('Layout failed. The report remains available with fallback positions.') })
    return () => { active = false }
  }, [cardSizes, layoutKey, union])

  const graphNodes = useMemo(() => {
    const merged = new Map(projected.nodes.map((node) => [node.key, { node, ghost: false }]))
    for (const node of compared?.nodes ?? []) {
      const statuses = statusesForNode(node, diff)
      if (!merged.has(node.key) && statuses.includes('removed')) merged.set(node.key, { node, ghost: true })
    }
    return [...merged.values()]
  }, [compared, diff, projected.nodes])
  const nodes = useMemo<CanvasNode[]>(() => {
    const byId = new Map(Object.entries(projected.rawState.rows).flatMap(([kind, rows]) => rows.map((row) => [row.id, { kind: kind as RowKind, row }] as const)))
    const propertyCounts = new Map<string, number>()
    for (const { node } of graphNodes) for (const key of Object.keys(node.row.properties ?? {})) propertyCounts.set(key, (propertyCounts.get(key) ?? 0) + 1)
    const factKeys = [...propertyCounts].sort(([leftKey, leftCount], [rightKey, rightCount]) => rightCount - leftCount || leftKey.localeCompare(rightKey)).slice(0, 3).map(([key]) => key)
    const memberKeys = (node: GraphNode) => new Set([node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)])
    const lensMatched = new Set(graphNodes.filter(({ node }) => nodeTags(node).some((tag) => view.lens.includes(tag))).map(({ node }) => node.key))
    const directionalEdges = projected.edges.flatMap((edge) => splitEdgeDirections(edge, view.aspect))
    const classified = classifyEmphasis(graphNodes.map(({ node }) => node.key), directionalEdges, selectedDisplayKey, lensMatched)
    const neighborKeys = (keys: Set<string>) => new Set(projected.edges.flatMap((edge) => keys.has(edge.a) ? [edge.b] : keys.has(edge.b) ? [edge.a] : []))
    const selectedNodes = new Set(graphNodes.filter(({ node }) => selectedKey && memberKeys(node).has(selectedKey)).map(({ node }) => node.key))
    const hoverNodes = new Set(hoveredKey ? [hoveredKey] : [])
    const hoverNeighbors = neighborKeys(hoverNodes)
    const emphasis = (key: string): ArchitectureData['emphasis'] => {
      if (selectedDisplayKey) return classified.nodes[key]
      if (selected?.type === 'edge') return key === selected.edge.a || key === selected.edge.b ? 'neighbor' : 'unrelated'
      if (view.lens.length) return classified.nodes[key]
      if (hoverNodes.size) return hoverNodes.has(key) ? 'emphasized' : hoverNeighbors.has(key) ? 'neighbor' : 'unrelated'
      return 'normal'
    }
    const boundaryEntityKeys = new Set(projected.boundaries.filter((boundary) => !boundary.stub).map((boundary) => boundary.nodeKey))
    const edgeEndpoints = new Set(projected.edges.flatMap((edge) => [edge.a, edge.b]))
    const visibleGraphNodes = graphNodes.filter(({ node }) => !boundaryEntityKeys.has(node.key) || edgeEndpoints.has(node.key))
    const architectureNodes: ArchitectureNode[] = visibleGraphNodes.map(({ ghost, node }, index) => {
      const parentId = node.row.parent ?? node.row.container ?? node.row.component
      const parent = parentId ? byId.get(parentId)?.row : undefined
      const childCount = Object.values(projected.rawState.rows).flat().filter((row) => [row.parent, row.container, row.component].includes(node.row.id)).length
      const connectionCount = new Set(projected.edges.filter((edge) => edge.a === node.key || edge.b === node.key)
        .flatMap((edge) => [...edge.interfaces, ...edge.relationships])).size
      const size = cardSizes.get(node.key) ?? { width: NODE_WIDTH, height: NODE_HEIGHT }
      return {
        data: {
          boundary: node.boundary,
          changes: changesForNode(node, diff),
          childCount,
          connectionCount,
          context: parent ? rowLabel(parent) : KIND_LABEL[node.kind],
          description: node.row.description ?? '',
          drillable: childCount > 0,
          emphasis: emphasis(node.key),
          facts: factKeys.flatMap((key) => {
            const value = node.row.properties?.[key]
            return value === undefined ? [] : [[key, Array.isArray(value) ? value.join(', ') : value] as [string, string]]
          }),
          kind: node.kind,
          label: rowLabel(node.row),
          members: node.members,
          onDrill: () => setView({ deps: null, drill: node.key }, true),
          row: node.row,
          statuses: ghost ? ['removed'] : statusesForNode(node, diff),
          tags: nodeTags(node),
        },
        height: size.height,
        id: node.key,
        position: { x: index * 280, y: 0 },
        selected: selectedNodes.has(node.key),
        type: 'architecture',
        width: size.width,
      }
    })
    const boundaryByKey = new Map(projected.boundaries.map((boundary) => [boundary.key, boundary]))
    const boundaryDepth = (boundary: GraphBoundary): number => boundary.parentKey
      ? 1 + boundaryDepth(boundaryByKey.get(boundary.parentKey)!) : 0
    const boundaryNodes: BoundaryNode[] = projected.boundaries.filter((boundary) => !boundary.stub)
      .sort((left, right) => boundaryDepth(left) - boundaryDepth(right) || left.key.localeCompare(right.key)).map((boundary) => ({
      data: {
        boundary,
        label: rowLabel(boundary.row),
        onDrill: () => setView({ deps: null, drill: boundary.nodeKey }, true),
      },
      id: boundary.key,
      position: { x: 0, y: 0 },
      selectable: true,
      selected: selectedKey === boundary.nodeKey,
      style: { zIndex: -1 },
      type: 'boundary',
    }))
    return applyPositions([...boundaryNodes, ...architectureNodes], positions) as CanvasNode[]
  }, [cardSizes, diff, graphNodes, hoveredKey, positions, projected, selected, selectedDisplayKey, selectedKey, setView, view.aspect, view.lens])

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
    const classified = classifyEmphasis(projected.nodes.map((node) => node.key), rendered.map(({ spline }) => spline), selectedDisplayKey, lensMatched)
    const edgeEmphasis = (spline: DirectionalSpline): SemanticData['emphasis'] => {
      if (selectedSplineId) return spline.id === selectedSplineId ? 'selected' : 'unrelated'
      if (selectedDisplayKey || view.lens.length) return classified.edges[spline.id]
      if (hoveredEdgeId) return spline.id === hoveredEdgeId ? 'selected' : 'unrelated'
      if (hoveredKey) return spline.source === hoveredKey || spline.target === hoveredKey ? 'neighbor' : 'unrelated'
      return 'normal'
    }
    return rendered.flatMap(({ edge, ghost, spline }, _index, all) => {
      const sourceRect = absoluteRect(spline.source, positions)
      const targetRect = absoluteRect(spline.target, positions)
      if (!sourceRect || !targetRect) return []
      const siblings = all.filter((item) => item.edge.key === edge.key)
      const laneIndex = siblings.findIndex((item) => item.spline.id === spline.id)
      const anchors = edgeAnchors(sourceRect, targetRect, laneIndex, siblings.length)
      const route = splinePath(anchors, obstacleRects)
      const isSelected = spline.id === selectedSplineId
      const isHovered = spline.id === hoveredEdgeId
      return [flowEdge(
        edge,
        spline,
        anchors,
        route,
        ghost ? ['removed'] : statusesForMembers(spline.members, diff),
        edgeEmphasis(spline),
        isSelected,
        isHovered,
        edgeLabelVisible(depth, isSelected, isHovered),
        zoom,
        () => revealInfo({ type: 'edge', direction: spline.direction, edge }),
        (hovered) => setHoveredEdgeId(hovered ? spline.id : null),
      )]
    })
  }, [depth, diff, graphEdges, hoveredEdgeId, hoveredKey, nodes, positions, projected.nodes, revealInfo, selectedDisplayKey, selectedSplineId, view.aspect, view.lens, zoom])

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
      void flow.setViewport(initialViewport(flow.getNodesBounds(nodeIds), visible, READING_DEPTH), { duration: 250 })
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
      return row && row !== current.row ? { ...current, row } : current
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
      await copyViewLink(view, selectedKey)
      setCopyStatus('Link copied')
    } catch {
      setCopyStatus('Copy unavailable')
    }
  }
  const closeSearch = useCallback(() => {
    setSearchOpen(false)
    requestAnimationFrame(() => searchTrigger.current?.focus())
  }, [])

  const openDependencies = (key: string) => {
    const displayKey = projected.nodes.find((node) => [node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)].includes(key))?.key ?? key
    setView({ deps: displayKey, drill: null }, true)
  }
  const parentKey = (key: string): string | null => {
    const [kind, ...idParts] = key.split(':')
    const row = payload.rows[kind as RowKind]?.find((item) => item.id === idParts.join(':'))
    const parentId = row?.parent ?? row?.container ?? row?.component
    if (!parentId) return null
    for (const parentKind of ['systems', 'subsystems', 'containers', 'components'] as EntityKind[]) {
      if (payload.rows[parentKind].some((item) => item.id === parentId)) return `${parentKind}:${parentId}`
    }
    return null
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
          const menu = document.querySelector<HTMLDetailsElement>('.table-menu[open], .change-popover[open]')
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

  const drillPath: string[] = []
  let drillCursor = view.drill
  while (drillCursor) {
    const [kind, ...id] = drillCursor.split(':')
    const row = payload.rows[kind as RowKind]?.find((item) => item.id === id.join(':'))
    if (row) drillPath.unshift(rowLabel(row))
    drillCursor = parentKey(drillCursor)
  }
  return (
    <div className="app" data-hover={hoveredKey || hoveredEdgeId ? 'active' : 'off'} data-lens={view.lens.length ? 'active' : 'off'} data-selection={selected ? 'active' : 'off'}>
      <header className="app-header">
        <div className="brand-lockup"><span className="brand-mark">OT</span><div><span>OneTool Architecture</span><strong>{payload.source}</strong></div></div>
        <button className="search-trigger" onClick={() => setSearchOpen(true)} ref={searchTrigger} type="button"><SearchIcon /><span>Search</span><kbd>⌘K</kbd></button>
      </header>

      <main className="workspace">
        <div className="dock-row">
          <ResizablePanel className="view-dock" label="View dock" layout={autoViewCollapsed ? { ...layout.docks.view, collapsed: true } : layout.docks.view} name="view" onChange={(dock) => { setAutoViewCollapsed(false); setDock('view', dock) }}>
            <ViewDock canvasActive={!view.deps} copyStatus={copyStatus} drillPath={drillPath} legend={legend} onCanvas={() => setView({ deps: null }, true)} onCopy={() => void copyLink()} onUp={() => setView({ drill: parentKey(view.drill!), deps: null }, true)} onView={setView} payload={payload} view={view} />
          </ResizablePanel>

          <div className={`canvas-root depth-${depth}`} data-reading-depth={depth} ref={canvasRef}>
            {view.deps ? <DependencyView aspect={view.aspect} focusKey={view.deps} onClose={() => setView({ deps: null }, true)} onFocus={(key) => setView({ deps: key }, true)} onSelect={selectRow} projected={projected} /> : !projected.nodes.length ? <div className="empty-state"><p>No entities match the current projection.</p><button onClick={() => setView({ deps: null, drill: null, lens: [] })} type="button">Show the full architecture</button></div> : <ReactFlow
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
              onInit={(instance) => { setFlow(instance); setZoom(instance.getZoom()) }}
              onNodeClick={(_event, node) => {
                if (node.type === 'boundary') {
                  const boundary = (node.data as BoundaryData).boundary
                  selectRow(boundary.kind, boundary.row)
                } else {
                  const data = node.data as ArchitectureData
                  selectRow(data.kind, data.row, data.members)
                }
              }}
              onNodeMouseEnter={(_event, node) => { if (node.type !== 'boundary') setHoveredKey(node.id) }}
              onNodeMouseLeave={() => setHoveredKey(null)}
              onViewportChange={(viewport) => setZoom(viewport.zoom)}
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

          <ResizablePanel className="info-dock" label="Info dock" layout={layout.docks.info} name="info" onChange={(dock) => { if (dock.collapsed) closeInfo(); else setDock('info', dock) }}>
            {selected ? <SidePanel aspect={view.aspect} onClose={closeInfo} onDependencyView={openDependencies} onSelect={selectRow} projected={projected} selection={selected} /> : <div className="info-empty"><span>Info</span><p>Select an item on Canvas or in Data.</p></div>}
          </ResizablePanel>
        </div>

        <ResizablePanel className="data-dock" label="Data dock" layout={layout.docks.data} name="data" onChange={(dock) => setDock('data', dock)}>
          <GridPanel
            density={layout.density}
            diff={diff}
            layouts={layout.tableLayouts}
            onDensity={(density) => setLayout((current) => ({ ...current, density }))}
            onDiagnostic={setDiagnostic}
            onLayout={(table, tableLayout) => setLayout((current) => ({ ...current, tableLayouts: { ...current.tableLayouts, [table]: tableLayout } }))}
            onSelect={selectById}
            payload={payload}
            projected={projected}
            selectedKey={selectedKey}
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
