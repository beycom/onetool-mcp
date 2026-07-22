import { describe, expect, it } from 'vitest'

import type { ViewGraph } from '../src/data/types'
import {
  afterInteraction,
  BoundedCache,
  LatestRequestGate,
  projectionSizeState,
} from '../src/solution/runtime'

function sizedGraph(nodes: number, edges: number): ViewGraph {
  return {
    id: 'sized',
    selection: {
      id: 'selection-sized',
      state_id: 'sized',
      selection: {
        display_statuses: [],
        system_set: { systems: [], system_groups: [], changes: [], change_groups: [], tags: [] },
        interface_depth: 0,
        level: 'system',
        color_by: 'change_status',
        theme: 'clean',
      },
    },
    resolved_state: { id: 'sized' },
    nodes: Array.from({ length: nodes }, (_, index) => ({
      id: `n-${index}`,
      entity_kind: 'system' as const,
      name: `Node ${index}`,
      children: [],
      status: 'No Change' as const,
      context_status: 'no_change' as const,
      tombstone: false,
      future: false,
      tags: [],
      groups: [],
      related_changes: [],
      properties: {},
    })),
    containers: [],
    edges: Array.from({ length: edges }, (_, index) => ({
      id: `e-${index}`,
      entity_kind: 'interface' as const,
      name: `Edge ${index}`,
      source_id: 'n-0',
      target_id: 'n-1',
      direction: 'provider_to_consumer' as const,
      status: 'No Change' as const,
      context_status: 'no_change' as const,
      tombstone: false,
      future: false,
      tags: [],
      interface_ids: [`e-${index}`],
      related_changes: [],
      properties: {},
    })),
    changes: [],
    focus: [],
    focus_overrides: [],
    diagram_ids: [],
    hints: {},
  }
}

describe('solution runtime hardening', () => {
  it('bounds and deterministically evicts least-recently-used layouts', () => {
    const cache = new BoundedCache<string, number>(2)
    cache.set('a', 1)
    cache.set('b', 2)
    expect(cache.get('a')).toBe(1)
    cache.set('c', 3)
    expect(cache.has('a')).toBe(true)
    expect(cache.has('b')).toBe(false)
    expect(cache.size).toBe(2)
    expect(cache).toMatchObject({ hits: 1, misses: 0 })
  })

  it('never accepts an older completion after a newer request', async () => {
    const gate = new LatestRequestGate()
    const accepted: string[] = []
    const slow = gate.start()
    const slowCompletion = new Promise<void>((resolve) => {
      setTimeout(() => {
        if (gate.isCurrent(slow)) accepted.push('slow')
        resolve()
      }, 10)
    })
    const fast = gate.start()
    if (gate.isCurrent(fast)) accepted.push('fast')
    await slowCompletion
    expect(accepted).toEqual(['fast'])
  })

  it('classifies warning and hard limits before layout dispatch', () => {
    const thresholds = { warningNodes: 2, warningEdges: 2, hardNodes: 4, hardEdges: 4 }
    expect(projectionSizeState(sizedGraph(2, 2), thresholds)).toBe('ok')
    expect(projectionSizeState(sizedGraph(3, 2), thresholds)).toBe('warning')
    expect(projectionSizeState(sizedGraph(5, 2), thresholds)).toBe('hard')
  })

  it('yields layout dispatch until after the current interaction task', async () => {
    const order = ['interaction']
    const deferred = afterInteraction().then(() => order.push('layout'))
    order.push('control-update')
    await deferred
    expect(order).toEqual(['interaction', 'control-update', 'layout'])
  })
})
