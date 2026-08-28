// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('@xyflow/react', () => ({
  Background: () => null,
  BackgroundVariant: { Lines: 'lines' },
  BaseEdge: () => null,
  EdgeLabelRenderer: ({ children }: { children: ReactNode }) => children,
  Handle: () => null,
  MarkerType: { ArrowClosed: 'arrowclosed' },
  MiniMap: () => null,
  Position: { Left: 'left', Right: 'right' },
  ReactFlow: ({ nodes }: { nodes: Array<{ id: string }> }) => (
    <div aria-label="Architecture canvas">{nodes.map((node) => <span key={node.id}>{node.id}</span>)}</div>
  ),
  getSmoothStepPath: () => ['', 0, 0],
}))

vi.mock('./layout', () => ({
  NODE_HEIGHT: 112,
  NODE_WIDTH: 240,
  applyPositions: (nodes: unknown[]) => nodes,
  makeLayoutKey: ({ timeline, level, drill }: { timeline: number; level: string; drill: string | null }) => `${timeline}:${level}:${drill ?? 'map'}`,
  unionLayout: async () => new Map(),
}))

vi.mock('./cardSize', () => ({
  cardSize: () => ({ width: 240, height: 112, nameLines: 1 }),
  measureCardText: () => 10,
}))

import App from './App'
import payload from './fixture-payload.json'

afterEach(cleanup)

test('the Stage dropdown has every position and changes the projected state', async () => {
  render(<App />)
  const nodeIds = screen.getByTestId('rendered-node-ids')
  const initial = nodeIds.textContent
  const stage = screen.getByLabelText('Stage') as HTMLSelectElement

  expect(stage.options).toHaveLength(payload.timelines[0].milestones.length + 1)
  fireEvent.change(stage, { target: { value: '1' } })

  await waitFor(() => expect(nodeIds.textContent).not.toBe(initial))
  expect(nodeIds.textContent).toContain('systems:commerce-platform')
})
