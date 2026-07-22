import { describe, expect, it } from 'vitest'

import type {
  PreparedSolutionSnapshots,
  SystemSetSelector,
  ViewGraph,
  ViewGraphEdge,
  ViewGraphNode,
} from '../src/data/types'
import {
  projectSolution,
  projectionCacheStats,
} from '../src/solution/projection'

const selection = {
  systems: [],
  system_groups: [],
  changes: [],
  change_groups: [],
  tags: [],
} satisfies SystemSetSelector

function node(
  id: string,
  options: Partial<ViewGraphNode> = {},
): ViewGraphNode {
  return {
    id,
    entity_kind: 'system',
    name: id,
    children: [],
    status: 'No Change',
    context_status: 'no_change',
    tombstone: false,
    future: false,
    tags: [],
    groups: [],
    related_changes: [],
    properties: {},
    ...options,
  }
}

function edge(
  id: string,
  source_id: string,
  target_id: string,
  entity_kind: ViewGraphEdge['entity_kind'] = 'interface',
): ViewGraphEdge {
  return {
    id,
    entity_kind,
    name: id,
    source_id,
    target_id,
    direction: entity_kind === 'interface' ? 'provider_to_consumer' : 'forward',
    status: 'No Change',
    context_status: 'no_change',
    tombstone: false,
    future: false,
    tags: [],
    interface_ids: entity_kind === 'interface' ? [id] : [],
    related_changes: [],
    properties: {},
  }
}

function graph(): ViewGraph {
  return {
    id: 'snapshot',
    selection: {
      id: 'selection-snapshot',
      state_id: 'snapshot',
      roadmap_id: 'delivery',
      order: 1,
      selection: {
        display_statuses: [],
        system_set: selection,
        interface_depth: 0,
        level: 'system',
        color_by: 'change_status',
        theme: 'clean',
      },
    },
    resolved_state: { id: 'snapshot' },
    nodes: [
      node('A', { groups: ['pair'], tags: ['core'] }),
      node('B', { groups: ['pair'] }),
      node('C'),
      node('X'),
      node('app-a', { entity_kind: 'application', parent: 'A' }),
    ],
    containers: [],
    edges: [edge('a-b', 'A', 'B'), edge('b-c', 'B', 'C'), edge('a-x', 'A', 'X', 'relationship')],
    changes: [],
    focus: [],
    focus_overrides: [],
    diagram_ids: [],
    hints: {},
  }
}

function prepared(): PreparedSolutionSnapshots {
  return {
    roadmap_id: 'delivery',
    snapshots: { '1': graph() },
    indexes: {
      '1': {
        systems: ['A', 'B', 'C', 'X'],
        system_groups: { pair: ['A', 'B'] },
        changes: { delivery: ['A', 'C'] },
        change_groups: { wave: ['A', 'C'] },
        change_impacts: {},
        change_group_impacts: {},
        tags: { core: ['A'] },
      },
    },
    system_presence: { A: [1], B: [1], C: [1], X: [1] },
    unavailable_orders: [],
  }
}

describe('local solution projection', () => {
  it('expands recursively by interface hops and reports the boundary', () => {
    const projections = [0, 1, 2].map((depth) =>
      projectSolution(
        prepared(),
        1,
        { ...selection, systems: ['A'] },
        depth,
        'system',
      ),
    )

    expect(projections.map((item) => item?.includedSystems)).toEqual([
      ['A'],
      ['A', 'B'],
      ['A', 'B', 'C'],
    ])
    expect(
      projections.map((item) =>
        item?.boundaryInterfaces.map((boundary) => boundary.interface.id),
      ),
    ).toEqual([
      ['a-b'],
      ['b-c'],
      [],
    ])
    expect(projections[2]?.includedSystems).not.toContain('X')
    expect(projections[2]?.systemDistances).toEqual({ A: 0, B: 1, C: 2 })
  })

  it('aggregates equivalent visible interfaces and retains actor boundaries and collapses', () => {
    const source = prepared()
    const snapshot = source.snapshots['1']!
    snapshot.nodes.push(
      node('app-a2', { entity_kind: 'application', parent: 'A' }),
      node('actor', { entity_kind: 'user' }),
    )
    snapshot.edges.push(
      edge('a-b-2', 'A', 'B'),
      edge('a-internal', 'app-a', 'app-a2'),
      edge('actor-a', 'actor', 'A'),
    )

    const projection = projectSolution(
      source,
      1,
      { ...selection, systems: ['A'] },
      1,
      'system',
    )!

    const aggregate = projection.graph.edges.find((item) => item.id.startsWith('aggregate-'))
    expect(aggregate?.interface_ids).toEqual(['a-b', 'a-b-2'])
    expect(projection.collapsedInterfaces.map((item) => item.interface.id)).toEqual([
      'a-internal',
    ])
    expect(projection.boundaryInterfaces).toContainEqual(
      expect.objectContaining({
        inside_system: 'A',
        outside_endpoint: 'actor',
        interface: expect.objectContaining({ id: 'actor-a' }),
      }),
    )
  })

  it.each([
    [{ ...selection, systems: ['A', 'C'] }, ['A', 'C']],
    [{ ...selection, system_groups: ['pair'] }, ['A', 'B']],
    [{ ...selection, changes: ['delivery'] }, ['A', 'C']],
    [{ ...selection, change_groups: ['wave'] }, ['A', 'C']],
    [{ ...selection, tags: ['core'] }, ['A']],
  ] satisfies [SystemSetSelector, string[]][])('resolves every selector form', (selector, expected) => {
    expect(projectSolution(prepared(), 1, selector, 0, 'system')?.selectedSystems).toEqual(expected)
  })

  it('keeps projection identities unique and includes level in the layout cache key', () => {
    const source = prepared()
    const first = projectSolution(source, 1, { ...selection, systems: ['A'] }, 0, 'system')!
    const second = projectSolution(source, 1, { ...selection, systems: ['A'] }, 0, 'application')!
    const third = projectSolution(source, 1, { ...selection, systems: ['B'] }, 0, 'system')!

    expect(first.cacheKey).not.toEqual(second.cacheKey)
    expect(first.graph.id).not.toEqual(second.graph.id)
    expect(first.graph.id).not.toEqual(third.graph.id)
    expect(second.graph.nodes.map((item) => item.id)).toContain('app-a')
  })

  it('normalizes selector ordering, caches hits, and invalidates topology options', () => {
    const source = prepared()
    const first = projectSolution(
      source,
      1,
      { ...selection, systems: ['B', 'A'] },
      1,
      'system',
      'clean',
    )!
    const equivalent = projectSolution(
      source,
      1,
      { ...selection, systems: ['A', 'B', 'A'] },
      1,
      'system',
      'clean',
    )!
    const themed = projectSolution(
      source,
      1,
      { ...selection, systems: ['A', 'B'] },
      1,
      'system',
      'topology-theme',
    )!

    expect(equivalent).toBe(first)
    expect(projectionCacheStats(source)).toMatchObject({ size: 2, hits: 1, misses: 2 })
    expect(themed.cacheKey).not.toEqual(first.cacheKey)
    expect(first.cacheKey).toContain('solution-projection-2')
    expect(first.cacheKey).toContain('likec4-adapter-1')
    expect(first.cacheKey).toContain('solution-layout-1')
  })

  it('rejects invalid interface depth before projection', () => {
    expect(() =>
      projectSolution(
        prepared(),
        1,
        { ...selection, systems: ['A'] },
        -1,
        'system',
      ),
    ).toThrow('interfaceDepth must be a non-negative integer')
  })

  it('keeps future scope valid and reports snapshot absence', () => {
    const source = prepared()
    const indexes = source.indexes['1']!
    indexes.systems.push('D')
    indexes.changes.future = ['D']
    source.system_presence.D = [2]

    const projection = projectSolution(
      source,
      1,
      { ...selection, changes: ['future'] },
      0,
      'system',
    )!

    expect(projection.selectedSystems).toEqual(['D'])
    expect(projection.graph.nodes).toEqual([])
    expect(projection.absentSystems).toEqual([
      {
        system_id: 'D',
        state: 'not_yet_present',
        message: 'not present at this snapshot',
      },
    ])
  })
})
