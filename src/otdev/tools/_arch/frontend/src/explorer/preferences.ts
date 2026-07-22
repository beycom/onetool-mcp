import type { Density } from '../data/types'

export const PREFERENCES_KEY = 'onetool-architecture-preferences:v1'

export interface ExplorerPreferences {
  schemaVersion: 1
  density: Density
  colorScheme: 'auto' | 'light' | 'dark'
  tableLayouts: Record<string, unknown[]>
}

export const DEFAULT_PREFERENCES: ExplorerPreferences = {
  schemaVersion: 1,
  density: 'comfortable',
  colorScheme: 'auto',
  tableLayouts: {},
}

export function validatePreferences(value: unknown): ExplorerPreferences | null {
  if (typeof value !== 'object' || value === null) return null
  const candidate = value as Partial<ExplorerPreferences>
  if (candidate.schemaVersion !== 1) return null
  if (candidate.density !== 'comfortable' && candidate.density !== 'compact') return null
  if (!['auto', 'light', 'dark'].includes(candidate.colorScheme ?? '')) return null
  if (
    typeof candidate.tableLayouts !== 'object' ||
    candidate.tableLayouts === null ||
    Array.isArray(candidate.tableLayouts)
  ) {
    return null
  }
  if (!Object.values(candidate.tableLayouts).every(Array.isArray)) return null
  return candidate as ExplorerPreferences
}

export function loadPreferences(storage: Pick<Storage, 'getItem' | 'removeItem'>): ExplorerPreferences {
  try {
    const serialized = storage.getItem(PREFERENCES_KEY)
    if (serialized === null) return DEFAULT_PREFERENCES
    const parsed = validatePreferences(JSON.parse(serialized))
    if (parsed !== null) return parsed
    storage.removeItem(PREFERENCES_KEY)
  } catch {
    // Storage and JSON parsing can be unavailable; workspace defaults remain authoritative.
  }
  return DEFAULT_PREFERENCES
}

export function savePreferences(
  storage: Pick<Storage, 'setItem'>,
  preferences: ExplorerPreferences,
): boolean {
  try {
    storage.setItem(PREFERENCES_KEY, JSON.stringify(preferences))
    return true
  } catch {
    return false
  }
}
