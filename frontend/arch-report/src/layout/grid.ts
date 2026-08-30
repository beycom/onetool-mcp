import type { RolledGraph } from '../types'
import {
  boundaryBottomPadding,
  boundaryTopPadding,
  graphParts,
  NODE_HEIGHT,
  NODE_WIDTH,
  sizeFor,
} from './shared'
import type { LayoutEngine, LayoutSettings, NodeSizes, Positions } from './types'

export function gridPack(graph: RolledGraph, sizes: NodeSizes, settings: LayoutSettings): Positions {
  const { boundaryByKey, rootIds, visibleNodeKeys } = graphParts(graph)
  const positions: Positions = new Map()

  const pack = (ids: string[], parentId?: string): { width: number; height: number } => {
    const items = ids.map((id) => {
      const boundary = boundaryByKey.get(id)
      if (!boundary) return { id, ...sizeFor(id, sizes) }
      const children = boundary.childKeys.filter((child) => boundaryByKey.has(child) || visibleNodeKeys.has(child))
      const content = pack(children, id)
      return {
        id,
        width: Math.max(NODE_WIDTH, content.width + settings.spacing.boundary * 2),
        height: Math.max(NODE_HEIGHT, content.height + boundaryTopPadding(settings) + boundaryBottomPadding(settings)),
      }
    })
    if (!items.length) return { width: 0, height: 0 }

    const columns = Math.ceil(Math.sqrt(items.length))
    const rows = Math.ceil(items.length / columns)
    const columnWidths = Array.from({ length: columns }, () => 0)
    const rowHeights = Array.from({ length: rows }, () => 0)
    items.forEach((item, index) => {
      const column = index % columns
      const row = Math.floor(index / columns)
      columnWidths[column] = Math.max(columnWidths[column], item.width)
      rowHeights[row] = Math.max(rowHeights[row], item.height)
    })
    const columnX = columnWidths.map((_, column) => columnWidths.slice(0, column).reduce((sum, value) => sum + value, 0) + column * settings.spacing.node)
    const rowY = rowHeights.map((_, row) => rowHeights.slice(0, row).reduce((sum, value) => sum + value, 0) + row * settings.spacing.node)
    items.forEach((item, index) => {
      const column = index % columns
      const row = Math.floor(index / columns)
      positions.set(item.id, {
        x: columnX[column] + (columnWidths[column] - item.width) / 2 + (parentId ? settings.spacing.boundary : 0),
        y: rowY[row] + (rowHeights[row] - item.height) / 2 + (parentId ? boundaryTopPadding(settings) : 0),
        width: item.width,
        height: item.height,
        ...(parentId ? { parentId } : {}),
      })
    })
    return {
      width: columnWidths.reduce((sum, value) => sum + value, 0) + (columns - 1) * settings.spacing.node,
      height: rowHeights.reduce((sum, value) => sum + value, 0) + (rows - 1) * settings.spacing.node,
    }
  }

  pack(rootIds)
  return positions
}

export const gridEngine: LayoutEngine = {
  async layout(graph, sizes, settings) {
    return gridPack(graph, sizes, settings)
  },
}
