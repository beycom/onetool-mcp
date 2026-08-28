export type EdgeRect = { x: number; y: number; width: number; height: number }
export type EdgeSide = 'top' | 'right' | 'bottom' | 'left'
export type EdgePoint = { x: number; y: number; side: EdgeSide }
export type EdgeAnchorPair = { sourcePoint: EdgePoint; targetPoint: EdgePoint }

function pointOnSide(rect: EdgeRect, side: EdgeSide, offset: number): EdgePoint {
  if (side === 'left' || side === 'right') {
    return {
      x: side === 'left' ? rect.x : rect.x + rect.width,
      y: rect.y + rect.height / 2 + offset,
      side,
    }
  }
  return {
    x: rect.x + rect.width / 2 + offset,
    y: side === 'top' ? rect.y : rect.y + rect.height,
    side,
  }
}

export function edgeAnchors(
  sourceRect: EdgeRect,
  targetRect: EdgeRect,
  laneIndex: number,
  laneCount: number,
): EdgeAnchorPair {
  const sourceCenter = {
    x: sourceRect.x + sourceRect.width / 2,
    y: sourceRect.y + sourceRect.height / 2,
  }
  const targetCenter = {
    x: targetRect.x + targetRect.width / 2,
    y: targetRect.y + targetRect.height / 2,
  }
  const horizontal = Math.abs(targetCenter.x - sourceCenter.x) >= Math.abs(targetCenter.y - sourceCenter.y)
  const sourceSide: EdgeSide = horizontal
    ? targetCenter.x >= sourceCenter.x ? 'right' : 'left'
    : targetCenter.y >= sourceCenter.y ? 'bottom' : 'top'
  const targetSide: EdgeSide = sourceSide === 'right' ? 'left'
    : sourceSide === 'left' ? 'right'
      : sourceSide === 'bottom' ? 'top' : 'bottom'
  const count = Math.max(1, laneCount)
  const index = Math.max(0, Math.min(count - 1, laneIndex))
  const sideSpan = horizontal
    ? Math.min(sourceRect.height, targetRect.height)
    : Math.min(sourceRect.width, targetRect.width)
  const spacing = Math.min(18, Math.max(8, (sideSpan - 24) / count))
  const offset = (index - (count - 1) / 2) * spacing
  return {
    sourcePoint: pointOnSide(sourceRect, sourceSide, offset),
    targetPoint: pointOnSide(targetRect, targetSide, offset),
  }
}
