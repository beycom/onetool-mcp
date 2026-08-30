import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js'

import type { RolledGraph } from '../types'
import {
  boundaryBottomPadding,
  boundaryTopPadding,
  graphParts,
  NODE_HEIGHT,
  NODE_WIDTH,
  sizeFor,
} from './shared'
import type { LayoutContext, LayoutEngine, LayoutPosition, LayoutSettings, NodeSizes, Positions } from './types'

const elk = new ELK()
const GRID_MIN_CHILDREN = 5

type GridPlan = { width: number; height: number; children: Map<string, LayoutPosition> }

// Boundaries with many children get a pre-computed grid interior whose final
// size is handed to ELK as a fixed leaf, so parent growth and sibling spacing
// are correct by construction (a post-ELK resize cannot overflow anything).
function planGridInteriors(graph: RolledGraph, sizes: NodeSizes, settings: LayoutSettings): Map<string, GridPlan> {
  const { boundaryByKey, visibleNodeKeys } = graphParts(graph)
  const childIds = (key: string) => (boundaryByKey.get(key)?.childKeys ?? [])
    .filter((child) => boundaryByKey.has(child) || visibleNodeKeys.has(child))
  const depth = (key: string): number => {
    const parent = boundaryByKey.get(key)?.parentKey
    return parent ? depth(parent) + 1 : 0
  }
  const plans = new Map<string, GridPlan>()
  const ordered = [...boundaryByKey.keys()].sort((left, right) => depth(right) - depth(left) || left.localeCompare(right))
  for (const key of ordered) {
    const ids = childIds(key)
    if (ids.length < GRID_MIN_CHILDREN) continue
    if (ids.some((id) => boundaryByKey.has(id) && !plans.has(id))) continue
    const items = ids.map((id) => {
      const plan = plans.get(id)
      return { id, ...(plan ? { width: plan.width, height: plan.height } : sizeFor(id, sizes)) }
    })
    const columns = Math.ceil(Math.sqrt(items.length * 1.6))
    const rows = Math.ceil(items.length / columns)
    const columnWidths = Array.from({ length: columns }, () => 0)
    const rowHeights = Array.from({ length: rows }, () => 0)
    items.forEach((item, index) => {
      columnWidths[index % columns] = Math.max(columnWidths[index % columns], item.width)
      rowHeights[Math.floor(index / columns)] = Math.max(rowHeights[Math.floor(index / columns)], item.height)
    })
    const columnX = columnWidths.map((_, index) => settings.spacing.boundary
      + columnWidths.slice(0, index).reduce((sum, width) => sum + width, 0)
      + index * settings.spacing.node)
    const rowY = rowHeights.map((_, index) => boundaryTopPadding(settings)
      + rowHeights.slice(0, index).reduce((sum, height) => sum + height, 0)
      + index * settings.spacing.node)
    const children = new Map<string, LayoutPosition>()
    items.forEach((item, index) => {
      const column = index % columns
      const row = Math.floor(index / columns)
      children.set(item.id, {
        x: columnX[column] + (columnWidths[column] - item.width) / 2,
        y: rowY[row] + (rowHeights[row] - item.height) / 2,
        width: item.width,
        height: item.height,
        parentId: key,
      })
    })
    plans.set(key, {
      width: columnWidths.reduce((sum, width) => sum + width, 0)
        + (columns - 1) * settings.spacing.node
        + settings.spacing.boundary * 2,
      height: rowHeights.reduce((sum, height) => sum + height, 0)
        + (rows - 1) * settings.spacing.node
        + boundaryTopPadding(settings)
        + boundaryBottomPadding(settings),
      children,
    })
  }
  return plans
}

export function buildLayoutInput(
  graph: RolledGraph,
  sizes: NodeSizes,
  aspectRatio: number,
  settings: LayoutSettings,
): ElkNode {
  const { boundaryByKey, parentByChild, rootIds, visibleNodeKeys } = graphParts(graph)
  const plans = planGridInteriors(graph, sizes, settings)
  const makeNode = (id: string): ElkNode => {
    const boundary = boundaryByKey.get(id)
    if (!boundary) return { id, ...sizeFor(id, sizes) }
    const plan = plans.get(id)
    if (plan) return { id, width: plan.width, height: plan.height }
    return {
      id,
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': settings.direction.toUpperCase(),
        'elk.padding': `[top=${boundaryTopPadding(settings)},left=${settings.spacing.boundary},bottom=${boundaryBottomPadding(settings)},right=${settings.spacing.boundary}]`,
        'elk.spacing.nodeNode': String(settings.spacing.node),
        'elk.layered.spacing.nodeNodeBetweenLayers': String(settings.spacing.layer),
      },
      children: boundary.childKeys.filter((child) => boundaryByKey.has(child) || visibleNodeKeys.has(child)).map(makeNode),
    }
  }
  // An edge endpoint hidden inside a planned grid is not an ELK node any
  // more; reattach it to its topmost planned ancestor.
  const representative = (key: string): string => {
    const chain: string[] = []
    let current: string | undefined = key
    while (current) {
      chain.unshift(current)
      current = parentByChild.get(current)
    }
    return chain.find((item) => plans.has(item)) ?? key
  }
  const edges: Array<{ id: string; sources: string[]; targets: string[] }> = []
  for (const edge of graph.edges) {
    const a = representative(edge.a)
    const b = representative(edge.b)
    if (a !== b) edges.push({ id: edge.key, sources: [a], targets: [b] })
  }
  return {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.aspectRatio': String(Math.max(1.2, Math.min(2, aspectRatio))),
      'elk.direction': settings.direction.toUpperCase(),
      'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
      'elk.layered.crossingMinimization.semiInteractive': 'true',
      'elk.randomSeed': '1',
      'elk.spacing.nodeNode': String(settings.spacing.node),
      'elk.layered.spacing.nodeNodeBetweenLayers': String(settings.spacing.layer),
    },
    children: rootIds.map(makeNode),
    edges,
  }
}

function propertyValue(graph: RolledGraph, key: string, property: string): string | null {
  const node = graph.nodes.find((item) => item.key === key)
  const value = node?.row.properties?.[property]
  return typeof value === 'string' ? value : null
}

function applyRanking(graph: RolledGraph, positions: Positions, settings: LayoutSettings): Positions {
  if (settings.ranking === 'auto') return positions
  const property = settings.ranking.slice('property:'.length)
  const groups = new Map<string | undefined, string[]>()
  for (const [key, position] of positions) {
    groups.set(position.parentId, [...(groups.get(position.parentId) ?? []), key])
  }
  const result = new Map(positions)
  for (const ids of groups.values()) {
    if (!ids.some((id) => propertyValue(graph, id, property) !== null)) continue
    const axis = settings.direction === 'right' ? 'x' : 'y'
    const size = settings.direction === 'right' ? 'width' : 'height'
    const explicit = [...new Set(ids.flatMap((id) => {
      const value = propertyValue(graph, id, property)
      return value === null ? [] : [value]
    }))]
    explicit.sort((left, right) => {
      if (property !== 'layer') return left.localeCompare(right)
      const order = ['frontend', 'service', 'data', 'external']
      const leftIndex = order.indexOf(left)
      const rightIndex = order.indexOf(right)
      return (leftIndex < 0 ? order.length : leftIndex) - (rightIndex < 0 ? order.length : rightIndex) || left.localeCompare(right)
    })
    const original = ids.map((id) => result.get(id)![axis])
    const minimum = Math.min(...original)
    const span = Math.max(1, Math.max(...original) - minimum)
    ids.sort((left, right) => {
      const leftValue = propertyValue(graph, left, property)
      const rightValue = propertyValue(graph, right, property)
      const leftRank = leftValue === null ? (result.get(left)![axis] - minimum) / span * Math.max(1, explicit.length - 1) : explicit.indexOf(leftValue)
      const rightRank = rightValue === null ? (result.get(right)![axis] - minimum) / span * Math.max(1, explicit.length - 1) : explicit.indexOf(rightValue)
      return leftRank - rightRank || result.get(left)![axis] - result.get(right)![axis] || left.localeCompare(right)
    })
    let cursor = minimum
    for (const id of ids) {
      const position = result.get(id)!
      result.set(id, { ...position, [axis]: cursor })
      cursor += position[size] + settings.spacing.layer
    }
  }
  return result
}

async function layeredLayout(
  graph: RolledGraph,
  sizes: NodeSizes,
  settings: LayoutSettings,
  context: LayoutContext,
): Promise<Positions> {
  const layout = await elk.layout(buildLayoutInput(graph, sizes, context.aspectRatio, settings))
  const positions: Positions = new Map()
  const visit = (nodes: typeof layout.children, parentId?: string) => {
    for (const node of nodes ?? []) {
      positions.set(node.id, {
        x: node.x ?? 0,
        y: node.y ?? 0,
        width: node.width ?? NODE_WIDTH,
        height: node.height ?? NODE_HEIGHT,
        ...(parentId ? { parentId } : {}),
      })
      visit(node.children, node.id)
    }
  }
  visit(layout.children)
  const ranked = applyRanking(graph, positions, settings)
  // Fill in the planned grid interiors, outermost first so a nested planned
  // boundary exists before its own children are placed.
  const plans = planGridInteriors(graph, sizes, settings)
  const pending = [...plans.keys()]
  while (pending.length) {
    const index = pending.findIndex((key) => ranked.has(key))
    if (index < 0) break
    const [key] = pending.splice(index, 1)
    for (const [childKey, position] of plans.get(key)!.children) ranked.set(childKey, position)
  }
  return ranked
}

export const layeredEngine: LayoutEngine = { layout: layeredLayout }
