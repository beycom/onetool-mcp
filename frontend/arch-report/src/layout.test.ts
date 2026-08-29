import { expect, test } from 'vitest'

import payloadFixture from './fixture-payload.json'
import { buildLayoutInput, gridPack, makeLayoutKey, starHub, unionLayout } from './layout'
import { unionGraph } from './projection'
import type { Aspect, GraphNode, ReportPayload, RolledGraph, View } from './types'

const payload = payloadFixture as unknown as ReportPayload

test('stage, relationship, and lens changes leave the layout key and ELK input unchanged', () => {
  const base = {
    timeline: 0,
    position: 0,
    level: 'systems',
    drill: null,
    aspect: 'call-direction',
    lens: [],
  } satisfies Pick<View, 'timeline' | 'position' | 'level' | 'drill' | 'aspect' | 'lens'>
  const changed = { ...base, position: 4, aspect: 'data-flow' as Aspect, lens: ['core'] }
  const baseGraph = unionGraph(payload, base.timeline, base.level, base.drill)
  const changedGraph = unionGraph(payload, changed.timeline, changed.level, changed.drill)

  expect(makeLayoutKey(base)).toBe(makeLayoutKey(changed))
  expect(buildLayoutInput(baseGraph, new Map(), 1.6)).toEqual(buildLayoutInput(changedGraph, new Map(), 1.6))
})

test('star graphs use a centered radial ring while non-stars retain the layered ELK input', async () => {
  const nodes = Array.from({ length: 6 }, (_, index): GraphNode => ({
    key: `systems:node-${index}`,
    kind: 'systems',
    row: { id: `node-${index}`, name: `Node ${index}`, intervals: [] },
    boundary: false,
    members: [],
  }))
  const graph = (pairs: Array<[number, number]>): RolledGraph => ({
    nodes,
    edges: pairs.map(([left, right]) => ({
      key: `systems:node-${left}|systems:node-${right}`,
      a: `systems:node-${left}`,
      b: `systems:node-${right}`,
      interfaces: [],
      relationships: [`relationship-${left}-${right}`],
      interfaceRows: [],
      relationshipRows: [],
      orientations: [],
    })),
    boundaries: [],
    state: {} as RolledGraph['state'],
  })
  const sizes = new Map(nodes.map((node) => [node.key, { width: 100, height: 60 }]))
  const star = graph([[0, 1], [0, 2], [0, 3], [0, 4], [0, 5]])
  const positions = await unionLayout(star, 'test:radial-star', sizes)
  const hub = positions.get('systems:node-0')!
  const bounds = [...positions.values()].reduce((result, position) => ({
    minX: Math.min(result.minX, position.x),
    minY: Math.min(result.minY, position.y),
    maxX: Math.max(result.maxX, position.x + position.width),
    maxY: Math.max(result.maxY, position.y + position.height),
  }), { minX: Number.POSITIVE_INFINITY, minY: Number.POSITIVE_INFINITY, maxX: Number.NEGATIVE_INFINITY, maxY: Number.NEGATIVE_INFINITY })
  const hubCenter = { x: hub.x + hub.width / 2, y: hub.y + hub.height / 2 }
  const radii = nodes.slice(1).map((node) => {
    const position = positions.get(node.key)!
    return Math.hypot(position.x + position.width / 2 - hubCenter.x, position.y + position.height / 2 - hubCenter.y)
  })
  const meanRadius = radii.reduce((sum, radius) => sum + radius, 0) / radii.length

  expect(starHub(star)).toBe('systems:node-0')
  expect(hubCenter.x).toBeCloseTo((bounds.minX + bounds.maxX) / 2)
  expect(hubCenter.y).toBeCloseTo((bounds.minY + bounds.maxY) / 2)
  for (const radius of radii) expect(radius).toBeGreaterThanOrEqual(meanRadius * 0.9)
  for (const radius of radii) expect(radius).toBeLessThanOrEqual(meanRadius * 1.1)

  const nonStar = graph([[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0]])
  expect(starHub(nonStar)).toBeNull()
  expect(buildLayoutInput(nonStar, sizes, 1.6).layoutOptions).toEqual({
    'elk.algorithm': 'layered',
    'elk.aspectRatio': '1.6',
    'elk.direction': 'RIGHT',
    'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
    'elk.layered.crossingMinimization.semiInteractive': 'true',
    'elk.randomSeed': '1',
    'elk.spacing.nodeNode': '40',
    'elk.layered.spacing.nodeNodeBetweenLayers': '72',
  })
})

test('an edgeless drill set packs into a non-overlapping near-square grid', () => {
  const graph = {
    nodes: Array.from({ length: 5 }, (_, index): GraphNode => ({
      key: `components:node-${index}`,
      kind: 'components',
      row: { id: `node-${index}`, intervals: [] },
      boundary: false,
      members: [],
    })),
    edges: [],
    boundaries: [],
    state: {} as RolledGraph['state'],
  }
  const positions = gridPack(graph, new Map(graph.nodes.map((node) => [node.key, { width: 100, height: 60 }])))
  const cards = [...positions.values()]

  expect(new Set(cards.map((card) => card.x))).toHaveLength(3)
  for (let leftIndex = 0; leftIndex < cards.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < cards.length; rightIndex += 1) {
      const left = cards[leftIndex]
      const right = cards[rightIndex]
      const overlaps = left.x < right.x + right.width && left.x + left.width > right.x
        && left.y < right.y + right.height && left.y + left.height > right.y
      expect(overlaps).toBe(false)
    }
  }
})
