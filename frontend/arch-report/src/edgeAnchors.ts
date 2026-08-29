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
  side: EdgeSide
  bearing: number
}

const CORNER_CLEARANCE = 14
const MIN_SEPARATION = 14
const PREFERRED_SEPARATION = 18

function center(rect: EdgeRect): { x: number; y: number } {
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
}

function sideAndBearing(rect: EdgeRect, counterpart: EdgeRect): Pick<Endpoint, 'side' | 'bearing'> {
  const own = center(rect)
  const other = center(counterpart)
  const dx = other.x - own.x
  const dy = other.y - own.y
  if (Math.abs(dx) >= Math.abs(dy)) {
    return { side: dx >= 0 ? 'right' : 'left', bearing: Math.atan2(dy, Math.abs(dx)) }
  }
  return { side: dy >= 0 ? 'bottom' : 'top', bearing: Math.atan2(dx, Math.abs(dy)) }
}

function pointOnSide(rect: EdgeRect, side: EdgeSide, along: number): EdgePoint {
  if (side === 'left' || side === 'right') {
    return { x: side === 'left' ? rect.x : rect.x + rect.width, y: rect.y + along, side }
  }
  return { x: rect.x + along, y: side === 'top' ? rect.y : rect.y + rect.height, side }
}

function distribute(endpoints: Endpoint[]): Map<string, EdgePoint> {
  const result = new Map<string, EdgePoint>()
  const groups = new Map<string, Endpoint[]>()
  for (const endpoint of endpoints) {
    const key = `${endpoint.nodeId}\u0000${endpoint.side}`
    groups.set(key, [...(groups.get(key) ?? []), endpoint])
  }

  for (const group of groups.values()) {
    group.sort((left, right) => left.bearing - right.bearing
      || left.edgeId.localeCompare(right.edgeId)
      || left.end.localeCompare(right.end))
    const { rect, side } = group[0]
    const span = side === 'left' || side === 'right' ? rect.height : rect.width
    const usable = span - CORNER_CLEARANCE * 2
    const required = (group.length - 1) * MIN_SEPARATION
    if (usable < 0 || required > usable) {
      throw new RangeError(
        `Cannot distribute ${group.length} edge anchors on the ${side} side of ${group[0].nodeId}: `
        + `${span}px side cannot provide ${MIN_SEPARATION}px separation and ${CORNER_CLEARANCE}px corner clearance`,
      )
    }
    const separation = group.length <= 1 ? 0 : Math.min(PREFERRED_SEPARATION, usable / (group.length - 1))
    const first = (span - separation * (group.length - 1)) / 2
    group.forEach((endpoint, index) => {
      result.set(`${endpoint.edgeId}\u0000${endpoint.end}`, pointOnSide(rect, side, first + index * separation))
    })
  }
  return result
}

export function edgeAnchors(inputs: readonly EdgeAnchorInput[]): Map<string, EdgeAnchorPair> {
  const ids = new Set<string>()
  const endpoints: Endpoint[] = []
  for (const input of inputs) {
    if (ids.has(input.id)) throw new RangeError(`Duplicate edge anchor id: ${input.id}`)
    ids.add(input.id)
    endpoints.push({ edgeId: input.id, end: 'source', nodeId: input.sourceId, rect: input.sourceRect, ...sideAndBearing(input.sourceRect, input.targetRect) })
    endpoints.push({ edgeId: input.id, end: 'target', nodeId: input.targetId, rect: input.targetRect, ...sideAndBearing(input.targetRect, input.sourceRect) })
  }
  const points = distribute(endpoints)
  return new Map(inputs.map((input) => [input.id, {
    sourcePoint: points.get(`${input.id}\u0000source`)!,
    targetPoint: points.get(`${input.id}\u0000target`)!,
  }]))
}
