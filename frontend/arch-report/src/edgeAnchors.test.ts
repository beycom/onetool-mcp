import { expect, test } from 'vitest'

import { edgeAnchors, type EdgeRect } from './edgeAnchors'

test('anchors use every facing border and separate parallel lanes', () => {
  const center: EdgeRect = { x: 100, y: 100, width: 80, height: 60 }
  const placements = [
    [{ x: 260, y: 100, width: 80, height: 60 }, 'right', 'left'],
    [{ x: -60, y: 100, width: 80, height: 60 }, 'left', 'right'],
    [{ x: 100, y: -40, width: 80, height: 60 }, 'top', 'bottom'],
    [{ x: 100, y: 240, width: 80, height: 60 }, 'bottom', 'top'],
  ] as const

  for (const [target, sourceSide, targetSide] of placements) {
    const anchors = edgeAnchors(center, target, 0, 1)
    expect(anchors.sourcePoint.side).toBe(sourceSide)
    expect(anchors.targetPoint.side).toBe(targetSide)
  }

  const first = edgeAnchors(center, placements[0][0], 0, 2)
  const second = edgeAnchors(center, placements[0][0], 1, 2)
  expect(first.sourcePoint.y).not.toBe(second.sourcePoint.y)
  expect(first.targetPoint.y).not.toBe(second.targetPoint.y)
})
