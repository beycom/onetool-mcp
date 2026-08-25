import type {
  Aspect,
  CompareMode,
  DiagramMode,
  Level,
  ReportPayload,
  ScopeSelection,
  Theme,
  View,
} from './types'

const LEVELS = new Set<Level>(['systems', 'containers', 'components'])
const COMPARE_MODES = new Set<CompareMode>(['off', 'base', 'position'])
const ASPECTS = new Set<Aspect>(['ownership', 'call-direction', 'data-flow'])
const MODES = new Set<DiagramMode>(['MAP', 'PATH', 'LENS'])
const THEMES = new Set<Theme>(['light', 'dark'])

function integer(value: string | null, fallback: number, maximum: number): number {
  const parsed = Number(value)
  return Number.isInteger(parsed) ? Math.max(0, Math.min(parsed, maximum)) : fallback
}

function oneOf<T extends string>(value: string | null, values: Set<T>, fallback: T): T {
  return value !== null && values.has(value as T) ? value as T : fallback
}

export function defaultView(payload: ReportPayload): View {
  const params = new URLSearchParams(globalThis.location?.hash.replace(/^#/, '') ?? '')
  const timeline = integer(params.get('timeline'), 0, payload.timelines.length - 1)
  const maximum = payload.timelines[timeline]?.milestones.length ?? 0
  const scopeValue = params.get('scope')
  const scope: ScopeSelection = scopeValue && scopeValue !== 'all'
    ? {
        systems: scopeValue.split(',').filter(Boolean),
        hops: integer(params.get('hops'), 1, 20),
      }
    : null
  return {
    timeline,
    position: integer(params.get('time'), 0, maximum),
    level: oneOf(params.get('level'), LEVELS, 'systems'),
    scope,
    compare: oneOf(params.get('compare'), COMPARE_MODES, 'off'),
    comparePosition: integer(params.get('compare-at'), 0, maximum),
    aspect: oneOf(params.get('aspect'), ASPECTS, 'ownership'),
    mode: oneOf(params.get('mode'), MODES, 'MAP'),
    theme: oneOf(params.get('theme'), THEMES, 'light'),
  }
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
  params.set('mode', view.mode)
  params.set('theme', view.theme)
  return params.toString()
}

export function persistView(view: View): void {
  const fragment = encodeView(view)
  if (globalThis.location?.hash.slice(1) !== fragment) history.replaceState(null, '', `#${fragment}`)
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
