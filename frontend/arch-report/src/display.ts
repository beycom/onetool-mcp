import type { EntityKind, Level, ReportPayload, ReportRow, RowKind } from './types'

export const KIND_LABEL: Record<RowKind, string> = {
  systems: 'System',
  subsystems: 'Subsystem',
  containers: 'Container',
  components: 'Component',
  code: 'Code',
  users: 'User',
  interfaces: 'Interface',
  relationships: 'Relationship',
}

export function rowLabel(row: ReportRow): string {
  return row.name ?? row.action ?? row.id
}

export function humanizeField(field: string): string {
  const words = field.replace(/^propert(?:y|ies)\./, '').replace(/[._-]+/g, ' ').trim().toLocaleLowerCase()
  return words ? `${words[0].toLocaleUpperCase()}${words.slice(1)}` : ''
}

export function displayValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(', ')
  if (value === null || value === undefined || value === '') return 'None'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function levelForKind(kind: EntityKind): Level {
  if (kind === 'code') return 'components'
  if (kind === 'users') return 'systems'
  return kind
}

function stageLabel(payload: ReportPayload, timeline: number, position: number): string {
  if (position === 0) return 'Base'
  const milestoneId = payload.timelines[timeline]?.milestones[position - 1]
  const milestone = payload.milestones.find((item) => item.id === milestoneId)
  return `${position} · ${milestone?.name ?? milestoneId ?? 'Unknown stage'}`
}

export function lifecycleLabel(row: ReportRow, payload: ReportPayload, timeline: number): string {
  const segments = row.intervals[timeline]?.live ?? []
  return segments.map(([start, end]) => {
    const from = stageLabel(payload, timeline, start)
    if (end === null) return `${from} onward`
    if (end === start) return from
    return `${from} → ${stageLabel(payload, timeline, end)}`
  }).join(' · ') || 'Not live on this timeline'
}
