import { expect, test } from 'vitest'

import { BODY_FONT_SIZE, NAME_FONT_SIZE, READING_DEPTH, readingDepth } from './zoom'

test('reading-depth boundaries equal the thresholds derived from the type scale', () => {
  expect(READING_DEPTH.read).toBe(11 / NAME_FONT_SIZE)
  expect(READING_DEPTH.full).toBe(11 / BODY_FONT_SIZE)
  expect(readingDepth(READING_DEPTH.read - Number.EPSILON)).toBe('far')
  expect(readingDepth(READING_DEPTH.read)).toBe('read')
  expect(readingDepth(READING_DEPTH.full)).toBe('full')
})
