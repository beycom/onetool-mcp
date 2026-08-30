import type { Node } from '@xyflow/react'

import { gridPack as runGridPack } from './layout/grid'
import { buildLayoutInput as makeLayeredInput } from './layout/layered'
import { radialLayout as runRadialLayout } from './layout/radial'
import { defaultLayoutMethod, layoutEngines, registeredLayoutMethods } from './layout/registry'
import {
  boundaryBottomPadding,
  boundaryTopPadding,
  DEFAULT_LAYOUT_SETTINGS,
  NODE_HEIGHT,
  NODE_WIDTH,
  positionBounds,
  RADIAL_CLEARANCE,
  rectClearance,
  starHub,
} from './layout/shared'
import type { LayoutPosition, LayoutSettings, NodeSizes, Positions } from './layout/types'
import type { RolledGraph } from './types'

export type { LayoutEngine, LayoutMethod, LayoutPosition, LayoutSettings, NodeSizes, Positions } from './layout/types'
export { DEFAULT_LAYOUT_SETTINGS, defaultLayoutMethod, layoutEngines, NODE_HEIGHT, NODE_WIDTH, registeredLayoutMethods, starHub }

const cache = new Map<string, Promise<Positions>>()

export function makeLayoutKey(view: { timeline: number; expand: readonly string[] }): string {
  return `${view.timeline}:${[...new Set(view.expand)].sort().join(',')}`
}

export function buildLayoutInput(
  graph: RolledGraph,
  sizes: NodeSizes,
  aspectRatio: number,
  settings: LayoutSettings = DEFAULT_LAYOUT_SETTINGS,
) {
  return makeLayeredInput(graph, sizes, aspectRatio, settings)
}

export function gridPack(
  graph: RolledGraph,
  sizes: NodeSizes,
  settings: LayoutSettings = DEFAULT_LAYOUT_SETTINGS,
): Positions {
  return runGridPack(graph, sizes, settings)
}

export function radialLayout(
  graph: RolledGraph,
  sizes: NodeSizes,
  preferredHub: string | null = null,
  settings: LayoutSettings = DEFAULT_LAYOUT_SETTINGS,
): Positions {
  return runRadialLayout(graph, sizes, settings, preferredHub)
}

export function unionLayout(
  graph: RolledGraph,
  cacheKey: string,
  sizes: NodeSizes = new Map(),
  aspectRatio = 1.6,
  preferredHub: string | null = null,
  fresh = false,
  configured: LayoutSettings | null = null,
): Promise<Positions> {
  const method = configured?.method ?? defaultLayoutMethod(graph, preferredHub)
  const settings = configured ? { ...configured, method } : { ...DEFAULT_LAYOUT_SETTINGS, method }
  const resolvedKey = `${cacheKey}|${JSON.stringify(settings)}`
  const cached = fresh ? undefined : cache.get(resolvedKey)
  if (cached) return cached
  const result = layoutEngines[method].layout(graph, sizes, settings, {
    aspectRatio,
    hub: preferredHub,
  })
  cache.set(resolvedKey, result)
  return result
}

function sameParent(position: LayoutPosition, parentId: string | undefined): boolean {
  return position.parentId === parentId
}

function overlapsWithClearance(left: LayoutPosition, right: LayoutPosition): boolean {
  return rectClearance(left, right) < RADIAL_CLEARANCE
}

function shifted(position: LayoutPosition, dx: number, dy: number): LayoutPosition {
  return { ...position, x: position.x + dx, y: position.y + dy }
}

function minimumShift(position: LayoutPosition, obstacle: LayoutPosition, vector: { x: number; y: number }): LayoutPosition {
  let high = 1
  while (overlapsWithClearance(shifted(position, vector.x * high, vector.y * high), obstacle)) high *= 2
  let low = 0
  for (let step = 0; step < 40; step += 1) {
    const middle = (low + high) / 2
    if (overlapsWithClearance(shifted(position, vector.x * middle, vector.y * middle), obstacle)) low = middle
    else high = middle
  }
  return shifted(position, vector.x * high, vector.y * high)
}

export function stableExpansionLayout(
  previous: Positions,
  fresh: Positions,
  anchorKey: string,
  settings: LayoutSettings = DEFAULT_LAYOUT_SETTINGS,
): Positions {
  const oldAnchor = previous.get(anchorKey)
  const nextAnchor = fresh.get(anchorKey)
  if (!oldAnchor || !nextAnchor) return fresh
  const result: Positions = new Map()
  for (const [key, position] of previous) if (fresh.has(key)) result.set(key, { ...position })

  const descendants = new Set([anchorKey])
  let changed = true
  while (changed) {
    changed = false
    for (const [key, position] of fresh) {
      if (position.parentId && descendants.has(position.parentId) && !descendants.has(key)) {
        descendants.add(key)
        changed = true
      }
    }
  }
  for (const key of descendants) {
    const position = fresh.get(key)
    if (position) result.set(key, { ...position })
  }
  result.set(anchorKey, {
    ...nextAnchor,
    parentId: oldAnchor.parentId,
    x: oldAnchor.x + (oldAnchor.width - nextAnchor.width) / 2,
    y: oldAnchor.y + (oldAnchor.height - nextAnchor.height) / 2,
  })

  const pushApart = (changedKey: string) => {
    const anchor = result.get(changedKey)!
    const anchorCenter = { x: anchor.x + anchor.width / 2, y: anchor.y + anchor.height / 2 }
    const candidates = [...result.entries()]
      .filter(([key, position]) => key !== changedKey && sameParent(position, anchor.parentId))
      .sort(([leftKey, left], [rightKey, right]) => {
        const leftDistance = Math.hypot(left.x + left.width / 2 - anchorCenter.x, left.y + left.height / 2 - anchorCenter.y)
        const rightDistance = Math.hypot(right.x + right.width / 2 - anchorCenter.x, right.y + right.height / 2 - anchorCenter.y)
        return leftDistance - rightDistance || leftKey.localeCompare(rightKey)
      })
    const displaced: LayoutPosition[] = [anchor]
    for (const [key, original] of candidates) {
      let position = original
      let moved = false
      for (;;) {
        const obstacle = displaced.find((item) => overlapsWithClearance(position, item))
        if (!obstacle) break
        const dx = position.x + position.width / 2 - anchorCenter.x
        const dy = position.y + position.height / 2 - anchorCenter.y
        const length = Math.hypot(dx, dy)
        const vector = length ? { x: dx / length, y: dy / length } : { x: key.localeCompare(changedKey) < 0 ? -1 : 1, y: 0 }
        position = minimumShift(position, obstacle, vector)
        moved = true
      }
      if (moved) {
        result.set(key, position)
        displaced.push(position)
      }
    }
  }

  pushApart(anchorKey)
  let parentId = oldAnchor.parentId
  while (parentId) {
    const parent = result.get(parentId)
    if (!parent) break
    const childKeys = [...result.entries()].filter(([, position]) => position.parentId === parentId).map(([key]) => key)
    const childBounds = positionBounds(result, childKeys)
    const shiftX = Math.max(0, settings.spacing.boundary - childBounds.minX)
    const shiftY = Math.max(0, boundaryTopPadding(settings) - childBounds.minY)
    if (shiftX || shiftY) {
      for (const key of childKeys) result.set(key, shifted(result.get(key)!, shiftX, shiftY))
    }
    const grown = {
      ...parent,
      x: parent.x - shiftX,
      y: parent.y - shiftY,
      width: Math.max(parent.width, childBounds.maxX + shiftX + settings.spacing.boundary),
      height: Math.max(parent.height, childBounds.maxY + shiftY + boundaryBottomPadding(settings)),
    }
    result.set(parentId, grown)
    pushApart(parentId)
    parentId = parent.parentId
  }
  return result
}

export function applyPositions(nodes: Node[], positions: Positions): Node[] {
  const nodeIds = new Set(nodes.map((node) => node.id))
  return nodes.map((node) => {
    const layout = positions.get(node.id)
    if (!layout) return node
    const parentId = layout.parentId && nodeIds.has(layout.parentId) ? layout.parentId : undefined
    return {
      ...node,
      position: { x: layout.x, y: layout.y },
      width: layout.width,
      height: layout.height,
      ...(parentId ? { parentId } : {}),
    }
  })
}
