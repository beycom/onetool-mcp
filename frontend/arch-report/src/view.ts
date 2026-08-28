import type {
  Aspect,
  Level,
  ReportPayload,
  View,
} from './types'
import { ENTITY_KINDS } from './types'

const LEVELS = new Set<Level>(['systems', 'subsystems', 'containers', 'components'])
const ASPECTS = new Set<Aspect>(['ownership', 'call-direction', 'data-flow'])
const RETIRED_FRAGMENT_KEYS = new Set([
  'mode', 'scope', 'hops', 'compare', 'compare-at', 'theme',
  'x', 'y', 'zoom', 'width', 'height', 'side-size', 'table-size',
])

function integer(value: string | null, fallback: number, maximum: number): number {
  const parsed = Number(value)
  return Number.isInteger(parsed) ? Math.max(0, Math.min(parsed, maximum)) : fallback
}

function oneOf<T extends string>(value: string | null, values: Set<T>, fallback: T): T {
  return value !== null && values.has(value as T) ? value as T : fallback
}

export type ViewDecodeResult = { diagnostics: string[]; select: string | null; view: View }

export function decodeView(payload: ReportPayload, fragment = ''): ViewDecodeResult {
  const params = new URLSearchParams(fragment.replace(/^#/, ''))
  const diagnostics: string[] = []
  for (const key of params.keys()) {
    if (RETIRED_FRAGMENT_KEYS.has(key)) diagnostics.push(`view.fragment.${key}: ignored retired or local-only key`)
  }
  const timeline = integer(params.get('timeline'), 0, payload.timelines.length - 1)
  const maximum = payload.timelines[timeline]?.milestones.length ?? 0
  const entityIds = new Set(ENTITY_KINDS.flatMap((kind) => payload.rows[kind].map((row) => `${kind}:${row.id}`)))
  const entityKey = (key: 'drill' | 'deps'): string | null => {
    const value = params.get(key)
    if (!value) return null
    if (entityIds.has(value)) return value
    diagnostics.push(`view.fragment.${key}.${value}: unknown entity id ignored`)
    return null
  }
  const selectableIds = new Set([
    ...entityIds,
    ...payload.rows.interfaces.map((row) => `interfaces:${row.id}`),
  ])
  const selectValue = params.get('select')
  const select = selectValue && selectableIds.has(selectValue) ? selectValue : null
  if (selectValue && !select) diagnostics.push(`view.fragment.select.${selectValue}: unknown row id ignored`)
  const knownTags = new Set(ENTITY_KINDS.flatMap((kind) => payload.rows[kind].flatMap((row) => row.tags ?? [])))
  const lens = (params.get('lens')?.split(',').filter(Boolean) ?? []).filter((tag) => {
    if (knownTags.has(tag)) return true
    diagnostics.push(`view.fragment.lens.${tag}: unknown tag ignored`)
    return false
  })
  return { diagnostics, select, view: {
    timeline,
    position: integer(params.get('time'), 0, maximum),
    level: oneOf(params.get('level'), LEVELS, 'systems'),
    scope: null,
    compare: 'off',
    comparePosition: 0,
    aspect: oneOf(params.get('aspect'), ASPECTS, 'call-direction'),
    deps: entityKey('deps'),
    drill: entityKey('drill'),
    lens,
    theme: 'light',
  } }
}

export function defaultView(payload: ReportPayload): View {
  const { diagnostics, view } = decodeView(payload, globalThis.location?.hash ?? '')
  for (const diagnostic of diagnostics) console.warn(diagnostic)
  return view
}

export function encodeView(view: View, select: string | null = null): string {
  const params = new URLSearchParams()
  params.set('level', view.level)
  params.set('timeline', String(view.timeline))
  params.set('time', String(view.position))
  params.set('aspect', view.aspect)
  if (view.deps) params.set('deps', view.deps)
  if (view.drill) params.set('drill', view.drill)
  if (view.lens.length) params.set('lens', view.lens.join(','))
  if (select) params.set('select', select)
  return params.toString()
}

export function persistView(view: View, push = false, select: string | null = null): void {
  const fragment = encodeView(view, select)
  if (globalThis.location?.hash.slice(1) !== fragment) {
    history[push ? 'pushState' : 'replaceState'](null, '', `#${fragment}`)
  }
}

export async function copyViewLink(view: View, select: string | null = null): Promise<string> {
  const url = new URL(globalThis.location.href)
  url.hash = encodeView(view, select)
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
