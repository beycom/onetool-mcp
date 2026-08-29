import type { CSSProperties } from 'react'

import type { EntityKind, PresentationTheme, ThemeKind } from './types'

export const DEFAULT_KIND_COLORS: Record<ThemeKind, string> = {
  system: '#2e6f9b',
  subsystem: '#257b72',
  container: '#686d9a',
  component: '#865b7e',
  code: '#68713e',
  user: '#925d37',
}

const THEME_KIND: Record<EntityKind, ThemeKind> = {
  systems: 'system',
  subsystems: 'subsystem',
  containers: 'container',
  components: 'component',
  code: 'code',
  users: 'user',
}

type CustomProperties = CSSProperties & Record<`--kind-${ThemeKind}`, string>

export function kindColorReference(kind: EntityKind): string {
  return `var(--kind-${THEME_KIND[kind]})`
}

export function kindPresentationStyle(kind: EntityKind, selected = false): CSSProperties {
  return {
    '--card-border': selected ? 'var(--accent)' : 'var(--kind-color)',
    '--kind-color': kindColorReference(kind),
  } as CSSProperties
}

export function themeStyle(theme: PresentationTheme): CustomProperties {
  const colors = { ...DEFAULT_KIND_COLORS, ...theme.kinds }
  return Object.fromEntries(Object.entries(colors).map(([kind, color]) => [`--kind-${kind}`, color])) as unknown as CustomProperties
}
