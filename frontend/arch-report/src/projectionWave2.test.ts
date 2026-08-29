import { describe, expect, test } from 'vitest'

import { mapGraph, scopeAt, stateAt } from './projection'
import { KINDS, type ReportPayload, type ReportRow, type RowKind } from './types'

const intervals = [{ live: [[0, null] as [number, null]], clips: [] }]
const row = (id: string, fields: Partial<ReportRow> = {}): ReportRow => ({ id, intervals, ...fields })

function payload(rows: Partial<Record<RowKind, ReportRow[]>>): ReportPayload {
  return {
    payload: 'arch-report/v1', schema_version: 3, source: 'map-contract-test', milestones: [],
    timelines: [{ id: null, milestones: [] }], theme: {},
    rows: Object.fromEntries(KINDS.map((kind) => [kind, rows[kind] ?? []])) as ReportPayload['rows'],
  }
}

function graph(model: ReportPayload, expand: string[]) {
  return mapGraph(scopeAt(stateAt(model, 0, 0), null), expand)
}

describe('P12 map contract', () => {
  test('mixed-kind expansion renders direct children and preserves collapsed sibling roll-ups', () => {
    const model = payload({
      systems: [row('sys1'), row('sys2')],
      subsystems: [row('ss1', { parent: 'sys1' }), row('ss2', { parent: 'sys1' })],
      containers: [row('direct', { parent: 'sys1' }), row('nested', { parent: 'ss1' }), row('sibling-child', { parent: 'sys2' })],
    })
    const projected = graph(model, ['systems:sys1'])
    const boundary = projected.boundaries.find((item) => item.key === 'systems:sys1')
    const sibling = projected.nodes.find((item) => item.key === 'systems:sys2')

    expect(boundary?.childKeys).toEqual(['containers:direct', 'subsystems:ss1', 'subsystems:ss2'])
    expect(boundary?.childKeys.map((key) => projected.nodes.find((node) => node.key === key)?.kind)).toEqual(['containers', 'subsystems', 'subsystems'])
    expect(sibling?.members.map((member) => `${member.kind}:${member.row.id}`)).toContain('containers:sibling-child')
  })

  test('endpoint resolution follows the deepest visible ancestor and splits aggregates', () => {
    const model = payload({
      systems: [row('sys1'), row('sys2')],
      subsystems: [row('ss1', { parent: 'sys1' })],
      containers: [row('c', { parent: 'ss1' }), row('d', { parent: 'ss1' })],
      interfaces: [row('c-out', { provider: 'c', consumer: 'sys2' }), row('d-out', { provider: 'd', consumer: 'sys2' })],
    })
    const collapsed = graph(model, [])
    const systemExpanded = graph(model, ['systems:sys1'])
    const subsystemExpanded = graph(model, ['systems:sys1', 'subsystems:ss1'])

    expect(collapsed.edges[0]).toMatchObject({ a: 'systems:sys1', b: 'systems:sys2', interfaces: ['c-out', 'd-out'] })
    expect(systemExpanded.edges[0]).toMatchObject({ a: 'subsystems:ss1', b: 'systems:sys2', interfaces: ['c-out', 'd-out'] })
    expect(subsystemExpanded.edges.map(({ a, b, interfaces }) => ({ a, b, interfaces }))).toEqual([
      { a: 'containers:c', b: 'systems:sys2', interfaces: ['c-out'] },
      { a: 'containers:d', b: 'systems:sys2', interfaces: ['d-out'] },
    ])
  })

  test('internal edges stay hidden until both endpoints become visible', () => {
    const model = payload({
      systems: [row('sys1')], subsystems: [row('ss1', { parent: 'sys1' })],
      containers: [row('c', { parent: 'ss1' }), row('d', { parent: 'ss1' })],
      interfaces: [row('inside', { provider: 'c', consumer: 'd' })],
    })

    expect(graph(model, []).edges).toHaveLength(0)
    expect(graph(model, ['systems:sys1']).edges).toHaveLength(0)
    expect(graph(model, ['systems:sys1', 'subsystems:ss1']).edges[0]).toMatchObject({
      a: 'containers:c', b: 'containers:d', interfaces: ['inside'],
    })
  })
})
