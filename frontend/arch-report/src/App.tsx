import {
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  getSmoothStepPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from '@xyflow/react'
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { GridPanel } from './GridPanel'
import { applyPositions, NODE_HEIGHT, NODE_WIDTH, unionLayout, type Positions } from './layout'
import { loadLayout, saveLayout, type LayoutPreferences, type PanelName } from './layoutPreferences'
import { readPayload } from './payload'
import { diffStates, legendEntries, projectState, unionGraph } from './projection'
import { ResizablePanel } from './ResizablePanel'
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
import { copyViewLink, defaultView, persistView } from './view'
import { readingDepth } from './zoom'

type DiffStatus = 'added' | 'removed' | 'changed'
type ArchitectureData = {
  boundary: boolean
  changes: FieldChange[]
  childCount: number
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
  edge: GraphEdge
  emphasis: 'normal' | 'outgoing' | 'incoming' | 'both' | 'neighbor' | 'unrelated'
  label: string
  memberCount: number
  onSelect: () => void
  statuses: DiffStatus[]
}
type SemanticFlowEdge = Edge<SemanticData, 'semantic'>
type Selection =
  | { type: 'row'; kind: RowKind; members: RowRef[]; row: ReportRow }
  | { type: 'edge'; edge: GraphEdge }

const payload = readPayload()
const STATUS_ORDER: DiffStatus[] = ['added', 'removed', 'changed']
const STATUS_ICON: Record<DiffStatus, string> = { added: '+', removed: '−', changed: 'Δ' }
const KIND_LABEL: Record<RowKind, string> = {
  systems: 'System',
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

function entityIcon(kind: EntityKind, row: ReportRow): string {
  if (kind === 'users') return '♙'
  const technology = String(row.properties?.technology ?? row.properties?.type ?? '').toLowerCase()
  if (/(database|store|postgres|sql|redis|cache)/.test(technology)) return '◉'
  if (/(browser|web|react|ui)/.test(technology)) return '▣'
  if (kind === 'systems') return '⬡'
  if (kind === 'containers') return '▱'
  if (kind === 'components') return '◇'
  return '⌁'
}

function connectionLabel(row: ReportRow, aspect: Aspect): string {
  const direction = aspect === 'data-flow' ? row.data_flow_direction ?? 'provider_to_consumer' : row.call_direction ?? 'consumer_to_provider'
  if (direction === 'bidirectional') return `${row.provider} ↔ ${row.consumer}`
  return direction === 'provider_to_consumer' ? `${row.provider} → ${row.consumer}` : `${row.consumer} → ${row.provider}`
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
      <span className="node-context">{data.context}</span>
      <div className="node-identity"><span aria-hidden="true" className="node-icon">{data.boundary ? '◁' : entityIcon(data.kind, data.row)}</span><strong>{data.label}</strong></div>
      <p className="node-description">{data.description}</p>
      <span className="node-subtitle">{data.boundary ? 'BOUNDARY STUB' : KIND_LABEL[data.kind].toUpperCase()}</span>
      <dl className="node-facts">{data.facts.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
      <div className="node-badges">
        {data.childCount ? <span title={`${data.childCount} children`}>{data.childCount} children</span> : null}
        {data.tags.length ? <span title={data.tags.join(', ')}>{data.tags.length} tags</span> : null}
      </div>
      {data.drillable ? <button aria-label={`Drill into ${data.label}`} className="drill-button" onClick={(event) => { event.stopPropagation(); data.onDrill() }} title="Drill into direct children" type="button">⌕</button> : null}
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
      {[25, 50, 75].map((top, index) => <Handle id={`target-${index}`} key={`target-${top}`} position={Position.Left} style={{ top: `${top}%` }} type="target" />)}
      {[25, 50, 75].map((top, index) => <Handle id={`source-${index}`} key={`source-${top}`} position={Position.Right} style={{ top: `${top}%` }} type="source" />)}
    </article>
  )
}

function BoundaryNodeView({ data, selected }: NodeProps<BoundaryNode>) {
  return (
    <section className="containment-boundary" data-selected={selected ? 'true' : 'false'} data-stub={data.boundary.stub ? 'true' : 'false'}>
      <header><span aria-hidden="true">{entityIcon(data.boundary.kind, data.boundary.row)}</span><strong>{data.label}</strong><button aria-label={`Drill into ${data.label}`} onClick={(event) => { event.stopPropagation(); data.onDrill() }} type="button">⌕</button></header>
    </section>
  )
}

function SemanticEdge({
  data,
  id,
  markerEnd,
  markerStart,
  sourcePosition,
  sourceX,
  sourceY,
  targetPosition,
  targetX,
  targetY,
}: EdgeProps<SemanticFlowEdge>) {
  const [path, x, y] = getSmoothStepPath({ sourcePosition, sourceX, sourceY, targetPosition, targetX, targetY })
  const statuses = data?.statuses ?? []
  const emphasis = data?.emphasis ?? 'normal'
  return (
    <>
      <BaseEdge className="semantic-edge-hit" id={`${id}:hit`} path={path} />
      <BaseEdge className={`semantic-edge-focus is-${emphasis}`} id={`${id}:focus`} path={path} />
      <BaseEdge
        className={`semantic-edge is-${emphasis} ${statuses.map((status) => `is-${status}`).join(' ')}`}
        id={id}
        markerEnd={markerEnd}
        markerStart={markerStart}
        path={path}
      />
      <EdgeLabelRenderer>
        <button className="edge-label" data-emphasis={emphasis} data-status={statuses.join(' ')} onClick={() => data?.onSelect()} style={{ transform: `translate(-50%, -50%) translate(${x}px,${y}px)` }} type="button">
          {data?.label ?? id}
          {(data?.memberCount ?? 0) > 1 ? <i>{data?.memberCount}</i> : null}
          {statuses.map((status) => <b data-status={status} key={status}>{STATUS_ICON[status]}</b>)}
        </button>
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
    const presentation = edgePresentation(item, aspect)
    const source = presentation.reverse ? item.b : item.a
    const target = presentation.reverse ? item.a : item.b
    if (presentation.bidirectional || target === selectedNodeKey) groupedConnections.incoming.push(...item.interfaceRows)
    if (presentation.bidirectional || source === selectedNodeKey) groupedConnections.outgoing.push(...item.interfaceRows)
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

function PositionControls({ payload, setView, view }: {
  payload: ReportPayload
  setView: (change: Partial<View>) => void
  view: View
}) {
  const timeline = payload.timelines[view.timeline]
  const milestones = timeline.milestones
  if (!milestones.length) return null
  const milestoneById = new Map(payload.milestones.map((milestone) => [milestone.id, milestone]))
  const label = view.position === 0
    ? 'Base'
    : milestoneById.get(milestones[view.position - 1])?.name ?? milestones[view.position - 1]
  return (
    <div className="time-controls control-group">
      <label>
        <span>Time</span>
        <input
          aria-label="Architecture position"
          max={milestones.length}
          min="0"
          onChange={(event) => setView({ position: Number(event.target.value) })}
          step="1"
          type="range"
          value={view.position}
        />
      </label>
      <output aria-live="polite">{view.position}. {label}</output>
      <label>
        <span>Compare</span>
        <select aria-label="Diff comparison" onChange={(event) => setView({ compare: event.target.value as View['compare'] })} value={view.compare}>
          <option value="off">Off</option>
          <option value="base">vs base</option>
          <option value="position">vs position</option>
        </select>
      </label>
      {view.compare === 'position' ? (
        <label>
          <span>Position</span>
          <input
            aria-label="Comparison position"
            max={milestones.length}
            min="0"
            onChange={(event) => setView({ comparePosition: Number(event.target.value) })}
            type="number"
            value={view.comparePosition}
          />
        </label>
      ) : null}
    </div>
  )
}

function ScopeControl({ disabled, payload, setView, view }: {
  disabled?: boolean
  payload: ReportPayload
  setView: (change: Partial<View>) => void
  view: View
}) {
  const systems = [...new Map(payload.rows.systems.map((row) => [row.id, row])).values()]
  const selected = new Set(view.scope?.systems ?? [])
  const toggle = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setView({ scope: next.size ? { systems: [...next], hops: view.scope?.hops ?? 1 } : null })
  }
  return (
    <details aria-disabled={disabled} className="scope-control control-group" onClick={(event) => { if (disabled) event.preventDefault() }}>
      <summary>Scope: {disabled ? 'disabled while drilled' : view.scope ? `${view.scope.systems.length} selected` : 'all'}</summary>
      <div className="scope-menu">
        <button onClick={() => setView({ scope: null })} type="button">All architecture</button>
        <label>
          <span>System hops</span>
          <input
            aria-label="System hops"
            max="20"
            min="0"
            onChange={(event) => setView({
              scope: { systems: view.scope?.systems ?? [systems[0]?.id].filter(Boolean), hops: Number(event.target.value) },
            })}
            type="number"
            value={view.scope?.hops ?? 1}
          />
        </label>
        <div className="scope-systems">{systems.map((system) => (
          <label key={system.id}>
            <input checked={selected.has(system.id)} onChange={() => toggle(system.id)} type="checkbox" />
            <span>{system.name ?? system.id}</span>
          </label>
        ))}</div>
      </div>
    </details>
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

function statusesForEdge(edge: GraphEdge, diff: StateDiff | null): DiffStatus[] {
  if (!diff) return []
  const interfaces = new Set(edge.interfaces)
  const relationships = new Set(edge.relationships)
  const includes = (kind: string, id: string) => (
    kind === 'interfaces' ? interfaces.has(id) : kind === 'relationships' && relationships.has(id)
  )
  const found = new Set<DiffStatus>()
  if (diff.added.some((item) => includes(item.kind, item.id))) found.add('added')
  if (diff.removed.some((item) => includes(item.kind, item.id))) found.add('removed')
  if (diff.changed.some((item) => includes(item.kind, item.id))) found.add('changed')
  return STATUS_ORDER.filter((status) => found.has(status))
}

function edgePresentation(edge: GraphEdge, aspect: Aspect): {
  bidirectional: boolean
  label: string
  reverse: boolean
  showArrow: boolean
} {
  const directions = new Set<'forward' | 'reverse'>()
  const addDirection = (from: string, to: string) => {
    if (from === edge.a && to === edge.b) directions.add('forward')
    if (from === edge.b && to === edge.a) directions.add('reverse')
  }
  if (aspect === 'ownership') {
    const relationActions = edge.relationshipRows.map((row) => row.action).filter(Boolean)
    edge.orientations.forEach(({ from, to }) => addDirection(from, to))
    return {
      bidirectional: directions.size === 2,
      label: relationActions.length ? relationActions.join(' · ') : edge.interfaceRows.map(rowLabel).join(' · '),
      reverse: directions.has('reverse') && !directions.has('forward'),
      showArrow: directions.size > 0,
    }
  }
  const field = aspect === 'call-direction' ? 'call_direction' : 'data_flow_direction'
  for (const row of edge.interfaceRows) {
    const orientation = edge.orientations.find((item) => item.kind === 'interfaces' && item.id === row.id)
    if (!orientation) continue
    const direction = row[field] ?? (
      aspect === 'call-direction' ? 'consumer_to_provider' : 'provider_to_consumer'
    )
    if (direction === 'provider_to_consumer' || direction === 'bidirectional') {
      addDirection(orientation.from, orientation.to)
    }
    if (direction === 'consumer_to_provider' || direction === 'bidirectional') {
      addDirection(orientation.to, orientation.from)
    }
  }
  return {
    bidirectional: directions.size === 2,
    label: edge.interfaceRows.length ? edge.interfaceRows.map(rowLabel).join(' · ') : 'No interface',
    reverse: directions.has('reverse') && !directions.has('forward'),
    showArrow: directions.size > 0,
  }
}

function flowEdge(
  edge: GraphEdge,
  aspect: Aspect,
  statuses: DiffStatus[],
  emphasis: SemanticData['emphasis'] = 'normal',
  onSelect: () => void = () => {},
): SemanticFlowEdge {
  const presentation = edgePresentation(edge, aspect)
  let source = edge.a
  let target = edge.b
  if (presentation.reverse) [source, target] = [target, source]
  return {
    data: {
      edge,
      emphasis,
      label: presentation.label || edge.key,
      memberCount: edge.interfaces.length + edge.relationships.length,
      onSelect,
      statuses,
    },
    id: edge.key,
    markerEnd: presentation.showArrow ? { type: MarkerType.ArrowClosed } : undefined,
    markerStart: presentation.bidirectional ? { type: MarkerType.ArrowClosed } : undefined,
    source,
    sourceHandle: `source-${[...edge.key].reduce((total, value) => total + value.charCodeAt(0), 0) % 3}`,
    target,
    targetHandle: `target-${[...edge.key].reduce((total, value) => total + value.charCodeAt(0), 0) % 3}`,
    type: 'semantic',
  }
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
    const presentation = edgePresentation(edge, aspect)
    const source = presentation.reverse ? edge.b : edge.a
    const target = presentation.reverse ? edge.a : edge.b
    const neighbor = projected.nodes.find((node) => node.key === (edge.a === focusKey ? edge.b : edge.a))
    if (!neighbor) continue
    if (presentation.bidirectional || target === focusKey) incoming.push({ edge, node: neighbor })
    if (presentation.bidirectional || source === focusKey) outgoing.push({ edge, node: neighbor })
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
        <button className="dependency-focus-node" onClick={() => onSelect(focus.kind, focus.row, focus.members)} type="button"><span>{entityIcon(focus.kind, focus.row)}</span><strong>{rowLabel(focus.row)}</strong><small>{KIND_LABEL[focus.kind]}</small></button>
        {column('Outgoing', outgoing)}
      </div>
    </section>
  )
}

function LegendPanel({ entries, lens, onLens }: {
  entries: Array<{ tag: string; count: number }>
  lens: string[]
  onLens: (tags: string[]) => void
}) {
  const selected = new Set(lens)
  const toggle = (tag: string) => {
    const next = new Set(selected)
    if (next.has(tag)) next.delete(tag)
    else next.add(tag)
    onLens(next.size === entries.length ? [] : [...next].sort())
  }
  return <div className="legend-content"><header><span>Tags</span>{lens.length ? <button onClick={() => onLens([])} type="button">Clear</button> : null}</header><div>{entries.map(({ tag, count }) => <button aria-pressed={selected.has(tag)} key={tag} onClick={() => toggle(tag)} type="button"><i aria-hidden="true" /><span>{tag}</span><b>{count}</b></button>)}</div></div>
}

function ControlCluster({ children, className, summary }: { children: React.ReactNode; className: string; summary: string }) {
  const [open, setOpen] = useState(() => window.innerWidth >= 761)
  useEffect(() => {
    const resize = () => setOpen(window.innerWidth >= 761)
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])
  return <details className={`floating-cluster ${className}`} onToggle={(event) => setOpen(event.currentTarget.open)} open={open}><summary>{summary}</summary><div className="cluster-content">{children}</div></details>
}

const EMPTY_POSITIONS: Positions = new Map()

export default function App() {
  const [view, setViewState] = useState<View>(() => defaultView(payload))
  const [selected, setSelected] = useState<Selection | null>(null)
  const [layoutResult, setLayoutResult] = useState<{ key: string; positions: Positions }>({ key: '', positions: new Map() })
  const [flow, setFlow] = useState<ReactFlowInstance<CanvasNode, SemanticFlowEdge> | null>(null)
  const [layout, setLayout] = useState<LayoutPreferences>(() => loadLayout(window.localStorage))
  const [copyStatus, setCopyStatus] = useState('')
  const [diagnostic, setDiagnostic] = useState('')
  const [zoom, setZoom] = useState(1)
  const [fullscreen, setFullscreen] = useState(false)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const appRef = useRef<HTMLDivElement>(null)
  const fullscreenInvoker = useRef<HTMLElement | null>(null)
  const nativeFullscreen = useRef(false)
  const timeline = payload.timelines[view.timeline]
  const setView = useCallback((change: Partial<View>, push = false) => setViewState((current) => {
    const next = { ...current, ...change }
    if (push) persistView(next, true)
    return next
  }), [])
  const depth = readingDepth(zoom)

  const projected = useMemo(() => projectState(payload, view), [view])
  const compareFrom = view.compare === 'off' ? null : view.compare === 'base' ? 0 : view.comparePosition
  const diff = useMemo(() => compareFrom === null
    ? null
    : diffStates(payload, view.timeline, compareFrom, view.position), [compareFrom, view.position, view.timeline])
  const compared = useMemo(() => compareFrom === null
    ? null
    : projectState(payload, { ...view, compare: 'off', position: compareFrom }), [compareFrom, view])
  const union = useMemo(() => unionGraph(payload, view.timeline, view.level, view.drill), [view.drill, view.level, view.timeline])
  const layoutKey = `${view.timeline}:${view.level}:${view.drill ?? 'map'}`
  // A layout computed for a different projection must never apply
  // (INT-STATE-06): stale positions carry parentIds for boundaries that no
  // longer exist in the current graph.
  const positions = layoutResult.key === layoutKey ? layoutResult.positions : EMPTY_POSITIONS
  const legend = useMemo(() => legendEntries(projected), [projected])

  useEffect(() => persistView(view), [view])
  useEffect(() => {
    const restore = () => setViewState(defaultView(payload))
    window.addEventListener('popstate', restore)
    return () => window.removeEventListener('popstate', restore)
  }, [])
  useEffect(() => { saveLayout(window.localStorage, layout) }, [layout])
  useEffect(() => {
    let active = true
    void unionLayout(union, layoutKey)
      .then((next) => { if (active) setLayoutResult({ key: layoutKey, positions: next }) })
      .catch(() => { if (active) setDiagnostic('Layout failed. The report remains available with fallback positions.') })
    return () => { active = false }
  }, [layoutKey, union])
  useEffect(() => {
    if (flow && positions.size) void flow.fitView({ duration: 250, padding: 0.2 })
  }, [flow, positions])
  useEffect(() => {
    const sync = () => {
      const active = document.fullscreenElement === appRef.current
      if (active) nativeFullscreen.current = true
      if (active || nativeFullscreen.current) setFullscreen(active)
      if (!active && nativeFullscreen.current) {
        nativeFullscreen.current = false
        fullscreenInvoker.current?.focus()
      }
    }
    document.addEventListener('fullscreenchange', sync)
    return () => document.removeEventListener('fullscreenchange', sync)
  }, [])

  const selectedKey = selected?.type === 'row' ? `${selected.kind}:${selected.row.id}` : null
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
    const factKeys = [...propertyCounts].sort(([leftKey, leftCount], [rightKey, rightCount]) => rightCount - leftCount || leftKey.localeCompare(rightKey)).slice(0, 2).map(([key]) => key)
    const memberKeys = (node: GraphNode) => new Set([node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)])
    const lensMatched = new Set(graphNodes.filter(({ node }) => nodeTags(node).some((tag) => view.lens.includes(tag))).map(({ node }) => node.key))
    const neighborKeys = (keys: Set<string>) => new Set(projected.edges.flatMap((edge) => keys.has(edge.a) ? [edge.b] : keys.has(edge.b) ? [edge.a] : []))
    const selectedNodes = new Set(graphNodes.filter(({ node }) => selectedKey && memberKeys(node).has(selectedKey)).map(({ node }) => node.key))
    const selectedNeighbors = neighborKeys(selectedNodes)
    const hoverNodes = new Set(hoveredKey ? [hoveredKey] : [])
    const hoverNeighbors = neighborKeys(hoverNodes)
    const lensNeighbors = neighborKeys(lensMatched)
    const emphasis = (key: string): ArchitectureData['emphasis'] => {
      if (selectedNodes.size) return selectedNodes.has(key) ? 'emphasized' : selectedNeighbors.has(key) ? 'neighbor' : 'unrelated'
      if (hoverNodes.size) return hoverNodes.has(key) ? 'emphasized' : hoverNeighbors.has(key) ? 'neighbor' : 'unrelated'
      if (view.lens.length) return lensMatched.has(key) ? 'emphasized' : lensNeighbors.has(key) ? 'neighbor' : 'unrelated'
      return 'normal'
    }
    const boundaryEntityKeys = new Set(projected.boundaries.filter((boundary) => !boundary.stub).map((boundary) => boundary.nodeKey))
    const edgeEndpoints = new Set(projected.edges.flatMap((edge) => [edge.a, edge.b]))
    const visibleGraphNodes = graphNodes.filter(({ node }) => !boundaryEntityKeys.has(node.key) || edgeEndpoints.has(node.key))
    const architectureNodes: ArchitectureNode[] = visibleGraphNodes.map(({ ghost, node }, index) => {
      const parentId = node.row.parent ?? node.row.container ?? node.row.component
      const parent = parentId ? byId.get(parentId)?.row : undefined
      const childCount = Object.values(projected.rawState.rows).flat().filter((row) => [row.parent, row.container, row.component].includes(node.row.id)).length
      return {
        data: {
          boundary: node.boundary,
          changes: changesForNode(node, diff),
          childCount,
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
        height: NODE_HEIGHT,
        id: node.key,
        position: { x: index * 280, y: 0 },
        selected: selectedNodes.has(node.key),
        type: 'architecture',
        width: NODE_WIDTH,
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
  }, [diff, graphNodes, hoveredKey, positions, projected, selectedKey, setView, view.lens])

  const graphEdges = useMemo(() => {
    const merged = new Map(projected.edges.map((edge) => [edge.key, { edge, ghost: false }]))
    for (const edge of compared?.edges ?? []) {
      const statuses = statusesForEdge(edge, diff)
      if (!merged.has(edge.key) && statuses.includes('removed')) merged.set(edge.key, { edge, ghost: true })
    }
    return [...merged.values()]
  }, [compared, diff, projected.edges])
  const edges = useMemo(() => {
    const selectedDisplayKey = projected.nodes.find((node) => selectedKey && [node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)].includes(selectedKey))?.key
    const lensMatched = new Set(projected.nodes.filter((node) => nodeTags(node).some((tag) => view.lens.includes(tag))).map((node) => node.key))
    const edgeEmphasis = (edge: GraphEdge): SemanticData['emphasis'] => {
      if (selectedDisplayKey) {
        if (edge.a !== selectedDisplayKey && edge.b !== selectedDisplayKey) return 'unrelated'
        const presentation = edgePresentation(edge, view.aspect)
        if (presentation.bidirectional) return 'both'
        const source = presentation.reverse ? edge.b : edge.a
        return source === selectedDisplayKey ? 'outgoing' : 'incoming'
      }
      if (hoveredKey) return edge.a === hoveredKey || edge.b === hoveredKey ? 'neighbor' : 'unrelated'
      if (view.lens.length) return lensMatched.has(edge.a) || lensMatched.has(edge.b) ? 'neighbor' : 'unrelated'
      return 'normal'
    }
    return graphEdges.map(({ edge, ghost }) => flowEdge(
      edge,
      view.aspect,
      ghost ? ['removed'] : statusesForEdge(edge, diff),
      edgeEmphasis(edge),
      () => { setSelected({ type: 'edge', edge }); setPanel('side', { ...layout.panels.side, collapsed: false }) },
    ))
  }, [diff, graphEdges, hoveredKey, layout.panels.side, projected.nodes, selectedKey, view.aspect, view.lens])

  const systemRows = [...new Map(payload.rows.systems.map((row) => [row.id, row])).values()]
  const timelineLabel = timeline.id ?? 'implicit timeline'
  const currentPositionLabel = view.position === 0
    ? 'Base'
    : payload.milestones.find((item) => item.id === timeline.milestones[view.position - 1])?.name ?? `Position ${view.position}`

  const chooseTimeline = (value: number) => {
    const maximum = payload.timelines[value].milestones.length
    setView({
      timeline: value,
      position: Math.min(view.position, maximum),
      comparePosition: Math.min(view.comparePosition, maximum),
    })
  }

  const copyLink = async () => {
    try {
      await copyViewLink(view)
      setCopyStatus('Link copied')
    } catch {
      setCopyStatus('Copy unavailable')
    }
  }

  const setPanel = (name: PanelName, panel: LayoutPreferences['panels'][PanelName]) => {
    setLayout((current) => ({ ...current, panels: { ...current.panels, [name]: panel } }))
  }
  const selectRow = useCallback((kind: RowKind, row: ReportRow, members: RowRef[] = []) => {
    setSelected({ type: 'row', kind, members, row })
    setLayout((current) => ({ ...current, panels: { ...current.panels, side: { ...current.panels.side, collapsed: false } } }))
  }, [])
  const selectById = (kind: RowKind, id: string) => {
    const row = projected.rawState.rows[kind].find((item) => item.id === id)
      ?? payload.rows[kind].find((item) => item.id === id)
    if (row) {
      const node = projected.nodes.find((item) => item.kind === kind && item.row.id === id)
      selectRow(kind, row, node?.members)
    }
  }
  const openDependencies = (key: string) => {
    const displayKey = projected.nodes.find((node) => [node.key, ...node.members.map((member) => `${member.kind}:${member.row.id}`)].includes(key))?.key ?? key
    setView({ deps: displayKey, drill: null }, true)
  }
  const parentKey = (key: string): string | null => {
    const [kind, ...idParts] = key.split(':')
    const row = payload.rows[kind as RowKind]?.find((item) => item.id === idParts.join(':'))
    const parentId = row?.parent ?? row?.container ?? row?.component
    if (!parentId) return null
    for (const parentKind of ['systems', 'containers', 'components'] as EntityKind[]) {
      if (payload.rows[parentKind].some((item) => item.id === parentId)) return `${parentKind}:${parentId}`
    }
    return null
  }
  const toggleFullscreen = useCallback(async (invoker?: HTMLElement) => {
    if (fullscreen) {
      if (document.fullscreenElement) await document.exitFullscreen()
      setFullscreen(false)
      fullscreenInvoker.current?.focus()
    } else {
      fullscreenInvoker.current = invoker ?? document.activeElement as HTMLElement | null
      setFullscreen(true)
      try { await appRef.current?.requestFullscreen?.() } catch { /* file:// uses the full-window fallback. */ }
    }
    requestAnimationFrame(() => { if (flow) void flow.fitView({ padding: 0.2 }) })
  }, [flow, fullscreen])

  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      const target = event.target
      if (target instanceof HTMLElement && target.matches('input, textarea, select, [contenteditable="true"]')) return
      if (event.key === 'Escape') {
        event.preventDefault()
        const menu = document.querySelector<HTMLDetailsElement>('details[open]')
        if (menu) menu.open = false
        else if (selected) setSelected(null)
        else if (view.lens.length || view.drill || view.deps) setView({ deps: null, drill: null, lens: [] })
        else if (fullscreen) void toggleFullscreen()
        return
      }
      if (event.key.toLowerCase() === 'f') { event.preventDefault(); void toggleFullscreen(document.activeElement as HTMLElement | undefined); return }
      if (!(event.ctrlKey || event.metaKey) || !flow) return
      if (event.key === '+' || event.key === '=') { event.preventDefault(); void flow.zoomIn({ duration: 120 }) }
      if (event.key === '-') { event.preventDefault(); void flow.zoomOut({ duration: 120 }) }
      if (event.key === '0') { event.preventDefault(); void flow.fitView({ duration: 120, padding: 0.2 }) }
    }
    window.addEventListener('keydown', keydown)
    return () => window.removeEventListener('keydown', keydown)
  }, [flow, fullscreen, selected, setView, toggleFullscreen, view.deps, view.drill, view.lens.length])

  const drillRow = view.drill ? projected.boundaries.find((boundary) => boundary.nodeKey === view.drill)?.row
    ?? payload.rows[view.drill.split(':')[0] as RowKind]?.find((row) => row.id === view.drill!.split(':').slice(1).join(':')) : null
  const drillPath: string[] = []
  let drillCursor = view.drill
  while (drillCursor) {
    const [kind, ...id] = drillCursor.split(':')
    const row = payload.rows[kind as RowKind]?.find((item) => item.id === id.join(':'))
    if (row) drillPath.unshift(rowLabel(row))
    drillCursor = parentKey(drillCursor)
  }
  return (
    <div className={`app${fullscreen ? ' is-fullscreen' : ''}`} data-hover={hoveredKey ? 'active' : 'off'} data-lens={view.lens.length ? 'active' : 'off'} data-selection={selectedKey ? 'active' : 'off'} data-theme={view.theme} ref={appRef}>
      <header className="app-header">
        <div className="brand-lockup"><span className="brand-mark">⌘</span><div><span>ONETOOL ARCHITECTURE</span><strong>{payload.source}</strong></div></div>
        <span className="state-badge">{view.drill && drillRow ? <><button aria-label="Up one architecture level" onClick={() => setView({ drill: parentKey(view.drill!), deps: null }, true)} type="button">↑ Up</button><b>{drillPath.join(' / ')}</b></> : <>{currentPositionLabel} · {view.level}</>}</span>
        <div className="header-actions">
          <button aria-label="Copy view link" className="icon-button" onClick={() => void copyLink()} title="Copy view link" type="button">⌁</button>
          <button aria-label={`Use ${view.theme === 'light' ? 'dark' : 'light'} theme`} className="icon-button" onClick={() => setView({ theme: view.theme === 'light' ? 'dark' : 'light' })} type="button">{view.theme === 'light' ? '◐' : '○'}</button>
          <button aria-label={fullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} className="icon-button" onClick={(event) => void toggleFullscreen(event.currentTarget)} type="button">{fullscreen ? '↙' : '↗'}</button>
          <span aria-live="polite" className="copy-status">{copyStatus}</span>
        </div>
      </header>

      <main className="workspace" data-inspector={selected ? 'true' : 'false'}>
        <div className="canvas-row">
            <div className={`canvas-root depth-${depth}`} data-reading-depth={depth}>
            {!view.deps ? <><ControlCluster className="time-cluster" summary={`Time · ${currentPositionLabel}`}>
                {payload.timelines.length > 1 ? <label className="control-group"><span>Timeline</span><select aria-label="Timeline" onChange={(event) => chooseTimeline(Number(event.target.value))} value={view.timeline}>{payload.timelines.map((item, index) => <option key={item.id ?? 'implicit'} value={index}>{item.id ?? 'Default'}</option>)}</select></label> : null}
                <PositionControls payload={payload} setView={setView} view={view} />
            </ControlCluster>
            <ControlCluster className="projection-cluster" summary={`Projection · ${view.level}`}>
                <div className="segmented control-group" role="group" aria-label="Architecture level">{([
                  ['systems', 'System'],
                  ['top-containers', 'Container'],
                  ['containers', 'Child Containers'],
                  ['components', 'Component'],
                ] as Array<[Level, string]>).map(([level, label]) => <button aria-pressed={view.level === level} key={level} onClick={() => setView({ level })} type="button">{label}</button>)}</div>
                <ScopeControl disabled={Boolean(view.drill)} payload={payload} setView={setView} view={view} />
                <label className="control-group"><span>Aspect</span><select aria-label="Edge aspect" onChange={(event) => setView({ aspect: event.target.value as Aspect })} value={view.aspect}><option value="ownership">Ownership</option><option value="call-direction">Call direction</option><option value="data-flow">Data flow</option></select></label>
                {selectedKey ? <button onClick={() => openDependencies(selectedKey)} type="button">Dependencies</button> : null}
                {(view.lens.length || view.drill || view.deps) ? <button onClick={() => setView({ deps: null, drill: null, lens: [] })} type="button">Reset view</button> : null}
            </ControlCluster></> : null}

            {view.deps ? <DependencyView aspect={view.aspect} focusKey={view.deps} onClose={() => setView({ deps: null }, true)} onFocus={(key) => setView({ deps: key }, true)} onSelect={selectRow} projected={projected} /> : !projected.nodes.length ? <div className="empty-state"><p>No entities match the current projection.</p><button onClick={() => setView({ deps: null, drill: null, lens: [], scope: null })} type="button">Show the full architecture</button></div> : <ReactFlow
              colorMode={view.theme}
              edges={edges}
              edgeTypes={edgeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.2}
              nodes={nodes}
              nodesConnectable={false}
              nodesDraggable={false}
              nodeTypes={nodeTypes}
              onEdgeClick={(_event, edge) => {
                const graphEdge = (edge.data as SemanticData | undefined)?.edge
                if (graphEdge) { setSelected({ type: 'edge', edge: graphEdge }); setPanel('side', { ...layout.panels.side, collapsed: false }) }
              }}
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
              <MiniMap className="semantic-radar" pannable zoomable />
            </ReactFlow>}

            {!view.deps && legend.length ? <ResizablePanel className="legend-panel" label="Legend panel" layout={layout.panels.legend} name="legend" onChange={(panel) => setPanel('legend', panel)}><LegendPanel entries={legend} lens={view.lens} onLens={(lens) => setView({ lens })} /></ResizablePanel> : null}

            <div aria-label="Canvas zoom" className="zoom-rail" role="group">
              <button aria-label="Fit canvas" onClick={() => { if (flow) void flow.fitView({ duration: 150, padding: 0.2 }) }} title="Fit" type="button">Fit</button>
              <button aria-label="Zoom out" onClick={() => { if (flow) void flow.zoomOut({ duration: 120 }) }} title="Zoom out" type="button">−</button>
              <output aria-live="polite"><strong>{Math.round(zoom * 100)}%</strong><span>{depth.toUpperCase()}</span></output>
              <button aria-label="Zoom in" onClick={() => { if (flow) void flow.zoomIn({ duration: 120 }) }} title="Zoom in" type="button">+</button>
              <button aria-label={fullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} onClick={(event) => void toggleFullscreen(event.currentTarget)} title="Fullscreen" type="button">{fullscreen ? '↙' : '↗'}</button>
            </div>
          </div>

          {selected ? <ResizablePanel className="side-panel" label="Details panel" layout={layout.panels.side} name="side" onChange={(panel) => setPanel('side', panel)}><SidePanel aspect={view.aspect} onClose={() => setSelected(null)} onDependencyView={openDependencies} onSelect={selectRow} projected={projected} selection={selected} /></ResizablePanel> : null}
        </div>

        <ResizablePanel className="table-panel" label="Tables panel" layout={layout.panels.bottom} name="bottom" onChange={(panel) => setPanel('bottom', panel)}>
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
      <footer><span><b data-testid="rendered-node-count">{projected.nodes.length}</b> nodes · {edges.length} connections · {view.scope ? `${view.scope.systems.length} scoped systems + ${view.scope.hops} hops` : 'all systems'}</span><span data-testid="rendered-node-ids">{projected.nodes.map((node) => node.key).join(',')}</span><span>{positions.size ? 'ELK union layout' : 'laying out'} · offline · position {view.position} · {timelineLabel} · {systemRows.length} authored systems</span></footer>
      {diagnostic ? <div aria-live="polite" className="diagnostic"><span>{diagnostic}</span><button aria-label="Dismiss diagnostic" onClick={() => setDiagnostic('')} type="button">×</button></div> : null}
    </div>
  )
}
