const MIN_SCREEN_TEXT = 11
export const NAME_FONT_SIZE = 14
export const BODY_FONT_SIZE = 10

// Read starts when the 14 px name line reaches 11 screen px.
// Full starts when the 10 px body copy reaches 11 screen px.
export const READING_DEPTH = {
  read: MIN_SCREEN_TEXT / NAME_FONT_SIZE,
  full: MIN_SCREEN_TEXT / BODY_FONT_SIZE,
} as const

export type ReadingDepth = 'far' | 'read' | 'full'

export function readingDepth(zoom: number): ReadingDepth {
  if (zoom < READING_DEPTH.read) return 'far'
  if (zoom < READING_DEPTH.full) return 'read'
  return 'full'
}
