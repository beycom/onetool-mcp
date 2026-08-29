import { expect, test } from 'vitest'

import { classifyEmphasis, interfacePort, splitEdgeDirections } from './edgePresentation'
import type { EdgeAnchorPair } from './edgeAnchors'
import type { GraphEdge, ReportRow } from './types'

function row(id: string, call: string, data: string): ReportRow {
  return { id, name: id, provider: 'a', consumer: 'b', call_direction: call, data_flow_direction: data, intervals: [] }
}

function aggregate(): GraphEdge {
  const rows = [
    row('forward', 'provider_to_consumer', 'consumer_to_provider'),
    row('reverse', 'consumer_to_provider', 'provider_to_consumer'),
    row('both', 'bidirectional', 'bidirectional'),
  ]
  return {
    a: 'systems:a',
    b: 'systems:b',
    interfaceRows: rows,
    interfaces: rows.map((item) => item.id),
    key: 'systems:a|systems:b',
    orientations: rows.map((item) => ({ kind: 'interfaces' as const, id: item.id, from: 'systems:a', to: 'systems:b' })),
    relationshipRows: [],
    relationships: [],
  }
}

test('direction splitting counts forward, reverse, and bidirectional members for every relationship mode', () => {
  const calls = splitEdgeDirections(aggregate(), 'call-direction')
  const data = splitEdgeDirections(aggregate(), 'data-flow')
  const ownership = splitEdgeDirections(aggregate(), 'ownership')

  expect(calls.map((spline) => [spline.direction, spline.members.map((member) => member.row.id)])).toEqual([
    ['forward', ['forward', 'both']],
    ['reverse', ['reverse', 'both']],
  ])
  expect(data.map((spline) => [spline.direction, spline.members.map((member) => member.row.id)])).toEqual([
    ['forward', ['reverse', 'both']],
    ['reverse', ['forward', 'both']],
  ])
  expect(ownership.map((spline) => [spline.direction, spline.members.length])).toEqual([['forward', 3]])
})

test('selection classifies one hop before tag emphasis', () => {
  const splines = [
    { id: 'a-b', source: 'a', target: 'b' },
    { id: 'c-a', source: 'c', target: 'a' },
    { id: 'c-d', source: 'c', target: 'd' },
  ]
  const result = classifyEmphasis(['a', 'b', 'c', 'd'], splines, 'a', new Set(['d']))

  expect(result.nodes).toEqual({ a: 'emphasized', b: 'neighbor', c: 'neighbor', d: 'unrelated' })
  expect(result.edges).toEqual({ 'a-b': 'outgoing', 'c-a': 'incoming', 'c-d': 'unrelated' })
})

test('a grouped interface port uses the provider anchor and reports one deterministic count', () => {
  const spline = splitEdgeDirections(aggregate(), 'ownership')[0]
  const anchors: EdgeAnchorPair = {
    sourcePoint: { x: 10, y: 20, side: 'right' },
    targetPoint: { x: 80, y: 20, side: 'left' },
  }

  expect(interfacePort(spline, anchors)).toEqual({
    count: 3,
    label: 'forward',
    point: anchors.sourcePoint,
  })
})
