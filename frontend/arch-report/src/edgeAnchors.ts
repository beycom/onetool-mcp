export type EdgeRect = { x: number; y: number; width: number; height: number }
export type EdgeSide = 'top' | 'right' | 'bottom' | 'left'
export type EdgePoint = { x: number; y: number; side: EdgeSide }
export type EdgeAnchorPair = { sourcePoint: EdgePoint; targetPoint: EdgePoint }
export type EdgeAnchorInput = {
  id: string
  sourceId: string
  sourceRect: EdgeRect
  targetId: string
  targetRect: EdgeRect
}

type Endpoint = {
  edgeId: string
  end: 'source' | 'target'
  nodeId: string
  rect: EdgeRect
  counterpart: EdgeRect
  side: EdgeSide
  bearing: number
}

const CORNER_CLEARANCE = 14
const MIN_SEPARATION = 14
const PREFERRED_SEPARATION = 18
const SIDE_ORDER: readonly EdgeSide[] = ['top', 'right', 'bottom', 'left']

function center(rect: EdgeRect): { x: number; y: number } {
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
}

function bearingOn(side: EdgeSide, rect: EdgeRect, counterpart: EdgeRect): number {
  const own = center(rect)
  const other = center(counterpart)
  const dx = other.x - own.x
  const dy = other.y - own.y
  return side === 'left' || side === 'right' ? Math.atan2(dy, Math.abs(dx)) : Math.atan2(dx, Math.abs(dy))
}

function sideAndBearing(rect: EdgeRect, counterpart: EdgeRect): Pick<Endpoint, 'side' | 'bearing'> {
  const own = center(rect)
  const other = center(counterpart)
  const dx = other.x - own.x
  const dy = other.y - own.y
  const side: EdgeSide = Math.abs(dx) >= Math.abs(dy)
    ? dx >= 0 ? 'right' : 'left'
    : dy >= 0 ? 'bottom' : 'top'
  return { side, bearing: bearingOn(side, rect, counterpart) }
}

function sideSpan(rect: EdgeRect, side: EdgeSide): number {
  return side === 'left' || side === 'right' ? rect.height : rect.width
}

function sideCapacity(rect: EdgeRect, side: EdgeSide): number {
  const usable = sideSpan(rect, side) - CORNER_CLEARANCE * 2
  return usable < 0 ? 0 : Math.floor(usable / MIN_SEPARATION) + 1
}

function byBearing(left: Endpoint, right: Endpoint): number {
  return left.bearing - right.bearing
    || left.edgeId.localeCompare(right.edgeId)
    || left.end.localeCompare(right.end)
}

// An over-full side sheds its outermost endpoints around the nearest
// corner: the batch's low-bearing end spills to the side adjacent to
// that corner, the high end to the opposite one. Bearings are
// recomputed in the destination side's metric, so a spilled endpoint
// stays in perimeter order. Only a node whose total demand exceeds its
// whole perimeter is an error.
function rebalance(sides: Map<EdgeSide, Endpoint[]>, rect: EdgeRect, nodeId: string): void {
  const demand = [...sides.values()].reduce((total, group) => total + group.length, 0)
  const capacity = SIDE_ORDER.reduce((total, side) => total + sideCapacity(rect, side), 0)
  if (demand > capacity) {
    throw new RangeError(
      `Cannot distribute ${demand} edge anchors around ${nodeId}: the ${rect.width}x${rect.height}px perimeter `
      + `holds at most ${capacity} with ${MIN_SEPARATION}px separation and ${CORNER_CLEARANCE}px corner clearance`,
    )
  }
  const visited = new Map<Endpoint, Set<EdgeSide>>()
  const visitedFor = (endpoint: Endpoint) => {
    const existing = visited.get(endpoint) ?? new Set([endpoint.side])
    visited.set(endpoint, existing)
    return existing
  }
  for (let guard = demand * SIDE_ORDER.length; guard >= 0; guard -= 1) {
    const over = SIDE_ORDER.find((side) => (sides.get(side)?.length ?? 0) > sideCapacity(rect, side))
    if (!over) return
    const batch = sides.get(over)!
    const [lowSide, highSide]: [EdgeSide, EdgeSide] = over === 'left' || over === 'right'
      ? ['top', 'bottom']
      : ['left', 'right']
    const candidates: Array<[Endpoint, EdgeSide]> = [[batch[0], lowSide], [batch.at(-1)!, highSide]]
    candidates.sort(([left], [right]) => Math.abs(right.bearing) - Math.abs(left.bearing))
    const move = candidates.find(([endpoint, destination]) => !visitedFor(endpoint).has(destination))
    if (!move) break
    const [endpoint, destination] = move
    batch.splice(batch.indexOf(endpoint), 1)
    visitedFor(endpoint).add(destination)
    endpoint.side = destination
    endpoint.bearing = bearingOn(destination, endpoint.rect, endpoint.counterpart)
    const target = sides.get(destination) ?? []
    target.push(endpoint)
    target.sort(byBearing)
    sides.set(destination, target)
  }
  throw new RangeError(`Cannot rebalance ${demand} edge anchors around ${nodeId} without violating spacing`)
}

function pointOnSide(rect: EdgeRect, side: EdgeSide, along: number): EdgePoint {
  if (side === 'left' || side === 'right') {
    return { x: side === 'left' ? rect.x : rect.x + rect.width, y: rect.y + along, side }
  }
  return { x: rect.x + along, y: side === 'top' ? rect.y : rect.y + rect.height, side }
}

function distribute(endpoints: Endpoint[]): Map<string, EdgePoint> {
  const result = new Map<string, EdgePoint>()
  const byNode = new Map<string, Endpoint[]>()
  for (const endpoint of endpoints) {
    byNode.set(endpoint.nodeId, [...(byNode.get(endpoint.nodeId) ?? []), endpoint])
  }

  for (const [nodeId, nodeEndpoints] of byNode) {
    const rect = nodeEndpoints[0].rect
    const sides = new Map<EdgeSide, Endpoint[]>()
    for (const endpoint of nodeEndpoints) {
      sides.set(endpoint.side, [...(sides.get(endpoint.side) ?? []), endpoint])
    }
    for (const group of sides.values()) group.sort(byBearing)
    rebalance(sides, rect, nodeId)
    for (const [side, group] of sides) {
      if (!group.length) continue
      const span = sideSpan(rect, side)
      const usable = span - CORNER_CLEARANCE * 2
      const separation = group.length <= 1 ? 0 : Math.min(PREFERRED_SEPARATION, usable / (group.length - 1))
      const first = (span - separation * (group.length - 1)) / 2
      group.forEach((endpoint, index) => {
        result.set(`${endpoint.edgeId}\u0000${endpoint.end}`, pointOnSide(rect, side, first + index * separation))
      })
    }
  }
  return result
}

export function edgeAnchors(inputs: readonly EdgeAnchorInput[]): Map<string, EdgeAnchorPair> {
  const ids = new Set<string>()
  const endpoints: Endpoint[] = []
  for (const input of inputs) {
    if (ids.has(input.id)) throw new RangeError(`Duplicate edge anchor id: ${input.id}`)
    ids.add(input.id)
    endpoints.push({ edgeId: input.id, end: 'source', nodeId: input.sourceId, rect: input.sourceRect, counterpart: input.targetRect, ...sideAndBearing(input.sourceRect, input.targetRect) })
    endpoints.push({ edgeId: input.id, end: 'target', nodeId: input.targetId, rect: input.targetRect, counterpart: input.sourceRect, ...sideAndBearing(input.targetRect, input.sourceRect) })
  }
  const points = distribute(endpoints)
  return new Map(inputs.map((input) => [input.id, {
    sourcePoint: points.get(`${input.id}\u0000source`)!,
    targetPoint: points.get(`${input.id}\u0000target`)!,
  }]))
}
