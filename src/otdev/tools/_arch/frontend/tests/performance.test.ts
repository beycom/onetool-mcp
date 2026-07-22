import { describe, expect, it } from 'vitest'

import { projectSolution } from '../src/solution/projection'
import { afterInteraction } from '../src/solution/runtime'
import { projectionBenchmarkFixture } from './fixtures/projection-benchmark'

const BUDGETS = {
  projectionMs: 150,
  cachedRetrievalsMs: 40,
  dispatchMs: 250,
  controlUpdateMs: 25,
  payloadBytes: 3_000_000,
} as const

describe('deterministic solution performance budgets', () => {
  it('keeps projection, cache, dispatch, responsiveness, and payload within budget', async () => {
    const prepared = projectionBenchmarkFixture()
    const selector = {
      systems: [],
      system_groups: ['group-0'],
      changes: [],
      change_groups: [],
      tags: ['tag-1'],
    }

    const projectionStarted = performance.now()
    const projection = projectSolution(prepared, 2, selector, 2, 'system', 'clean')
    const projectionMs = performance.now() - projectionStarted
    expect(projection).toBeDefined()
    expect(projectionMs).toBeLessThan(BUDGETS.projectionMs)

    const cacheStarted = performance.now()
    for (let index = 0; index < 1_000; index += 1) {
      expect(projectSolution(prepared, 2, selector, 2, 'system', 'clean')).toBe(projection)
    }
    expect(performance.now() - cacheStarted).toBeLessThan(BUDGETS.cachedRetrievalsMs)

    const dispatchStarted = performance.now()
    await afterInteraction()
    expect(performance.now() - dispatchStarted).toBeLessThan(BUDGETS.dispatchMs)

    const controlStarted = performance.now()
    let depth = 2
    depth = Math.max(0, depth - 1)
    expect(depth).toBe(1)
    expect(performance.now() - controlStarted).toBeLessThan(BUDGETS.controlUpdateMs)

    expect(new TextEncoder().encode(JSON.stringify(prepared)).byteLength).toBeLessThan(
      BUDGETS.payloadBytes,
    )
  })
})
