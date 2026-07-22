import { describe, expect, it } from 'vitest'

import type { PresentationConfig, ViewGraph } from '../src/data/types'
import { solutionColors } from '../src/solution/colors'

const presentation: PresentationConfig = {
  title: 'Colors',
  default_theme: 'clean',
  palettes: {
    change_status: Object.fromEntries(
      ['system', 'application', 'component', 'interface'].map((kind) => [
        kind,
        {
          no_change: { color: '#d5e8d4', border: '#82b366 solid' },
          changed: { color: '#fff2cc', border: '#d6b656 solid' },
          added: { color: '#dae8fc', border: '#6c8ebf double' },
          removed: { color: '#f8cecc', border: '#b85450 double' },
        },
      ]),
    ) as PresentationConfig['palettes']['change_status'],
    integration_type: { api: { color: '#123456' } },
    tag: { core: { color: '#abcdef' } },
  },
  resolved_themes: {
    clean: {
      elements: {},
      statuses: {
        out_of_scope: {},
        future: {},
        new: {},
        change: {},
        no_change: {},
        decommission: {},
      },
    },
  },
}

const graph = {
  id: 'solution',
  selection: {
    id: 'selection',
    state_id: 'base',
    selection: {
      focus: [],
      system_set: {
        systems: ['A'],
        system_groups: [],
        changes: [],
        change_groups: [],
        tags: [],
      },
      interface_depth: 1,
      display_statuses: [],
      include_future: false,
      level: 'system',
      color_by: 'change_status',
      theme: 'clean',
    },
  },
  resolved_state: { id: 'base' },
  nodes: [
    {
      id: 'A',
      entity_kind: 'system',
      name: 'A',
      children: [],
      status: 'Changed',
      context_status: 'change',
      tombstone: false,
      future: false,
      tags: ['core'],
      groups: [],
      related_changes: [],
      properties: {},
    },
    {
      id: 'B',
      entity_kind: 'system',
      name: 'B',
      children: [],
      status: 'Removed',
      context_status: 'decommission',
      tombstone: true,
      future: false,
      tags: [],
      groups: [],
      related_changes: [],
      properties: {},
    },
  ],
  containers: [],
  edges: [
    {
      id: 'a-b',
      entity_kind: 'interface',
      name: 'A to B',
      source_id: 'A',
      target_id: 'B',
      direction: 'provider_to_consumer',
      status: 'Removed',
      context_status: 'decommission',
      tombstone: true,
      future: false,
      tags: ['core'],
      integration_type: 'api',
      interface_ids: ['a-b'],
      related_changes: [],
      properties: {},
    },
  ],
  changes: [],
  focus: [],
  focus_overrides: [],
  diagram_ids: [],
  hints: {},
} satisfies ViewGraph

describe('solution coloring', () => {
  it('uses fills for nodes and borders for change-status edges', () => {
    const colors = solutionColors(graph, 'change_status', presentation)

    expect(colors.nodeColors.get('A')).toBe('#fff2cc')
    expect(colors.nodeBorders.get('A')).toBe('#d6b656')
    expect(colors.edgeColors.get('a-b')).toBe('#b85450')
  })

  it('uses configured integration and tag colors with neutral fallbacks', () => {
    expect(solutionColors(graph, 'integration_type', presentation).edgeColors.get('a-b')).toBe(
      '#123456',
    )
    const tags = solutionColors(graph, 'tag', presentation)
    expect(tags.nodeColors.get('A')).toBe('#abcdef')
    expect(tags.nodeColors.get('B')).toBe('#f8fafc')
    expect(tags.edgeColors.get('a-b')).toBe('#abcdef')
  })
})
