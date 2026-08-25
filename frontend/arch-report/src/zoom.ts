export const READING_DEPTH = {
  full: 175,
  map: 100,
} as const

export type ReadingDepth = 'map' | 'read' | 'full'

export function readingDepth(zoom: number): ReadingDepth {
  const percentage = Math.round(zoom * 100)
  if (percentage < READING_DEPTH.map) return 'map'
  if (percentage < READING_DEPTH.full) return 'read'
  return 'full'
}
