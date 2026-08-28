import {
  AllCommunityModule,
  ModuleRegistry,
  createGrid,
  themeQuartz,
  type ColDef,
  type ColumnState,
  type GridApi,
  type RowSelectedEvent,
} from 'ag-grid-community'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { humanizeField } from './display'
import type { Density } from './layoutPreferences'
import { ENTITY_KINDS, type EntityKind, type ProjectedView, type ReportPayload, type RowKind, type StateDiff } from './types'

ModuleRegistry.registerModules([AllCommunityModule])

export type TableTab = 'entities' | 'interfaces' | 'milestones' | 'diff'
type GridRow = Record<string, unknown> & { _key: string; id: string; kind?: RowKind; status?: string }

function selectedRowsAsTsv(rows: GridRow[], columns: string[]): string {
  const clean = (value: unknown) => String(value ?? '').replaceAll('\t', ' ').replaceAll('\n', ' ')
  return [columns.join('\t'), ...rows.map((row) => columns.map((column) => clean(row[column])).join('\t'))].join('\n')
}

function propertyFields(rows: GridRow[]): string[] {
  const core = new Set(['_key', 'kind', 'id', 'name', 'status', 'parent', 'boundary', 'provider', 'consumer', 'call_direction', 'data_flow_direction'])
  return [...new Set(rows.flatMap((row) => Object.keys(row).filter((key) => !core.has(key))))].sort()
}

function statusFor(kind: RowKind, id: string, diff: StateDiff | null): string {
  if (!diff) return 'Current'
  if (diff.added.some((item) => item.kind === kind && item.id === id)) return 'Added'
  if (diff.removed.some((item) => item.kind === kind && item.id === id)) return 'Removed'
  if (diff.changed.some((item) => item.kind === kind && item.id === id)) return 'Changed'
  return 'Unchanged'
}

function Grid({
  columns,
  density,
  layout,
  onDiagnostic,
  onLayout,
  onSelect,
  rows,
  selectedKey,
  emptyLabel,
}: {
  columns: ColDef<GridRow>[]
  density: Density
  layout?: ColumnState[]
  onDiagnostic: (message: string) => void
  onLayout: (layout: ColumnState[]) => void
  onSelect: (row: GridRow) => void
  rows: GridRow[]
  selectedKey: string | null
  emptyLabel: string
}) {
  const element = useRef<HTMLDivElement>(null)
  const apiRef = useRef<GridApi<GridRow> | null>(null)
  const layoutRef = useRef(layout)
  const callbacks = useRef({ onDiagnostic, onLayout, onSelect })
  const filters = useRef({ kinds: [] as string[], statuses: [] as string[] })
  const [query, setQuery] = useState('')
  const [columnQuery, setColumnQuery] = useState('')
  const [kindFilter, setKindFilter] = useState<string[]>([])
  const [statusFilter, setStatusFilter] = useState<string[]>([])
  const [revision, setRevision] = useState(0)
  const knownColumns = useMemo(() => new Set(columns.map((column) => column.field).filter((field): field is string => Boolean(field))), [columns])
  layoutRef.current = layout
  callbacks.current = { onDiagnostic, onLayout, onSelect }
  filters.current = { kinds: kindFilter, statuses: statusFilter }
  const persist = useCallback(() => {
    if (apiRef.current) callbacks.current.onLayout(apiRef.current.getColumnState().filter((column) => knownColumns.has(column.colId)))
    setRevision((value) => value + 1)
  }, [knownColumns])

  useEffect(() => {
    if (!element.current) return undefined
    const initialLayout = layoutRef.current
    const validLayout = initialLayout?.every((column) => typeof column.colId === 'string' && knownColumns.has(column.colId)) ?? true
    if (!validLayout) callbacks.current.onDiagnostic('Stored table layout references an unknown column; defaults restored')
    const api = createGrid(element.current, {
      columnDefs: columns,
      defaultColDef: { filter: true, minWidth: 80, resizable: true, sortable: true },
      doesExternalFilterPass: (node) => (
        (filters.current.kinds.length === 0 || filters.current.kinds.includes(String(node.data?.kind ?? '')))
        && (filters.current.statuses.length === 0 || filters.current.statuses.includes(String(node.data?.status ?? '')))
      ),
      getRowId: ({ data }) => data._key,
      isExternalFilterPresent: () => filters.current.kinds.length > 0 || filters.current.statuses.length > 0,
      onColumnMoved: (event) => { if (event.finished) persist() },
      onColumnPinned: persist,
      onColumnResized: (event) => { if (event.finished) persist() },
      onColumnVisible: persist,
      onFirstDataRendered: (event) => {
        if (!validLayout || !initialLayout?.length) {
          event.api.autoSizeColumns(event.api.getAllDisplayedColumns(), false)
        }
      },
      onRowSelected: (event: RowSelectedEvent<GridRow>) => { if (event.node.isSelected() && event.data) callbacks.current.onSelect(event.data) },
      rowData: rows,
      rowHeight: density === 'compact' ? 31 : 40,
      rowSelection: { checkboxes: true, enableClickSelection: true, mode: 'multiRow' },
      theme: themeQuartz.withParams({
        accentColor: '#008fc7', backgroundColor: 'var(--surface)', borderColor: 'var(--border)',
        fontFamily: 'Inter, ui-sans-serif, system-ui', foregroundColor: 'var(--text)',
        headerBackgroundColor: 'var(--surface-muted)',
        selectedRowBackgroundColor: 'color-mix(in srgb, #008fc7 15%, transparent)', wrapperBorder: false,
      }),
    })
    apiRef.current = api
    if (validLayout && initialLayout?.length) api.applyColumnState({ applyOrder: true, state: initialLayout })
    if (!validLayout) callbacks.current.onLayout([])
    return () => { apiRef.current = null; api.destroy() }
  }, [columns, density, knownColumns, persist, rows])

  useEffect(() => { apiRef.current?.setGridOption('quickFilterText', query) }, [query])
  useEffect(() => { apiRef.current?.onFilterChanged() }, [kindFilter, statusFilter])
  useEffect(() => {
    const api = apiRef.current
    if (!api) return
    for (const node of api.getSelectedNodes()) node.setSelected(node.id === selectedKey)
    if (selectedKey) {
      const node = api.getRowNode(selectedKey)
      node?.setSelected(true)
      if (node) api.ensureNodeVisible(node, 'middle')
    }
  }, [rows, selectedKey])

  const availableKinds = [...new Set(rows.map((row) => String(row.kind ?? '')).filter(Boolean))].sort()
  const availableStatuses = [...new Set(rows.map((row) => String(row.status ?? '')).filter(Boolean))].sort()
  void revision
  const visibleColumns = (apiRef.current?.getColumns() ?? []).filter((column) => (
    column.getColId() !== '_key' && column.getColId().toLowerCase().includes(columnQuery.toLowerCase())
  ))
  const copySelected = async () => {
    const api = apiRef.current
    if (!api) return
    const text = selectedRowsAsTsv(api.getSelectedRows(), api.getAllDisplayedColumns().map((column) => column.getColId()))
    try { await navigator.clipboard.writeText(text) } catch { onDiagnostic('Clipboard access is unavailable') }
  }

  return (
    <div className="grid-region" data-density={density}>
      <div className="table-toolbar">
        <input aria-label="Quick filter" onChange={(event) => setQuery(event.target.value)} placeholder="Quick filter" type="search" value={query} />
        {[['Kind', availableKinds, kindFilter, setKindFilter], ['Status', availableStatuses, statusFilter, setStatusFilter]].map(([label, options, selected, setSelected]) => (
          <details className="table-menu" key={label as string}>
            <summary>{label as string}</summary>
            <div>{(options as string[]).map((option) => <label key={option}><input checked={(selected as string[]).includes(option)} onChange={() => (setSelected as (value: string[]) => void)((selected as string[]).includes(option) ? (selected as string[]).filter((item) => item !== option) : [...selected as string[], option])} type="checkbox" />{option}</label>)}</div>
          </details>
        ))}
        <details className="table-menu columns-menu">
          <summary>Columns</summary>
          <div>
            <input aria-label="Search columns" onChange={(event) => setColumnQuery(event.target.value)} placeholder="Find a column" type="search" value={columnQuery} />
            {visibleColumns.map((column) => <label key={column.getColId()}><input checked={column.isVisible()} onChange={(event) => { apiRef.current?.setColumnsVisible([column], event.target.checked); persist() }} type="checkbox" />{column.getColDef().headerName ?? column.getColId()}<button aria-label={`${column.isPinned() ? 'Unpin' : 'Pin'} ${column.getColId()}`} onClick={() => { apiRef.current?.setColumnsPinned([column], column.isPinned() ? null : 'left'); persist() }} type="button">{column.isPinned() ? 'Unpin' : 'Pin'}</button></label>)}
          </div>
        </details>
        <button onClick={() => void copySelected()} type="button">Copy TSV</button>
        <button onClick={() => apiRef.current?.exportDataAsCsv({ exportedRows: 'filteredAndSorted' })} type="button">CSV filtered</button>
        <button onClick={() => apiRef.current?.exportDataAsCsv({ allColumns: true, exportedRows: 'all' })} type="button">CSV all</button>
        <button onClick={() => { apiRef.current?.resetColumnState(); apiRef.current?.setFilterModel(null); setKindFilter([]); setStatusFilter([]); setQuery(''); persist() }} type="button">Reset table</button>
      </div>
      {rows.length ? <div aria-label="Architecture data grid" className="data-grid" ref={element} /> : <div className="table-empty" role="status"><strong>{emptyLabel}</strong><span>Choose another stage or table.</span></div>}
    </div>
  )
}

export function GridPanel({
  density,
  diff,
  layouts,
  onDensity,
  onDiagnostic,
  onLayout,
  onSelect,
  onShowOnCanvas,
  payload,
  projected,
  selectedKey,
  selectedOnCanvas,
  timeline,
}: {
  density: Density
  diff: StateDiff | null
  layouts: Record<string, ColumnState[]>
  onDensity: (density: Density) => void
  onDiagnostic: (message: string) => void
  onLayout: (table: string, layout: ColumnState[]) => void
  onSelect: (kind: RowKind, id: string) => void
  onShowOnCanvas: (kind: EntityKind, id: string) => void
  payload: ReportPayload
  projected: ProjectedView
  selectedKey: string | null
  selectedOnCanvas: boolean
  timeline: number
}) {
  const [tab, setTab] = useState<TableTab>('entities')
  const table = useMemo(() => {
    let rows: GridRow[]
    if (tab === 'entities') {
      rows = ENTITY_KINDS.flatMap((kind) => projected.rawState.rows[kind].map((row) => ({
        _key: `${kind}:${row.id}`, id: row.id, kind, name: row.name ?? row.id,
        parent: row.parent ?? row.container ?? row.component ?? '', status: statusFor(kind, row.id, diff),
        ...Object.fromEntries(Object.entries(row.properties ?? {}).map(([key, value]) => [`property.${key}`, Array.isArray(value) ? value.join(', ') : value])),
      })))
    } else if (tab === 'interfaces') {
      rows = projected.state.rows.interfaces.map((row) => ({
        _key: `interfaces:${row.id}`, call_direction: row.call_direction ?? 'consumer_to_provider', consumer: row.consumer,
        data_flow_direction: row.data_flow_direction ?? 'provider_to_consumer', id: row.id, kind: 'interfaces',
        name: row.name ?? row.id, provider: row.provider, status: statusFor('interfaces', row.id, diff),
        ...Object.fromEntries(Object.entries(row.properties ?? {}).map(([key, value]) => [`property.${key}`, Array.isArray(value) ? value.join(', ') : value])),
      }))
    } else if (tab === 'milestones') {
      const byId = new Map(payload.milestones.map((milestone) => [milestone.id, milestone]))
      rows = payload.timelines[timeline].milestones.map((id, index) => ({ _key: `milestone:${id}`, description: byId.get(id)?.description ?? '', id, name: byId.get(id)?.name ?? id, position: index + 1 }))
    } else {
      rows = diff ? [
        ...diff.added.map((item) => ({ _key: `${item.kind}:${item.id}`, change: 'added', ...item })),
        ...diff.removed.map((item) => ({ _key: `${item.kind}:${item.id}`, change: 'removed', detail: item.clipped_by ? `clipped by ${item.clipped_by}` : '', ...item })),
        ...diff.changed.map((item) => ({ _key: `${item.kind}:${item.id}`, change: 'changed', detail: item.changes.map((change) => change.field).join(', '), id: item.id, kind: item.kind })),
      ] : []
    }
    const fields = Object.keys(rows[0] ?? {}).filter((field) => field !== '_key')
    const ordered = ['kind', 'id', 'name', 'status', ...fields.filter((field) => !['kind', 'id', 'name', 'status'].includes(field)), ...propertyFields(rows)]
    const unique = [...new Set(ordered)].filter((field) => rows.some((row) => field in row))
    const empty = (field: string) => rows.every((row) => row[field] === undefined || row[field] === null || row[field] === '')
    return { columns: [{ field: '_key', hide: true }, ...unique.map((field) => {
      const headerName = humanizeField(field)
      return { field, headerName, hide: empty(field), minWidth: Math.max(80, headerName.length * 7 + 36) }
    })] as ColDef<GridRow>[], rows }
  }, [diff, payload, projected, tab, timeline])
  const selectedEntity = selectedKey?.split(':', 1)[0] as EntityKind | undefined
  const showOnCanvas = selectedKey && selectedEntity && (ENTITY_KINDS as readonly string[]).includes(selectedEntity) && !selectedOnCanvas
  const emptyLabel = `No ${tab} at this stage`

  return (
    <div className="tables-content">
      <header>
        <nav aria-label="Architecture table">{(['entities', 'interfaces', 'milestones', 'diff'] as const).map((name) => <button aria-pressed={tab === name} key={name} onClick={() => setTab(name)} type="button">{humanizeField(name)}</button>)}</nav>
        <label>Density<select aria-label="Table density" onChange={(event) => onDensity(event.target.value as Density)} value={density}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
      </header>
      {showOnCanvas ? <div className="show-on-canvas"><span>The selected row is outside the current detail.</span><button onClick={() => onShowOnCanvas(selectedEntity, selectedKey.split(':').slice(1).join(':'))} type="button">Show on Canvas</button></div> : null}
      <Grid columns={table.columns} density={density} emptyLabel={emptyLabel} layout={layouts[tab]} onDiagnostic={onDiagnostic} onLayout={(layout) => onLayout(tab, layout)} onSelect={(row) => { if (row.kind) onSelect(row.kind, row.id) }} rows={table.rows} selectedKey={selectedKey} />
    </div>
  )
}
