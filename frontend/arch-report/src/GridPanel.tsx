import {
  AllCommunityModule,
  ModuleRegistry,
  createGrid,
  themeQuartz,
  type ColDef,
} from 'ag-grid-community'
import { useEffect, useMemo, useRef, useState } from 'react'

import type { ProjectedView, ReportPayload, StateDiff } from './types'

ModuleRegistry.registerModules([AllCommunityModule])

type TableTab = 'entities' | 'interfaces' | 'milestones' | 'diff'
type GridRow = Record<string, unknown>

function Grid({ columns, rows }: { columns: ColDef<GridRow>[]; rows: GridRow[] }) {
  const element = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!element.current) return undefined
    const api = createGrid(element.current, {
      columnDefs: columns,
      defaultColDef: { flex: 1, minWidth: 110, resizable: true, sortable: true },
      rowData: rows,
      theme: themeQuartz,
    })
    return () => api.destroy()
  }, [columns, rows])
  return <div aria-label="Architecture data grid" className="data-grid" ref={element} />
}

export function GridPanel({
  diff,
  onClose,
  payload,
  projected,
  timeline,
}: {
  diff: StateDiff | null
  onClose: () => void
  payload: ReportPayload
  projected: ProjectedView
  timeline: number
}) {
  const [tab, setTab] = useState<TableTab>('entities')
  const table = useMemo(() => {
    if (tab === 'entities') {
      return {
        columns: [
          { field: 'kind' }, { field: 'id' }, { field: 'name' }, { field: 'parent' }, { field: 'boundary' },
        ],
        rows: projected.nodes.map((node) => ({
          boundary: node.boundary ? 'yes' : '',
          id: node.row.id,
          kind: node.kind,
          name: node.row.name,
          parent: node.row.system ?? node.row.subsystem ?? '',
        })),
      }
    }
    if (tab === 'interfaces') {
      return {
        columns: [
          { field: 'id' }, { field: 'name' }, { field: 'provider' }, { field: 'consumer' },
          { field: 'call_direction', headerName: 'Call direction' },
          { field: 'data_flow', headerName: 'Data flow' },
        ],
        rows: projected.state.rows.interfaces.map((row) => ({
          call_direction: row.call_direction ?? 'unspecified',
          consumer: row.consumer,
          data_flow: row.data_flow ?? 'unspecified',
          id: row.id,
          name: row.name,
          provider: row.provider,
        })),
      }
    }
    if (tab === 'milestones') {
      const milestoneById = new Map(payload.milestones.map((milestone) => [milestone.id, milestone]))
      return {
        columns: [{ field: 'position' }, { field: 'id' }, { field: 'name' }, { field: 'description' }],
        rows: payload.timelines[timeline].milestones.map((id, index) => {
          const milestone = milestoneById.get(id)
          return { position: index + 1, id, name: milestone?.name ?? id, description: milestone?.description ?? '' }
        }),
      }
    }
    const rows = diff ? [
      ...diff.added.map((item) => ({ change: 'added', ...item, detail: '' })),
      ...diff.removed.map((item) => ({ change: 'removed', ...item, detail: item.clipped_by ? `clipped by ${item.clipped_by}` : '' })),
      ...diff.changed.map((item) => ({
        change: 'changed',
        detail: item.changes.map((change) => change.field).join(', '),
        id: item.id,
        kind: item.kind,
      })),
    ] : []
    return {
      columns: [{ field: 'change' }, { field: 'kind' }, { field: 'id' }, { field: 'name' }, { field: 'detail' }],
      rows,
    }
  }, [diff, payload, projected, tab, timeline])

  return (
    <section aria-label="Architecture tables" className="table-panel">
      <header>
        <nav aria-label="Architecture table">
          {(['entities', 'interfaces', 'milestones', 'diff'] as const).map((name) => (
            <button aria-pressed={tab === name} key={name} onClick={() => setTab(name)} type="button">{name}</button>
          ))}
        </nav>
        <button aria-label="Close tables" className="icon-button" onClick={onClose} type="button">×</button>
      </header>
      <Grid columns={table.columns} rows={table.rows} />
    </section>
  )
}
