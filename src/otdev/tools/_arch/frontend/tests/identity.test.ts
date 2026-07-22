import { describe, expect, it } from 'vitest'

import type { ViewSelection } from '../src/data/types'
import { solutionSelectionIdentity } from '../src/solution/identity'

const selection: ViewSelection = {
  roadmap: 'preferred',
  order: 1,
  focus: [],
  browse_by: 'system',
  system_set: {
    systems: ['A'],
    system_groups: [],
    changes: [],
    change_groups: [],
    tags: [],
  },
  interface_depth: 1,
  visibility: 'all',
  display_statuses: [],
  include_future: false,
  level: 'component',
  color_by: 'tag',
  theme: 'clean',
}

describe('solution selection identity', () => {
  it('matches the canonical Python identity contract', async () => {
    await expect(solutionSelectionIdentity(selection)).resolves.toBe(
      'selection-2c19b1d9be72a5ef',
    )
  })

  it('normalizes set-valued fields before hashing', async () => {
    const reordered: ViewSelection = {
      ...selection,
      focus: ['D', 'A', 'D'],
      display_statuses: ['new', 'change', 'new'],
      system_set: {
        ...selection.system_set,
        systems: ['A', 'A'],
        tags: ['zeta', 'alpha', 'zeta'],
      },
    }
    const normalized: ViewSelection = {
      ...reordered,
      focus: ['A', 'D'],
      display_statuses: ['change', 'new'],
      system_set: {
        ...reordered.system_set,
        systems: ['A'],
        tags: ['alpha', 'zeta'],
      },
    }

    await expect(solutionSelectionIdentity(reordered)).resolves.toBe(
      await solutionSelectionIdentity(normalized),
    )
  })
})
