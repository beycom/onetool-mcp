import { expect, test } from 'vitest'

import payloadFixture from './fixture-payload.json'
import { buildLayoutInput, gridPack, makeLayoutKey } from './layout'
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
