import {
  Background,
  BackgroundVariant,
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
import { memo, useEffect, useMemo, useState } from 'react'

import { GridPanel } from './GridPanel'
import { applyPositions, NODE_HEIGHT, NODE_WIDTH, unionLayout, type Positions } from './layout'
import { readPayload } from './payload'
import { diffStates, projectState, unionGraph } from './projection'
import {
  type Aspect,
  type FieldChange,
  type GraphEdge,
  type GraphNode,
  type Level,
  type ReportPayload,
  type ReportRow,
  type StateDiff,
  type View,
} from './types'
import { copyViewLink, defaultView, persistView } from './view'

type DiffStatus = 'added' | 'removed' | 'changed'
type ArchitectureData = {
  boundary: boolean
  changes: FieldChange[]
  kind: string
  label: string
  row: ReportRow
  statuses: DiffStatus[]
}
type ArchitectureNode = Node<ArchitectureData, 'architecture'>
type SemanticData = { label: string; statuses: DiffStatus[] }
type SemanticFlowEdge = Edge<SemanticData, 'semantic'>

const payload = readPayload()
const STATUS_ORDER: DiffStatus[] = ['added', 'removed', 'changed']
const STATUS_ICON: Record<DiffStatus, string> = { added: '+', removed: '−', changed: 'Δ' }

function rowLabel(row: ReportRow): string {
  return row.name ?? row.action ?? row.id
}

function ArchitectureNodeView({ data, selected }: NodeProps<ArchitectureNode>) {
  return (
    <article
      className="architecture-node"
      data-boundary={data.boundary ? 'true' : 'false'}
      data-selected={selected ? 'true' : 'false'}
      data-status={data.statuses.join(' ')}
    >
      <span aria-hidden="true" className="node-icon">{data.boundary ? '◁' : '◇'}</span>
      <strong>{data.label}</strong>
      <span className="node-subtitle">{data.boundary ? 'BOUNDARY' : data.kind.toUpperCase()}</span>
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
      <Handle id="target" position={Position.Left} type="target" />
      <Handle id="source" position={Position.Right} type="source" />
    </article>
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
  return (
    <>
      <BaseEdge
        className={`semantic-edge ${statuses.map((status) => `is-${status}`).join(' ')}`}
        id={id}
        markerEnd={markerEnd}
        markerStart={markerStart}
        path={path}
      />
      <EdgeLabelRenderer>
        <span className="edge-label" data-status={statuses.join(' ')} style={{ transform: `translate(-50%, -50%) translate(${x}px,${y}px)` }}>
          {data?.label ?? id}
          {statuses.map((status) => <b data-status={status} key={status}>{STATUS_ICON[status]}</b>)}
        </span>
      </EdgeLabelRenderer>
    </>
  )
}

const nodeTypes = { architecture: memo(ArchitectureNodeView) }
const edgeTypes = { semantic: memo(SemanticEdge) }

function Passport({ kind, row, onClose }: { kind: string; row: ReportRow; onClose: () => void }) {
  const ordinaryFields = Object.entries(row).filter(([key, value]) => (
    !['id', 'name', 'action', 'description', 'tags', 'properties', 'intervals'].includes(key) && value !== undefined
  ))
  return (
    <aside aria-label={`Details for ${rowLabel(row)}`} className="semantic-passport">
      <header>
        <div><span className="panel-kicker">{kind.toUpperCase()} PASSPORT</span><h2>{rowLabel(row)}</h2><code>{row.id}</code></div>
        <button aria-label="Close passport" className="icon-button" onClick={onClose} type="button">×</button>
      </header>
      {row.description ? <p>{row.description}</p> : null}
      {row.tags?.length ? <div className="passport-chips">{row.tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
      {ordinaryFields.length || (row.properties && Object.keys(row.properties).length) ? (
        <dl>
          {ordinaryFields.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}
          {Object.entries(row.properties ?? {}).map(([key, value]) => (
            <div key={key}><dt>{key}</dt><dd>{Array.isArray(value) ? value.join(', ') : value}</dd></div>
          ))}
        </dl>
      ) : null}
    </aside>
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
    ? 'Current'
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
          <option value="current">vs current</option>
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

function ScopeControl({ payload, setView, view }: {
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
    <details className="scope-control control-group">
      <summary>Scope: {view.scope ? `${view.scope.systems.length} selected` : 'all'}</summary>
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
  const field = aspect === 'call-direction' ? 'call_direction' : 'data_flow'
  for (const row of edge.interfaceRows) {
    const orientation = edge.orientations.find((item) => item.kind === 'interfaces' && item.id === row.id)
    if (!orientation) continue
    const direction = row[field] ?? 'unspecified'
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

function flowEdge(edge: GraphEdge, aspect: Aspect, statuses: DiffStatus[]): SemanticFlowEdge {
  const presentation = edgePresentation(edge, aspect)
  let source = edge.a
  let target = edge.b
  if (presentation.reverse) [source, target] = [target, source]
  return {
    data: { label: presentation.label || edge.key, statuses },
    id: edge.key,
    markerEnd: presentation.showArrow ? { type: MarkerType.ArrowClosed } : undefined,
    markerStart: presentation.bidirectional ? { type: MarkerType.ArrowClosed } : undefined,
    source,
    target,
    type: 'semantic',
  }
}

export default function App() {
  const [view, setViewState] = useState<View>(() => defaultView(payload))
  const [selected, setSelected] = useState<{ kind: string; row: ReportRow } | null>(null)
  const [positions, setPositions] = useState<Positions>(new Map())
  const [flow, setFlow] = useState<ReactFlowInstance | null>(null)
  const [showTables, setShowTables] = useState(false)
  const [copyStatus, setCopyStatus] = useState('')
  const timeline = payload.timelines[view.timeline]
  const setView = (change: Partial<View>) => setViewState((current) => ({ ...current, ...change }))

  const projected = useMemo(() => projectState(payload, view), [view])
  const compareFrom = view.compare === 'off' ? null : view.compare === 'current' ? 0 : view.comparePosition
  const diff = useMemo(() => compareFrom === null
    ? null
    : diffStates(payload, view.timeline, compareFrom, view.position), [compareFrom, view.position, view.timeline])
  const compared = useMemo(() => compareFrom === null
    ? null
    : projectState(payload, { ...view, compare: 'off', position: compareFrom }), [compareFrom, view])
  const union = useMemo(() => unionGraph(payload, view.timeline, view.level), [view.level, view.timeline])

  useEffect(() => persistView(view), [view])
  useEffect(() => {
    let active = true
    setPositions(new Map())
    void unionLayout(union, `${view.timeline}:${view.level}`).then((next) => { if (active) setPositions(next) })
    return () => { active = false }
  }, [union, view.level, view.timeline])
  useEffect(() => {
    if (flow && positions.size) void flow.fitView({ duration: 250, padding: 0.2 })
  }, [flow, positions])

  const graphNodes = useMemo(() => {
    const merged = new Map(projected.nodes.map((node) => [node.key, { node, ghost: false }]))
    for (const node of compared?.nodes ?? []) {
      const statuses = statusesForNode(node, diff)
      if (!merged.has(node.key) && statuses.includes('removed')) merged.set(node.key, { node, ghost: true })
    }
    return [...merged.values()]
  }, [compared, diff, projected.nodes])
  const nodes = useMemo<ArchitectureNode[]>(() => applyPositions(graphNodes.map(({ ghost, node }, index) => ({
    data: {
      boundary: node.boundary,
      changes: changesForNode(node, diff),
      kind: node.kind,
      label: rowLabel(node.row),
      row: node.row,
      statuses: ghost ? ['removed'] : statusesForNode(node, diff),
    },
    height: NODE_HEIGHT,
    id: node.key,
    position: { x: index * 280, y: 0 },
    selected: selected?.row.id === node.row.id && selected.kind === node.kind,
    type: 'architecture',
    width: NODE_WIDTH,
  })), positions) as ArchitectureNode[], [diff, graphNodes, positions, selected])

  const graphEdges = useMemo(() => {
    const merged = new Map(projected.edges.map((edge) => [edge.key, { edge, ghost: false }]))
    for (const edge of compared?.edges ?? []) {
      const statuses = statusesForEdge(edge, diff)
      if (!merged.has(edge.key) && statuses.includes('removed')) merged.set(edge.key, { edge, ghost: true })
    }
    return [...merged.values()]
  }, [compared, diff, projected.edges])
  const edges = useMemo(() => graphEdges.map(({ edge, ghost }) => (
    flowEdge(edge, view.aspect, ghost ? ['removed'] : statusesForEdge(edge, diff))
  )), [diff, graphEdges, view.aspect])

  const systemRows = [...new Map(payload.rows.systems.map((row) => [row.id, row])).values()]
  const timelineLabel = timeline.id ?? 'implicit timeline'
  const currentPositionLabel = view.position === 0
    ? 'Current'
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

  return (
    <div className="app" data-mode={view.mode.toLowerCase()} data-theme={view.theme}>
      <header className="app-header">
        <div className="brand-lockup"><span className="brand-mark">⌘</span><div><span>ONETOOL · ARCHITECTURE REPORT</span><strong>{payload.source}</strong></div></div>
        <span className="state-badge">{currentPositionLabel.toUpperCase()} · {view.level.toUpperCase()}</span>
        <div className="header-actions">
          <button aria-label="Copy view link" className="icon-button" onClick={() => { void copyLink() }} title="Copy view link" type="button">⌁</button>
          <button aria-label={`Use ${view.theme === 'light' ? 'dark' : 'light'} theme`} className="icon-button" onClick={() => setView({ theme: view.theme === 'light' ? 'dark' : 'light' })} type="button">{view.theme === 'light' ? '◐' : '○'}</button>
          <span aria-live="polite" className="copy-status">{copyStatus}</span>
        </div>
      </header>

      <section aria-label="Report controls" className="control-bar">
        {payload.timelines.length > 1 ? (
          <label className="control-group"><span>Timeline</span><select aria-label="Timeline" onChange={(event) => chooseTimeline(Number(event.target.value))} value={view.timeline}>
            {payload.timelines.map((item, index) => <option key={item.id ?? 'implicit'} value={index}>{item.id ?? 'Default'}</option>)}
          </select></label>
        ) : null}
        <PositionControls payload={payload} setView={setView} view={view} />
        <div className="segmented control-group" role="group" aria-label="Architecture level">
          {(['systems', 'subsystems', 'components'] as Level[]).map((level) => (
            <button aria-pressed={view.level === level} key={level} onClick={() => setView({ level })} type="button">{level}</button>
          ))}
        </div>
        <ScopeControl payload={payload} setView={setView} view={view} />
        <label className="control-group"><span>Aspect</span><select aria-label="Edge aspect" onChange={(event) => setView({ aspect: event.target.value as Aspect })} value={view.aspect}>
          <option value="ownership">Ownership</option>
          <option value="call-direction">Call direction</option>
          <option value="data-flow">Data flow</option>
        </select></label>
        <div className="segmented control-group" role="group" aria-label="Diagram mode">
          {(['MAP', 'PATH', 'LENS'] as const).map((mode) => (
            <button aria-pressed={view.mode === mode} key={mode} onClick={() => setView({ mode })} type="button">{mode}</button>
          ))}
        </div>
        <button onClick={() => { if (flow) void flow.fitView({ duration: 250, padding: 0.2 }) }} type="button">Re-fit this state</button>
        <button aria-pressed={showTables} onClick={() => setShowTables(!showTables)} type="button">Tables</button>
      </section>

      <main data-inspector={selected ? 'true' : 'false'}>
        <ReactFlow
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
          onInit={setFlow}
          onNodeClick={(_event, node) => {
            const data = node.data as ArchitectureData
            setSelected({ kind: data.kind, row: data.row })
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--grid-line)" gap={32} variant={BackgroundVariant.Lines} />
          <MiniMap className="semantic-radar" pannable zoomable />
        </ReactFlow>
        {selected ? <Passport kind={selected.kind} onClose={() => setSelected(null)} row={selected.row} /> : null}
        {showTables ? <GridPanel diff={diff} onClose={() => setShowTables(false)} payload={payload} projected={projected} timeline={view.timeline} /> : null}
      </main>
      <footer>
        <span><b data-testid="rendered-node-count">{nodes.length}</b> nodes · {edges.length} connections · {view.scope ? `${view.scope.systems.length} scoped systems + ${view.scope.hops} hops` : 'all systems'}</span>
        <span data-testid="rendered-node-ids">{nodes.map((node) => node.id).join(',')}</span>
        <span>{positions.size ? 'ELK union layout' : 'laying out'} · offline · position {view.position} · {timelineLabel} · {systemRows.length} authored systems</span>
      </footer>
    </div>
  )
}
