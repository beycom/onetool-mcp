import {
  Background,
  BackgroundVariant,
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  getSmoothStepPath,
  type EdgeProps,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from '@xyflow/react'
import { memo, useEffect, useMemo, useState } from 'react'

import { applyPositions, connectionEdges, unionLayout } from './layout'
import { readPayload } from './payload'
import { projectState } from './projection'
import type { ReportRow } from './types'

type SystemData = { label: string; description: string; row: ReportRow }
type SystemNode = Node<SystemData, 'system'>
const payload = readPayload()
const view = { timeline: 0, position: 0, level: 'systems' } as const

function SystemNodeView({ data, selected }: NodeProps<SystemNode>) {
  return (
    <article className="architecture-node" data-selected={selected ? 'true' : 'false'}>
      <span aria-hidden="true" className="node-icon">◇</span>
      <strong>{data.label}</strong>
      <span className="node-subtitle">SYSTEM</span>
      <Handle id="target" position={Position.Left} type="target" />
      <Handle id="source" position={Position.Right} type="source" />
    </article>
  )
}

function SemanticEdge({ id, data, markerEnd, selected, sourcePosition, sourceX, sourceY, targetPosition, targetX, targetY }: EdgeProps) {
  const [path, x, y] = getSmoothStepPath({ sourcePosition, sourceX, sourceY, targetPosition, targetX, targetY })
  return (
    <>
      <BaseEdge id={id} markerEnd={markerEnd} path={path} className="semantic-edge" />
      <EdgeLabelRenderer>
        <span className="edge-label" data-selected={selected ? 'true' : 'false'} style={{ transform: `translate(-50%, -50%) translate(${x}px,${y}px)` }}>
          {String(data?.label ?? id)}
        </span>
      </EdgeLabelRenderer>
    </>
  )
}

const nodeTypes = { system: memo(SystemNodeView) }
const edgeTypes = { semantic: memo(SemanticEdge) }

function Passport({ row, onClose }: { row: ReportRow; onClose: () => void }) {
  return (
    <aside aria-label={`Details for ${row.name}`} className="semantic-passport">
      <header>
        <div><span className="panel-kicker">SYSTEM PASSPORT</span><h2>{row.name}</h2><code>{row.id}</code></div>
        <button aria-label="Close passport" className="icon-button" onClick={onClose} type="button">×</button>
      </header>
      {row.description ? <p>{row.description}</p> : null}
      {row.tags?.length ? <div className="passport-chips">{row.tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
      {row.properties && Object.keys(row.properties).length ? (
        <dl>{Object.entries(row.properties).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{Array.isArray(value) ? value.join(', ') : value}</dd></div>)}</dl>
      ) : null}
    </aside>
  )
}

export default function App() {
  const state = useMemo(() => projectState(payload, view), [])
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [selected, setSelected] = useState<ReportRow | null>(null)
  const [positions, setPositions] = useState<Map<string, { x: number; y: number }>>(new Map())
  const [flow, setFlow] = useState<ReactFlowInstance | null>(null)
  const nodes = useMemo<SystemNode[]>(() => applyPositions(state.systems.map((row, index) => ({
    id: row.id,
    type: 'system',
    position: { x: index * 300, y: 0 },
    data: { label: row.name ?? row.id, description: row.description ?? '', row },
    selected: selected?.id === row.id,
  })), positions) as SystemNode[], [positions, selected, state.systems])
  const edges = useMemo(() => {
    const currentIds = new Set(state.systems.map((row) => row.id))
    const currentConnections = new Set([...state.interfaces, ...state.relationships].map((row) => row.id))
    return connectionEdges(payload).filter((edge) => currentIds.has(edge.source) && currentIds.has(edge.target) && currentConnections.has(edge.id))
  }, [state])

  useEffect(() => { void unionLayout(payload).then(setPositions) }, [])
  useEffect(() => {
    if (flow && positions.size) void flow.fitView({ duration: 250, padding: 0.2 })
  }, [flow, positions])

  return (
    <div className="app" data-theme={theme}>
      <header className="app-header">
        <div className="brand-lockup"><span className="brand-mark">⌘</span><div><span>ONETOOL · ARCHITECTURE REPORT</span><strong>{payload.source}</strong></div></div>
        <span className="state-badge">CURRENT · SYSTEMS</span>
        <button aria-label={`Use ${theme === 'light' ? 'dark' : 'light'} theme`} className="icon-button" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} type="button">{theme === 'light' ? '◐' : '○'}</button>
      </header>
      <main data-inspector={selected ? 'true' : 'false'}>
        <ReactFlow
          colorMode={theme}
          edges={edges}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          nodes={nodes}
          nodesConnectable={false}
          nodesDraggable={false}
          nodeTypes={nodeTypes}
          onNodeClick={(_event, node) => setSelected((node.data as SystemData).row)}
          onInit={setFlow}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--grid-line)" gap={32} variant={BackgroundVariant.Lines} />
          <MiniMap className="semantic-radar" pannable zoomable />
        </ReactFlow>
        {selected ? <Passport onClose={() => setSelected(null)} row={selected} /> : null}
      </main>
      <footer><span>{state.systems.length} systems · {edges.length} direct connections</span><span>{positions.size ? 'ELK union layout' : 'laying out'} · offline · position 0 · {payload.timelines[0].id ?? 'implicit timeline'}</span></footer>
    </div>
  )
}
