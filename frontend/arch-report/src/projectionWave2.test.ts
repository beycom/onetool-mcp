import { describe, expect, test } from 'vitest'

import projectionFixture from '../../../tests/unit/tools/fixtures/arch/projection/payload.json'
import acmeFixture from './fixture-payload.json'
import { drillAt, legendEntries, rollUp, scopeAt, stateAt, withBoundaries } from './projection'
import type { ReportPayload } from './types'

const projectionPayload = projectionFixture as unknown as ReportPayload
const acmePayload = acmeFixture as unknown as ReportPayload

describe('wave-2 canvas projections', () => {
  test('subsystems preserves structural and edge invariants', () => {
    const state = stateAt(projectionPayload, 0, 2)
    const graph = rollUp(scopeAt(state, null), 'subsystems')
    const systemIds = new Set(state.rows.systems.map((row) => row.id))
    const subsystemIds = new Set(state.rows.subsystems.map((row) => row.id))

    for (const node of graph.nodes.filter((item) => item.kind !== 'users')) {
      expect(node.kind === 'systems' || node.kind === 'subsystems'
        || (node.kind === 'containers' && systemIds.has(node.row.parent!))).toBe(true)
    }
    const hidden = [
      ...state.rows.containers.filter((row) => subsystemIds.has(row.parent!)).map((row) => `containers:${row.id}`),
      ...state.rows.components.map((row) => `components:${row.id}`),
      ...state.rows.code.map((row) => `code:${row.id}`),
    ]
    for (const key of hidden) {
      const memberships = graph.nodes.flatMap((node) => node.members).filter((member) => `${member.kind}:${member.row.id}` === key)
      expect(memberships, key).toHaveLength(1)
    }
    for (const edge of graph.edges) {
      expect(edge.a < edge.b).toBe(true)
      expect(edge.a).not.toBe(edge.b)
    }
  })

  test('subsystem roll-up groups containers and leaves ungrouped containers visible', () => {
    const graph = rollUp(scopeAt(stateAt(projectionPayload, 0, 2), null), 'subsystems')
    const grouped = graph.nodes.find((node) => node.key === 'subsystems:ssA')

    expect(grouped?.members.map((member) => `${member.kind}:${member.row.id}`)).toContain('containers:subA')
    expect(graph.nodes.map((node) => node.key)).toContain('containers:subG')
  })

  test('container level nests subsystem boundaries inside system boundaries', () => {
    const graph = withBoundaries(
      rollUp(scopeAt(stateAt(projectionPayload, 0, 2), null), 'containers'),
      'containers',
    )
    const system = graph.boundaries.find((boundary) => boundary.key === 'boundary:systems:sysA')
    const subsystem = graph.boundaries.find((boundary) => boundary.key === 'boundary:subsystems:ssA')

    expect(subsystem?.parentKey).toBe(system?.key)
    expect(subsystem?.childKeys).toEqual(expect.arrayContaining(['containers:subA', 'containers:subR']))
  })

  test('drilling a system shows its direct children and external system stubs', () => {
    const graph = drillAt(stateAt(acmePayload, 0, 5), 'systems:commerce-platform')
    expect(graph.nodes.map((node) => node.key)).toEqual([
      'subsystems:back-office-insight',
      'subsystems:catalog-search',
      'subsystems:customer-cart-pricing',
      'subsystems:platform-foundation',
      'subsystems:storefront-edge',
      'subsystems:transaction-core',
      'systems:analytics-provider',
      'systems:customer-engagement',
      'systems:enterprise-finance',
      'systems:enterprise-fulfilment',
      'systems:enterprise-identity',
      'systems:enterprise-order-management',
      'systems:fraud-provider',
      'systems:payment-provider',
      'systems:tax-provider',
      'users:customer',
      'users:customer-service-agent',
      'users:merchandiser',
    ])
    expect(graph.nodes.filter((node) => node.boundary).map((node) => node.key)).toEqual([
      'systems:analytics-provider',
      'systems:customer-engagement',
      'systems:enterprise-finance',
      'systems:enterprise-fulfilment',
      'systems:enterprise-identity',
      'systems:enterprise-order-management',
      'systems:fraud-provider',
      'systems:payment-provider',
      'systems:tax-provider',
    ])
  })

  test('drilling an entity whose connections are authored on itself keeps it as a leaf endpoint', () => {
    const rootKey = 'containers:commerce-monolith'
    const graph = drillAt(stateAt(acmePayload, 0, 0), rootKey)

    const rootNode = graph.nodes.find((node) => node.key === rootKey)
    expect(rootNode).toBeDefined()
    expect(rootNode!.boundary).toBe(false)
    expect(graph.edges.length).toBeGreaterThan(0)
    for (const edge of graph.edges) {
      expect([edge.a, edge.b]).toContain(rootKey)
    }
    const rootBoundary = graph.boundaries.find((boundary) => boundary.nodeKey === rootKey)
    expect(rootBoundary?.stub).toBe(false)
    expect(rootBoundary?.childKeys).toContain(rootKey)
  })

  test('legend counts equal the number of projected nodes carrying each tag', () => {
    const graph = rollUp(scopeAt(stateAt(acmePayload, 0, 3), null), 'components')
    const expected = new Map<string, number>()
    for (const node of graph.nodes) {
      const tags = new Set([...(node.row.tags ?? []), ...node.members.flatMap((member) => member.row.tags ?? [])])
      for (const tag of tags) expected.set(tag, (expected.get(tag) ?? 0) + 1)
    }
    expect(legendEntries(graph)).toEqual([...expected].sort(([left], [right]) => left.localeCompare(right)).map(([tag, count]) => ({ tag, count })))
  })
})
