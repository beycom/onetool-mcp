import type { EdgeAnchorPair, EdgePoint, EdgeRect, EdgeSide } from './edgeAnchors'

export type SplinePoint = { x: number; y: number }
export type SplinePath = { labelPoint: SplinePoint; labelRect: EdgeRect; path: string; points: SplinePoint[] }

type Point = SplinePoint

const CLEARANCE = 8
const OUTSET = 12

function distance(left: Point, right: Point): number {
  return Math.hypot(right.x - left.x, right.y - left.y)
}

function inflate(rect: EdgeRect): EdgeRect {
  return {
    x: rect.x - CLEARANCE,
    y: rect.y - CLEARANCE,
    width: rect.width + CLEARANCE * 2,
    height: rect.height + CLEARANCE * 2,
  }
}

function contains(rect: EdgeRect, point: Point): boolean {
  return point.x >= rect.x && point.x <= rect.x + rect.width
    && point.y >= rect.y && point.y <= rect.y + rect.height
}

function interval(start: number, end: number, low: number, high: number): [number, number] | null {
  const delta = end - start
  if (Math.abs(delta) < 0.0001) return start > low && start < high ? [0, 1] : null
  const first = (low - start) / delta
  const second = (high - start) / delta
  return [Math.min(first, second), Math.max(first, second)]
}

function crossesInterior(left: Point, right: Point, rect: EdgeRect): boolean {
  const epsilon = 0.25
  const x = interval(left.x, right.x, rect.x + epsilon, rect.x + rect.width - epsilon)
  const y = interval(left.y, right.y, rect.y + epsilon, rect.y + rect.height - epsilon)
  if (!x || !y) return false
  const start = Math.max(0, x[0], y[0])
  const end = Math.min(1, x[1], y[1])
  return end - start > 0.0001
}

function visible(left: Point, right: Point, obstacles: EdgeRect[]): boolean {
  return obstacles.every((rect) => !crossesInterior(left, right, rect))
}

function outset(point: EdgePoint): Point {
  const delta: Record<EdgeSide, Point> = {
    bottom: { x: 0, y: OUTSET },
    left: { x: -OUTSET, y: 0 },
    right: { x: OUTSET, y: 0 },
    top: { x: 0, y: -OUTSET },
  }
  return { x: point.x + delta[point.side].x, y: point.y + delta[point.side].y }
}

function corners(rect: EdgeRect): Point[] {
  return [
    { x: rect.x, y: rect.y },
    { x: rect.x + rect.width, y: rect.y },
    { x: rect.x + rect.width, y: rect.y + rect.height },
    { x: rect.x, y: rect.y + rect.height },
  ]
}

function shortestPath(start: Point, end: Point, obstacles: EdgeRect[]): Point[] {
  const unique = new Map<string, Point>()
  for (const point of [start, end, ...obstacles.flatMap(corners)]) {
    unique.set(`${point.x.toFixed(3)}:${point.y.toFixed(3)}`, point)
  }
  const points = [...unique.values()]
  const startIndex = points.indexOf(start)
  const endIndex = points.indexOf(end)
  const costs = points.map(() => Number.POSITIVE_INFINITY)
  const previous = points.map(() => -1)
  const pending = new Set(points.map((_, index) => index))
  costs[startIndex] = 0

  while (pending.size) {
    let current = -1
    for (const index of pending) if (current < 0 || costs[index] < costs[current]) current = index
    if (current < 0 || !Number.isFinite(costs[current]) || current === endIndex) break
    pending.delete(current)
    for (const next of pending) {
      if (!visible(points[current], points[next], obstacles)) continue
      const cost = costs[current] + distance(points[current], points[next])
      if (cost >= costs[next]) continue
      costs[next] = cost
      previous[next] = current
    }
  }

  if (!Number.isFinite(costs[endIndex])) return [start, end]
  const route: Point[] = []
  for (let cursor = endIndex; cursor >= 0; cursor = previous[cursor]) {
    route.unshift(points[cursor])
    if (cursor === startIndex) break
  }
  return route
}

function simplify(points: Point[], obstacles: EdgeRect[]): Point[] {
  if (points.length < 3) return points
  const result = [points[0]]
  let cursor = 0
  while (cursor < points.length - 1) {
    let next = points.length - 1
    while (next > cursor + 1 && !visible(points[cursor], points[next], obstacles)) next -= 1
    result.push(points[next])
    cursor = next
  }
  return result
}

function pointAt(points: Point[], ratio: number): Point {
  const lengths = points.slice(1).map((point, index) => distance(points[index], point))
  const target = lengths.reduce((total, value) => total + value, 0) * ratio
  let elapsed = 0
  for (let index = 0; index < lengths.length; index += 1) {
    if (elapsed + lengths[index] >= target) {
      const ratio = (target - elapsed) / lengths[index]
      return {
        x: points[index].x + (points[index + 1].x - points[index].x) * ratio,
        y: points[index].y + (points[index + 1].y - points[index].y) * ratio,
      }
    }
    elapsed += lengths[index]
  }
  return points.at(-1)!
}

function intersects(left: EdgeRect, right: EdgeRect): boolean {
  return left.x < right.x + right.width && left.x + left.width > right.x
    && left.y < right.y + right.height && left.y + left.height > right.y
}

function labelPlacement(
  points: Point[],
  cardRects: EdgeRect[],
  occupied: EdgeRect[],
  width: number,
  preferNegative: boolean,
): { point: Point; rect: EdgeRect } {
  const direction = preferNegative ? -1 : 1
  const ratios = [0, 0.05, -0.05, 0.1, -0.1, 0.15, -0.15, 0.2, -0.2]
    .map((offset) => 0.5 + offset * direction)
  const candidates = ratios.map((ratio) => {
    const point = pointAt(points, ratio)
    return { point, rect: { x: point.x - width / 2, y: point.y - 12, width, height: 24 } }
  })
  return candidates.find(({ rect }) => (
    cardRects.every((card) => !intersects(rect, card))
    && occupied.every((label) => !intersects(rect, label))
  )) ?? candidates[0]
}

function cubicCommands(points: Point[]): string[] {
  const commands: string[] = []
  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index]
    const next = points[index + 1]
    const previous = points[Math.max(0, index - 1)]
    const after = points[Math.min(points.length - 1, index + 2)]
    const first = index === 0
      ? { x: current.x + (next.x - current.x) * 0.45, y: current.y + (next.y - current.y) * 0.45 }
      : { x: current.x + (next.x - previous.x) * 0.04, y: current.y + (next.y - previous.y) * 0.04 }
    const second = index === points.length - 2
      ? { x: next.x - (next.x - current.x) * 0.45, y: next.y - (next.y - current.y) * 0.45 }
      : { x: next.x - (after.x - current.x) * 0.04, y: next.y - (after.y - current.y) * 0.04 }
    commands.push(`C ${first.x} ${first.y}, ${second.x} ${second.y}, ${next.x} ${next.y}`)
  }
  return commands
}

export function splinePath(
  anchors: EdgeAnchorPair,
  rects: EdgeRect[],
  occupiedLabels: EdgeRect[] = [],
  labelWidth = 180,
  preferNegativeNudge = false,
): SplinePath {
  const obstacles = rects.filter((rect) => (
    !contains(rect, anchors.sourcePoint) && !contains(rect, anchors.targetPoint)
  )).map(inflate)
  const sourceOutset = outset(anchors.sourcePoint)
  const targetOutset = outset(anchors.targetPoint)
  const middle = simplify(shortestPath(sourceOutset, targetOutset, obstacles), obstacles)
  const points = [anchors.sourcePoint, ...middle, anchors.targetPoint]
    .filter((point, index, all) => index === 0 || distance(point, all[index - 1]) > 0.01)
  const path = [
    `M ${anchors.sourcePoint.x} ${anchors.sourcePoint.y}`,
    `L ${sourceOutset.x} ${sourceOutset.y}`,
    ...cubicCommands(middle),
    `L ${anchors.targetPoint.x} ${anchors.targetPoint.y}`,
  ].join(' ')
  const label = labelPlacement(points, rects, occupiedLabels, labelWidth, preferNegativeNudge)
  return { labelPoint: label.point, labelRect: label.rect, path, points }
}
