import { describe, expect, it } from 'vitest'

import { parseFragment, serializeFragment } from '../src/explorer/fragment'

describe('solution URL fragment', () => {
  it('round-trips all independent solution axes and multi-value selectors', () => {
    const hash = serializeFragment({
      graph: 'graph-a',
      order: 2,
      depth: 3,
      level: 'component',
      colorBy: 'tag',
      browse: 'system_group',
      systemSet: {
        systems: ['A', 'B'],
        system_groups: ['platform'],
        changes: ['2027'],
        change_groups: ['wave-one'],
        tags: ['core'],
      },
    })

    expect(parseFragment(hash)).toEqual({
      graph: 'graph-a',
      order: 2,
      depth: 3,
      level: 'component',
      colorBy: 'tag',
      browse: 'system_group',
      systemSet: {
        systems: ['A', 'B'],
        system_groups: ['platform'],
        changes: ['2027'],
        change_groups: ['wave-one'],
        tags: ['core'],
      },
    })
  })

  it('ignores malformed selector arrays and invalid control values', () => {
    expect(parseFragment('#systems=A&depth=-1&level=flow&colorBy=kind')).toEqual({})
  })
})
