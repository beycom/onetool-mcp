import { expect, test } from 'vitest'

import payloadFixture from './fixture-payload.json'
import {
  buildLayoutInput,
  DEFAULT_LAYOUT_SETTINGS,
  gridPack,
  layoutEngines,
  makeLayoutKey,
  registeredLayoutMethods,
  stableExpansionLayout,
  starHub,
  unionLayout,
  type LayoutMethod,
  type LayoutPosition,
  type Positions,
} from './layout'
import { unionGraph } from './projection'
import type { Aspect, GraphNode, ReportPayload, RolledGraph, View } from './types'

const payload = payloadFixture as unknown as ReportPayload

function fixtureGraph(
  nodeKeys: string[],
  pairs: Array<[number, number]>,
  boundaries: RolledGraph['boundaries'] = [],
  properties: Record<string, string>[] = [],
): RolledGraph {
  return {
    nodes: nodeKeys.map((key, index) => ({
      key,
      kind: key.split(':')[0] as GraphNode['kind'],
      row: { id: key.split(':').slice(1).join(':'), name: key, properties: properties[index] ?? {}, intervals: [] },
      boundary: false,
      members: [],
    })),
    edges: pairs.map(([left, right], index) => ({
      key: `edge-${index}`,
      a: nodeKeys[left],
      b: nodeKeys[right],
      interfaces: [],
      relationships: [`relationship-${index}`],
      interfaceRows: [],
      relationshipRows: [],
      orientations: [],
    })),
    boundaries,
    state: {} as RolledGraph['state'],
  }
}

const flatKeys = Array.from({ length: 6 }, (_, index) => `systems:node-${index}`)
const nestedKeys = ['components:nested-a', 'components:nested-b', 'systems:outside']
const nestedBoundaries: RolledGraph['boundaries'] = [
  { key: 'systems:parent', nodeKey: 'systems:parent', kind: 'systems', row: { id: 'parent', intervals: [] }, parentKey: null, childKeys: ['containers:nested'], stub: false },
  { key: 'containers:nested', nodeKey: 'containers:nested', kind: 'containers', row: { id: 'nested', intervals: [] }, parentKey: 'systems:parent', childKeys: ['components:nested-a', 'components:nested-b'], stub: false },
]
const expansionKeys = Array.from({ length: 11 }, (_, index) => `components:child-${index}`)
const expansionBoundary: RolledGraph['boundaries'] = [{
  key: 'containers:expanded',
  nodeKey: 'containers:expanded',
  kind: 'containers',
  row: { id: 'expanded', intervals: [] },
  parentKey: null,
  childKeys: expansionKeys,
  stub: false,
}]
const packedKeys = [
  ...Array.from({ length: 6 }, (_, index) => `components:packed-${index}`),
  'containers:beside',
  'systems:outside',
]
const packedBoundaries: RolledGraph['boundaries'] = [
  { key: 'systems:small-parent', nodeKey: 'systems:small-parent', kind: 'systems', row: { id: 'small-parent', intervals: [] }, parentKey: null, childKeys: ['containers:packed', 'containers:beside'], stub: false },
  { key: 'containers:packed', nodeKey: 'containers:packed', kind: 'containers', row: { id: 'packed', intervals: [] }, parentKey: 'systems:small-parent', childKeys: packedKeys.slice(0, 6), stub: false },
]
const fixtureGraphs = {
  'star hub': fixtureGraph(flatKeys, [[0, 1], [0, 2], [0, 3], [0, 4], [0, 5]]),
  chain: fixtureGraph(flatKeys, [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]]),
  'dense mesh': fixtureGraph(flatKeys, flatKeys.flatMap((_, left) => flatKeys.slice(left + 1).map((_item, offset) => [left, left + offset + 1] as [number, number]))),
  'nested boundaries': fixtureGraph(nestedKeys, [[0, 2], [1, 2]], nestedBoundaries),
  '11-child expansion': fixtureGraph(expansionKeys, expansionKeys.slice(1).map((_key, index) => [0, index + 1]), expansionBoundary),
  'packed interior beside siblings': fixtureGraph(packedKeys, [[0, 6], [1, 7], [7, 6]], packedBoundaries),
}

function center(position: LayoutPosition) {
  return { x: position.x + position.width / 2, y: position.y + position.height / 2 }
}

test.each(registeredLayoutMethods.flatMap((method) => Object.entries(fixtureGraphs).map(([name, graph]) => [method, name, graph] as const)))(
  '%s engine satisfies shared invariants for %s',
  async (method, name, graph) => {
    const settings = { ...DEFAULT_LAYOUT_SETTINGS, method }
    const sizes = new Map([
      ...graph.nodes.map((node) => [node.key, { width: 120, height: 72 }] as const),
      ...graph.boundaries.map((boundary) => [boundary.key, { width: 120, height: 72 }] as const),
    ])
    const context = { aspectRatio: 1.6, hub: starHub(graph) }
    const first = await layoutEngines[method].layout(graph, sizes, settings, context)
    const second = await layoutEngines[method].layout(graph, sizes, settings, context)

    expect([...second]).toEqual([...first])
    const siblings = new Map<string | undefined, LayoutPosition[]>()
    for (const position of first.values()) siblings.set(position.parentId, [...(siblings.get(position.parentId) ?? []), position])
    for (const positions of siblings.values()) {
      for (let left = 0; left < positions.length; left += 1) {
        for (let right = left + 1; right < positions.length; right += 1) {
          expect(positions[left].x + positions[left].width <= positions[right].x
            || positions[right].x + positions[right].width <= positions[left].x
            || positions[left].y + positions[left].height <= positions[right].y
            || positions[right].y + positions[right].height <= positions[left].y).toBe(true)
        }
      }
    }
    for (const [key, position] of first) {
      if (!position.parentId) continue
      const parent = first.get(position.parentId)!
      expect(position.x).toBeGreaterThanOrEqual(settings.spacing.boundary)
      expect(position.y).toBeGreaterThanOrEqual(settings.spacing.boundary)
      expect(position.x + position.width).toBeLessThanOrEqual(parent.width - settings.spacing.boundary)
      expect(position.y + position.height).toBeLessThanOrEqual(parent.height)
      expect(key).not.toBe(position.parentId)
    }
    const anchorKey = graph.boundaries[0]?.key ?? graph.nodes[0].key
    const freshAnchor = first.get(anchorKey)!
    const previous = new Map(first)
    previous.set(anchorKey, { ...freshAnchor, width: freshAnchor.width / 2, height: freshAnchor.height / 2 })
    const stabilized = stableExpansionLayout(previous, first, anchorKey)
    expect(center(stabilized.get(anchorKey)!)).toEqual(center(previous.get(anchorKey)!))

    if (name === '11-child expansion') {
      const children = expansionKeys.map((key) => first.get(key)!)
      expect(new Set(children.map((position) => position.x)).size).toBeGreaterThan(1)
      expect(new Set(children.map((position) => position.y)).size).toBeGreaterThan(1)
    }
  },
)

test('layered property ranking orders lanes and retains inference for missing properties', async () => {
  const keys = ['systems:frontend', 'systems:inferred', 'systems:service', 'systems:data', 'systems:external']
  const graph = fixtureGraph(keys, [[0, 1], [1, 2], [2, 3], [3, 4]], [ ], [
    { layer: 'frontend' },
    {},
    { layer: 'service' },
    { layer: 'data' },
    { layer: 'external' },
  ])
  const settings = { ...DEFAULT_LAYOUT_SETTINGS, method: 'layered' as LayoutMethod, ranking: 'property:layer' as const }
  const positions = await layoutEngines.layered.layout(graph, new Map(), settings, { aspectRatio: 1.6, hub: null })
  const x = (key: string) => positions.get(key)!.x

  expect(x(keys[0])).toBeLessThan(x(keys[2]))
  expect(x(keys[2])).toBeLessThan(x(keys[3]))
  expect(x(keys[3])).toBeLessThan(x(keys[4]))
  expect(x(keys[1])).toBeGreaterThan(x(keys[0]))
  expect(x(keys[1])).toBeLessThan(x(keys[4]))
})

test('stage, relationship, and lens changes leave the layout key and ELK input unchanged', () => {
  const base = {
    timeline: 0,
    position: 0,
    expand: [],
    aspect: 'call-direction',
    lens: [],
  } satisfies Pick<View, 'timeline' | 'position' | 'expand' | 'aspect' | 'lens'>
  const changed = { ...base, position: 4, aspect: 'data-flow' as Aspect, lens: ['core'] }
  const baseGraph = unionGraph(payload, base.timeline, base.expand)
  const changedGraph = unionGraph(payload, changed.timeline, changed.expand)

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

test('an edgeless set packs into a non-overlapping near-square grid', () => {
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

test('local expansion displaces only overlaps and the cached collapse restores every position', () => {
  const previous: Positions = new Map([
    ['systems:anchor', { x: 0, y: 0, width: 100, height: 100 }],
    ['systems:near', { x: 180, y: 0, width: 100, height: 100 }],
    ['systems:far', { x: 900, y: 0, width: 100, height: 100 }],
  ])
  const fresh: Positions = new Map([
    ['systems:anchor', { x: 0, y: 0, width: 400, height: 240 }],
    ['containers:child', { x: 20, y: 50, width: 120, height: 80, parentId: 'systems:anchor' }],
    ['systems:near', { x: 600, y: 0, width: 100, height: 100 }],
    ['systems:far', { x: 800, y: 0, width: 100, height: 100 }],
  ])
  const expanded = stableExpansionLayout(previous, fresh, 'systems:anchor')

  expect(expanded.get('systems:far')).toEqual(previous.get('systems:far'))
  expect(expanded.get('systems:near')).not.toEqual(previous.get('systems:near'))
  expect(expanded.get('systems:anchor')).toMatchObject({ x: -150, y: -70, width: 400, height: 240 })
  const cache = new Map([['0:', previous], ['0:systems:anchor', expanded]])
  expect(cache.get('0:')).toEqual(previous)
})
