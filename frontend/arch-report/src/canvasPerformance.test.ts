import { expect, test } from 'vitest'

import { shouldCommitViewport, stabilizeItemData } from './canvasPerformance'
import { atRestEdgePresentation } from './edgePresentation'

test('viewport commits only at a depth transition or gesture end', () => {
  let committed = { x: 0, y: 0, zoom: 0.3 }
  let commits = 0
  const move = (next: typeof committed, reason: 'gesture' | 'gesture-end' | 'programmatic') => {
    if (!shouldCommitViewport(committed, next, reason)) return
    committed = next
    commits += 1
  }

  move({ x: 20, y: 10, zoom: 0.4 }, 'gesture')
  move({ x: 40, y: 20, zoom: 0.7 }, 'gesture')
  move({ x: 60, y: 30, zoom: 0.8 }, 'gesture')
  expect(commits).toBe(1)
  move({ x: 60, y: 30, zoom: 0.8 }, 'gesture-end')
  expect(commits).toBe(2)
})

test('edge data remains referentially stable when the presentation tuple is unchanged', () => {
  const onSelect = () => undefined
  const previous = [{ data: { emphasis: 'normal', label: 'Calls', onSelect, point: { x: 10, y: 20 } }, id: 'edge-a' }]
  const recomputed = [{ data: { emphasis: 'normal', label: 'Calls', onSelect, point: { x: 10, y: 20 } }, id: 'edge-a' }]

  const stabilized = stabilizeItemData(previous, recomputed)

  expect(stabilized[0].data).toBe(previous[0].data)
})

test('settled presentation retains the pre-chunk label, port, and emphasis output byte-for-byte', () => {
  const presentation = atRestEdgePresentation({
    depth: 'full',
    directReveal: false,
    emphasis: 'outgoing',
    endpointVisible: true,
    hasCompetingFocus: false,
    hovered: false,
    labelObstacles: [],
    labelPlaced: true,
    labelRect: { height: 20, width: 40, x: 0, y: 0 },
    occupiedLabels: [],
    port: { count: 1, label: 'API', point: { side: 'right', x: 100, y: 20 } },
    selectedOrConnected: true,
  })

  expect(JSON.stringify(presentation)).toBe('{"emphasis":"outgoing","portLabel":{"x":123.5,"y":20},"showLabel":true}')
})
