import { DEFAULT_LAYOUT_SETTINGS, registeredLayoutMethods, type LayoutMethod, type LayoutSettings } from './layout'

export type AuthoredLayout = {
  method?: unknown
  direction?: unknown
  spacing?: unknown
  ranking?: unknown
  user_choice?: unknown
  [key: string]: unknown
}

export function isLayoutMethod(value: unknown): value is LayoutMethod {
  return typeof value === 'string' && registeredLayoutMethods.includes(value as LayoutMethod)
}

function positiveInt(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : fallback
}

export function configuredLayoutMethod(layout: AuthoredLayout | undefined): LayoutMethod | null {
  if (!layout || !Object.keys(layout).length) return null
  return isLayoutMethod(layout.method) ? layout.method : DEFAULT_LAYOUT_SETTINGS.method
}

export function configuredUserChoice(layout: AuthoredLayout | undefined): boolean {
  return layout?.user_choice === true
}

export function layoutSettings(
  layout: AuthoredLayout | undefined,
  method: LayoutMethod | null,
): LayoutSettings | null {
  if (method === null) return null
  const spacing = layout?.spacing && typeof layout.spacing === 'object' && !Array.isArray(layout.spacing)
    ? layout.spacing as Record<string, unknown>
    : {}
  const ranking = typeof layout?.ranking === 'string'
    && (layout.ranking === 'auto' || /^property:.+/.test(layout.ranking))
    ? layout.ranking as LayoutSettings['ranking']
    : DEFAULT_LAYOUT_SETTINGS.ranking
  return {
    method,
    direction: layout?.direction === 'down' ? 'down' : DEFAULT_LAYOUT_SETTINGS.direction,
    spacing: {
      node: positiveInt(spacing.node, DEFAULT_LAYOUT_SETTINGS.spacing.node),
      layer: positiveInt(spacing.layer, DEFAULT_LAYOUT_SETTINGS.spacing.layer),
      boundary: positiveInt(spacing.boundary, DEFAULT_LAYOUT_SETTINGS.spacing.boundary),
    },
    ranking,
  }
}

export function layoutStorageKey(source: string): string {
  return `onetool-arch-report-layout-method:${source}`
}

export function loadLayoutMethod(storage: Pick<Storage, 'getItem'>, source: string): LayoutMethod | null {
  try {
    const value = storage.getItem(layoutStorageKey(source))
    return isLayoutMethod(value) ? value : null
  } catch {
    return null
  }
}

export function saveLayoutMethod(storage: Pick<Storage, 'setItem'>, source: string, method: LayoutMethod): boolean {
  try {
    storage.setItem(layoutStorageKey(source), method)
    return true
  } catch {
    return false
  }
}

export function queryLayoutMethod(search: string, enabled: boolean): LayoutMethod | null {
  if (!enabled) return null
  const value = new URLSearchParams(search).get('layout')
  return isLayoutMethod(value) ? value : null
}

export function resolveLayoutMethod({
  query,
  hash,
  stored,
  config,
}: {
  query: LayoutMethod | null
  hash: LayoutMethod | null
  stored: LayoutMethod | null
  config: LayoutMethod | null
}): LayoutMethod | null {
  return query ?? hash ?? stored ?? config
}
