export const READING_DEPTH = {
  full: 175,
  far: 100,
} as const

export type ReadingDepth = 'far' | 'read' | 'full'

export function readingDepth(zoom: number): ReadingDepth {
  const percentage = Math.round(zoom * 100)
  if (percentage < READING_DEPTH.far) return 'far'
  if (percentage < READING_DEPTH.full) return 'read'
  return 'full'
}
