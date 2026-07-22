import { describe, expect, it } from 'vitest'

import type { ViewGraph, ViewGraphNode } from '../src/data/types'
import {
  type AdapterDiagramGeometry,
  toSolutionLayout,
} from '../src/solution/renderer/LikeC4SolutionRenderer'

function node(
  id: string,
  entity_kind: ViewGraphNode['entity_kind'],
  parent?: string,
): ViewGraphNode {
  return {
    id,
    entity_kind,
    name: id,
    parent,
    children: [],
    status: 'No Change',
    context_status: 'no_change',
    tombstone: false,
    future: false,
    tags: [],
    groups: [],
    related_changes: [],
    properties: {},
  }
}

const graph: ViewGraph = {
  id: 'canonical-projection',
  selection: {
    id: 'selection-canonical',
    state_id: 'roadmap@1',
    roadmap_id: 'roadmap',
    order: 1,
      selection: {
        focus: [],
        display_statuses: [],
        include_future: false,
      system_set: { systems: ['A'], system_groups: [], changes: [], change_groups: [], tags: [] },
      interface_depth: 1,
      level: 'component',
      color_by: 'change_status',
      theme: 'clean',
    },
  },
  resolved_state: { id: 'roadmap@1' },
  nodes: [node('A', 'system'), node('app-a', 'application', 'A'), node('cmp-a', 'component', 'app-a')],
  containers: ['A', 'app-a'],
  edges: [
    {
      id: 'aggregate-canonical',
      entity_kind: 'interface',
      name: '2 interfaces',
      source_id: 'cmp-a',
      target_id: 'A',
      direction: 'provider_to_consumer',
      status: 'No Change',
      context_status: 'no_change',
      tombstone: false,
      future: false,
      tags: [],
      interface_ids: ['interface-1', 'interface-2'],
      related_changes: [],
      properties: {},
    },
  ],
  changes: [],
  focus: [],
  focus_overrides: [],
  diagram_ids: [],
  hints: {},
}

const diagram = {
  bounds: { x: 0, y: 0, width: 600, height: 400 },
  nodes: [
    { id: 'A', parent: null, x: 10, y: 10, width: 500, height: 300 },
    { id: 'app-a', parent: 'A', x: 30, y: 40, width: 400, height: 220 },
    { id: 'cmp-a', parent: 'app-a', x: 60, y: 80, width: 240, height: 100 },
  ],
  edges: [
    {
      id: 'aggregate-canonical',
      source: 'cmp-a',
      target: 'A',
      points: [[300, 130], [450, 130]],
    },
  ],
} satisfies AdapterDiagramGeometry

describe('renderer-neutral adapter geometry', () => {
  it('preserves SYS/APP/CMP containment, canonical routes, and aggregate members', () => {
    const first = toSolutionLayout(
      graph,
      'layout-request',
      diagram,
    )
    const second = toSolutionLayout(
      graph,
      'layout-request',
      diagram,
    )

    expect(first).toEqual(second)
    expect(first).toMatchObject({
      requestId: 'layout-request',
      graphId: 'canonical-projection',
      bounds: { width: 600, height: 400 },
    })
    expect(first.nodes.map(({ id, parent }) => [id, parent])).toEqual([
      ['A', undefined],
      ['app-a', 'A'],
      ['cmp-a', 'app-a'],
    ])
    expect(first.edges).toEqual([
      {
        id: 'aggregate-canonical',
        source: 'cmp-a',
        target: 'A',
        route: [{ x: 300, y: 130 }, { x: 450, y: 130 }],
        interfaceIds: ['interface-1', 'interface-2'],
      },
    ])
    expect(first.nodes.some((item) => item.id === 'outside-boundary')).toBe(false)
  })
})
