import type {
  Aspect,
  CompareMode,
  Level,
  ReportPayload,
  ScopeSelection,
  Theme,
  View,
} from './types'
import { ENTITY_KINDS } from './types'

const LEVELS = new Set<Level>(['systems', 'top-containers', 'containers', 'components'])
const COMPARE_MODES = new Set<CompareMode>(['off', 'base', 'position'])
const ASPECTS = new Set<Aspect>(['ownership', 'call-direction', 'data-flow'])
const THEMES = new Set<Theme>(['light', 'dark'])
const FORBIDDEN_FRAGMENT_KEYS = new Set(['mode', 'x', 'y', 'zoom', 'width', 'height', 'side-size', 'table-size'])

function integer(value: string | null, fallback: number, maximum: number): number {
  const parsed = Number(value)
  return Number.isInteger(parsed) ? Math.max(0, Math.min(parsed, maximum)) : fallback
}

function oneOf<T extends string>(value: string | null, values: Set<T>, fallback: T): T {
  return value !== null && values.has(value as T) ? value as T : fallback
}

export type ViewDecodeResult = { diagnostics: string[]; view: View }

export function decodeView(payload: ReportPayload, fragment = ''): ViewDecodeResult {
  const params = new URLSearchParams(fragment.replace(/^#/, ''))
  const diagnostics: string[] = []
  for (const key of params.keys()) {
    if (FORBIDDEN_FRAGMENT_KEYS.has(key)) diagnostics.push(`view.fragment.${key}: ignored retired or local-only key`)
  }
  const timeline = integer(params.get('timeline'), 0, payload.timelines.length - 1)
  const maximum = payload.timelines[timeline]?.milestones.length ?? 0
  const scopeValue = params.get('scope')
  const knownSystems = new Set(payload.rows.systems.map((row) => row.id))
  const requestedSystems = scopeValue && scopeValue !== 'all' ? scopeValue.split(',').filter(Boolean) : []
  const systems = requestedSystems.filter((id) => {
    if (knownSystems.has(id)) return true
    diagnostics.push(`view.fragment.scope.${id}: unknown system id ignored`)
    return false
  })
  const scope: ScopeSelection = scopeValue && scopeValue !== 'all'
    ? {
        systems,
        hops: integer(params.get('hops'), 1, 20),
      }
    : null
  const entityIds = new Set(ENTITY_KINDS.flatMap((kind) => payload.rows[kind].map((row) => `${kind}:${row.id}`)))
  const entityKey = (key: 'drill' | 'deps'): string | null => {
    const value = params.get(key)
    if (!value) return null
    if (entityIds.has(value)) return value
    diagnostics.push(`view.fragment.${key}.${value}: unknown entity id ignored`)
    return null
  }
  const knownTags = new Set(ENTITY_KINDS.flatMap((kind) => payload.rows[kind].flatMap((row) => row.tags ?? [])))
  const lens = (params.get('lens')?.split(',').filter(Boolean) ?? []).filter((tag) => {
    if (knownTags.has(tag)) return true
    diagnostics.push(`view.fragment.lens.${tag}: unknown tag ignored`)
    return false
  })
  return { diagnostics, view: {
    timeline,
    position: integer(params.get('time'), 0, maximum),
    level: oneOf(params.get('level'), LEVELS, 'systems'),
    scope,
    compare: oneOf(params.get('compare'), COMPARE_MODES, 'off'),
    comparePosition: integer(params.get('compare-at'), 0, maximum),
    aspect: oneOf(params.get('aspect'), ASPECTS, 'ownership'),
    deps: entityKey('deps'),
    drill: entityKey('drill'),
    lens,
    theme: oneOf(params.get('theme'), THEMES, 'light'),
  } }
}

export function defaultView(payload: ReportPayload): View {
  const { diagnostics, view } = decodeView(payload, globalThis.location?.hash ?? '')
  for (const diagnostic of diagnostics) console.warn(diagnostic)
  return view
}

export function encodeView(view: View): string {
  const params = new URLSearchParams()
  params.set('scope', view.scope?.systems.join(',') || 'all')
  params.set('hops', String(view.scope?.hops ?? 1))
  params.set('level', view.level)
  params.set('timeline', String(view.timeline))
  params.set('time', String(view.position))
  params.set('compare', view.compare)
  params.set('compare-at', String(view.comparePosition))
  params.set('aspect', view.aspect)
  if (view.deps) params.set('deps', view.deps)
  if (view.drill) params.set('drill', view.drill)
  if (view.lens.length) params.set('lens', view.lens.join(','))
  params.set('theme', view.theme)
  return params.toString()
}

export function persistView(view: View, push = false): void {
  const fragment = encodeView(view)
  if (globalThis.location?.hash.slice(1) !== fragment) {
    history[push ? 'pushState' : 'replaceState'](null, '', `#${fragment}`)
  }
}

export async function copyViewLink(view: View): Promise<string> {
  const url = new URL(globalThis.location.href)
  url.hash = encodeView(view)
  const text = url.toString()
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
  } else {
    const input = document.createElement('textarea')
    input.value = text
    input.style.position = 'fixed'
    input.style.opacity = '0'
    document.body.append(input)
    input.select()
    document.execCommand('copy')
    input.remove()
  }
  return text
}
