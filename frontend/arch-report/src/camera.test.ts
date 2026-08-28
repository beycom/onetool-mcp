import { expect, test } from 'vitest'

import { initialViewport, shiftViewport } from './camera'

test('initial framing fits a small graph and caps a large graph at Read', () => {
  const visible = { x: 0, y: 0, width: 800, height: 600 }
  const thresholds = { read: 0.8, full: 1.1 }
  const small = initialViewport({ x: 100, y: 50, width: 400, height: 200 }, visible, thresholds)
  const large = initialViewport({ x: 0, y: 0, width: 2000, height: 1000 }, visible, thresholds)

  expect(small.zoom).toBeCloseTo(1.52)
  expect(small.x + (100 + 200) * small.zoom).toBeCloseTo(400)
  expect(small.y + (50 + 100) * small.zoom).toBeCloseTo(300)
  expect(large).toEqual({ x: -400, y: -100, zoom: 0.8 })
})

test('camera shifting is unchanged inside and uses the minimum pan outside without changing zoom', () => {
  const viewport = { x: 0, y: 0, zoom: 1.25 }
  const visible = { x: 0, y: 0, width: 200, height: 120 }

  expect(shiftViewport(viewport, visible, { x: 20, y: 20, width: 40, height: 30 })).toBe(viewport)
  expect(shiftViewport(viewport, visible, { x: 150, y: 20, width: 40, height: 30 })).toEqual({ x: -37.5, y: 0, zoom: 1.25 })
})
