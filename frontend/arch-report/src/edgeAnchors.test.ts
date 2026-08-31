import { expect, test } from 'vitest'

import { edgeAnchors, type EdgeRect } from './edgeAnchors'
import { endpointsNearViewport, intersects, placeEdgeLabel, splinePath } from './splinePath'

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

test('an over-capacity side spills its outermost anchors to adjacent sides; only perimeter overflow throws', () => {
  const hub: EdgeRect = { x: 0, y: 0, width: 250, height: 162 }
  const inputs = Array.from({ length: 11 }, (_, index) => ({
    id: `spill-${String(index).padStart(2, '0')}`,
    sourceId: 'hub',
    sourceRect: hub,
    targetId: `spill-target-${index}`,
    targetRect: { x: 700, y: index * 90 - 380, width: 80, height: 60 },
  }))
  const anchors = edgeAnchors(inputs)

  const sourcePoints = inputs.map((input) => anchors.get(input.id)!.sourcePoint)
  const bySide = new Map<string, typeof sourcePoints>()
  for (const point of sourcePoints) bySide.set(point.side, [...(bySide.get(point.side) ?? []), point])
  expect(bySide.get('right')!).toHaveLength(10)
  expect(sourcePoints).toHaveLength(11)
  expect((bySide.get('top')?.length ?? 0) + (bySide.get('bottom')?.length ?? 0)).toBe(1)
  const rightYs = bySide.get('right')!.map((point) => point.y).sort((left, right) => left - right)
  for (let index = 1; index < rightYs.length; index += 1) {
    expect(rightYs[index] - rightYs[index - 1]).toBeGreaterThanOrEqual(14)
  }
  expect(rightYs[0] - hub.y).toBeGreaterThanOrEqual(14)
  expect(hub.y + hub.height - rightYs.at(-1)!).toBeGreaterThanOrEqual(14)

  const tiny: EdgeRect = { x: 0, y: 0, width: 20, height: 20 }
  expect(() => edgeAnchors([{
    id: 'impossible',
    sourceId: 'tiny',
    sourceRect: tiny,
    targetId: 'far',
    targetRect: { x: 700, y: 0, width: 80, height: 60 },
  }])).toThrow(RangeError)
})

test('selected-hub labels nudge away from cards and pills, then hide overflow instead of stacking', () => {
  const hub = { x: 420, y: 80, width: 160, height: 40 }
  const curve = [{ x: 0, y: 100 }, { x: 1000, y: 100 }]
  const occupied: EdgeRect[] = []
  let hidden = 0

  for (let index = 0; index < 6; index += 1) {
    const placement = placeEdgeLabel(curve, [hub], occupied, 140, index % 2 === 0)
    if (!placement) {
      hidden += 1
      continue
    }
    expect(intersects(placement.rect, hub)).toBe(false)
    expect(occupied.every((pill) => !intersects(placement.rect, pill))).toBe(true)
    occupied.push(placement.rect)
  }

  expect(occupied.length).toBeGreaterThan(0)
  expect(hidden).toBeGreaterThan(0)
})

test('orphan labels require at least one endpoint in or near the viewport', () => {
  const viewport = { x: 0, y: 0, width: 500, height: 300 }
  const farSource = { x: 900, y: 80, width: 100, height: 60 }
  const farTarget = { x: 1200, y: 120, width: 100, height: 60 }
  const nearSource = { ...farSource, x: 560 }

  expect(endpointsNearViewport(farSource, farTarget, viewport, 80)).toBe(false)
  expect(endpointsNearViewport(nearSource, farTarget, viewport, 80)).toBe(true)
})
