import type { ColumnState } from 'ag-grid-community'

export const LAYOUT_KEY = 'onetool-arch-report-layout:v2'
export const DOCK_DEFAULTS = {
  data: { collapsed: true, size: 280 },
  info: { collapsed: true, size: 360 },
  view: { collapsed: false, size: 280 },
} as const
export const DOCK_LIMITS = {
  data: [180, 640],
  info: [280, 720],
  view: [220, 480],
} as const

export type Density = 'comfortable' | 'compact'
export type DockName = keyof typeof DOCK_DEFAULTS
export type DockLayout = { collapsed: boolean; size: number }
export type LayoutPreferences = {
  schemaVersion: 2
  density: Density
  docks: Record<DockName, DockLayout>
  tableLayouts: Record<string, ColumnState[]>
}

export function defaultLayout(): LayoutPreferences {
  return {
    schemaVersion: 2,
    density: 'comfortable',
    docks: {
      data: { ...DOCK_DEFAULTS.data },
      info: { ...DOCK_DEFAULTS.info },
      view: { ...DOCK_DEFAULTS.view },
    },
    tableLayouts: {},
  }
}

function validDock(value: unknown, name: DockName): value is DockLayout {
  if (!value || typeof value !== 'object') return false
  const dock = value as Partial<DockLayout>
  const limits = DOCK_LIMITS[name]
  return typeof dock.collapsed === 'boolean'
    && typeof dock.size === 'number'
    && Number.isFinite(dock.size)
    && dock.size >= limits[0]
    && dock.size <= limits[1]
}

export function validateLayout(
  value: unknown,
  knownColumns: Record<string, ReadonlySet<string>> = {},
): LayoutPreferences | null {
  if (!value || typeof value !== 'object') return null
  const layout = value as Partial<LayoutPreferences>
  if (layout.schemaVersion !== 2 || !['comfortable', 'compact'].includes(layout.density ?? '')) return null
  if (!layout.docks
    || !validDock(layout.docks.view, 'view')
    || !validDock(layout.docks.info, 'info')
    || !validDock(layout.docks.data, 'data')) return null
  if (!layout.tableLayouts || typeof layout.tableLayouts !== 'object' || Array.isArray(layout.tableLayouts)) return null
  for (const [table, columns] of Object.entries(layout.tableLayouts)) {
    if (!Array.isArray(columns)) return null
    const known = knownColumns[table]
    for (const column of columns) {
      if (!column || typeof column !== 'object' || typeof column.colId !== 'string') return null
      if (known && !known.has(column.colId)) return null
    }
  }
  return layout as LayoutPreferences
}

export function loadLayout(
  storage: Pick<Storage, 'getItem' | 'removeItem'>,
  knownColumns: Record<string, ReadonlySet<string>> = {},
): LayoutPreferences {
  try {
    const serialized = storage.getItem(LAYOUT_KEY)
    if (serialized === null) return defaultLayout()
    const parsed = validateLayout(JSON.parse(serialized), knownColumns)
    if (parsed) return parsed
    storage.removeItem(LAYOUT_KEY)
  } catch {
    // localStorage can be unavailable under locked-down file viewers.
  }
  return defaultLayout()
}

export function saveLayout(storage: Pick<Storage, 'setItem'>, layout: LayoutPreferences): boolean {
  try {
    storage.setItem(LAYOUT_KEY, JSON.stringify(layout))
    return true
  } catch {
    return false
  }
}
