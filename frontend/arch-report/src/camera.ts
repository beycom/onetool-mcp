export type Rect = { x: number; y: number; width: number; height: number }
export type Viewport = { x: number; y: number; zoom: number }

const VIEW_PADDING = 0.12
const MIN_ZOOM = 0.2
const MAX_ZOOM = 2

function centeredViewport(bounds: Rect, visible: Rect, zoom: number): Viewport {
  return {
    x: visible.x + (visible.width - bounds.width * zoom) / 2 - bounds.x * zoom,
    y: visible.y + (visible.height - bounds.height * zoom) / 2 - bounds.y * zoom,
    zoom,
  }
}

export function fitViewport(bounds: Rect, visible: Rect): Viewport {
  const usableWidth = visible.width * (1 - VIEW_PADDING * 2)
  const usableHeight = visible.height * (1 - VIEW_PADDING * 2)
  const zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, usableWidth / bounds.width, usableHeight / bounds.height))
  return centeredViewport(bounds, visible, zoom)
}

export function initialViewport(bounds: Rect, visible: Rect): Viewport {
  const fitted = fitViewport(bounds, visible)
  return fitted.zoom <= 1 ? fitted : centeredViewport(bounds, visible, 1)
}

export function shiftViewport(viewport: Viewport, visible: Rect, focus: Rect): Viewport {
  const left = viewport.x + focus.x * viewport.zoom
  const top = viewport.y + focus.y * viewport.zoom
  const width = focus.width * viewport.zoom
  const height = focus.height * viewport.zoom
  const right = left + width
  const bottom = top + height
  let x = viewport.x
  let y = viewport.y

  if (width > visible.width) x += visible.x + visible.width / 2 - (left + width / 2)
  else if (left < visible.x) x += visible.x - left
  else if (right > visible.x + visible.width) x -= right - visible.x - visible.width

  if (height > visible.height) y += visible.y + visible.height / 2 - (top + height / 2)
  else if (top < visible.y) y += visible.y - top
  else if (bottom > visible.y + visible.height) y -= bottom - visible.y - visible.height

  return x === viewport.x && y === viewport.y ? viewport : { x, y, zoom: viewport.zoom }
}
