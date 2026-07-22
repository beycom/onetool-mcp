import type { ViewSelection } from '../data/types'

function sortedUnique(values: string[]): string[] {
  return [...new Set(values)].sort()
}

export function normalizedSelection(selection: ViewSelection): ViewSelection {
  return {
    ...selection,
    focus: sortedUnique(selection.focus),
    display_statuses: sortedUnique(selection.display_statuses) as ViewSelection['display_statuses'],
    system_set: {
      systems: sortedUnique(selection.system_set.systems),
      system_groups: sortedUnique(selection.system_set.system_groups),
      changes: sortedUnique(selection.system_set.changes),
      change_groups: sortedUnique(selection.system_set.change_groups),
      tags: sortedUnique(selection.system_set.tags),
    },
  }
}

export function stableJson(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== undefined)
    .sort(([left], [right]) => left.localeCompare(right))
  return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`).join(',')}}`
}

export async function solutionSelectionIdentity(selection: ViewSelection): Promise<string> {
  const encoded = new TextEncoder().encode(stableJson(normalizedSelection(selection)))
  const digest = await globalThis.crypto.subtle.digest('SHA-256', encoded)
  const hash = [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')
  return `selection-${hash.slice(0, 16)}`
}
