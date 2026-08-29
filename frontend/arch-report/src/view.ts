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

const PRESET_KINDS: Record<Level, Set<string>> = {
  systems: new Set(),
  subsystems: new Set(['systems']),
  containers: new Set(['systems', 'subsystems']),
  components: new Set(['systems', 'subsystems', 'containers']),
}

function entityKey(kind: string, id: string): string {
  return `${kind}:${id}`
}

function parentId(row: ReportPayload['rows'][keyof ReportPayload['rows']][number]): string | undefined {
  return row.parent ?? row.container ?? row.component
}

export function containmentIndex(payload: ReportPayload) {
  const refs = ENTITY_KINDS.flatMap((kind) => payload.rows[kind].map((row) => ({ key: entityKey(kind, row.id), kind, row })))
  const byKey = new Map(refs.map((ref) => [ref.key, ref]))
  const byId = new Map<string, typeof refs[number]>()
  for (const ref of refs) if (!byId.has(ref.row.id)) byId.set(ref.row.id, ref)
  const parentByKey = new Map<string, string>()
  const childrenByKey = new Map<string, string[]>()
  for (const ref of refs) {
    const id = parentId(ref.row)
    const parent = id ? byId.get(id) : undefined
    if (!parent) continue
    parentByKey.set(ref.key, parent.key)
    childrenByKey.set(parent.key, [...(childrenByKey.get(parent.key) ?? []), ref.key])
  }
  return { byKey, childrenByKey, parentByKey }
}

export function presetExpansion(payload: ReportPayload, preset: Level): string[] {
  const { byKey, childrenByKey } = containmentIndex(payload)
  const kinds = PRESET_KINDS[preset]
  return [...childrenByKey.keys()].filter((key) => kinds.has(byKey.get(key)!.kind)).sort()
}

export function expansionPreset(payload: ReportPayload, expand: readonly string[]): Level | 'custom' {
  const current = [...new Set(expand)].sort().join(',')
  for (const preset of LEVELS) {
    if (presetExpansion(payload, preset).join(',') === current) return preset
  }
  return 'custom'
}

export function expansionPath(payload: ReportPayload, key: string, includeSelf = true): string[] {
  const { childrenByKey, parentByKey } = containmentIndex(payload)
  const path: string[] = []
  let cursor: string | undefined = includeSelf ? key : parentByKey.get(key)
  while (cursor) {
    if (childrenByKey.has(cursor)) path.unshift(cursor)
    cursor = parentByKey.get(cursor)
  }
  return path
}

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
  const { byKey, childrenByKey } = containmentIndex(payload)
  const entityIds = new Set(byKey.keys())
  const validatedEntityKey = (key: 'drill' | 'deps'): string | null => {
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
  const expand = new Set<string>()
  const requestedExpand = params.get('expand')?.split(',').filter(Boolean) ?? []
  for (const key of requestedExpand) {
    if (childrenByKey.has(key)) expand.add(key)
    else diagnostics.push(`view.fragment.expand.${key}: unknown or childless entity id ignored`)
  }
  const legacyLevel = params.get('level')
  if (!requestedExpand.length && legacyLevel) {
    const level = oneOf(legacyLevel, LEVELS, 'systems')
    presetExpansion(payload, level).forEach((key) => expand.add(key))
  }
  const legacyDrill = validatedEntityKey('drill')
  if (legacyDrill) expansionPath(payload, legacyDrill).forEach((key) => expand.add(key))
  return { diagnostics, select: legacyDrill ?? select, view: {
    timeline,
    position: integer(params.get('time'), 0, maximum),
    expand: [...expand].sort(),
    scope: null,
    compare: 'off',
    comparePosition: 0,
    aspect: oneOf(params.get('aspect'), ASPECTS, 'call-direction'),
    deps: validatedEntityKey('deps'),
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
  params.set('timeline', String(view.timeline))
  params.set('time', String(view.position))
  params.set('aspect', view.aspect)
  if (view.deps) params.set('deps', view.deps)
  if (view.expand.length) params.set('expand', [...new Set(view.expand)].sort().join(','))
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
