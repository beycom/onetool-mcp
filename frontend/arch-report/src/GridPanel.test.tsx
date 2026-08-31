// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

const grid = vi.hoisted(() => {
  const api = {
    applyColumnState: vi.fn(),
    autoSizeColumns: vi.fn(),
    destroy: vi.fn(),
    ensureNodeVisible: vi.fn(),
    getAllDisplayedColumns: vi.fn(),
    getColumns: vi.fn(() => []),
    getRowNode: vi.fn(),
    getSelectedNodes: vi.fn(() => []),
    onFilterChanged: vi.fn(),
    setGridOption: vi.fn(),
  }
  return { api, options: null as Record<string, unknown> | null }
})

vi.mock('ag-grid-community', () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: vi.fn() },
  createGrid: vi.fn((_element: HTMLElement, options: Record<string, unknown>) => {
    grid.options = options
    const columns = (options.columnDefs as Array<{ field: string; hide?: boolean }>).filter((column) => !column.hide).map((column) => ({ getColId: () => column.field }))
    grid.api.getAllDisplayedColumns.mockReturnValue(columns)
    ;(options.onFirstDataRendered as (event: { api: typeof grid.api }) => void)({ api: grid.api })
    return grid.api
  }),
  themeQuartz: { withParams: vi.fn(() => ({})) },
}))

import fixture from './fixture-payload.json'
import { CheckboxSetFilter, GridPanel } from './GridPanel'
import { projectState } from './projection'
import type { ReportPayload, View } from './types'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  grid.options = null
})

test('Data folds subsystems into raw Entities, hides empty columns, and auto-sizes populated columns', async () => {
  const payload = structuredClone(fixture) as unknown as ReportPayload
  const system = payload.rows.systems.find((row) => row.id === 'commerce-platform')!
  system.properties = { ...system.properties, empty_note: '', populated_note: 'Visible value' }
  const view: View = {
    aspect: 'call-direction', compare: 'off', comparePosition: 0, deps: null, expand: [],
    lens: [], position: 5, scope: null, theme: 'light', timeline: 0, layout: null,
  }

  render(<GridPanel
    density="comfortable"
    diff={null}
    layouts={{}}
    onDensity={() => undefined}
    onDiagnostic={() => undefined}
    onLayout={() => undefined}
    onSelect={() => undefined}
    onShowOnCanvas={() => undefined}
    payload={payload}
    projected={projectState(payload, view)}
    selectedKey={null}
    selectedOnCanvas={false}
    timeline={0}
  />)

  await waitFor(() => expect(grid.options).not.toBeNull())
  const columns = grid.options!.columnDefs as Array<{ field: string; headerName: string; hide?: boolean }>
  const rows = grid.options!.rowData as Array<{ kind: string }>
  expect(screen.queryByRole('button', { name: 'Subsystems' })).toBeNull()
  expect(rows.some((row) => row.kind === 'subsystems')).toBe(true)
  expect(columns.find((column) => column.field === 'property.empty_note')).toMatchObject({ headerName: 'Empty note', hide: true })
  expect(columns.find((column) => column.field === 'property.populated_note')).toMatchObject({ headerName: 'Populated note', hide: false })
  expect(grid.api.autoSizeColumns).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ getColId: expect.any(Function) })]), false)
})

test('Kind and Status use checkbox header filters instead of toolbar menus', async () => {
  const projected = projectState(fixture as unknown as ReportPayload, {
    aspect: 'call-direction', compare: 'off', comparePosition: 0, deps: null, expand: [],
    lens: [], position: 1, scope: null, theme: 'light', timeline: 0, layout: null,
  })
  render(<GridPanel
    density="comfortable"
    diff={{ added: [], changed: [], removed: [] }}
    layouts={{}}
    onDensity={() => undefined}
    onDiagnostic={() => undefined}
    onLayout={() => undefined}
    onSelect={() => undefined}
    onShowOnCanvas={() => undefined}
    payload={fixture as unknown as ReportPayload}
    projected={projected}
    selectedKey={null}
    selectedOnCanvas={false}
    timeline={0}
  />)

  await waitFor(() => expect(grid.options).not.toBeNull())
  const columns = grid.options!.columnDefs as Array<{ field: string; filter?: unknown; filterParams?: { values: string[] } }>
  expect(columns.find(({ field }) => field === 'kind')).toMatchObject({ filter: CheckboxSetFilter })
  expect(columns.find(({ field }) => field === 'status')).toMatchObject({ filter: CheckboxSetFilter })
  expect(screen.queryByRole('button', { name: 'Kind' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Status' })).toBeNull()

  const filterChangedCallback = vi.fn()
  const filter = new CheckboxSetFilter()
  filter.init({
    filterChangedCallback,
    formatValue: (value: string) => value,
    getValue: (node: { data?: { kind?: string } }) => node.data?.kind,
    values: ['', 'systems', 'users'],
  } as never)
  expect([...filter.getGui().querySelectorAll('label')].map((label) => label.textContent)).toEqual(['(Blank)', 'systems', 'users'])
  filter.setModel({ values: ['', 'systems'] })
  expect(filter.doesFilterPass({ node: { data: { kind: 'systems' } } } as never)).toBe(true)
  expect(filter.doesFilterPass({ node: { data: { kind: 'users' } } } as never)).toBe(false)
  expect(filter.doesFilterPass({ node: { data: {} } } as never)).toBe(true)
})
