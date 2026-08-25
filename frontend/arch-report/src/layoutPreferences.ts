import type { ColumnState } from 'ag-grid-community'

export const LAYOUT_KEY = 'onetool-arch-report-layout:v1'
export const PANEL_DEFAULTS = {
  bottom: { collapsed: true, size: 280 },
  legend: { collapsed: false, size: 250 },
  side: { collapsed: false, size: 360 },
} as const

export type Density = 'comfortable' | 'compact'
export type PanelName = keyof typeof PANEL_DEFAULTS
export type PanelLayout = { collapsed: boolean; size: number }
export type LayoutPreferences = {
  schemaVersion: 1
  density: Density
  panels: Record<PanelName, PanelLayout>
  tableLayouts: Record<string, ColumnState[]>
}

export function defaultLayout(): LayoutPreferences {
  return {
    schemaVersion: 1,
    density: 'comfortable',
    panels: {
      bottom: { ...PANEL_DEFAULTS.bottom },
      legend: { ...PANEL_DEFAULTS.legend },
      side: { ...PANEL_DEFAULTS.side },
    },
    tableLayouts: {},
  }
}

function validPanel(value: unknown, name: PanelName): value is PanelLayout {
  if (!value || typeof value !== 'object') return false
  const panel = value as Partial<PanelLayout>
  const limits = name === 'side' ? [280, 720] : name === 'legend' ? [180, 400] : [180, 640]
  return typeof panel.collapsed === 'boolean'
    && typeof panel.size === 'number'
    && Number.isFinite(panel.size)
    && panel.size >= limits[0]
    && panel.size <= limits[1]
}

export function validateLayout(
  value: unknown,
  knownColumns: Record<string, ReadonlySet<string>> = {},
): LayoutPreferences | null {
  if (!value || typeof value !== 'object') return null
  const layout = value as Partial<LayoutPreferences>
  if (layout.schemaVersion !== 1 || !['comfortable', 'compact'].includes(layout.density ?? '')) return null
  if (!layout.panels || !validPanel(layout.panels.side, 'side') || !validPanel(layout.panels.bottom, 'bottom') || !validPanel(layout.panels.legend, 'legend')) return null
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
