import {
  ActionIcon,
  Button,
  Checkbox,
  Group,
  Menu,
  MultiSelect,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core'
import type {
  ColDef,
  ColumnState,
  GridApi,
  GridReadyEvent,
  RowSelectedEvent,
} from 'ag-grid-community'
import { themeQuartz } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import type { Density, TableConfig, TransitionStatus } from '../data/types'
import './modules'

export interface ArchitectureRow {
  id: string
  name: string
  kind: string
  status: TransitionStatus
  source?: string
  target?: string
  [key: string]: string | number | boolean | undefined
}

export interface GridConfigResult {
  valid: boolean
  diagnostic?: string
  columns: ColumnState[]
}

interface ArchitectureGridProps {
  rows: ArchitectureRow[]
  tableId: string
  label: string
  density: Density
  selectedIds: string[]
  config?: TableConfig
  rememberedLayout?: unknown[]
  onDensityChange: (density: Density) => void
  onLayoutChange: (layout: ColumnState[]) => void
  onDiagnostic: (diagnostic: string) => void
  onSelect: (id?: string) => void
}

const STATUS_OPTIONS: { label: string; value: TransitionStatus }[] = [
  { label: 'No Change', value: 'No Change' },
  { label: 'Changed', value: 'Changed' },
  { label: 'Added', value: 'Added' },
  { label: 'Removed', value: 'Removed' },
]

const gridTheme = themeQuartz.withParams({
  accentColor: '#008FC7',
  backgroundColor: 'var(--ot-surface)',
  borderColor: 'var(--ot-border)',
  borderRadius: 8,
  browserColorScheme: 'inherit',
  cellHorizontalPaddingScale: 0.9,
  fontFamily: 'IBM Plex Sans Variable, sans-serif',
  foregroundColor: 'var(--ot-text)',
  headerBackgroundColor: 'var(--ot-surface-muted)',
  headerFontWeight: 600,
  rowBorder: { color: 'var(--ot-border)', width: 1 },
  selectedRowBackgroundColor: 'color-mix(in srgb, #008FC7 14%, transparent)',
  spacing: 7,
  wrapperBorder: false,
})

export function validateGridConfig(
  config: TableConfig | undefined,
  knownColumns: Set<string>,
  rememberedLayout: unknown[] | undefined,
): GridConfigResult {
  const candidate =
    rememberedLayout ??
    config?.columns.map((column) => ({
      colId: column.id,
      hide: column.visible === false,
      pinned: column.pinned ?? null,
      width: column.width,
    })) ??
    []
  if (!Array.isArray(candidate)) {
    return { valid: false, diagnostic: 'Stored table layout must be an array', columns: [] }
  }
  const columns: ColumnState[] = []
  for (const entry of candidate) {
    if (typeof entry !== 'object' || entry === null || typeof (entry as { colId?: unknown }).colId !== 'string') {
      return { valid: false, diagnostic: 'Stored table layout contains an invalid column', columns: [] }
    }
    const column = entry as ColumnState
    if (!knownColumns.has(column.colId)) {
      return {
        valid: false,
        diagnostic: `Stored table layout references unknown column '${column.colId}'`,
        columns: [],
      }
    }
    columns.push(column)
  }
  if (config) {
    for (const column of config.columns) {
      if (!knownColumns.has(column.id)) {
        return {
          valid: false,
          diagnostic: `Workspace table '${config.id}' references unknown column '${column.id}'`,
          columns: [],
        }
      }
    }
  }
  return { valid: true, columns }
}

export function selectedRowsAsTsv(rows: ArchitectureRow[], columns: string[]): string {
  const escape = (value: unknown) => String(value ?? '').replaceAll('\t', ' ').replaceAll('\n', ' ')
  return [columns.join('\t'), ...rows.map((row) => columns.map((column) => escape(row[column])).join('\t'))].join('\n')
}

function extensionColumns(rows: ArchitectureRow[]): string[] {
  const core = new Set(['id', 'name', 'kind', 'status', 'source', 'target'])
  const extensions = new Set<string>()
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!core.has(key)) extensions.add(key)
    }
  }
  return [...extensions].sort()
}

export function ArchitectureGrid({
  rows,
  tableId,
  label,
  density,
  selectedIds,
  config,
  rememberedLayout,
  onDensityChange,
  onLayoutChange,
  onDiagnostic,
  onSelect,
}: ArchitectureGridProps) {
  const apiRef = useRef<GridApi<ArchitectureRow> | null>(null)
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const [statusFilter, setStatusFilter] = useState<TransitionStatus[]>([])
  const [columnQuery, setColumnQuery] = useState('')
  const [columnRevision, setColumnRevision] = useState(0)
  const [ready, setReady] = useState(false)
  const extensions = useMemo(() => extensionColumns(rows), [rows])
  const columns = useMemo<ColDef<ArchitectureRow>[]>(
    () => [
      { field: 'id', headerName: 'Stable ID', pinned: 'left', minWidth: 170 },
      { field: 'name', minWidth: 220 },
      { field: 'kind', filter: 'agTextColumnFilter', minWidth: 140 },
      { field: 'status', filter: 'agTextColumnFilter', minWidth: 150 },
      { field: 'source', filter: 'agTextColumnFilter', minWidth: 160 },
      { field: 'target', filter: 'agTextColumnFilter', minWidth: 160 },
      ...extensions.map<ColDef<ArchitectureRow>>((field) => ({
        field,
        filter: true,
        headerName: field.replaceAll('_', ' '),
        minWidth: 140,
      })),
    ],
    [extensions],
  )
  const knownColumns = useMemo(
    () => new Set(columns.map((column) => column.field).filter((field): field is string => Boolean(field))),
    [columns],
  )

  const persistLayout = useCallback(() => {
    const api = apiRef.current
    if (!api) return
    onLayoutChange(api.getColumnState())
    setColumnRevision((revision) => revision + 1)
  }, [onLayoutChange])

  const onGridReady = useCallback(
    (event: GridReadyEvent<ArchitectureRow>) => {
      apiRef.current = event.api
      const validated = validateGridConfig(config, knownColumns, rememberedLayout)
      if (!validated.valid && validated.diagnostic) onDiagnostic(validated.diagnostic)
      if (validated.columns.length > 0) {
        event.api.applyColumnState({ state: validated.columns, applyOrder: true })
      }
      setReady(true)
    },
    [config, knownColumns, onDiagnostic, rememberedLayout],
  )

  const onRowSelected = useCallback(
    (event: RowSelectedEvent<ArchitectureRow>) => {
      if (event.node.isSelected()) onSelect(event.data?.id)
    },
    [onSelect],
  )

  useEffect(() => {
    apiRef.current?.onFilterChanged()
  }, [statusFilter])

  useEffect(() => {
    const api = apiRef.current
    if (!api || !ready) return
    for (const row of api.getSelectedNodes()) row.setSelected(false)
    for (const selectedId of selectedIds) api.getRowNode(selectedId)?.setSelected(true)
  }, [ready, selectedIds])

  const copySelected = useCallback(async () => {
    const api = apiRef.current
    if (!api) return
    const selected = api.getSelectedRows()
    const visible = api.getAllDisplayedColumns().map((column) => column.getColId())
    const text = selectedRowsAsTsv(selected, visible)
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      onDiagnostic('Clipboard access is unavailable in this browser context')
    }
  }, [onDiagnostic])

  const visibleColumns = useMemo(() => {
    void columnRevision
    const all = apiRef.current?.getColumns() ?? []
    return all.filter((column) => column.getColId().toLowerCase().includes(columnQuery.toLowerCase()))
  }, [columnQuery, columnRevision])

  return (
    <div data-density={density} data-table-id={tableId}>
      <div className="data-toolbar">
        <div>
          <h2 id={`${tableId}-grid-heading`}>{label}</h2>
          <span aria-live="polite" className="row-count">
            {rows.length.toLocaleString()} rows{ready ? '' : ' - loading'}
          </span>
        </div>
        <TextInput
          aria-label={`Search ${label.toLowerCase()}`}
          onChange={(event) => setQuery(event.currentTarget.value)}
          placeholder="ID, name, property..."
          type="search"
          value={query}
        />
        <MultiSelect
          aria-label="Filter by status"
          clearable
          data={STATUS_OPTIONS}
          onChange={(values) => setStatusFilter(values as TransitionStatus[])}
          placeholder="Status"
          value={statusFilter}
        />
        <Menu position="bottom-end" shadow="md" width={300}>
          <Menu.Target>
            <Button variant="default">Columns</Button>
          </Menu.Target>
          <Menu.Dropdown>
            <TextInput
              aria-label="Search columns"
              m="xs"
              onChange={(event) => setColumnQuery(event.currentTarget.value)}
              placeholder="Find a column"
              value={columnQuery}
            />
            <Stack gap={2} mah={280} p="xs" style={{ overflow: 'auto' }}>
              {visibleColumns.map((column) => (
                <Group gap="xs" justify="space-between" key={column.getColId()} wrap="nowrap">
                  <Checkbox
                    checked={column.isVisible()}
                    label={column.getColDef().headerName ?? column.getColId()}
                    onChange={(event) => {
                      apiRef.current?.setColumnsVisible(
                        [column],
                        event.currentTarget.checked,
                      )
                      persistLayout()
                    }}
                  />
                  <Tooltip label={column.isPinned() ? 'Unpin column' : 'Pin column left'}>
                    <ActionIcon
                      aria-label={column.isPinned() ? 'Unpin column' : 'Pin column left'}
                      onClick={() => {
                        apiRef.current?.setColumnsPinned(
                          [column],
                          column.isPinned() ? null : 'left',
                        )
                        persistLayout()
                      }}
                      variant="subtle"
                    >
                      {column.isPinned() ? '×' : '↤'}
                    </ActionIcon>
                  </Tooltip>
                </Group>
              ))}
            </Stack>
          </Menu.Dropdown>
        </Menu>
        <SegmentedControl
          aria-label="Table density"
          data={[
            { label: 'Comfortable', value: 'comfortable' },
            { label: 'Compact', value: 'compact' },
          ]}
          onChange={(value) => onDensityChange(value as Density)}
          size="xs"
          value={density}
        />
        <Menu position="bottom-end">
          <Menu.Target>
            <Button variant="light">Actions</Button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item onClick={() => void copySelected()}>Copy selected rows</Menu.Item>
            <Menu.Item
              onClick={() =>
                apiRef.current?.exportDataAsCsv({ exportedRows: 'filteredAndSorted' })
              }
            >
              Export current view
            </Menu.Item>
            <Menu.Item
              onClick={() =>
                apiRef.current?.exportDataAsCsv({ allColumns: true, exportedRows: 'all' })
              }
            >
              Export all rows and columns
            </Menu.Item>
            <Menu.Item
              onClick={() => {
                apiRef.current?.resetColumnState()
                apiRef.current?.setFilterModel(null)
                setStatusFilter([])
                setQuery('')
                persistLayout()
              }}
            >
              Reset table
            </Menu.Item>
          </Menu.Dropdown>
        </Menu>
      </div>
      {rows.length === 0 ? (
        <Text c="dimmed" p="xl" ta="center">
          No architecture rows match this view.
        </Text>
      ) : (
        <div className="grid-shell" data-testid="architecture-grid">
          <AgGridReact<ArchitectureRow>
            animateRows={false}
            columnDefs={columns}
            defaultColDef={{
              filter: true,
              flex: 1,
              minWidth: 120,
              resizable: true,
              sortable: true,
            }}
            doesExternalFilterPass={(node) =>
              statusFilter.length === 0 || statusFilter.includes(node.data?.status ?? 'No Change')
            }
            getRowId={({ data }) => data.id}
            isExternalFilterPresent={() => statusFilter.length > 0}
            onColumnMoved={persistLayout}
            onColumnPinned={persistLayout}
            onColumnResized={(event) => {
              if (event.finished) persistLayout()
            }}
            onColumnVisible={persistLayout}
            onGridReady={onGridReady}
            onRowSelected={onRowSelected}
            quickFilterText={deferredQuery}
            rowData={rows}
            rowHeight={density === 'compact' ? 32 : 42}
            rowSelection={{ checkboxes: true, enableClickSelection: true, mode: 'multiRow' }}
            theme={gridTheme}
            onFirstDataRendered={(event) => {
              for (const selectedId of selectedIds) {
                event.api.getRowNode(selectedId)?.setSelected(true)
              }
            }}
          />
        </div>
      )}
    </div>
  )
}
