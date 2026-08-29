import { describe, expect, test } from 'vitest'

import payloadFixture from '../../../tests/unit/tools/fixtures/arch/projection/payload.json'
import vectorFixture from '../../../tests/unit/tools/fixtures/arch/projection/vectors.json'
import { diffStates, mapGraph, scopeAt, stateAt, unionGraph } from './projection'
import { KINDS, type ReportPayload } from './types'

const payload = payloadFixture as unknown as ReportPayload
const vectors = vectorFixture as unknown as {
  state_at: Array<{ timeline: string; position: number; expect: unknown }>
  diff: Array<{ timeline: string; a: number; b: number; expect: unknown }>
  scope: Array<{ timeline: string; position: number; systems: string[]; hops: number; expect: unknown }>
  map: Array<{ timeline: string; position?: number; union?: boolean; expand: string[]; expect: unknown }>
}

function timelineIndex(id: string): number {
  const index = payload.timelines.findIndex((timeline) => timeline.id === id)
  if (index < 0) throw new Error(`Unknown vector timeline ${id}`)
  return index
}

describe('client projection vectors', () => {
  test.each(vectors.state_at)('stateAt $timeline position $position', ({ timeline, position, expect: expected }) => {
    const state = stateAt(payload, timelineIndex(timeline), position)
    const live = Object.fromEntries(KINDS.map((kind) => [kind, state.rows[kind].map((row) => row.id)]))
    const clips = Object.fromEntries(KINDS.flatMap((kind) => {
      const items = [...state.clips[kind].values()].map(({ row, by }) => ({ id: row.id, by }))
      return items.length ? [[kind, items]] : []
    }))
    expect({ live, clips }).toEqual(expected)
  })

  test.each(vectors.diff)('diffStates $timeline $a to $b', ({ timeline, a, b, expect: expected }) => {
    expect(diffStates(payload, timelineIndex(timeline), a, b)).toEqual(expected)
  })

  test.each(vectors.scope)('scopeAt $timeline position $position hops $hops', ({ timeline, position, systems, hops, expect: expected }) => {
    const scoped = scopeAt(stateAt(payload, timelineIndex(timeline), position), { systems, hops })
    expect({
      kept: [...scoped.keptRepresentatives].sort(),
      stubs: [...scoped.boundaryStubs.keys()].sort(),
      interfaces: scoped.rows.interfaces.map((row) => row.id),
      relationships: scoped.rows.relationships.map((row) => row.id),
    }).toEqual(expected)
  })

  test.each(vectors.map)('mapGraph $timeline $expand', ({ timeline, position, union, expand, expect: expected }) => {
    const timelinePosition = timelineIndex(timeline)
    const graph = union
      ? unionGraph(payload, timelinePosition, expand)
      : mapGraph(scopeAt(stateAt(payload, timelinePosition, position!), null), expand)
    expect({
      nodes: graph.nodes.map((node) => node.key),
      boundaries: graph.boundaries.map((boundary) => boundary.key),
      edges: graph.edges.map(({ a, b, interfaces, relationships }) => ({ a, b, interfaces, relationships })),
    }).toEqual(expected)
  })
})
