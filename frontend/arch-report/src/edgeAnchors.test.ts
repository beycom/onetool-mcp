import { expect, test } from 'vitest'

import { edgeAnchors, type EdgeRect } from './edgeAnchors'
import { splinePath } from './splinePath'

test('anchors use facing borders, distribute each side, and terminate with perpendicular stubs', () => {
  const center: EdgeRect = { x: 100, y: 100, width: 80, height: 60 }
  const placements = [
    [{ x: 260, y: 100, width: 80, height: 60 }, 'right', 'left'],
    [{ x: -60, y: 100, width: 80, height: 60 }, 'left', 'right'],
    [{ x: 100, y: -40, width: 80, height: 60 }, 'top', 'bottom'],
    [{ x: 100, y: 240, width: 80, height: 60 }, 'bottom', 'top'],
  ] as const

  const facing = edgeAnchors(placements.map(([target], index) => ({
    id: `facing-${index}`,
    sourceId: 'center',
    sourceRect: center,
    targetId: `target-${index}`,
    targetRect: target,
  })))
  for (const [index, [, sourceSide, targetSide]] of placements.entries()) {
    const anchors = facing.get(`facing-${index}`)!
    expect(anchors.sourcePoint.side).toBe(sourceSide)
    expect(anchors.targetPoint.side).toBe(targetSide)
  }

  const sourceRect: EdgeRect = { x: 100, y: 100, width: 80, height: 80 }
  const inputs = [60, 100, 140].map((y, index) => ({
    id: `same-side-${index}`,
    sourceId: 'source',
    sourceRect,
    targetId: `same-side-target-${index}`,
    targetRect: { x: 300, y, width: 80, height: 80 },
  }))
  const distributed = edgeAnchors(inputs)
  const points = inputs.map((input) => distributed.get(input.id)!.sourcePoint).sort((left, right) => left.y - right.y)
  expect(new Set(points.map((point) => `${point.x}:${point.y}`))).toHaveLength(3)
  expect(points[1].y - points[0].y).toBeGreaterThanOrEqual(14)
  expect(points[2].y - points[1].y).toBeGreaterThanOrEqual(14)
  expect(points[0].y - sourceRect.y).toBeGreaterThanOrEqual(14)
  expect(sourceRect.y + sourceRect.height - points[2].y).toBeGreaterThanOrEqual(14)

  for (const input of inputs) {
    const anchors = distributed.get(input.id)!
    const route = splinePath(anchors, [])
    const first = route.points[0]
    const second = route.points[1]
    const penultimate = route.points.at(-2)!
    const last = route.points.at(-1)!
    expect(first.y).toBe(second.y)
    expect(Math.abs(second.x - first.x)).toBe(12)
    expect(penultimate.y).toBe(last.y)
    expect(Math.abs(last.x - penultimate.x)).toBe(12)
  }
})
