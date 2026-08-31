import type { Viewport } from './camera'
import { readingDepth } from './zoom'

export type ViewportCommitReason = 'gesture' | 'gesture-end' | 'programmatic'

export function shouldCommitViewport(current: Viewport, next: Viewport, reason: ViewportCommitReason): boolean {
  return reason !== 'gesture' || readingDepth(current.zoom) !== readingDepth(next.zoom)
}

type DataItem<T> = { data?: T; id: string }

function sameValue(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true
  if (typeof left !== 'object' || left === null || typeof right !== 'object' || right === null) return false
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length
      && left.every((value, index) => sameValue(value, right[index]))
  }
  const leftRecord = left as Record<string, unknown>
  const rightRecord = right as Record<string, unknown>
  const keys = Object.keys(leftRecord)
  return keys.length === Object.keys(rightRecord).length
    && keys.every((key) => Object.hasOwn(rightRecord, key) && sameValue(leftRecord[key], rightRecord[key]))
}

export function stabilizeItemData<T, Item extends DataItem<T>>(previous: Item[], next: Item[]): Item[] {
  const previousById = new Map(previous.map((item) => [item.id, item]))
  return next.map((item) => {
    const prior = previousById.get(item.id)
    return prior?.data !== undefined && item.data !== undefined && sameValue(prior.data, item.data)
      ? { ...item, data: prior.data }
      : item
  })
}
