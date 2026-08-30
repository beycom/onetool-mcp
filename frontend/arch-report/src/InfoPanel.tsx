import { useMemo, useState } from 'react'

import { displayValue, humanizeField, KIND_LABEL, lifecycleLabel, rowLabel } from './display'
import { splitEdgeDirections, type SplineDirection } from './edgePresentation'
import type { Aspect, FieldChange, GraphEdge, ReportPayload, ReportRow, RowKind, RowRef, StateDiff } from './types'
import { ENTITY_KINDS } from './types'
import type { projectState } from './projection'

export type Selection =
  | { type: 'row'; kind: RowKind; members: RowRef[]; row: ReportRow }
  | { type: 'edge'; direction: SplineDirection; edge: GraphEdge }

export function selectionKey(selection: Selection): string {
  return selection.type === 'row'
    ? `${selection.kind}:${selection.row.id}`
    : `${selection.edge.key}:${selection.direction}`
}

function connectionDirection(row: ReportRow, aspect: Aspect): { bidirectional: boolean; from: string; to: string } | null {
  if (row.source && row.target) return { bidirectional: false, from: row.source, to: row.target }
  if (!row.provider || !row.consumer) return null
  const direction = aspect === 'data-flow'
    ? row.data_flow_direction ?? 'provider_to_consumer'
    : row.call_direction ?? 'consumer_to_provider'
  if (direction === 'bidirectional') return { bidirectional: true, from: row.provider, to: row.consumer }
  return direction === 'provider_to_consumer'
    ? { bidirectional: false, from: row.provider, to: row.consumer }
    : { bidirectional: false, from: row.consumer, to: row.provider }
}

function changedAtStage(kind: RowKind | null, row: ReportRow | null, diff: StateDiff | null): {
  changes: FieldChange[]
  status: 'added' | 'removed' | 'changed' | null
} {
  if (!kind || !row || !diff) return { changes: [], status: null }
  if (diff.added.some((item) => item.kind === kind && item.id === row.id)) return { changes: [], status: 'added' }
  if (diff.removed.some((item) => item.kind === kind && item.id === row.id)) return { changes: [], status: 'removed' }
  const changed = diff.changed.find((item) => item.kind === kind && item.id === row.id)
  return changed ? { changes: changed.changes, status: 'changed' } : { changes: [], status: null }
}

function Chips({ rows, onSelect }: {
  rows: RowRef[]
  onSelect: (kind: RowKind, row: ReportRow) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? rows : rows.slice(0, 8)
  const remaining = rows.length - visible.length
  return (
    <span className="linked-chips">
      {visible.map(({ kind, row }) => <button data-kind={kind} key={`${kind}:${row.id}`} onClick={() => onSelect(kind, row)} type="button">{rowLabel(row)}</button>)}
      {remaining > 0 ? <button className="more-chip" onClick={() => setExpanded(true)} type="button">and {remaining} more</button> : null}
    </span>
  )
}

export function InfoPanel({
  aspect,
  diff,
  hasBack,
  onBack,
  onClose,
  onDependencyView,
  onSelect,
  payload,
  projected,
  selection,
  timeline,
}: {
  aspect: Aspect
  diff: StateDiff | null
  hasBack: boolean
  onBack: () => void
  onClose: () => void
  onDependencyView: (key: string) => void
  onSelect: (kind: RowKind, row: ReportRow) => void
  payload: ReportPayload
  projected: ReturnType<typeof projectState>
  selection: Selection
  timeline: number
}) {
  const [tab, setTab] = useState<'details' | 'connections'>('details')
  const allRows = useMemo(() => Object.entries(projected.rawState.rows).flatMap(([kind, rows]) => (
    rows.map((row) => ({ kind: kind as RowKind, row }))
  )), [projected.rawState.rows])
  const rowsById = useMemo(() => new Map(allRows.map((item) => [item.row.id, item])), [allRows])
  const rowsByKey = useMemo(() => new Map(allRows.map((item) => [`${item.kind}:${item.row.id}`, item])), [allRows])
  const edge = selection.type === 'edge' ? selection.edge : null
  const row = selection.type === 'row' ? selection.row : null
  const kind = selection.type === 'row' ? selection.kind : null
  const entity = kind !== null && (ENTITY_KINDS as readonly string[]).includes(kind)
  const spline = selection.type === 'edge'
    ? splitEdgeDirections(selection.edge, aspect).find((item) => item.direction === selection.direction)
    : null
  const members = spline?.members ?? []
  const parentId = row?.parent ?? row?.container ?? row?.component
  const parent = parentId ? rowsById.get(parentId) : undefined
  const children = row && entity ? allRows.filter((item) => (
    (ENTITY_KINDS as readonly string[]).includes(item.kind)
    && [item.row.parent, item.row.container, item.row.component].includes(row.id)
  )) : []
  const selectedNodeKey = entity && row ? `${kind}:${row.id}` : null
  const selectedMemberIds = new Set(row && entity ? [row.id] : [])
  let foundMember = true
  while (foundMember) {
    foundMember = false
    for (const item of allRows) {
      if (!(ENTITY_KINDS as readonly string[]).includes(item.kind) || selectedMemberIds.has(item.row.id)) continue
      const parent = item.row.parent ?? item.row.container ?? item.row.component
      if (parent && selectedMemberIds.has(parent)) {
        selectedMemberIds.add(item.row.id)
        foundMember = true
      }
    }
  }
  const groupedConnections = { incoming: [] as ReportRow[], outgoing: [] as ReportRow[] }
  for (const item of projected.rawState.rows.interfaces) {
    const direction = connectionDirection(item, aspect)
    if (!direction) continue
    const fromSelected = selectedMemberIds.has(direction.from)
    const toSelected = selectedMemberIds.has(direction.to)
    if (fromSelected === toSelected) continue
    if (direction.bidirectional || toSelected) groupedConnections.incoming.push(item)
    if (direction.bidirectional || fromSelected) groupedConnections.outgoing.push(item)
  }
  const ordinaryFields = row && entity ? Object.entries(row).filter(([key, value]) => (
    !['id', 'name', 'action', 'description', 'tags', 'properties', 'intervals', 'parent', 'container', 'component'].includes(key)
    && value !== undefined
  )) : []
  const stageChange = changedAtStage(kind, row, diff)
  const title = row ? rowLabel(row) : members[0]
    ? `${rowLabel(members[0].row)}${members.length > 1 ? ` and ${members.length - 1} more` : ''}`
    : 'Connection'
  const rowDirection = row ? connectionDirection(row, aspect) : null
  const edgeEndpoints = spline ? [rowsByKey.get(spline.source), rowsByKey.get(spline.target)] : []
  const connection = kind === 'interfaces' || kind === 'relationships'
  const endpointRows = row && connection
    ? kind === 'interfaces'
      ? [['Provider', rowsById.get(row.provider ?? '')], ['Consumer', rowsById.get(row.consumer ?? '')]] as const
      : [['Source', rowsById.get(row.source ?? '')], ['Target', rowsById.get(row.target ?? '')]] as const
    : []
  const directionLabel = rowDirection
    ? [rowDirection.from, rowDirection.to].map((id) => rowLabel(rowsById.get(id)?.row ?? { id, intervals: [] })).join(rowDirection.bidirectional ? ' ↔ ' : ' → ')
    : edgeEndpoints.filter(Boolean).map((item) => rowLabel(item!.row)).join(' → ')

  return (
    <div className="side-panel-body" data-tabs={entity ? 'true' : 'false'}>
      <header>
        <div className="info-heading">
          {hasBack ? <button className="back-action" onClick={onBack} type="button">← Back</button> : null}
          <span className="panel-kicker">{kind ? KIND_LABEL[kind] : 'Connection'}</span>
          <h2>{title}</h2>
          {row ? <code>{row.id}</code> : null}
        </div>
        <button aria-label="Close details" className="icon-button" onClick={onClose} type="button">×</button>
      </header>
      {entity ? <nav aria-label="Selection details">
        <button aria-pressed={tab === 'details'} onClick={() => setTab('details')} type="button">Details</button>
        <button aria-pressed={tab === 'connections'} onClick={() => setTab('connections')} type="button">Connections</button>
      </nav> : null}
      {tab === 'details' || !entity ? <div className="side-panel-scroll">
        {row?.description ? <p>{row.description}</p> : null}
        {entity && row ? <>
          <dl className="details-grid">
            <div><dt>Status</dt><dd>{projected.rawState.clips[kind!].get(row.id) ? 'Retired at this stage' : 'Live at this stage'}</dd></div>
            {parent ? <div><dt>Belongs to</dt><dd><button className="text-link" onClick={() => onSelect(parent.kind, parent.row)} type="button">{rowLabel(parent.row)}</button></dd></div> : null}
            <div><dt>Contains</dt><dd>{children.length ? <Chips onSelect={onSelect} rows={children} /> : 'None'}</dd></div>
            {ordinaryFields.map(([field, value]) => <div key={field}><dt>{humanizeField(field)}</dt><dd>{displayValue(value)}</dd></div>)}
            {Object.entries(row.properties ?? {}).map(([field, value]) => <div key={field}><dt>{humanizeField(field)}</dt><dd>{displayValue(value)}</dd></div>)}
          </dl>
          {row.tags?.length ? <section className="info-section"><h3>Tags</h3><span className="value-chips">{row.tags.map((tag) => <span key={tag}>{tag}</span>)}</span></section> : null}
          {stageChange.status ? <section className="info-section stage-changes">
            <h3>Changes at this stage</h3>
            <p className="change-status" data-status={stageChange.status}>{humanizeField(stageChange.status)}</p>
            {stageChange.changes.length ? <dl className="change-list">{stageChange.changes.map((change, index) => <div key={`${change.field}:${index}`}><dt>{humanizeField(change.field)}</dt><dd><span>{displayValue(change.old)}</span><b aria-hidden="true">→</b><span>{displayValue(change.new)}</span></dd></div>)}</dl> : null}
          </section> : null}
          <button className="details-action" onClick={() => onDependencyView(selectedNodeKey!)} type="button">View dependencies</button>
        </> : null}
        {connection && row ? <>
          <dl className="details-grid connection-details">
            {endpointRows.map(([label, endpoint]) => <div key={label}><dt>{label}</dt><dd>{endpoint ? <button className="text-link" onClick={() => onSelect(endpoint.kind, endpoint.row)} type="button">{rowLabel(endpoint.row)}</button> : 'Unknown'}</dd></div>)}
            <div><dt>Direction</dt><dd>{directionLabel || 'Not specified'}</dd></div>
            <div><dt>Lifecycle</dt><dd>{lifecycleLabel(row, payload, timeline)}</dd></div>
            {Object.entries(row.properties ?? {}).map(([field, value]) => <div key={field}><dt>{humanizeField(field)}</dt><dd>{displayValue(value)}</dd></div>)}
          </dl>
          {row.tags?.length ? <section className="info-section"><h3>Tags</h3><span className="value-chips">{row.tags.map((tag) => <span key={tag}>{tag}</span>)}</span></section> : null}
        </> : null}
        {edge ? <>
          <dl className="details-grid connection-details">
            {edgeEndpoints.map((endpoint, index) => <div key={index}><dt>{index === 0 ? 'From' : 'To'}</dt><dd>{endpoint ? <button className="text-link" onClick={() => onSelect(endpoint.kind, endpoint.row)} type="button">{rowLabel(endpoint.row)}</button> : 'Unknown'}</dd></div>)}
            <div><dt>Direction</dt><dd>{directionLabel || 'Not specified'}</dd></div>
          </dl>
          <section className="info-section"><h3>Members</h3><ul className="member-list">{members.map((member) => <li key={`${member.kind}:${member.row.id}`}><button onClick={() => onSelect(member.kind, member.row)} type="button"><strong>{rowLabel(member.row)}</strong><code>{member.row.id}</code></button></li>)}</ul></section>
        </> : null}
      </div> : <div className="side-panel-scroll connections-panel">
        {(Object.entries(groupedConnections) as Array<['incoming' | 'outgoing', ReportRow[]]>).map(([direction, items]) => <section key={direction}><h3>{humanizeField(direction)}</h3>{items.length ? <ul className="connection-list">{items.map((item) => {
          const itemDirection = connectionDirection(item, aspect)
          const label = itemDirection ? [itemDirection.from, itemDirection.to].map((id) => rowLabel(rowsById.get(id)?.row ?? { id, intervals: [] })).join(itemDirection.bidirectional ? ' ↔ ' : ' → ') : 'Direction unavailable'
          return <li key={item.id}><button onClick={() => onSelect('interfaces', item)} type="button"><strong>{rowLabel(item)}</strong><span>{label}</span></button></li>
        })}</ul> : <p>No {direction} connections at this stage.</p>}</section>)}
      </div>}
    </div>
  )
}
